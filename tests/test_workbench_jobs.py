from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.services.workbench_api import material_record, output_record
from src.services.workbench_jobs import JobRunner
from src.services.workbench_store import Store


def task(status="queued", **extra):
    return {
        "id": "task_1", "name": "fixture", "kind": "analysis", "status": status,
        "progress": None, "stage": "fixture", "createdAt": "2026-01-01T00:00:00+00:00",
        "materialIds": ["mat_1"], "steps": ["scenes"], "threshold": 27,
        "requestedOutputs": [], "outputIds": [], "events": [],
        "_settings": {
            "sourceDirectory": "", "outputDirectory": "/tmp/output",
            "draftDirectory": "", "transcriptionModel": "tiny",
            "reuseAnalysis": True, "preserveLongShots": True,
        },
        **extra,
    }


class WorkbenchJobsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name))
        source = Path(self.directory.name) / "source.mp4"
        source.write_bytes(b"fixture")
        with self.store.transaction():
            self.store.put("materials", {"id": "mat_1", "_path": str(source)})

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_running_intent_is_committed_before_process_spawn(self):
        with self.store.transaction():
            self.store.put("tasks", task())
        runner = JobRunner(self.store)

        def observe_spawn(*_args, **_kwargs):
            persisted = self.store.get("tasks", "task_1")
            self.assertEqual(persisted["status"], "running")
            self.assertTrue(persisted["_input"])
            raise RuntimeError("stop after observing durable state")

        with patch("src.services.workbench_jobs.subprocess.Popen", side_effect=observe_spawn):
            with self.assertRaisesRegex(RuntimeError, "durable state"):
                runner._execute("task_1")

    def test_recovery_terminates_cancelled_orphan_before_retry_is_possible(self):
        input_path = str(Path(self.directory.name) / "input.json")
        with self.store.transaction():
            self.store.put("tasks", task("cancelled", _workerPid=1234, _input=input_path))
        runner = JobRunner(self.store)
        with (
            patch("src.services.workbench_jobs.subprocess.run",
                  return_value=Mock(stdout=f"python -m src.services.workbench_worker {input_path} result events")),
            patch.object(runner, "_terminate_process_group") as terminate,
        ):
            runner.recover()
        terminate.assert_called_once_with(1234)
        recovered = self.store.get("tasks", "task_1")
        self.assertNotIn("_workerPid", recovered)
        self.assertNotIn("_input", recovered)

    def test_stop_waits_until_worker_thread_has_exited(self):
        runner = JobRunner(self.store)

        class Thread:
            joins = 0

            def join(self, timeout=None):
                self.joins += 1

            def is_alive(self):
                return self.joins < 3

        runner.thread = Thread()
        runner.stop()
        self.assertGreaterEqual(runner.thread.joins, 3)

    def test_verified_worker_metadata_avoids_parent_ffprobe_during_result_commit(self):
        media = Path(self.directory.name) / "verified.mp4"
        media.write_bytes(b"already verified by worker")
        with patch("src.services.workbench_api.probe", side_effect=AssertionError("must not probe")):
            material = material_record(media, duration_seconds=1.25)
            output = output_record(
                media, duration_seconds=1.25, width=1080, height=1920,
                size_bytes=media.stat().st_size,
            )
        self.assertEqual(material["durationSeconds"], 1.25)
        self.assertEqual(output["durationSeconds"], 1.25)
        self.assertEqual((output["width"], output["height"]), (1080, 1920))


if __name__ == "__main__":
    unittest.main()
