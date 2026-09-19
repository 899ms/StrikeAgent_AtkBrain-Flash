"""二次验证 / 红队评级：入库门闩、pending 过滤、开关缺键当开。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


class GateTests(unittest.TestCase):
    def test_first_ingest_empty_ok(self) -> None:
        from ..graph.model import secondary_review_error
        self.assertIsNone(secondary_review_error(False, None, None))
        self.assertIsNone(secondary_review_error(False, "", "  "))

    def test_secondary_only_needs_rationale(self) -> None:
        from ..graph.model import secondary_review_error
        self.assertIsNotNone(secondary_review_error(True, None, "太短"))
        why = "换通道重放 PoC，对照首次回显，命令未打成，二次确认仍是任意文件写而非 RCE。"
        self.assertGreaterEqual(len(why), 40)
        self.assertIsNone(secondary_review_error(True, None, why))
        self.assertIsNone(secondary_review_error(True, "", why))

    def test_rating_only_needs_rationale(self) -> None:
        from ..graph.model import secondary_review_error
        self.assertIsNotNone(secondary_review_error(False, "high", "高危"))
        why = "任意文件读默认中危：可拉取配置但无命令执行回显，按四级表评 medium 而不是高危。"
        self.assertGreaterEqual(len(why), 40)
        self.assertIsNone(secondary_review_error(False, "medium", why))
        self.assertIsNone(secondary_review_error(False, "中危", why))

    def test_both_still_require_three(self) -> None:
        from ..graph.model import secondary_review_error
        why = "独立重放并对照回显后仍可写任意文件，按四级表中危，不抬成高危，也不压成低危处理。"
        self.assertGreaterEqual(len(why), 40)
        self.assertIsNotNone(secondary_review_error(True, "high", "短"))
        self.assertIsNone(secondary_review_error(True, "medium", why))

    def test_rationale_without_intent_rejected(self) -> None:
        from ..graph.model import secondary_review_error
        self.assertIsNotNone(secondary_review_error(False, None, "x" * 50))


class NeedTests(unittest.TestCase):
    def test_need_by_flags(self) -> None:
        from ..graph.model import finding_review_need
        row = {"secondary_verified": 0, "redteam_rating": None}
        self.assertEqual(finding_review_need(row, want_secondary=True, want_rating=True), "both")
        self.assertEqual(finding_review_need(row, want_secondary=True, want_rating=False), "secondary")
        self.assertEqual(finding_review_need(row, want_secondary=False, want_rating=True), "rating")
        self.assertIsNone(finding_review_need(row, want_secondary=False, want_rating=False))
        done = {"secondary_verified": 1, "redteam_rating": "high"}
        self.assertIsNone(finding_review_need(done, want_secondary=True, want_rating=True))
        half = {"secondary_verified": 1, "redteam_rating": None}
        self.assertEqual(finding_review_need(half, want_secondary=True, want_rating=True), "rating")
        rated = {"secondary_verified": 0, "redteam_rating": "low"}
        self.assertEqual(finding_review_need(rated, want_secondary=True, want_rating=True), "secondary")


class FlagTests(unittest.TestCase):
    def test_missing_keys_default_on(self) -> None:
        from ..review import flags as fl
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "proxy-settings.json"
            with patch.object(fl, "_settings_path", lambda: p):
                got = fl.get_review_flags()
                self.assertTrue(got["secondary_verify"])
                self.assertTrue(got["redteam_rating"])
                p.write_text("{}", encoding="utf-8")
                got = fl.get_review_flags()
                self.assertTrue(got["secondary_verify"])
                self.assertTrue(got["redteam_rating"])
                p.write_text(json.dumps({"finding_secondary_verify": False}), encoding="utf-8")
                got = fl.get_review_flags()
                self.assertFalse(got["secondary_verify"])
                self.assertTrue(got["redteam_rating"])

    def test_set_writes_keys(self) -> None:
        from ..review import flags as fl
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "proxy-settings.json"

            def fake_merge(updates):
                data = {}
                if p.is_file():
                    data = json.loads(p.read_text(encoding="utf-8") or "{}")
                data.update(updates)
                p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

            with patch.object(fl, "_settings_path", lambda: p), patch.object(fl, "_merge_settings", fake_merge):
                out = fl.set_review_flags(secondary_verify=False, redteam_rating=True)
                self.assertFalse(out["secondary_verify"])
                data = json.loads(p.read_text(encoding="utf-8"))
                self.assertFalse(data["finding_secondary_verify"])
                self.assertTrue(data["finding_redteam_rating"])


class PendingFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_flags_split_pending(self) -> None:
        from ..graph import store as gstore

        rows = [
            {
                "id": "f1", "project_id": "p1", "node_key": "n1", "severity": "high",
                "category": "xss", "title": "stored xss", "description": "", "evidence": "e",
                "poc_curl": "", "poc_python": "", "cvss": None, "created_at": 1,
                "verification_status": "verified", "verified_at": 1,
                "proof_type": None, "proof_canary": None, "proof_url": None, "proof_detail": None,
                "secondary_verified": 0, "redteam_rating": None, "redteam_rating_rationale": None,
                "report_summary": None, "report_impact": None, "report_rating": None,
                "report_repro": None, "report_fix": None,
            },
            {
                "id": "f2", "project_id": "p1", "node_key": "n2", "severity": "medium",
                "category": "sqli", "title": "sqli", "description": "", "evidence": "e",
                "poc_curl": "", "poc_python": "", "cvss": None, "created_at": 2,
                "verification_status": "verified", "verified_at": 2,
                "proof_type": None, "proof_canary": None, "proof_url": None, "proof_detail": None,
                "secondary_verified": 1, "redteam_rating": None, "redteam_rating_rationale": "x" * 50,
                "report_summary": None, "report_impact": None, "report_rating": None,
                "report_repro": None, "report_fix": None,
            },
            {
                "id": "f3", "project_id": "p1", "node_key": "n3", "severity": "low",
                "category": "info", "title": "banner", "description": "", "evidence": "e",
                "poc_curl": "", "poc_python": "", "cvss": None, "created_at": 3,
                "verification_status": "rejected", "verified_at": None,
                "proof_type": None, "proof_canary": None, "proof_url": None, "proof_detail": None,
                "secondary_verified": 0, "redteam_rating": None, "redteam_rating_rationale": None,
                "report_summary": None, "report_impact": None, "report_rating": None,
                "report_repro": None, "report_fix": None,
            },
        ]

        async def fake_fetchall(sql, params=()):
            return list(rows)

        with patch.object(gstore.db, "fetchall", fake_fetchall), \
             patch("atkbrain.projects.get_project", new=AsyncMock(return_value={"config": {}})):
            both = await gstore.findings_pending_review("p1", want_secondary=True, want_rating=True)
            ids = {x["id"]: x["_review_mode"] for x in both}
            self.assertEqual(ids["f1"], "both")
            self.assertEqual(ids["f2"], "rating")
            self.assertNotIn("f3", ids)
            sec = await gstore.findings_pending_review("p1", want_secondary=True, want_rating=False)
            self.assertEqual([x["id"] for x in sec], ["f1"])
            self.assertEqual(sec[0]["_review_mode"], "secondary")
            rate = await gstore.findings_pending_review("p1", want_secondary=False, want_rating=True)
            self.assertEqual({x["id"] for x in rate}, {"f1", "f2"})
            none = await gstore.findings_pending_review("p1", want_secondary=False, want_rating=False)
            self.assertEqual(none, [])


class JobBusyTests(unittest.TestCase):
    def test_same_mode_conflicts(self) -> None:
        from ..review import jobs
        jobs._JOBS.clear()
        jobs._ACTIVE.clear()
        jobs.claim("p", "f", "secondary")
        with self.assertRaises(jobs.ReviewBusy):
            jobs.claim("p", "f", "secondary")
        with self.assertRaises(jobs.ReviewBusy):
            jobs.claim("p", "f", "both")
        jobs.claim("p", "f", "rating")
        jobs._JOBS.clear()
        jobs._ACTIVE.clear()


if __name__ == "__main__":
    unittest.main()
