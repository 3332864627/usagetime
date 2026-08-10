import unittest
from datetime import datetime
from unittest.mock import patch

from monitor import (
    WindowMonitor,
    _active_time_cutoff,
    _idle_seconds_from_ticks,
)


class IdleTimeTests(unittest.TestCase):
    def test_tick_counter_wrap_keeps_idle_time_positive(self):
        self.assertAlmostEqual(
            _idle_seconds_from_ticks(0x00000010, 0xFFFFFFF0),
            0.032,
        )

    def test_active_time_is_capped_after_a_long_sleep(self):
        now = 7_200.0
        idle_seconds = 3_600.0
        threshold = 300

        self.assertEqual(
            _active_time_cutoff(now, idle_seconds, threshold),
            3_900.0,
        )

    def test_recent_activity_uses_current_time(self):
        self.assertEqual(_active_time_cutoff(1_000.0, 30.0, 300), 1_000.0)

    @patch("monitor.get_ignored_apps", return_value=set())
    def test_flush_current_accepts_an_idle_cutoff(self, _ignored_apps):
        monitor = WindowMonitor()
        monitor._last_app = "example.exe"
        monitor._last_title = "Example"
        monitor._last_exe = "C:/Example/example.exe"
        monitor._last_start = 100.0

        monitor._flush_current(160.0)

        self.assertEqual(len(monitor._buffer), 1)
        self.assertEqual(monitor._buffer[0]["duration"], 60.0)
        self.assertEqual(
            datetime.fromisoformat(monitor._buffer[0]["end_time"]),
            datetime.fromtimestamp(160.0),
        )

    @patch("monitor.record_fragments_batch")
    @patch("monitor.get_ignored_apps", return_value=set())
    @patch("monitor.get_setting", return_value="300")
    @patch("monitor._get_idle_seconds", return_value=3_600.0)
    @patch("monitor.time.time", return_value=7_200.0)
    def test_stop_after_sleep_does_not_count_the_whole_sleep(
        self,
        _time,
        _idle_seconds,
        _setting,
        _ignored_apps,
        record_batch,
    ):
        monitor = WindowMonitor()
        monitor._last_app = "example.exe"
        monitor._last_title = "Example"
        monitor._last_exe = "C:/Example/example.exe"
        monitor._last_start = 3_500.0

        monitor.stop()

        fragments = record_batch.call_args.args[0]
        self.assertEqual(len(fragments), 1)
        self.assertEqual(fragments[0]["duration"], 400.0)


if __name__ == "__main__":
    unittest.main()
