"""Regression tests for garmin_mcp.sync."""

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_DIR = Path(__file__).resolve().parent.parent


class TestIncrementalSyncChdir(unittest.TestCase):
    """Issue #35 bug 1: incremental_sync must chdir to PROJECT_DIR before
    SeleniumBase launches. The host CWD when run as an MCP server can be
    a system path with no write access (e.g. C:\\Windows\\System32 on
    Windows), and SeleniumBase tries to create downloaded_files/ relative
    to CWD, which crashes with PermissionError.
    """

    def setUp(self):
        self._original_cwd = os.getcwd()

    def tearDown(self):
        try:
            os.chdir(self._original_cwd)
        except OSError:
            pass

    def test_incremental_sync_chdirs_to_project_dir(self):
        # Simulate an MCP launch from a different CWD
        os.chdir("/tmp")
        self.assertNotEqual(Path(os.getcwd()).resolve(), PROJECT_DIR)

        mock_client_cls = MagicMock()
        mock_client_cls.return_value.login.return_value = False  # short-circuit
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []

        with (
            patch("garmin_client.GarminClient", mock_client_cls),
            patch("garmin_mcp.sync.get_connection", return_value=mock_conn),
            patch("garmin_mcp.sync.init_db"),
            patch.dict(os.environ, {"GARMIN_EMAIL": "x", "GARMIN_PASSWORD": "y"}),
        ):
            from garmin_mcp.sync import incremental_sync

            incremental_sync()

        self.assertEqual(Path(os.getcwd()).resolve(), PROJECT_DIR)


if __name__ == "__main__":
    unittest.main()
