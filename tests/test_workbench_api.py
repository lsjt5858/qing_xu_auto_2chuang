"""Local HTTP integration tests. Uses a synthetic video, never a platform account."""
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.services import workbench_api
from src.services.workbench_api import create_app


class WorkbenchAPITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_dir = tempfile.TemporaryDirectory()
        path = Path(cls.media_dir.name) / "sample.mp4"
        subprocess.run([
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
            "color=c=blue:s=160x90:d=0.4", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", str(path),
        ], check=True)
        cls.video = path.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.media_dir.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.directory.name), start_worker=False)
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8766")
        self.client.__enter__()
        self.client.headers["Origin"] = "http://127.0.0.1:8766"
        response = self.client.post("/api/session", headers={"X-Workbench": "1"})
        self.assertEqual(response.status_code, 200, response.text)
        self.client.headers["X-CSRF-Token"] = response.json()["csrfToken"]

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.directory.cleanup()

    def upload(self, outputs=False):
        response = self.client.post(
            "/api/outputs/import" if outputs else "/api/materials/import",
            files=[("files", ("sample.mp4", io.BytesIO(self.video), "video/mp4"))],
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["outputs" if outputs else "materials"][0]

    def pair(self, extension_id="a" * 32):
        code = self.client.post("/api/pairing", json={}).json()["code"]
        response = self.client.post("/api/extension/pair", json={
            "code": code, "extensionId": extension_id, "name": "Test runner",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.extension_headers = {
            "Authorization": f"Bearer {response.json()['token']}",
            "X-Extension-Id": extension_id,
            "Origin": f"chrome-extension://{extension_id}",
        }
        response = self.client.post("/api/extension/heartbeat", headers=self.extension_headers,
                                    json={"account": {"uid": "u1", "nickname": "Fixture",
                                                     "unique_id": "fixture", "short_id": "1"}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.post("/api/extension/pair", json={
            "code": code, "extensionId": extension_id, "name": "duplicate",
        }).status_code, 403)
        return self.client.get("/api/snapshot").json()["accounts"][0]

    def queue_publish(self, mode="direct"):
        output = self.upload(outputs=True)
        account = self.pair()
        request = {"outputId": output["id"], "accountId": account["id"], "title": "Fixture",
                   "caption": "Only a test", "mode": mode, "confirmed": True}
        response = self.client.post("/api/publish", json=request)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["receipts"][0], request

    def claim(self):
        response = self.client.post("/api/extension/claim", headers=self.extension_headers,
                                    json={"accountUid": "u1"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["job"]

    def event(self, job, status):
        return self.client.post(f"/api/extension/jobs/{job['id']}/event",
                                headers=self.extension_headers,
                                json={"leaseToken": job["leaseToken"], "status": status,
                                      "evidence": "fixture success" if status == "submitted" else ""})

    def test_cross_site_and_missing_csrf_are_rejected(self):
        self.assertEqual(self.client.post("/api/tasks", json={},
                                         headers={"Origin": "https://evil.test"}).status_code, 403)
        self.assertEqual(self.client.get("/api/snapshot",
                                        headers={"Host": "evil.test"}).status_code, 403)
        self.assertEqual(self.client.post("/api/tasks", json={},
                                         headers={"X-CSRF-Token": ""}).status_code, 403)
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/snapshot").status_code, 401)

    def test_malformed_origin_is_rejected_instead_of_crashing_middleware(self):
        other = create_app(Path(self.directory.name) / "origin", start_worker=False)
        with TestClient(
            other,
            base_url="http://127.0.0.1:8766",
            raise_server_exceptions=False,
        ) as client:
            response = client.post(
                "/api/session",
                headers={
                    "X-Workbench": "1",
                    "Origin": "http://127.0.0.1:70000",
                },
            )
        self.assertEqual(response.status_code, 403)

    def test_registered_file_supports_range_and_invalid_upload_does_not_register(self):
        material = self.upload()
        response = self.client.get(material["fileUrl"], headers={"Range": "bytes=0-15"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, self.video[:16])
        self.assertEqual(self.client.get("/api/materials/no-such-id/file").status_code, 404)
        bad = self.client.post("/api/materials/import",
                               files={"files": ("bad.mp4", b"not video", "video/mp4")})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(len(self.client.get("/api/snapshot").json()["materials"]), 1)

    def test_persisted_plan_uses_full_clip_and_task_cancel_retry(self):
        material = self.upload()
        response = self.client.post("/api/mix/plans", json={
            "seed": "42", "template": "teaching", "pool": "all",
            "materialIds": [material["id"]],
        })
        self.assertEqual(response.status_code, 200, response.text)
        plan = response.json()
        self.assertAlmostEqual(plan["durationSeconds"], material["durationSeconds"])
        task_response = self.client.post("/api/mix/tasks",
                                         json={"planId": plan["id"], "outputs": ["preview"]})
        self.assertEqual(task_response.status_code, 200, task_response.text)
        task = task_response.json()["tasks"][0]
        self.assertEqual(task["plan"], plan)
        command = f"/api/tasks/{task['id']}/command"
        self.assertEqual(self.client.post(command, json={"command": "advance"}).status_code, 422)
        cancelled = self.client.post(command, json={"command": "cancel"}).json()["tasks"][0]
        self.assertEqual(cancelled["status"], "cancelled")
        retried = self.client.post(command, json={"command": "retry"}).json()["tasks"][0]
        self.assertEqual(retried["status"], "queued")

    def test_directory_report_is_applied_only_to_its_matching_video(self):
        directory = Path(self.directory.name) / "analysis"
        directory.mkdir()
        (directory / "a.mp4").write_bytes(self.video)
        (directory / "b.mp4").write_bytes(self.video)
        (directory / "report.json").write_text(
            json.dumps(
                {
                    "video_name": "a",
                    "scenes": [{"start_time": 0, "duration": 0.4}],
                    "transcript_segments": [{"start": 0, "text": "only a"}],
                }
            ),
            encoding="utf-8",
        )
        response = self.client.post(
            "/api/materials/directory", json={"path": str(directory)}
        )
        self.assertEqual(response.status_code, 200, response.text)
        materials = {
            item["name"]: item
            for item in response.json()["materials"]
            if item["name"] in {"a.mp4", "b.mp4"}
        }
        self.assertEqual(materials["a.mp4"]["status"], "analyzed")
        self.assertEqual(materials["a.mp4"]["transcript"][0]["text"], "only a")
        self.assertEqual(materials["b.mp4"]["status"], "ready")
        self.assertEqual(materials["b.mp4"]["transcript"], [])

    def test_malformed_report_numbers_return_422_without_registering_material(self):
        directory = Path(self.directory.name) / "malformed"
        directory.mkdir()
        (directory / "bad.mp4").write_bytes(self.video)
        (directory / "report.json").write_text(
            json.dumps({"video_name": "bad", "scenes": [{"start_time": "oops"}]}),
            encoding="utf-8",
        )
        response = self.client.post(
            "/api/materials/directory", json={"path": str(directory)}
        )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertFalse(
            any(
                item["name"] == "bad.mp4"
                for item in self.client.get("/api/snapshot").json()["materials"]
            )
        )

    def test_directory_probe_runs_outside_global_store_lock(self):
        directory = Path(self.directory.name) / "unlocked-import"
        directory.mkdir()
        (directory / "clip.mp4").write_bytes(b"fixture")
        lock_results = []

        def probe_without_lock(_path):
            def acquire():
                acquired = self.app.state.store.lock.acquire(timeout=0.2)
                lock_results.append(acquired)
                if acquired:
                    self.app.state.store.lock.release()

            thread = threading.Thread(target=acquire)
            thread.start()
            thread.join()
            return {"durationSeconds": 1, "width": 64, "height": 64}

        with patch.object(workbench_api, "probe", side_effect=probe_without_lock):
            response = self.client.post(
                "/api/materials/directory", json={"path": str(directory)}
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(lock_results, [True])

    def test_publish_copy_and_hash_run_outside_global_store_lock(self):
        output = self.upload(outputs=True)
        account = self.pair()
        lock_results = []
        original_copy = shutil.copyfile

        def copy_without_lock(source, destination):
            def acquire():
                acquired = self.app.state.store.lock.acquire(timeout=0.2)
                lock_results.append(acquired)
                if acquired:
                    self.app.state.store.lock.release()

            thread = threading.Thread(target=acquire)
            thread.start()
            thread.join()
            return original_copy(source, destination)

        with patch.object(
            workbench_api.shutil, "copyfile", side_effect=copy_without_lock
        ):
            response = self.client.post(
                "/api/publish",
                json={
                    "outputId": output["id"],
                    "accountId": account["id"],
                    "title": "Fixture",
                    "caption": "",
                    "mode": "prefill",
                    "confirmed": True,
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(lock_results, [True])

    def test_empty_account_nickname_is_accepted_with_safe_display_name(self):
        code = self.client.post("/api/pairing", json={}).json()["code"]
        extension_id = "c" * 32
        pair = self.client.post(
            "/api/extension/pair",
            json={"code": code, "extensionId": extension_id, "name": "Empty nickname"},
        )
        headers = {
            "Authorization": f"Bearer {pair.json()['token']}",
            "X-Extension-Id": extension_id,
            "Origin": f"chrome-extension://{extension_id}",
        }
        response = self.client.post(
            "/api/extension/heartbeat",
            headers=headers,
            json={
                "account": {
                    "uid": "empty-name",
                    "nickname": "",
                    "unique_id": "",
                    "short_id": "",
                }
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        account = self.client.get("/api/snapshot").json()["accounts"][0]
        self.assertEqual(account["name"], "未命名账号")

    def test_publish_frozen_account_file_lease_and_no_duplicate_submit(self):
        receipt, request = self.queue_publish()
        frozen = Path(self.app.state.store.get("receipts", receipt["id"])["_path"])
        self.assertTrue(frozen.is_file())
        self.assertEqual(receipt["status"], "queued")
        self.assertFalse(receipt["simulated"])
        self.assertEqual(self.client.post("/api/publish", json=request).status_code, 409)
        wrong = self.client.post("/api/extension/claim", headers=self.extension_headers,
                                 json={"accountUid": "other"}).json()
        self.assertIsNone(wrong["job"])
        job = self.claim()
        self.assertEqual(job["accountUid"], "u1")
        self.assertIsNone(self.claim())
        self.assertEqual(self.event(job, "submitted").status_code, 409)
        download = self.client.get(f"/api/extension/jobs/{job['id']}/file",
                                   headers={**self.extension_headers,
                                            "X-Lease-Token": job["leaseToken"]})
        self.assertEqual(download.content, self.video)
        for status in ("uploading", "filling", "submitting", "submitted"):
            self.assertEqual(self.event(job, status).status_code, 200)
        self.assertFalse(frozen.exists())
        self.assertEqual(self.event(job, "submitting").status_code, 409)
        self.assertIsNone(self.claim())

    def test_expired_submitting_becomes_unknown_never_requeues(self):
        receipt, _ = self.queue_publish()
        frozen = Path(self.app.state.store.get("receipts", receipt["id"])["_path"])
        job = self.claim()
        for status in ("uploading", "filling", "submitting"):
            self.assertEqual(self.event(job, status).status_code, 200)
        with self.app.state.store.transaction():
            receipt = self.app.state.store.get("receipts", job["id"])
            receipt["_leaseExpires"] = 0
            self.app.state.store.put("receipts", receipt)
        snapshot = self.client.get("/api/snapshot").json()
        self.assertEqual(snapshot["receipts"][0]["status"], "unknown")
        self.assertFalse(frozen.exists())
        self.assertIsNone(self.claim())
        self.assertEqual(self.event(job, "submitted").status_code, 409)

    def test_prefill_cannot_submit_and_revocation_invalidates_token(self):
        receipt, _ = self.queue_publish(mode="prefill")
        frozen = Path(self.app.state.store.get("receipts", receipt["id"])["_path"])
        job = self.claim()
        self.event(job, "uploading")
        self.event(job, "filling")
        self.assertEqual(self.event(job, "submitting").status_code, 409)
        self.assertEqual(self.event(job, "awaiting_confirmation").status_code, 200)
        self.assertFalse(frozen.exists())
        response = self.client.delete("/api/pairing/" + "a" * 32)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post("/api/extension/claim",
                                         headers=self.extension_headers,
                                         json={"accountUid": "u1"}).status_code, 401)

    def test_cancelled_publish_removes_frozen_copy(self):
        receipt, _ = self.queue_publish(mode="prefill")
        frozen = Path(self.app.state.store.get("receipts", receipt["id"])["_path"])
        self.assertTrue(frozen.is_file())
        response = self.client.post(f"/api/publish/{receipt['id']}/cancel", json={})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(frozen.exists())

    def test_account_switch_invalidates_existing_lease(self):
        self.queue_publish()
        job = self.claim()
        self.event(job, "uploading")
        with self.app.state.store.transaction():
            extension = self.app.state.store.get("extensions", "a" * 32)
            extension["_accountUid"] = "u2"
            self.app.state.store.put("extensions", extension)
        self.assertEqual(self.event(job, "filling").status_code, 409)
        with self.app.state.store.transaction():
            extension = self.app.state.store.get("extensions", "a" * 32)
            extension["_accountUid"] = "u1"
            self.app.state.store.put("extensions", extension)
        response = self.client.post("/api/extension/heartbeat", headers=self.extension_headers,
                                    json={"account": {"uid": "u2", "nickname": "Other"}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.event(job, "filling").status_code, 409)
        self.assertEqual(self.client.get("/api/snapshot").json()["receipts"][0]["status"], "blocked")

    def test_same_platform_uid_cannot_bypass_deduplication_with_another_extension(self):
        _, request = self.queue_publish()
        job = self.claim()
        for status in ("uploading", "filling", "submitting", "unknown"):
            self.assertEqual(self.event(job, status).status_code, 200)
        other_account = self.pair("b" * 32)
        request["accountId"] = other_account["id"]
        self.assertEqual(self.client.post("/api/publish", json=request).status_code, 409)
        duplicate_output = self.upload(outputs=True)
        request["outputId"] = duplicate_output["id"]
        self.assertEqual(self.client.post("/api/publish", json=request).status_code, 409)


if __name__ == "__main__":
    unittest.main()
