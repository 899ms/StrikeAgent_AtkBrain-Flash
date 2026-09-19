"""升级脚本 tag 校验：拒绝客户端乱传。"""
from __future__ import annotations

import unittest

from .upgrade import start_upgrade


class UpgradeTagTests(unittest.TestCase):
    def test_rejects_metacharacters(self) -> None:
        with self.assertRaises(ValueError):
            start_upgrade("v1.0;rm")
        with self.assertRaises(ValueError):
            start_upgrade("../x")
        with self.assertRaises(ValueError):
            start_upgrade("")


if __name__ == "__main__":
    unittest.main()
