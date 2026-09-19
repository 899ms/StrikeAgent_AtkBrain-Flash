"""Yakit 出口/证书不变量。防止磁盘 CA、别人的 8084、错误页 IP 再次被当成就绪。"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from .yakit import (
    MITM_FAIL_MSG,
    engine_cert_stale,
    parse_echo_ip,
    resolve_egress,
    root_pem_from_chain_text,
    yakit,
)


class ParseEchoIpTests(unittest.TestCase):
    def test_plain_ipv4_200(self) -> None:
        self.assertEqual(parse_echo_ip(200, "101.36.112.205\n"), "101.36.112.205")

    def test_rejects_non_200(self) -> None:
        self.assertIsNone(parse_echo_ip(503, "101.36.112.205\n"))

    def test_rejects_html_error_with_embedded_ip(self) -> None:
        html = (
            "<!DOCTYPE html><html><title>Yakit MITM</title>"
            "<p>ProxyError: TLS连接失败(101.66.199.225:8085)</p></html>"
        )
        self.assertIsNone(parse_echo_ip(200, html))

    def test_rejects_empty(self) -> None:
        self.assertIsNone(parse_echo_ip(200, " \n"))


class LiveMitmCaTests(unittest.TestCase):
    def test_root_is_last_pem(self) -> None:
        leaf = "-----BEGIN CERTIFICATE-----\nLEAF\n-----END CERTIFICATE-----\n"
        root = "-----BEGIN CERTIFICATE-----\nROOT\n-----END CERTIFICATE-----\n"
        got = root_pem_from_chain_text(leaf + root)
        self.assertEqual(got.strip(), root.strip())

    def test_single_pem_is_not_root(self) -> None:
        self.assertIsNone(root_pem_from_chain_text("-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\n"))


class EngineCertStaleTests(unittest.TestCase):
    def test_unbound_is_stale(self) -> None:
        self.assertTrue(engine_cert_stale(bound_url=None, bound_fp=None, live_url="http://127.0.0.1:11433/mcp"))

    def test_url_switch_is_stale(self) -> None:
        self.assertTrue(engine_cert_stale(
            bound_url="http://127.0.0.1:11432/mcp",
            bound_fp="AA:BB",
            live_url="http://127.0.0.1:11433/mcp",
        ))

    def test_same_engine_ok(self) -> None:
        self.assertFalse(engine_cert_stale(
            bound_url="http://127.0.0.1:11433/mcp",
            bound_fp="AA:BB",
            live_url="http://127.0.0.1:11433/mcp",
        ))

    def test_fingerprint_mismatch(self) -> None:
        self.assertTrue(engine_cert_stale(
            bound_url="http://127.0.0.1:11433/mcp",
            bound_fp="AA:BB",
            live_url="http://127.0.0.1:11433/mcp",
            live_fp="CC:DD",
        ))


class MitmOwnershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self._enabled = yakit.enabled
        self._owned = yakit.listen_owned
        self._port = yakit.listen_port
        self._verified = yakit.verified_exit_ip

    def tearDown(self) -> None:
        yakit.enabled = self._enabled
        yakit.listen_owned = self._owned
        yakit.listen_port = self._port
        yakit.verified_exit_ip = self._verified

    def test_choose_listen_skips_occupied(self) -> None:
        occupied = {8084, 8085, 8086}

        def fake_listen(host: str, port: int) -> bool:
            return int(port) in occupied

        with patch("atkbrain.proxy.yakit.port_listening", side_effect=fake_listen):
            self.assertEqual(yakit._choose_listen_port("127.0.0.1"), 8087)

    def test_foreign_8084_is_not_ours(self) -> None:
        yakit.listen_owned = False
        yakit.listen_port = 8084
        with patch("atkbrain.proxy.yakit.port_listening", return_value=True):
            self.assertFalse(yakit.our_mitm_listening())

    def test_owned_port_counts(self) -> None:
        yakit.listen_owned = True
        yakit.listen_port = 8089
        with patch("atkbrain.proxy.yakit.port_listening", return_value=True):
            self.assertTrue(yakit.our_mitm_listening())

    def test_egress_refuses_foreign_listener(self) -> None:
        yakit.enabled = True
        yakit.listen_owned = False
        yakit.listen_port = 8084
        yakit.verified_exit_ip = "1.2.3.4"
        with patch("atkbrain.proxy.yakit.port_listening", return_value=True), \
             patch("atkbrain.proxy.yakit.pool.must_proxy", return_value=True):
            eg = resolve_egress("getshell")
        self.assertTrue(eg.refuse)
        self.assertEqual(eg.reason, MITM_FAIL_MSG)


class ReverifyExitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._enabled = yakit.enabled
        self._verified = yakit.verified_exit_ip
        self._leak_at = yakit._leak_at
        self._err = yakit.last_error

    def tearDown(self) -> None:
        yakit.enabled = self._enabled
        yakit.verified_exit_ip = self._verified
        yakit._leak_at = self._leak_at
        yakit.last_error = self._err

    async def test_live_echo_overwrites_stale_display_ip(self) -> None:
        yakit.enabled = True
        yakit.verified_exit_ip = "103.75.118.84"
        yakit._leak_at = 0.0
        with patch("atkbrain.proxy.yakit.pool.enabled", True), \
             patch.object(yakit, "_echo_via_mitm", return_value="198.51.100.9"), \
             patch.object(yakit, "_cached_direct_ip", return_value="117.176.229.214"):
            await yakit._reverify_exit()
        self.assertEqual(yakit.verified_exit_ip, "198.51.100.9")

    async def test_leak_to_direct_clears_verified(self) -> None:
        yakit.enabled = True
        yakit.verified_exit_ip = "103.75.118.84"
        yakit._leak_at = 0.0
        with patch("atkbrain.proxy.yakit.pool.enabled", True), \
             patch.object(yakit, "_echo_via_mitm", return_value="117.176.229.214"), \
             patch.object(yakit, "_cached_direct_ip", return_value="117.176.229.214"), \
             patch.object(yakit, "ensure_mitm") as ensure:
            await yakit._reverify_exit()
        self.assertIsNone(yakit.verified_exit_ip)
        ensure.assert_awaited()


class PoolFollowsCurrentTests(unittest.TestCase):
    def setUp(self) -> None:
        from .pool import pool
        self.pool = pool
        self._enabled = pool.enabled
        self._live = list(pool.live)
        self._exit = pool.exit_ip
        self._cur = pool._current_url
        self._good = yakit.last_good_proxy
        self._backup = yakit.backup_text

    def tearDown(self) -> None:
        from .pool import pool
        pool.enabled = self._enabled
        pool.live = self._live
        pool.exit_ip = self._exit
        pool._current_url = self._cur
        yakit.last_good_proxy = self._good
        yakit.backup_text = self._backup

    def test_pick_and_exit_ip_follow_https_current(self) -> None:
        from .pool import LiveProxy, pool
        pool.enabled = True
        pool.live = [
            LiveProxy(url="socks5://203.0.113.1:1080", exit_ip="203.0.113.1", proto="socks5", https_ok=False),
            LiveProxy(url="http://198.51.100.9:3128", exit_ip="198.51.100.9", proto="http", https_ok=True),
        ]
        pool.refresh_exit()
        self.assertEqual(pool.current_url(), "http://198.51.100.9:3128")
        self.assertEqual(pool.exit_ip, "198.51.100.9")
        self.assertEqual(pool.pick(), "http://198.51.100.9:3128")

    def test_last_good_is_behind_pool_current(self) -> None:
        from .pool import pool
        yakit.last_good_proxy = "socks5://103.75.118.84:1080"
        yakit.backup_text = ""
        with patch.object(pool, "current_url", return_value="http://198.51.100.9:3128"), \
             patch.object(pool, "mitm_candidates", return_value=["http://198.51.100.9:3128"]):
            downs = yakit._downstream_candidates()
        self.assertEqual(downs[0], "http://198.51.100.9:3128")
        self.assertGreater(downs.index("socks5://103.75.118.84:1080"), 0)


class RebindToPoolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._enabled = yakit.enabled
        self._verified = yakit.verified_exit_ip
        self._applied = yakit.applied_downstream

    def tearDown(self) -> None:
        yakit.enabled = self._enabled
        yakit.verified_exit_ip = self._verified
        yakit.applied_downstream = self._applied

    async def test_rebind_when_pool_current_differs(self) -> None:
        from .pool import pool
        yakit.enabled = True
        yakit.verified_exit_ip = "103.75.118.84"
        yakit.applied_downstream = "socks5://103.75.118.84:1080"
        with patch("atkbrain.proxy.yakit.pool.enabled", True), \
             patch("atkbrain.proxy.yakit.port_listening", return_value=True), \
             patch.object(pool, "current_url", return_value="http://198.51.100.9:3128"), \
             patch.object(yakit, "_downstream_candidates", return_value=["http://198.51.100.9:3128"]), \
             patch.object(yakit, "_apply_mitm_candidates") as apply:
            await yakit._ensure_mitm_locked()
        apply.assert_awaited()

    async def test_keep_when_already_on_pool_current(self) -> None:
        from .pool import pool
        yakit.enabled = True
        yakit.verified_exit_ip = "198.51.100.9"
        yakit.applied_downstream = "http://198.51.100.9:3128"
        with patch("atkbrain.proxy.yakit.pool.enabled", True), \
             patch("atkbrain.proxy.yakit.port_listening", return_value=True), \
             patch.object(pool, "current_url", return_value="http://198.51.100.9:3128"), \
             patch.object(yakit, "_downstream_candidates", return_value=["http://198.51.100.9:3128"]), \
             patch.object(yakit, "_apply_mitm_candidates") as apply:
            await yakit._ensure_mitm_locked()
        apply.assert_not_called()


class PrepareEgressFastPathTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._enabled = yakit.enabled
        self._owned = yakit.listen_owned
        self._verified = yakit.verified_exit_ip

    def tearDown(self) -> None:
        yakit.enabled = self._enabled
        yakit.listen_owned = self._owned
        yakit.verified_exit_ip = self._verified

    async def test_ready_mitm_skips_wait_pick(self) -> None:
        from .yakit import prepare_egress
        yakit.enabled = True
        yakit.listen_owned = True
        yakit.verified_exit_ip = "198.51.100.9"
        with patch("atkbrain.proxy.yakit.should_use_yakit", return_value=True), \
             patch("atkbrain.proxy.yakit.pool.must_proxy", return_value=True), \
             patch.object(yakit, "our_mitm_listening", return_value=True), \
             patch("atkbrain.proxy.yakit.pool.wait_pick") as wait, \
             patch.object(yakit, "ensure_mitm") as ensure:
            eg = await prepare_egress("getshell")
        wait.assert_not_called()
        ensure.assert_not_called()
        self.assertFalse(eg.refuse)
        self.assertEqual(eg.mode, "mitm")

    async def test_unverified_still_ensures(self) -> None:
        from .yakit import prepare_egress
        yakit.enabled = True
        yakit.listen_owned = True
        yakit.verified_exit_ip = None
        with patch("atkbrain.proxy.yakit.should_use_yakit", return_value=True), \
             patch("atkbrain.proxy.yakit.pool.must_proxy", return_value=True), \
             patch.object(yakit, "our_mitm_listening", return_value=True), \
             patch("atkbrain.proxy.yakit.pool.wait_pick") as wait, \
             patch.object(yakit, "ensure_mitm") as ensure, \
             patch("atkbrain.proxy.yakit.resolve_egress") as resolve:
            resolve.return_value = type("E", (), {"refuse": True, "reason": "x", "mode": "mitm"})()
            await prepare_egress("getshell")
        wait.assert_awaited()
        ensure.assert_awaited()


class SrcFanoutTests(unittest.TestCase):
    def test_src_does_not_open_web_exploit_and_src_hunt_together(self) -> None:
        from ..agents.prompts import default_fanout_roles
        self.assertEqual(default_fanout_roles("src"), ["src-hunt", "recon"])
        self.assertEqual(default_fanout_roles("getshell"), ["web-exploit", "recon"])


if __name__ == "__main__":
    unittest.main()
