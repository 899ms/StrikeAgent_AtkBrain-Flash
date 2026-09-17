"""活句柄优先于 DB 里残留的 running；人工停止必须 idle。"""
from __future__ import annotations

import unittest

from .engine.hunt_resume import cancel_project_status
from .project_status import displayed_status


class DisplayedStatusTests(unittest.TestCase):
    def test_live_running(self) -> None:
        self.assertEqual(displayed_status("idle", running=True), "running")
        self.assertEqual(displayed_status("running", running=True), "running")

    def test_queued(self) -> None:
        self.assertEqual(displayed_status("running", queued=True), "queued")

    def test_stale_db_running_is_idle(self) -> None:
        self.assertEqual(displayed_status("running", running=False), "idle")

    def test_keeps_terminal(self) -> None:
        self.assertEqual(displayed_status("completed"), "completed")
        self.assertEqual(displayed_status("error"), "error")
        self.assertEqual(displayed_status("idle"), "idle")
        self.assertEqual(displayed_status("goal_reached"), "completed")

    def test_user_stop_is_idle(self) -> None:
        self.assertEqual(
            cancel_project_status(user_stop=True, handle_status="running", slot_held=True),
            "idle",
        )
        self.assertEqual(
            cancel_project_status(user_stop=True, handle_status="stopping", slot_held=True),
            "idle",
        )

    def test_restart_keeps_running_only_if_slot_held(self) -> None:
        self.assertEqual(
            cancel_project_status(user_stop=False, handle_status="running", slot_held=True),
            "running",
        )
        self.assertIsNone(
            cancel_project_status(user_stop=False, handle_status="starting", slot_held=False),
        )


if __name__ == "__main__":
    unittest.main()
