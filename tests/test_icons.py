import unittest
from unittest.mock import patch

import icons


class IconSourceTests(unittest.TestCase):
    def setUp(self):
        icons._cache.clear()

    @patch("icons.get_shortcut_info")
    @patch("icons._extract_icon")
    @patch("icons.os.path.exists", return_value=True)
    def test_recorded_canonical_executable_has_first_priority(
        self, _exists, extract_icon, shortcut_info
    ):
        expected = object()
        extract_icon.return_value = expected

        actual = icons.get_icon(
            "codex.exe",
            "Codex",
            size=20,
            exe_path="C:/Apps/Codex.exe",
        )

        self.assertIs(actual, expected)
        extract_icon.assert_called_once_with("C:/Apps/Codex.exe", 20)
        shortcut_info.assert_not_called()

    @patch("icons._extract_icon")
    @patch("icons.os.path.exists", return_value=True)
    @patch("icons.get_shortcut_info")
    def test_canonical_shortcut_beats_a_merged_helper_process(
        self, shortcut_info, _exists, extract_icon
    ):
        shortcut_info.return_value = {
            "display_name": "百度网盘",
            "icon_path": "C:/Apps/BaiduNetdisk.exe",
            "icon_index": 0,
        }
        expected = object()
        extract_icon.return_value = expected

        actual = icons.get_icon(
            "baidunetdisk.exe",
            "百度网盘",
            size=20,
            exe_path="C:/Apps/BrowserEngine/BaiduNetdiskUnite.exe",
        )

        self.assertIs(actual, expected)
        extract_icon.assert_called_once_with("C:/Apps/BaiduNetdisk.exe", 20)


if __name__ == "__main__":
    unittest.main()
