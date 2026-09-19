"""单条二次验证 / 红队评级：内存任务；活猎复用 ProjectAgent，idle 开短会话。"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from ..i18n.strings import msg

_JOBS: dict[str, dict[str, Any]] = {}
_ACTIVE: dict[tuple[str, str, str], str] = {}
_IDLE_LOCKS: dict[str, asyncio.Lock] = {}
_JOBS_LOCK = asyncio.Lock()


class ReviewBusy(Exception):
    def __init__(self, message: str = "") -> None:
        super().__init__(message or msg("review_busy"))


def _modes_conflict(held: str, want: str) -> bool:
    if held == want:
        return True
    return held == "both" or want == "both"


def _busy_for(pid: str, fid: str, mode: str) -> str | None:
    for (p, f, m), jid in _ACTIVE.items():
        if p == pid and f == fid and _modes_conflict(m, mode):
            return jid
    return None


def snapshot(job_id: str) -> dict[str, Any] | None:
    job = _JOBS.get(job_id)
    if not job:
        return None
    return dict(job)


def list_active() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for jid in _ACTIVE.values():
        job = _JOBS.get(jid)
        if job and job.get("status") in ("queued", "running"):
            out.append(dict(job))
    return out


def reviewing_modes(pid: str, fid: str) -> set[str]:
    modes: set[str] = set()
    for (p, f, m), jid in _ACTIVE.items():
        if p != pid or f != fid:
            continue
        job = _JOBS.get(jid)
        if not job or job.get("status") not in ("queued", "running"):
            continue
        if m == "both":
            modes.add("secondary")
            modes.add("rating")
        else:
            modes.add(m)
    return modes


def claim(pid: str, fid: str, mode: str, *, source: str = "manual") -> dict[str, Any]:
    mode = str(mode or "").strip().lower()
    if mode not in ("secondary", "rating", "both"):
        raise ValueError("mode")
    if _busy_for(pid, fid, mode):
        raise ReviewBusy()
    jid = uuid.uuid4().hex[:16]
    job = {
        "id": jid,
        "job_id": jid,
        "project_id": pid,
        "finding_id": fid,
        "mode": mode,
        "source": source,
        "status": "queued",
        "error": "",
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    _JOBS[jid] = job
    _ACTIVE[(pid, fid, mode)] = jid
    return dict(job)


def try_claim(pid: str, fid: str, mode: str, *, source: str = "auto") -> dict[str, Any] | None:
    try:
        return claim(pid, fid, mode, source=source)
    except ReviewBusy:
        return None


def release(job_id: str, *, status: str = "done", error: str = "") -> None:
    job = _JOBS.get(job_id)
    if not job:
        return
    job["status"] = status
    job["error"] = error or ""
    job["updated_at"] = time.time()
    key = (str(job.get("project_id") or ""), str(job.get("finding_id") or ""), str(job.get("mode") or ""))
    if _ACTIVE.get(key) == job_id:
        _ACTIVE.pop(key, None)


def _idle_lock(pid: str) -> asyncio.Lock:
    lock = _IDLE_LOCKS.get(pid)
    if lock is None:
        lock = asyncio.Lock()
        _IDLE_LOCKS[pid] = lock
    return lock


def live_hunt_agent(pid: str) -> Any | None:
    from ..engine.scheduler import manager

    if not manager.is_running(pid):
        return None
    handle = manager.get(pid)
    agent = getattr(handle, "agent", None) if handle else None
    if agent is None or getattr(agent, "_stopped", False):
        return None
    return agent


async def _run_on_live(agent: Any, finding: dict, mode: str) -> None:
    await agent.review_one(finding, mode)


async def _run_idle(project: dict, finding: dict, mode: str) -> None:
    from ..agents.session import ProjectAgent
    from ..projects import build_scope

    pid = str(project.get("id") or "")
    async with _idle_lock(pid):
        live = live_hunt_agent(pid)
        if live is not None:
            await _run_on_live(live, finding, mode)
            return
        agent = ProjectAgent(project, build_scope(project))
        agent._owns_mcp = True
        try:
            await agent.connect()
            await agent.review_one(finding, mode)
        finally:
            live_now = live_hunt_agent(pid)
            if live_now is not None and live_now is not agent:
                agent._owns_mcp = False
            try:
                await agent.close()
            except Exception:
                pass


async def _execute(job_id: str, project: dict, finding: dict, mode: str) -> None:
    job = _JOBS.get(job_id)
    if job:
        job["status"] = "running"
        job["updated_at"] = time.time()
    pid = str(project.get("id") or "")
    try:
        live = live_hunt_agent(pid)
        if live is not None:
            await _run_on_live(live, finding, mode)
        else:
            await _run_idle(project, finding, mode)
        release(job_id, status="done")
    except Exception as e:
        release(job_id, status="error", error=str(e)[:240])


def start_manual(project: dict, finding: dict, mode: str) -> dict[str, Any]:
    pid = str(project.get("id") or "")
    fid = str(finding.get("id") or "")
    job = claim(pid, fid, mode, source="manual")
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_execute(job["id"], project, finding, mode))
    except RuntimeError:
        release(job["id"], status="error", error="no event loop")
        raise
    return snapshot(job["id"]) or job
