import os
import tempfile
import unittest
from unittest.mock import patch

import storage


class StorageDateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_db_path = storage.DB_PATH
        self.addCleanup(setattr, storage, "DB_PATH", self.original_db_path)
        storage.DB_PATH = os.path.join(self.temp_dir.name, "usage.db")
        storage.init_db()

    def test_fragment_crossing_midnight_is_split_between_days(self):
        storage.record_fragment(
            "example.exe",
            "Example",
            "C:/Example/example.exe",
            "2026-08-10T23:59:55",
            "2026-08-11T00:00:05",
            10.0,
        )

        self.assertEqual(storage.get_daily_total("2026-08-10"), 5.0)
        self.assertEqual(storage.get_daily_total("2026-08-11"), 5.0)
        self.assertEqual(len(storage.get_fragments_for_date("2026-08-10")), 1)
        self.assertEqual(len(storage.get_fragments_for_date("2026-08-11")), 1)

    def test_ads_processes_are_merged_and_use_the_main_executable(self):
        storage.record_fragment(
            "hpeesofde.exe", "ADS", "D:/ADS/bin/hpeesofde.exe",
            "2026-08-10T10:00:00", "2026-08-10T10:01:00", 60.0,
        )
        storage.record_fragment(
            "hpeesofdds.exe", "ADS", "D:/ADS/bin/hpeesofdds.exe",
            "2026-08-10T10:01:00", "2026-08-10T10:03:00", 120.0,
        )

        stats = storage.get_stats("2026-08-10")

        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["app_name"], "hpeesofde.exe")
        self.assertEqual(stats[0]["display_name"], "Keysight ADS")
        self.assertEqual(stats[0]["total_seconds"], 180.0)
        self.assertEqual(stats[0]["exe_path"], "D:/ADS/bin/hpeesofdds.exe")

    def test_wechat_legacy_rule_is_migrated_to_weixin(self):
        storage.add_app_rule("wechatappex.exe", "wechat.exe", "微信")

        storage.init_db()
        rules = storage.get_app_rules()

        self.assertEqual(rules["wechatappex.exe"], "weixin.exe")
        self.assertEqual(
            storage.canonical_app_name("wechat.exe", rules),
            "weixin.exe",
        )

    def test_codex_package_chatgpt_process_is_merged_into_codex(self):
        path = (
            "C:/Program Files/WindowsApps/"
            "OpenAI.Codex_26.803.5235.0_x64/app/ChatGPT.exe"
        )
        storage.record_fragment(
            "chatgpt.exe", "Codex", path,
            "2026-08-10T10:00:00", "2026-08-10T10:01:00", 60.0,
        )
        storage.record_fragment(
            "codex.exe", "Codex", "C:/Apps/Codex.exe",
            "2026-08-10T10:01:00", "2026-08-10T10:02:00", 60.0,
        )

        stats = storage.get_stats("2026-08-10")

        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["app_name"], "codex.exe")
        self.assertEqual(stats[0]["total_seconds"], 120.0)

    @patch("icons.get_shortcut_info")
    def test_known_system_name_beats_unrelated_shortcut(self, shortcut_info):
        shortcut_info.return_value = {
            "display_name": "Origin 2024 示例数据",
            "icon_path": "C:/Windows/explorer.exe",
            "icon_index": 0,
        }

        name = storage.get_display_name("explorer.exe")

        self.assertEqual(name, "文件资源管理器")
        shortcut_info.assert_not_called()

    def test_init_removes_usage_tracker_from_statistics(self):
        storage.record_fragment(
            "usagetracker.exe", "UsageTracker", "C:/UsageTracker.exe",
            "2026-08-10T10:00:00", "2026-08-10T10:01:00", 60.0,
        )

        storage.init_db()

        self.assertEqual(storage.get_daily_total("2026-08-10"), 0)
        self.assertEqual(storage.get_stats("2026-08-10"), [])


if __name__ == "__main__":
    unittest.main()
