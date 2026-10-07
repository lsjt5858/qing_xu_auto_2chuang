"""Real local HTTP -> subprocess -> ffmpeg integration, with synthetic media."""
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from src.services.workbench_api import create_app


def session(client):
    response = client.post("/api/session", headers={"X-Workbench": "1"})
    client.headers["X-CSRF-Token"] = response.json()["csrfToken"]


def wait_task(client, key, timeout=50):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        snapshot = client.get("/api/snapshot").json()
        task = next(task for task in snapshot["tasks"] if task["id"] == key)
        if task["status"] not in {"queued", "running"}:
            return task, snapshot
        time.sleep(0.2)
    raise AssertionError(f"Task {key} did not finish within {timeout}s")


class WorkbenchE2ETest(unittest.TestCase):
    def test_import_scenes_mix_download_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "synthetic.mp4"
            subprocess.run([
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=160x90:d=1",
                "-f", "lavfi", "-i", "color=blue:s=160x90:d=1",
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
            ], check=True)
            app = create_app(root / "state")
            with TestClient(app, base_url="http://127.0.0.1:8766") as client:
                session(client)
                settings = client.get("/api/snapshot").json()["settings"]
                settings["outputDirectory"] = str(root / "output")
                self.assertEqual(client.put("/api/settings", json=settings).status_code, 200)
                with source.open("rb") as file:
                    response = client.post("/api/materials/import", files={"files": (source.name, file)})
                self.assertEqual(response.status_code, 200, response.text)
                material = response.json()["materials"][0]
                response = client.post("/api/tasks", json={
                    "name": "Synthetic cuts", "materialIds": [material["id"]],
                    "steps": ["scenes"], "threshold": 27,
                })
                key = response.json()["tasks"][0]["id"]
                task, snapshot = wait_task(client, key)
                self.assertEqual(task["status"], "completed", task.get("error"))
                shots = [m for m in snapshot["materials"] if m["kind"] == "shot"]
                self.assertGreaterEqual(len(shots), 2)
                self.assertTrue(task["events"])
                response = client.post("/api/mix/plans", json={
                    "seed": "e2e", "template": "teaching", "pool": "all",
                    "materialIds": [material["id"], material["id"]],
                })
                plan = response.json()
                self.assertAlmostEqual(plan["durationSeconds"], 4, places=1)
                response = client.post("/api/mix/tasks", json={"planId": plan["id"], "outputs": ["preview"]})
                mix_key = response.json()["tasks"][0]["id"]
                task, snapshot = wait_task(client, mix_key)
                self.assertEqual(task["status"], "completed", task.get("error"))
                output = next(o for o in snapshot["outputs"] if o["taskId"] == mix_key)
                self.assertAlmostEqual(output["durationSeconds"], 4, delta=0.1)
                self.assertEqual(output["width"], 160)
                download = client.get(output["fileUrl"])
                self.assertEqual(download.status_code, 200)
                self.assertEqual(len(download.content), output["sizeBytes"])
                self.assertEqual(client.post(f"/api/outputs/{output['id']}/confirm").status_code, 200)
            # A fresh process-facing app reconstructs the same records from SQLite.
            with TestClient(create_app(root / "state"), base_url="http://127.0.0.1:8766") as client:
                session(client)
                snapshot = client.get("/api/snapshot").json()
                saved = next(o for o in snapshot["outputs"] if o["id"] == output["id"])
                self.assertEqual(saved["kind"], "final")
                self.assertEqual(client.get(saved["fileUrl"]).content, download.content)
                self.assertEqual(len(snapshot["tasks"]), 2)


if __name__ == "__main__":
    unittest.main()
