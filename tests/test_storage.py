import os
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
