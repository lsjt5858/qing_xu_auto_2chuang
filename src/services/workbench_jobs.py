"""Serial, restart-aware child-process execution for expensive video work."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from fastapi import HTTPException

from .workbench_store import identifier, now


class JobRunner:
    def __init__(self, store):
        self.store = store
        self.stopping = threading.Event()
        self.thread = None
        self.process = None
        self.task_id = None
        self.process_lock = threading.RLock()

    def recover(self):
        from .workbench_api import TERMINAL_PUBLISH, remove_frozen_publish_file

        cleanup = []
        with self.store.transaction() as store:
            for task in store.all("tasks"):
                if task["status"] in {"running", "cancelled"}:
                    pid = task.get("_workerPid")
                    input_path = task.get("_input")
                    if pid and input_path and self._process_matches(pid, input_path):
                        self._terminate_process_group(pid)
                    elif input_path:
                        for orphan_pid in self._find_worker_pids(input_path):
                            self._terminate_process_group(orphan_pid)
                    if task["status"] == "running":
                        task.update(status="interrupted", progress=None, stage="服务中断",
                                    error="服务退出，任务未自动重跑；可核查产物后重试")
                        task["events"].append({"at": now(), "message": task["error"]})
                    else:
                        task["events"].append({"at": now(), "message": "已确认取消任务的处理进程停止"})
                    for field in ("_workerPid", "_input", "_startGate"):
                        task.pop(field, None)
                    store.put("tasks", task)
            for job in store.all("receipts"):
                if job.get("_leaseToken") and job["status"] in {"queued", "uploading", "filling", "submitting"}:
                    job.update(status="unknown" if job["status"] == "submitting" else "blocked",
                               message="服务重启，请核查平台页面；不会自动重试", updatedAt=now())
                    store.put("receipts", job)
                if job["status"] in TERMINAL_PUBLISH:
                    cleanup.append(job)
        for job in cleanup:
            remove_frozen_publish_file(job)

    def start(self):
        self.thread = threading.Thread(target=self._loop, name="workbench-worker", daemon=True)
        self.thread.start()

    @staticmethod
    def _kill_group(pid):
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    @staticmethod
    def _process_matches(pid, input_path):
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True
        )
        return "src.services.workbench_worker" in result.stdout and input_path in result.stdout

    @staticmethod
    def _find_worker_pids(input_path):
        result = subprocess.run(["ps", "-axo", "pid=,args="], capture_output=True, text=True)
        matches = []
        for line in result.stdout.splitlines():
            pid, _, args = line.strip().partition(" ")
            if pid.isdigit() and "src.services.workbench_worker" in args and input_path in args:
                matches.append(int(pid))
        return matches

    def _terminate_process_group(self, pid, timeout=5):
        self._kill_group(pid)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.05)
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def is_active(self, key):
        with self.process_lock:
            return self.task_id == key

    def cancel(self, key):
        with self.process_lock:
            with self.store.transaction() as store:
                task = store.get("tasks", key)
                if not task:
                    raise HTTPException(404, "任务不存在")
                if task["status"] not in {"queued", "running"}:
                    raise HTTPException(409, "只有等待或运行中的任务可以取消")
                task.update(status="cancelled", progress=None, stage="已取消")
                task["events"].append({"at": now(), "message": "用户取消任务，正在停止处理进程"})
                store.put("tasks", task)
            if self.task_id == key and self.process:
                self._kill_group(self.process.pid)

    def stop(self):
        self.stopping.set()
        with self.process_lock:
            if self.process:
                self._kill_group(self.process.pid)
        if not self.thread:
            return
        deadline = time.monotonic() + 30
        force_at = time.monotonic() + 5
        while self.thread.is_alive() and time.monotonic() < deadline:
            self.thread.join(timeout=1)
            if time.monotonic() >= force_at:
                with self.process_lock:
                    if self.process and self.process.poll() is None:
                        try:
                            os.killpg(self.process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
        if self.thread.is_alive():
            raise RuntimeError("工作台处理线程未能安全停止；保留数据库连接以避免并发关闭")

    def _loop(self):
        while not self.stopping.wait(0.3):
            task = None
            with self.store.lock:
                task = next((t for t in reversed(self.store.all("tasks"))
                             if t["status"] == "queued"), None)
            if task:
                try:
                    self._execute(task["id"])
                except Exception as exc:
                    with self.store.transaction() as store:
                        current = store.get("tasks", task["id"])
                        if current and current["status"] == "running":
                            current.update(status="failed", progress=None, stage="处理失败", error=str(exc)[:4000])
                            current["events"].append({"at": now(), "message": current["error"]})
                            for field in ("_workerPid", "_input", "_startGate"):
                                current.pop(field, None)
                            store.put("tasks", current)
                finally:
                    with self.process_lock:
                        if self.process and self.process.poll() is None:
                            self._kill_group(self.process.pid)
                            try:
                                self.process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                os.killpg(self.process.pid, signal.SIGKILL)
                                self.process.wait(timeout=5)
                        self.process = None
                        self.task_id = None

    def _read_events(self, path, offset, key):
        if not path.is_file():
            return offset
        with path.open(encoding="utf-8") as events:
            events.seek(offset)
            lines = events.readlines()
            end = events.tell()
        # An append in flight can leave a partial final JSON line.
        if lines and not lines[-1].endswith("\n"):
            end -= len(lines.pop().encode("utf-8"))
        if lines:
            with self.store.transaction() as store:
                task = store.get("tasks", key)
                for line in lines:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    task["events"].append({"at": event.get("at", now()), "message": str(event.get("message", ""))})
                    if task["status"] == "running":
                        task["stage"] = str(event.get("message", "处理中"))
                task["events"] = task["events"][-500:]
                store.put("tasks", task)
        return end

    def _execute(self, key):
        from .workbench_api import material_record, output_record

        with self.process_lock:
            with self.store.transaction() as store:
                task = store.get("tasks", key)
                if task["status"] != "queued" or self.stopping.is_set():
                    return
                directory = store.root / "jobs" / key / identifier("attempt")
                directory.mkdir(parents=True, mode=0o700)
                input_path, result_path, events_path = [
                    directory / name for name in ("input.json", "result.json", "events.jsonl")
                ]
                start_gate = directory / "start"
                materials = []
                for mid in task["materialIds"]:
                    material = store.get("materials", mid)
                    materials.append({**material, "path": material["_path"],
                                      "reportPath": material.get("_reportPath")})
                task.update(
                    status="running", stage="正在启动处理进程", progress=None,
                    _input=str(input_path), _startGate=str(start_gate),
                )
                payload = {
                    "task": task, "materials": materials,
                    "settings": task["_settings"], "workDir": str(directory),
                }
                input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                store.put("tasks", task)
            log_path = directory / "worker.log"
            environment = {**os.environ, "WORKBENCH_START_GATE": str(start_gate)}
            with log_path.open("wb") as log:
                self.process = subprocess.Popen(
                    [sys.executable, "-u", "-m", "src.services.workbench_worker",
                     str(input_path), str(result_path), str(events_path)],
                    cwd=Path(__file__).resolve().parents[2], stdout=log, stderr=log,
                    start_new_session=True, env=environment,
                )
            self.task_id = key
            with self.store.transaction() as store:
                persisted = store.get("tasks", key)
                persisted["_workerPid"] = self.process.pid
                store.put("tasks", persisted)
            start_gate.touch(exist_ok=False)
        offset = 0
        cancel_wait = 0
        while self.process.poll() is None:
            offset = self._read_events(events_path, offset, key)
            if self.stopping.wait(0.25):
                self._kill_group(self.process.pid)
            with self.store.lock:
                cancelled = self.store.get("tasks", key)["status"] == "cancelled"
            if cancelled or self.stopping.is_set():
                cancel_wait += 1
                if cancel_wait >= 20:
                    try:
                        os.killpg(self.process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        self._read_events(events_path, offset, key)
        result = None
        prepared_materials = []
        prepared_outputs = []
        if (not self.stopping.is_set() and self.process.returncode == 0
                and result_path.is_file()):
            result = json.loads(result_path.read_text(encoding="utf-8"))
            for shot in result.get("newMaterials", []):
                path = Path(shot["path"]).resolve()
                prepared_materials.append((str(path), material_record(
                    path, name=shot.get("name"), kind=shot.get("kind", "shot"),
                    category=shot.get("category", "分镜片段"),
                    duration_seconds=shot.get("durationSeconds"),
                    size_bytes=shot.get("sizeBytes"),
                )))
            for output in result.get("outputs", []):
                prepared_outputs.append(output_record(
                    Path(output["path"]), task_id=key, kind=output["kind"],
                    material_id=output.get("materialId", ""), name=output.get("name"),
                    duration_seconds=output.get("durationSeconds"),
                    width=output.get("width"), height=output.get("height"),
                    size_bytes=output.get("sizeBytes"),
                ))
        with self.store.transaction() as store:
            task = store.get("tasks", key)
            if task["status"] == "cancelled":
                for field in ("_workerPid", "_input", "_startGate"):
                    task.pop(field, None)
                task["events"].append({"at": now(), "message": "处理进程已停止"})
                store.put("tasks", task)
                return
            if self.stopping.is_set():
                task.update(status="interrupted", stage="服务已停止", progress=None,
                            error="任务因服务退出中断，请核查后重试")
            elif result is None:
                # Full log remains local; expose only a bounded tail.
                with log_path.open("rb") as log:
                    log.seek(max(0, log_path.stat().st_size - 4000))
                    error = log.read().decode("utf-8", errors="replace").strip()
                task.update(status="failed", stage="处理失败", progress=None,
                            error=error or f"处理进程退出码 {self.process.returncode}")
            else:
                for update in result.get("materialUpdates", []):
                    material = store.get("materials", update["id"])
                    for field in ("scenes", "transcript", "status"):
                        if field in update:
                            material[field] = update[field]
                    if update.get("reportPath"):
                        material["_reportPath"] = update["reportPath"]
                    store.put("materials", material)
                known_paths = {m["_path"] for m in store.all("materials")}
                for path, record in prepared_materials:
                    if path not in known_paths:
                        store.put("materials", record)
                        known_paths.add(path)
                for record in prepared_outputs:
                    store.put("outputs", record)
                    task["outputIds"].append(record["id"])
                task.update(status=result["status"], stage=result.get("stage", "已完成"),
                            progress=100 if result["status"] == "completed" else None)
            task["events"].append({"at": now(), "message": task.get("error") or task["stage"]})
            for field in ("_workerPid", "_input", "_startGate"):
                task.pop(field, None)
            store.put("tasks", task)
