import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import autostart


class AutostartTests(unittest.TestCase):
    def test_source_command_uses_an_absolute_script_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                with (
                    patch.object(sys, "frozen", False, create=True),
                    patch.object(sys, "argv", ["main.py"]),
                    patch.object(sys, "executable", "C:/Python/python.exe"),
                ):
                    command = autostart._get_command()
            finally:
                os.chdir(previous_cwd)

        expected_script = os.path.join(temp_dir, "main.py")
        self.assertEqual(
            command,
            f'"C:/Python/python.exe" "{expected_script}"',
        )


if __name__ == "__main__":
    unittest.main()
