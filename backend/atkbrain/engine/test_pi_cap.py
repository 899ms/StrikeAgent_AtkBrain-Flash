"""Pi 进程闸：fanout 截断、cmdline 识别、health 数字不再写死 0。"""
from __future__ import annotations

import inspect
import unittest

from ..agents.pi_runtime import (
    _is_backend_cmd,
    _is_pi_cmdline,
    cap_hunt_workers,
    pi_max_live_limit,
    pi_per_project_limit,
)
from ..engine.scheduler import RunManager


class CapHelpersTests(unittest.TestCase):
    def test_defaults_are_capped(self) -> None:
        self.assertEqual(pi_per_project_limit(), 4)
        self.assertEqual(pi_max_live_limit(), 32)

    def test_cap_hunt_workers_reserves_lead(self) -> None:
        roles = ["web-exploit", "recon", "rce-hunt", "privesc", "lateral"]
        self.assertEqual(cap_hunt_workers(roles, per_project=4), ["web-exploit", "recon", "rce-hunt"])
        self.assertEqual(cap_hunt_workers(roles, per_project=1), [])
        self.assertEqual(cap_hunt_workers(roles, per_project=2), ["web-exploit"])

    def test_cap_drops_review_and_oneshot(self) -> None:
        roles = ["finding-review", "supervisor", "web-exploit", "recon"]
        self.assertEqual(cap_hunt_workers(roles, per_project=4), ["web-exploit", "recon"])

    def test_pi_cmdline(self) -> None:
        self.assertTrue(_is_pi_cmdline(b"pi\0--mode\0rpc\0"))
        self.assertTrue(_is_pi_cmdline(b"/usr/local/bin/pi\0--mode\0rpc"))
        self.assertTrue(_is_pi_cmdline(b"node\0/usr/lib/node_modules/@earendil-works/pi-coding-agent/dist/cli.js\0--mode\0rpc"))
        self.assertFalse(_is_pi_cmdline(b"python3\0-m\0atkbrain.main"))
        self.assertTrue(_is_backend_cmd(b"python3\0-m\0atkbrain.main"))


class FanoutAndPoolTests(unittest.TestCase):
    def test_fanout_calls_cap(self) -> None:
        from ..agents.session import ProjectAgent
        src = inspect.getsource(ProjectAgent._fanout_roles)
        self.assertIn("cap_hunt_workers", src)

    def test_acquire_uses_role_lock(self) -> None:
        from ..agents.session import ProjectAgent
        src = inspect.getsource(ProjectAgent._acquire_pi)
        self.assertIn("_pi_lock", src)
        self.assertIn("async with", src)

    def test_recover_kills_orphans(self) -> None:
        from ..agents.session import ProjectAgent
        src = inspect.getsource(ProjectAgent.recover_dead_cli)
        self.assertIn("kill_live_for_project", src)

    def test_idle_reap_keeps_lead(self) -> None:
        from ..agents.session import ProjectAgent
        src = inspect.getsource(ProjectAgent._reap_idle_workers)
        self.assertIn('role in ("lead", FINDING_REVIEW_ROLE)', src)

    def test_close_does_not_untrack_before_death(self) -> None:
        from ..agents.pi_runtime import PiSession

        text = inspect.getsource(PiSession.close)
        self.assertIn("_untrack_dead", text)
        self.assertNotIn("_LIVE.pop(pid, None)", text)

    def test_set_claude_per_project_sticks(self) -> None:
        mgr = RunManager()
        self.addCleanup(lambda: mgr.set_claude_per_project(4))
        n = mgr.set_claude_per_project(6)
        self.assertEqual(n, 6)
        self.assertEqual(mgr.snapshot()["claude"]["per_project"], 6)
        self.assertEqual(mgr.set_claude_per_project(99), 8)


class SnapshotTests(unittest.TestCase):
    def test_health_claude_limits_nonzero(self) -> None:
        mgr = RunManager()
        snap = mgr.snapshot()
        self.assertEqual(snap["claude"]["limit"], 32)
        self.assertGreater(snap["claude"]["cap"], 0)
        self.assertGreaterEqual(snap["claude"]["per_project"], 1)


if __name__ == "__main__":
    unittest.main()
