"""ProjectAgent：每个项目独立的 Pi 猎面。

- 从者与角色工人都是全新 Pi RPC：每轮不续接旧对话，局面只靠攻击图/简报。
- 项目内工人无上限；Python 按御主方案并发拉起，不再走 Task。
- 图工具经 HTTP /agent-tools 由 Pi 扩展调用。
"""
from __future__ import annotations

import asyncio
import os
import re
import time

from ..config import settings
from ..events import emit
from ..exec.guard import Guard
from ..objective import objective_allows_flag, objective_is_src
from ..scope import Scope
from .context import AgentContext
from .mcp_http import register_project_mcp, unregister_project_mcp
from .pi_runtime import PiSession
from .project_skills import skill_abs_paths
from .prompts import (
    build_brief,
    build_finding_review_instruction,
    build_subagents,
    build_system_prompt,
    default_fanout_roles,
    finding_review_system_prompt,
    FINDING_REVIEW_ROLE,
)
from .tools import tool_names

_DEAD_CLI_RE = re.compile(
    r"Cannot write to terminated process|terminated process|exit code:\s*-?11|"
    r"SIGSEGV|Broken pipe|Connection reset|pi rpc stdin closed",
    re.I,
)


def is_dead_cli_error(exc: BaseException | str) -> bool:
    return bool(_DEAD_CLI_RE.search(str(exc or "")))


def is_retryable_connect_error(exc: BaseException | str) -> bool:
    msg = str(exc or "")
    return is_dead_cli_error(msg) or "pi " in msg.lower() or "rpc" in msg.lower()


