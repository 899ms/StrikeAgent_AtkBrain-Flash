"""红队/SRC 禁止把写操作落到真实用户、资金、库存；http 与 https 同一套。"""
from __future__ import annotations

import unittest

from ..agents.context import AgentContext
from ..exec.guard import Guard, target_destructive_reason
from ..scope import Scope


def _scope() -> Scope:
    return Scope(targets=["example.com"], allow_subdomains=False, mode="strict")


class SqlWriteAllTracksTests(unittest.TestCase):
    def test_drop_blocked_everywhere(self) -> None:
        cmd = "curl -s 'https://example.com/q?id=1;DROP TABLE users--'"
        for obj in ("src", "getshell", "flag"):
            self.assertIsNotNone(target_destructive_reason(cmd, objective=obj), obj)

    def test_insert_and_outfile_all_tracks(self) -> None:
        ins = "POST https://example.com/q data=INSERT INTO users VALUES(1)"
        outf = "id=1 UNION SELECT 1 INTO OUTFILE '/tmp/x'"
        for obj in ("src", "getshell", "flag"):
            self.assertIsNotNone(target_destructive_reason(ins, objective=obj), obj)
            self.assertIsNotNone(target_destructive_reason(outf, objective=obj), obj)

    def test_update_in_http_body(self) -> None:
        blob = "POST https://example.com/api UPDATE users SET password='x'"
        self.assertIsNotNone(target_destructive_reason(blob, objective="src"))


class IdentityMoneyFloodTests(unittest.TestCase):
    def test_https_reset_admin_blocked_src(self) -> None:
        blob = (
            "POST https://example.com/reset-password "
            "username=admin&new_password=Hacked1"
        )
        why = target_destructive_reason(blob, objective="src")
        self.assertIsNotNone(why)
        self.assertIn("口令", why or "")

    def test_https_reset_admin_blocked_redteam(self) -> None:
        blob = (
            "POST https://example.com/reset-password "
            "username=admin&new_password=Hacked1"
        )
        self.assertIsNotNone(target_destructive_reason(blob, objective="getshell"))

    def test_login_password_allowed(self) -> None:
        blob = "POST https://example.com/login username=admin&password=secret"
        self.assertIsNone(target_destructive_reason(blob, objective="src"))

    def test_pay_submit_blocked(self) -> None:
        blob = "POST https://example.com/pay amount=0.01&order_id=9"
        why = target_destructive_reason(blob, objective="src")
        self.assertIsNotNone(why)
        self.assertIn("支付", why or "")

    def test_sms_loop_blocked(self) -> None:
        blob = "for i in {1..50}; do curl -s https://example.com/sms/send-code; done"
        why = target_destructive_reason(blob, objective="src")
        self.assertIsNotNone(why)

    def test_ab_blocked(self) -> None:
        blob = "ab -n 100 -c 20 https://example.com/checkout"
        self.assertIsNotNone(target_destructive_reason(blob, objective="src"))

    def test_xargs_p20_blocked(self) -> None:
        blob = "seq 1 20 | xargs -P 20 -I{} curl -s https://example.com/pay"
        self.assertIsNotNone(target_destructive_reason(blob, objective="src"))

    def test_ctf_skips_business_rules(self) -> None:
        reset = (
            "POST https://example.com/reset-password "
            "username=admin&new_password=Hacked1"
        )
        self.assertIsNone(target_destructive_reason(reset, objective="flag"))
        self.assertIsNone(target_destructive_reason("ab -n 100 https://example.com/", objective="flag"))
        pay = "POST https://example.com/pay amount=1"
        self.assertIsNone(target_destructive_reason(pay, objective="flag"))

    def test_guard_curl_https_reset(self) -> None:
        g = Guard(_scope(), objective="src")
        d = g.check_command(
            "curl -s -X POST https://example.com/reset-password "
            "-d 'username=admin&new_password=x'"
        )
        self.assertFalse(d.allow, d.reason)


class HttpRequestHttpsTests(unittest.IsolatedAsyncioTestCase):
    async def test_https_reset_body_blocked(self) -> None:
        sc = _scope()
        ctx = AgentContext(
            project_id="p_test",
            workspace_dir="/tmp",
            loot_dir="/tmp",
            scope=sc,
            guard=Guard(sc, objective="src"),
            objective="src",
        )
        res = await ctx.http(
            "https://example.com/reset-password",
            method="POST",
            data="username=admin&new_password=Hacked1",
        )
        self.assertTrue(res.get("blocked"), res)
        self.assertIn("口令", str(res.get("error") or ""))

    async def test_https_sql_body_blocked(self) -> None:
        sc = _scope()
        ctx = AgentContext(
            project_id="p_test",
            workspace_dir="/tmp",
            loot_dir="/tmp",
            scope=sc,
            guard=Guard(sc, objective="src"),
            objective="src",
        )
        res = await ctx.http(
            "https://example.com/q",
            method="POST",
            data="id=1; DROP TABLE users--",
        )
        self.assertTrue(res.get("blocked"), res)
        self.assertIn("DROP", str(res.get("error") or ""))

    async def test_https_login_allowed_by_destructive_gate(self) -> None:
        why = target_destructive_reason(
            "POST https://example.com/login username=admin&password=secret",
            objective="src",
        )
        self.assertIsNone(why)


if __name__ == "__main__":
    unittest.main()
