"""Concurrency guarantees for the workbench SQLite store."""
from pathlib import Path
import tempfile
import threading
import unittest

from src.services.workbench_store import Store


class StoreLockingTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name))

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def assert_write_waits_for_lock(self, operation):
        started = threading.Event()
        finished = threading.Event()
        errors = []

        def write():
            started.set()
            try:
                operation()
            except BaseException as exc:
                errors.append(exc)
            finally:
                finished.set()

        thread = threading.Thread(target=write)
        with self.store.lock:
            thread.start()
            self.assertTrue(started.wait(timeout=1))
            self.assertFalse(finished.wait(timeout=0.1))
        self.assertTrue(finished.wait(timeout=1))
        thread.join()
        if errors:
            raise errors[0]

    def test_put_waits_for_store_lock(self):
        record = {"id": "material_1", "name": "fixture"}

        self.assert_write_waits_for_lock(
            lambda: self.store.put("materials", record)
        )

        self.assertEqual(self.store.get("materials", record["id"]), record)

    def test_delete_waits_for_store_lock(self):
        record = {"id": "material_1", "name": "fixture"}
        self.store.put("materials", record)

        self.assert_write_waits_for_lock(
            lambda: self.store.delete("materials", record["id"])
        )

        self.assertIsNone(self.store.get("materials", record["id"]))


if __name__ == "__main__":
    unittest.main()
