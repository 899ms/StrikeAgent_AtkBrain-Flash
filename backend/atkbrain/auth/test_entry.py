"""安全入口路径剥离、回环旁路、未带入口跳转介绍站。"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class EntryPathTests(unittest.TestCase):
    def test_strip_and_match(self):
        from atkbrain.auth.entry import path_has_entry, strip_entry_path
        tok = "AbCdef12"
        self.assertTrue(path_has_entry(f"/{tok}", tok))
        self.assertTrue(path_has_entry(f"/{tok}/login", tok))
        self.assertFalse(path_has_entry("/login", tok))
        self.assertFalse(path_has_entry("/api/health", tok))
        self.assertEqual(strip_entry_path(f"/{tok}", tok), "/")
        self.assertEqual(strip_entry_path(f"/{tok}/api/health", tok), "/api/health")
        self.assertEqual(strip_entry_path(f"/{tok}/login", tok), "/login")

    def test_loopback_and_rewrite(self):
        from atkbrain.auth.entry import is_loopback_peer, rewrite_scope_entry
        self.assertTrue(is_loopback_peer("127.0.0.1"))
        self.assertTrue(is_loopback_peer("::1"))
        self.assertFalse(is_loopback_peer("8.8.8.8"))
        tok = "k7mNpQ2x"
        scope = {
            "type": "http",
            "path": f"/{tok}/api/health",
            "raw_path": f"/{tok}/api/health".encode(),
            "client": ("203.0.113.9", 1),
        }
        with patch("atkbrain.auth.entry.security_entry", return_value=tok), \
             patch("atkbrain.auth.entry.entry_disabled", return_value=False):
            self.assertTrue(rewrite_scope_entry(scope))
            self.assertEqual(scope["path"], "/api/health")
        bad = {
            "type": "http",
            "path": "/api/health",
            "client": ("203.0.113.9", 1),
        }
        with patch("atkbrain.auth.entry.security_entry", return_value=tok), \
             patch("atkbrain.auth.entry.entry_disabled", return_value=False):
            self.assertFalse(rewrite_scope_entry(bad))
        loop = {
            "type": "http",
            "path": "/api/health",
            "client": ("127.0.0.1", 1),
        }
        with patch("atkbrain.auth.entry.security_entry", return_value=tok), \
             patch("atkbrain.auth.entry.entry_disabled", return_value=False):
            self.assertFalse(rewrite_scope_entry(loop))
        # :2334 socat 对端也是 127.0.0.1，无入口不得进控制台。
        proxied = {
            "type": "http",
            "path": "/login",
            "client": ("127.0.0.1", 1),
        }
        with patch("atkbrain.auth.entry.security_entry", return_value=tok), \
             patch("atkbrain.auth.entry.entry_disabled", return_value=False):
            self.assertFalse(rewrite_scope_entry(proxied))
        via_proxy = {
            "type": "http",
            "path": f"/{tok}/login",
            "raw_path": f"/{tok}/login".encode(),
            "root_path": "",
            "client": ("127.0.0.1", 1),
        }
        with patch("atkbrain.auth.entry.security_entry", return_value=tok), \
             patch("atkbrain.auth.entry.entry_disabled", return_value=False):
            self.assertTrue(rewrite_scope_entry(via_proxy))
            self.assertEqual(via_proxy["path"], "/login")
            self.assertEqual(via_proxy.get("root_path") or "", "")
        assets = {
            "type": "http",
            "path": f"/{tok}/assets/index.js",
            "raw_path": f"/{tok}/assets/index.js".encode(),
            "root_path": "",
            "client": ("127.0.0.1", 1),
        }
        with patch("atkbrain.auth.entry.security_entry", return_value=tok), \
             patch("atkbrain.auth.entry.entry_disabled", return_value=False):
            self.assertTrue(rewrite_scope_entry(assets))
            self.assertEqual(assets["path"], "/assets/index.js")
            self.assertEqual(assets.get("root_path") or "", "")

    def test_decoy_page(self):
        import asyncio
        from atkbrain.auth.entry import SecurityEntryMiddleware, decoy_file

        index = decoy_file("/")
        self.assertTrue(index is not None and index.is_file())
        self.assertIn(b"StrikeAgent", index.read_bytes())
        css = decoy_file("/assets/index-DGxkHyXb.css")
        self.assertIsNotNone(css)
        self.assertEqual(css.suffix, ".css")
        self.assertTrue(css.is_file())
        self.assertIsNone(decoy_file("/../../etc/passwd"))
        self.assertIsNone(decoy_file("/login"))
        self.assertIsNone(decoy_file("/api/health"))
        self.assertIsNone(decoy_file("/assets/"))
        self.assertIsNone(decoy_file("/SOURCE.txt"))

        got: list[dict] = []

        async def inner(scope, receive, send):
            raise AssertionError("must not reach app")

        async def run():
            async def receive():
                return {"type": "http.disconnect"}

            async def send(msg):
                got.append(msg)

            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/",
                "raw_path": b"/",
                "query_string": b"",
                "headers": [],
                "client": ("203.0.113.9", 9),
                "server": ("0.0.0.0", 2334),
            }
            with patch("atkbrain.auth.entry.security_entry", return_value="k7mNpQ2x"), \
                 patch("atkbrain.auth.entry.entry_disabled", return_value=False):
                await SecurityEntryMiddleware(inner)(scope, receive, send)

        asyncio.run(run())
        start = next(m for m in got if m.get("type") == "http.response.start")
        self.assertEqual(start["status"], 200)
        headers = {k.decode(): v.decode() for k, v in start["headers"]}
        self.assertNotIn("location", headers)
        self.assertTrue(headers.get("content-type", "").startswith("text/html"))
        body = next(m for m in got if m.get("type") == "http.response.body").get("body") or b""
        self.assertIn(b"StrikeAgent", body)
        self.assertNotIn(b"github.io", body)

        got.clear()

        async def run_hidden():
            async def receive():
                return {"type": "http.disconnect"}

            async def send(msg):
                got.append(msg)

            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/login",
                "raw_path": b"/login",
                "query_string": b"",
                "headers": [],
                "client": ("203.0.113.9", 9),
                "server": ("0.0.0.0", 2334),
            }
            with patch("atkbrain.auth.entry.security_entry", return_value="k7mNpQ2x"), \
                 patch("atkbrain.auth.entry.entry_disabled", return_value=False):
                await SecurityEntryMiddleware(inner)(scope, receive, send)

        asyncio.run(run_hidden())
        hidden = next(m for m in got if m.get("type") == "http.response.start")
        self.assertEqual(hidden["status"], 404)

    def test_persist_once(self):
        from atkbrain.auth import entry as entry_mod
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        with patch.object(entry_mod.settings, "data_dir", Path(td.name)), \
             patch.object(entry_mod.settings, "security_entry", ""):
            a = entry_mod.load_or_create_entry()
            b = entry_mod.load_or_create_entry()
            self.assertEqual(a, b)
            self.assertEqual(len(a), 8)
            self.assertTrue(all(ch in entry_mod._ALPHABET for ch in a))
            self.assertEqual(os.stat(Path(td.name) / "security_entry").st_mode & 0o777, 0o600)

    def test_env_cannot_pin_entry(self):
        from atkbrain.auth import entry as entry_mod
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        with patch.object(entry_mod.settings, "data_dir", Path(td.name)), \
             patch.object(entry_mod.settings, "security_entry", "FixedTok1"):
            got = entry_mod.load_or_create_entry()
            self.assertEqual(len(got), 8)
            self.assertNotEqual(got, "FixedTok1")
            self.assertTrue(all(ch in entry_mod._ALPHABET for ch in got))
            self.assertEqual(entry_mod.security_entry(), got)


class OriginTests(unittest.TestCase):
    def test_same_host(self):
        from atkbrain.auth.gate import origin_ok
        from atkbrain.auth.test_auth import http_request
        req = http_request(headers=[("host", "10.0.0.5:2334"), ("origin", "http://10.0.0.5:2334")])
        self.assertTrue(origin_ok(req))
        bad = http_request(headers=[("host", "10.0.0.5:2334"), ("origin", "http://evil.example")])
        self.assertFalse(origin_ok(bad))
        none = http_request(headers=[("host", "10.0.0.5:2334")])
        self.assertTrue(origin_ok(none))

    def test_proxy_strips_host_port(self):
        from atkbrain.auth.gate import origin_ok
        from atkbrain.auth.test_auth import http_request
        req = http_request(headers=[
            ("host", "43.133.167.198"),
            ("origin", "https://43.133.167.198:2334"),
        ])
        self.assertTrue(origin_ok(req))
        other = http_request(headers=[
            ("host", "43.133.167.198"),
            ("origin", "https://evil.example:2334"),
        ])
        self.assertFalse(origin_ok(other))


class TokenQueryRemovedTests(unittest.TestCase):
    def test_no_query_token(self):
        from starlette.requests import Request
        from atkbrain.auth.gate import extract_api_token
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/health",
            "raw_path": b"/api/health",
            "query_string": b"token=secret",
            "headers": [],
            "client": ("127.0.0.1", 9),
            "server": ("test", 80),
        }
        self.assertEqual(extract_api_token(Request(scope)), "")
        scope["headers"] = [(b"x-api-token", b"abc")]
        self.assertEqual(extract_api_token(Request(scope)), "abc")


if __name__ == "__main__":
    unittest.main()
