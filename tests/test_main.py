import unittest
from unittest.mock import MagicMock, patch

import main


class SingleInstanceTests(unittest.TestCase):
    @patch("main.ctypes.windll.kernel32")
    def test_existing_instance_is_rejected(self, kernel32):
        kernel32.CreateMutexW = MagicMock(return_value=123)
        kernel32.GetLastError.return_value = 183

        handle = main._acquire_single_instance()

        self.assertIsNone(handle)
        kernel32.CloseHandle.assert_called_once_with(123)

    @patch("main.ctypes.windll.kernel32")
    def test_first_instance_keeps_mutex_handle(self, kernel32):
        kernel32.CreateMutexW = MagicMock(return_value=123)
        kernel32.GetLastError.return_value = 0

        handle = main._acquire_single_instance()

        self.assertEqual(handle, 123)
        kernel32.CloseHandle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