class ProjectAgent:
    def __init__(self, project: dict, scope: Scope) -> None:
        self.project = project
        self.project_id = project["id"]
        self.scope = scope
        cfg = project.get("config") or {}

        self.workspace_dir = os.path.join(str(settings.workspaces_dir), self.project_id)
        os.makedirs(self.workspace_dir, exist_ok=True)
        os.makedirs(os.path.join(self.workspace_dir, "loot"), exist_ok=True)

        _objective = cfg.get("objective", settings.default_objective)
        self.guard = Guard(scope, "", objective=_objective)
        self.guard.workspace_dir = self.workspace_dir
        self.objective = _objective
        _allows_flag = objective_allows_flag(self.objective)
        flags_needed = int(cfg.get("flag_count") or 1) if _allows_flag else 1
        bm = cfg.get("benchmark") if (_allows_flag and isinstance(cfg.get("benchmark"), dict)) else None
        self.ctx = AgentContext(
            project_id=self.project_id, workspace_dir=self.workspace_dir,
            loot_dir=os.path.join(self.workspace_dir, "loot"),
            scope=scope, guard=self.guard,
            objective=self.objective, project=project, flags_needed=flags_needed,
            benchmark=bm,
        )
        self._sessions: list[PiSession] = []
        self._pi_pool: dict[str, PiSession] = {}
        self._review_wake = asyncio.Event()
        self._review_lock = asyncio.Lock()
        self._review_task: asyncio.Task | None = None
        self._page_task: asyncio.Task | None = None
        self._stopped = False
        self._full_score_aborting = False
        self.ctx.abort_run = self._abort_on_full_score
        self.brief = build_brief(project)
        self._write_brief()
        self._project_skill_names = self._write_skills()
        self.model = (cfg.get("model") or "").strip() or settings.claude_model
        if self.model.lower() in ("sonnet", "haiku", "opus") or self.model.lower().startswith("claude"):
            self.model = settings.claude_model
        self._roles = build_subagents(self.objective)
        self.last_session_id: str | None = None
        self._connected = False
        register_project_mcp(self.ctx)

    def _write_brief(self) -> None:
        if not self.brief:
            return
        try:
            with open(os.path.join(self.workspace_dir, "BRIEF.md"), "w", encoding="utf-8") as f:
                f.write("# 题目简报\n\n" + self.brief + "\n")
        except OSError:
            pass

    def refresh_brief(self, project: dict | None = None) -> str:
        """入口重绑后按新 project 重写 BRIEF.md，避免从者继续打旧 vhost。"""
        if isinstance(project, dict):
            self.project = project
            ctx = getattr(self, "ctx", None)
            if ctx is not None:
                ctx.project = project
        self.brief = build_brief(self.project)
        self._write_brief()
        return self.brief

    def _write_skills(self) -> list[str]:
        try:
            from .project_skills import install_into_workspace
            return install_into_workspace(self.workspace_dir, objective=self.objective)
        except OSError:
            return []

    def _lead_system(self) -> str:
        return build_system_prompt(
            self.scope, self.workspace_dir, self.objective, self.brief,
        )

    def _role_system(self, role: str) -> str:
        spec = self._roles.get(role) or {}
        prompt = str(spec.get("prompt") or "")
        tools = ", ".join(tool_names(self.objective))
        return (
            f"{prompt}\n\n"
            f"工作目录：{self.workspace_dir}\n"
            f"可用工具：{tools}。禁止再开子进程或套娃。\n"
            "越界与破坏性写入由平台硬拦，不要改业务状态。"
        )

    def _fanout_roles(self) -> list[str]:
        raw = list(getattr(self.ctx, "fanout_roles", None) or [])
        known = set(self._roles)
        out: list[str] = []
        seen: set[str] = set()
        for r in raw:
            n = str(r or "").strip().lower()
            if n == FINDING_REVIEW_ROLE:
                continue
            if n in known and n not in seen:
                out.append(n)
                seen.add(n)
        if not out:
            for n in default_fanout_roles(self.objective):
                if n in known and n not in seen:
                    out.append(n)
                    seen.add(n)
        if objective_is_src(self.objective) and "src-hunt" in out and "web-exploit" in out:
            out = [n for n in out if n != "web-exploit"]
        return out

    async def connect(self, *, jitter: bool = False) -> None:
        _ = jitter
        self._connected = True

    async def close(self) -> None:
        await self._stop_background()
        await self._close_sessions(keep_review=False)
        self._connected = False
        unregister_project_mcp(self.project_id)
        try:
            await self.ctx.aclose()
        except Exception:
            pass

    async def interrupt(self, *, halt: bool = True) -> None:
        if halt:
            await self._stop_background()
        sessions = list(self._sessions)
        if not halt:
            sessions = [
                s for s in sessions
                if str(getattr(s, "role", "") or "") != FINDING_REVIEW_ROLE
            ]
        for s in sessions:
            try:
                await s.abort()
            except Exception:
                pass
        if halt:
            await self._close_sessions(keep_review=False)
        else:
            await self._abort_hunt_prompts()

    async def _stop_background(self) -> None:
        self._stopped = True
        try:
            self._review_wake.set()
        except Exception:
            pass
        task = self._review_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except Exception:
                pass
        self._review_task = None
        page = self._page_task
        if page is not None and not page.done():
            page.cancel()
        self._page_task = None

    async def _abort_roles(self, roles: set[str]) -> list[str]:
        """中止指定角色的 Pi（从者收工后收掉仍在跑的工人）。不碰二次验证会话。"""
        want = {str(r) for r in roles if r and r not in ("lead", FINDING_REVIEW_ROLE)}
        aborted: list[str] = []
        for s in list(self._sessions):
            role = str(getattr(s, "role", "") or "")
            if role not in want:
                continue
            try:
                await s.abort()
            except Exception:
                pass
            aborted.append(role)
        return aborted

    async def _abort_hunt_prompts(self) -> None:
        """结束本轮从者/工人的 prompt，进程保留给下一轮。不杀复核 Pi。"""
        for s in list(self._sessions):
            role = str(getattr(s, "role", "") or "")
            if role == FINDING_REVIEW_ROLE:
                continue
            try:
                await s.abort()
            except Exception:
                pass

    async def _close_sessions(self, *, keep_review: bool = False) -> None:
        if keep_review:
            drop = [
                s for s in self._sessions
                if str(getattr(s, "role", "") or "") != FINDING_REVIEW_ROLE
            ]
            keep = [
                s for s in self._sessions
                if str(getattr(s, "role", "") or "") == FINDING_REVIEW_ROLE
            ]
            self._sessions = keep
            for role, sess in list(self._pi_pool.items()):
                if role != FINDING_REVIEW_ROLE:
                    self._pi_pool.pop(role, None)
                    if sess not in drop:
                        drop.append(sess)
        else:
            drop = list(self._sessions)
            self._sessions = []
            self._pi_pool.clear()
        if not drop:
            return
        await asyncio.gather(*(s.close() for s in drop), return_exceptions=True)

    async def reset_session(self) -> None:
        await self.begin_fresh_session(connect=False)

    async def begin_fresh_session(self, *, connect: bool = True) -> None:
        await self._abort_hunt_prompts()
        self.last_session_id = None
        self._connected = bool(connect)

    async def resume_session(self) -> bool:
        await self.begin_fresh_session(connect=True)
        return False

    async def recover_dead_cli(self) -> None:
        await self._abort_hunt_prompts()
        dead: list[PiSession] = []
        for role, sess in list(self._pi_pool.items()):
            if role == FINDING_REVIEW_ROLE:
                continue
            if not sess.alive():
                dead.append(sess)
                self._pi_pool.pop(role, None)
        for sess in dead:
            try:
                await sess.close()
            except Exception:
                pass
            try:
                self._sessions.remove(sess)
            except ValueError:
                pass
        try:
            await self.ctx.aclose()
        except Exception:
            pass
        await asyncio.sleep(0.4)
        self._connected = True

    def set_run(self, run_id: str) -> None:
        self.ctx.run_id = run_id

    async def _abort_on_full_score(self) -> None:
        if self._full_score_aborting:
            return
        self._full_score_aborting = True
        await emit(
            self.project_id, "log",
            {"level": "info", "message": "本题满分，立即收工并释放靶场槽位，切换下一题。"},
            run_id=self.ctx.run_id,
        )
        try:
            if self.ctx.project:
                from .. import benchmark as bm
                await bm.close_challenge(self.ctx.project)
        except Exception:
            pass
        try:
            await self.interrupt()
        except Exception:
            pass

    def _kick_review(self) -> None:
        try:
            self._review_wake.set()
        except Exception:
            return
        self._ensure_review_loop()

    def _ensure_review_loop(self) -> None:
        if self._stopped:
            return
        task = self._review_task
        if task is not None and not task.done():
            return
        try:
            self._review_task = asyncio.get_running_loop().create_task(self._review_loop())
        except RuntimeError:
            return

    async def _review_loop(self) -> None:
        while not self._stopped:
            await self._review_wake.wait()
            if self._stopped:
                return
            self._review_wake.clear()
            try:
                async with self._review_lock:
                    await self._run_finding_review()
            except Exception:
                pass

    def _schedule_pages(self) -> None:
        if self._stopped:
            return
        page = self._page_task
        if page is not None and not page.done():
            return
        try:
            self._page_task = asyncio.get_running_loop().create_task(self._fill_pages_bg())
        except RuntimeError:
            return

    async def _fill_pages_bg(self) -> None:
        try:
            from ..projects import get_project as _gp_rev
            from ..report.pi_finding_page import fill_missing_pi_pages
            await fill_missing_pi_pages(
                self.project_id, project=await _gp_rev(self.project_id),
            )
        except Exception:
            pass

    async def _run_finding_review(self) -> int:
        """对当前未二次验证的入库漏洞立刻开专职复核 Pi；没有待办则跳过。"""
        from ..graph.store import findings_pending_secondary

        try:
            pending = await findings_pending_secondary(self.project_id)
        except Exception:
            pending = []
        if not pending:
            self._schedule_pages()
            return 0
        names = list(getattr(self.ctx, "task_subagents", None) or [])
        if FINDING_REVIEW_ROLE not in names:
            names.append(FINDING_REVIEW_ROLE)
            try:
                self.ctx.task_subagents = names
            except Exception:
                pass
        await emit(
            self.project_id, "log",
            {
                "level": "info",
                "message": f"专职二次验证 {len(pending)} 条（后台复核，不挡御主）",
            },
            run_id=self.ctx.run_id,
        )
        await emit(
            self.project_id, "finding_review",
            {
                "status": "running",
                "count": len(pending),
                "ids": [str(f.get("id") or "") for f in pending if f.get("id")],
                "titles": [str(f.get("title") or "")[:80] for f in pending],
                "role": FINDING_REVIEW_ROLE,
            },
            run_id=self.ctx.run_id,
        )
        try:
            await self._run_one(
                FINDING_REVIEW_ROLE,
                finding_review_system_prompt(self.workspace_dir, self.objective),
                build_finding_review_instruction(pending),
            )
            self._schedule_pages()
        finally:
            try:
                await emit(
                    self.project_id, "finding_review",
                    {
                        "status": "done",
                        "count": len(pending),
                        "ids": [str(f.get("id") or "") for f in pending if f.get("id")],
                        "role": FINDING_REVIEW_ROLE,
                    },
                    run_id=self.ctx.run_id,
                )
            except Exception:
                pass
        return len(pending)

    async def _acquire_pi(self, role: str, system_prompt: str) -> PiSession:
        sess = self._pi_pool.get(role)
        if sess is not None and sess.alive():
            sess.run_id = self.ctx.run_id
            sess.on_activity = self.ctx.mark_activity
            sess._emit = emit
            return sess
        if sess is not None:
            try:
                await sess.close()
            except Exception:
                pass
            self._pi_pool.pop(role, None)
            try:
                self._sessions.remove(sess)
            except ValueError:
                pass
        sess = PiSession(
            cwd=self.workspace_dir,
            system_prompt=system_prompt,
            project_id=self.project_id,
            role=role,
            tools=True,
            emit=emit,
            run_id=self.ctx.run_id,
            on_activity=self.ctx.mark_activity,
            model=self.model,
            skill_paths=skill_abs_paths(self.workspace_dir, self._project_skill_names),
        )
        await sess.start()
        self._pi_pool[role] = sess
        if sess not in self._sessions:
            self._sessions.append(sess)
        return sess

    async def _run_one(self, role: str, system_prompt: str, instruction: str) -> dict:
        sess = await self._acquire_pi(role, system_prompt)
        try:
            text = await sess.prompt(instruction, timeout=0)
            return {"text": text, "tool_uses": int(sess.tool_uses or 0), "role": role}
        except Exception as e:
            if is_dead_cli_error(e):
                self._connected = False
            try:
                await sess.close()
            except Exception:
                pass
            self._pi_pool.pop(role, None)
            try:
                self._sessions.remove(sess)
            except ValueError:
                pass
            raise

    async def run_turn(self, instruction: str) -> dict:
        try:
            self.ctx.task_subagents = []
        except Exception:
            pass
        await self.begin_fresh_session(connect=True)
        try:
            self.ctx.mark_activity()
        except Exception:
            pass
        roles = self._fanout_roles()
        try:
            self.ctx.task_subagents = list(roles)
        except Exception:
            pass
        leftover = 0
        try:
            from ..graph.store import findings_pending_secondary
            leftover = len(await findings_pending_secondary(self.project_id))
        except Exception:
            leftover = 0
        pi_names = ["从者"] + list(roles)
        await emit(
            self.project_id, "log",
            {
                "level": "info",
                "message": "本回合并发 Pi：" + "、".join(pi_names)
                + "（新入库漏洞立刻交专职二次验证"
                + (f"；上回合残留 {leftover} 条马上复核" if leftover else "")
                + "）",
            },
            run_id=self.ctx.run_id,
        )
        lead_instr = instruction
        extra_lead = []
        if roles:
            extra_lead.append(
                "本回合调度已并发拉起角色会话："
                + "、".join(f"`{r}`" for r in roles)
                + "。你负责计划、写图与汇总；不要自己 http_request，打洞交给工人；不要再开子进程。"
            )
        extra_lead.append(
            f"从者或工人一 `report_finding`，专职 `{FINDING_REVIEW_ROLE}` 在后台二次验证；"
            "你不要等复核、不要把二次验证当本回合主线。未复核洞是 pending_review，不能当已结案。"
        )
        extra_lead.append(
            "本轮小结/收尾写完即停，不要再打工具；系统会结束本轮去问御主。"
            "CTF / SRC / 红队同一条：工人不得把回合拖住。"
        )
        close_note = extra_lead[-1]
        lead_instr = instruction + "\n\n" + "\n".join(extra_lead)
        named = [("lead", self._run_one("lead", self._lead_system(), lead_instr))]
        worker_instr = instruction + "\n\n" + close_note
        for role in roles:
            named.append((role, self._run_one(role, self._role_system(role), worker_instr)))

        self.ctx.wake_finding_review = self._kick_review
        self._ensure_review_loop()
        if leftover:
            self._kick_review()
        results: list = []
        try:
            from ..engine.turn_close import WORKER_ABORT_GRACE_SEC, turn_must_close
            task_roles = {asyncio.create_task(coro): name for name, coro in named}
            by_role: dict[str, object] = {}
            pending: set[asyncio.Task] = set(task_roles)
            lead_closed = False
            t0 = time.monotonic()
            try:
                cap = float(getattr(settings, "turn_must_close_sec", 0) or 0)
            except (TypeError, ValueError):
                cap = 0.0

            def _take(done_set: set[asyncio.Task]) -> None:
                for t in done_set:
                    name = task_roles.get(t)
                    if not name or name in by_role:
                        try:
                            t.result()
                        except Exception:
                            pass
                        continue
                    try:
                        by_role[name] = t.result()
                    except Exception as e:
                        by_role[name] = e

            while pending:
                if turn_must_close(time.monotonic() - t0, cap):
                    try:
                        await emit(
                            self.project_id, "log",
                            {"level": "info",
                             "message": (
                                 f"本轮已满 {int(cap)}s，强制收口以让御主开口"
                                 "（CTF / SRC / 红队同一规则）。"
                             )},
                            run_id=self.ctx.run_id,
                        )
                    except Exception:
                        pass
                    try:
                        await self.interrupt(halt=False)
                    except Exception:
                        pass
                    for t in list(pending):
                        t.cancel()
                    leftover, pending = await asyncio.wait(pending, timeout=5)
                    _take(leftover)
                    break
                slice_wait = 2.0
                if cap > 0:
                    slice_wait = max(0.05, min(2.0, cap - (time.monotonic() - t0)))
                done, pending = await asyncio.wait(
                    pending, timeout=slice_wait, return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    continue
                _take(done)
                if (not lead_closed) and "lead" in by_role:
                    lead_closed = True
                    leftover_roles = [
                        r for r in (task_roles.get(p) for p in pending) if r
                    ]
                    await self._abort_roles(set(leftover_roles))
                    if leftover_roles:
                        try:
                            await emit(
                                self.project_id, "log",
                                {
                                    "level": "info",
                                    "message": (
                                        "从者本轮已返回，中止仍在跑的工人（"
                                        + "、".join(leftover_roles)
                                        + "）以让御主开口。"
                                    ),
                                },
                                run_id=self.ctx.run_id,
                            )
                        except Exception:
                            pass
                        more, pending = await asyncio.wait(
                            pending, timeout=WORKER_ABORT_GRACE_SEC,
                        )
                        _take(more)
                        if pending:
                            await self._abort_roles(
                                {r for r in (task_roles.get(p) for p in pending) if r}
                            )
                            for t in list(pending):
                                t.cancel()
                            extra, pending = await asyncio.wait(pending, timeout=5)
                            _take(extra)
                            pending = set()
            results = [by_role.get("lead")] + [by_role.get(r) for r in roles]
        finally:
            self._kick_review()
            self.ctx.wake_finding_review = self._kick_review
        texts: list[str] = []
        tool_uses = 0
        first_err: BaseException | None = None
        for item in results:
            if item is None:
                continue
            if isinstance(item, BaseException):
                if first_err is None:
                    first_err = item
                continue
            texts.append(str(item.get("text") or ""))
            tool_uses += int(item.get("tool_uses") or 0)
        if self.ctx.goal_reached:
            try:
                await self.interrupt()
            except Exception:
                pass
        if first_err and not texts and not self.ctx.goal_reached:
            raise first_err
        return {
            "text": "\n".join(t for t in texts if t).strip(),
            "tool_uses": tool_uses,
            "goal_reached": self.ctx.goal_reached,
            "task_subagents": list(getattr(self.ctx, "task_subagents", None) or []),
        }


def _preview(obj) -> str:
    try:
        import json
        s = json.dumps(obj, ensure_ascii=False)
    except Exception:
        s = str(obj)
    return s[:400]


def _get_spawn_sem() -> asyncio.Semaphore:
    """兼容旧调用：项目内 Pi 不设闸。"""
    return asyncio.Semaphore(10_000)
