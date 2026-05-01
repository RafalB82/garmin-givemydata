"""Regression tests for garmin_mcp.server."""

import time
import unittest
from unittest.mock import patch

from garmin_mcp import server


class TestBackgroundSync(unittest.TestCase):
    """Issue #35 bug 3: sync used to block the MCP tool call for ~2 minutes,
    but most MCP clients (Claude Desktop) time out at ~60s, so the result
    was never delivered. _start_background_sync() runs the sync in a
    daemon thread and returns immediately so the tool call completes within
    the client's timeout.
    """

    def setUp(self):
        # Reset state between tests
        server._sync_state.update(
            running=False,
            started_at=None,
            finished_at=None,
            last_result=None,
        )
        # Make sure the lock is free
        if server._sync_lock.locked():
            server._sync_lock.release()

    def tearDown(self):
        # Wait for any background thread to finish so it doesn't pollute
        # subsequent tests
        for _ in range(50):
            if not server._sync_state["running"]:
                break
            time.sleep(0.05)

    def test_start_background_sync_returns_quickly(self):
        # Mock incremental_sync to take 2 seconds. The call to
        # _start_background_sync() must still return in < 500ms because
        # the work happens in a daemon thread.
        def slow_sync():
            time.sleep(2)
            return {"status": "ok", "total_upserted": 0}

        with patch("garmin_mcp.sync.incremental_sync", slow_sync):
            t0 = time.monotonic()
            result = server._start_background_sync()
            elapsed = time.monotonic() - t0

        self.assertLess(elapsed, 0.5, f"_start_background_sync took {elapsed:.2f}s")
        self.assertEqual(result["status"], "started")
        self.assertIsNotNone(result["started_at"])
        self.assertTrue(server._sync_state["running"])

        # Wait for it to complete and confirm state transitions correctly
        for _ in range(50):
            if not server._sync_state["running"]:
                break
            time.sleep(0.1)

        self.assertFalse(server._sync_state["running"])
        self.assertIsNotNone(server._sync_state["finished_at"])
        self.assertEqual(server._sync_state["last_result"]["status"], "ok")

    def test_start_background_sync_rejects_concurrent_call(self):
        # First call holds the lock; second call should report in_progress.
        def slow_sync():
            time.sleep(2)
            return {"status": "ok"}

        with patch("garmin_mcp.sync.incremental_sync", slow_sync):
            first = server._start_background_sync()
            second = server._start_background_sync()

        self.assertEqual(first["status"], "started")
        self.assertEqual(second["status"], "in_progress")
        self.assertEqual(second["started_at"], first["started_at"])

    def test_background_sync_records_failure(self):
        def boom():
            raise RuntimeError("simulated browser crash")

        with patch("garmin_mcp.sync.incremental_sync", boom):
            server._start_background_sync()
            for _ in range(50):
                if not server._sync_state["running"]:
                    break
                time.sleep(0.05)

        self.assertFalse(server._sync_state["running"])
        self.assertEqual(server._sync_state["last_result"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
