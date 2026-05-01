"""Regression tests for garmin_client.client."""

import threading
import unittest

from garmin_client.client import _ProcessLifecycle


class TestProcessLifecycleThreadSafety(unittest.TestCase):
    """Issue #35 bug 2: _ProcessLifecycle.install() used to call
    signal.signal() unconditionally. The MCP server runs sync in a
    ThreadPoolExecutor worker, so install() runs from a non-main thread
    and signal.signal() raises ValueError("signal only works in main
    thread of the main interpreter").
    """

    def test_install_from_worker_thread_does_not_raise(self):
        errors: list[BaseException] = []

        def worker():
            try:
                lifecycle = _ProcessLifecycle(cleanup_fn=lambda: None)
                lifecycle.install()
            except BaseException as exc:
                errors.append(exc)

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertEqual(errors, [], f"install() raised in worker thread: {errors}")


if __name__ == "__main__":
    unittest.main()
