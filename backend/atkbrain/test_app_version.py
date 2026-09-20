"""版本比较：无 packaging 时也能解析数字版本。"""
from __future__ import annotations

import builtins
import unittest
from unittest.mock import patch


class ParseTests(unittest.TestCase):
    def test_parse_with_stdlib_fallback(self):
        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name == "packaging" or name.startswith("packaging."):
                raise ImportError("no packaging")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", blocked):
            from atkbrain.app_version import _parse, _status_for
            self.assertEqual(_parse("0.5.0"), (0, 5, 0))
            self.assertEqual(_parse("v1.2.3-beta.1"), (1, 2, 3))
            st, _, latest = _status_for("0.5.0", "0.6.0")
            self.assertEqual(st, "update_available")
            self.assertFalse(latest)
            st, _, latest = _status_for("0.6.0", "0.5.0")
            self.assertEqual(st, "latest")
            self.assertTrue(latest)


class LlmKeyTests(unittest.TestCase):
    def test_configured(self):
        from atkbrain.agents.pi_runtime import llm_api_key_configured
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": ""}, clear=False):
            self.assertFalse(llm_api_key_configured())
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "sk-test", "ANTHROPIC_AUTH_TOKEN": ""}, clear=False):
            self.assertTrue(llm_api_key_configured())


if __name__ == "__main__":
    unittest.main()
