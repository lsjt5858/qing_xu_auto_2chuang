"""Loopback-only workbench API and a durable, account-bound publishing queue."""
from contextlib import asynccontextmanager
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import subprocess
import time
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .workbench_store import Store, identifier, now, public

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
MAX_UPLOAD = 512 * 1024 * 1024
ACTIVE_PUBLISH = {"queued", "uploading", "filling", "submitting"}
TERMINAL_PUBLISH = {"submitted", "unknown", "cancelled", "blocked", "awaiting_confirmation"}


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Settings(Model):
    sourceDirectory: str = ""
    outputDirectory: str = str(PROJECT_ROOT / "output")
    draftDirectory: str = ""
    transcriptionModel: Literal["tiny", "base", "small", "medium"] = "base"
    reuseAnalysis: bool = True
    preserveLongShots: bool = True


class ProcessingRequest(Model):
    materialIds: list[str] = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    steps: list[Literal["clean", "scenes", "transcribe", "semantic"]] = Field(min_length=1)
    threshold: float = Field(default=27, gt=0, le=100)


class MixConfig(Model):
    seed: str = Field(default="42", max_length=200)
    template: Literal["teaching", "showcase"] = "teaching"
    pool: Literal["all", "shots"] = "all"
    materialIds: list[str] | None = Field(default=None, min_length=1, max_length=200)


class MixRequest(Model):
    planId: str
    outputs: list[Literal["preview", "draft"]] = Field(min_length=1)


class PublishRequest(Model):
    outputId: str
    accountId: str
    title: str = Field(min_length=1, max_length=55)
    caption: str = Field(default="", max_length=1000)
    mode: Literal["prefill", "direct"] = "prefill"
    confirmed: Literal[True]


class DirectoryRequest(Model):
    path: str = Field(min_length=1, max_length=4096)


class CommandRequest(Model):
    command: Literal["cancel", "retry"]


class PairRequest(Model):
    code: str = Field(min_length=6, max_length=100)
    extensionId: str = Field(pattern=r"^[a-p]{32}$")
    name: str = Field(default="Chrome 发布插件", min_length=1, max_length=100)


class AccountIdentity(Model):
    uid: str = Field(min_length=1, max_length=100)
    nickname: str = Field(default="", max_length=100)
    unique_id: str = Field(default="", max_length=100)
    short_id: str = Field(default="", max_length=100)


class HeartbeatRequest(Model):
    account: AccountIdentity | None = None


class ClaimRequest(Model):
    accountUid: str = Field(min_length=1, max_length=100)


class LeaseRequest(Model):
    leaseToken: str


class EventRequest(LeaseRequest):
    status: Literal["uploading", "filling", "awaiting_confirmation", "submitting",
                    "submitted", "blocked", "unknown"]
    message: str = Field(default="", max_length=2000)
    evidence: str = Field(default="", max_length=4000)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def file_digest(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def report_number(value, field, *, positive=False):
    if isinstance(value, bool):
        raise HTTPException(422, f"report.json 的 {field} 必须是数字")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, f"report.json 的 {field} 必须是数字") from exc
    if not math.isfinite(number) or number < 0 or (positive and number == 0):
        requirement = "正数" if positive else "非负有限数字"
        raise HTTPException(422, f"report.json 的 {field} 必须是{requirement}")
    return number


def parse_report_content(report):
    if not isinstance(report, dict):
        raise HTTPException(422, "report.json 顶层必须是对象")
    scenes = report.get("scenes", [])
    transcript = report.get("transcript_segments", [])
    if not isinstance(scenes, list) or not isinstance(transcript, list):
        raise HTTPException(422, "report.json 的 scenes 和 transcript_segments 必须是数组")
    try:
        parsed_scenes = [
            {
                "startSeconds": report_number(
                    scene.get("start_time", 0), f"scenes[{index}].start_time"
                ),
                "durationSeconds": report_number(
                    scene.get("duration", 0),
                    f"scenes[{index}].duration",
                    positive=True,
                ),
            }
            for index, scene in enumerate(scenes)
            if isinstance(scene, dict)
        ]
        parsed_transcript = [
            {
                "startSeconds": report_number(
                    segment.get("start", 0), f"transcript_segments[{index}].start"
                ),
                "text": str(segment.get("text", "")),
            }
            for index, segment in enumerate(transcript)
            if isinstance(segment, dict)
        ]
    except AttributeError as exc:
        raise HTTPException(422, "report.json 的分镜或转录条目必须是对象") from exc
    if len(parsed_scenes) != len(scenes) or len(parsed_transcript) != len(transcript):
        raise HTTPException(422, "report.json 的分镜或转录条目必须是对象")
    return parsed_scenes, parsed_transcript


def report_video_path(report, report_path, root_videos):
    resolved = {path.resolve(): path for path in root_videos}
    has_declared_source = False
    for key in ("processed_video_path", "original_video_path"):
        value = report.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        has_declared_source = True
        candidate = Path(value).expanduser()
        candidates = [candidate.resolve()]
        if not candidate.is_absolute():
            candidates.insert(0, (report_path.parent / candidate).resolve())
        matches = [resolved[path] for path in candidates if path in resolved]
        if len(matches) == 1:
            return matches[0]
    video_name = report.get("video_name")
    if isinstance(video_name, str) and video_name.strip():
        has_declared_source = True
        stem = Path(video_name.strip()).stem
        matches = [path for path in root_videos if path.stem == stem]
        if len(matches) == 1:
            return matches[0]
    if not has_declared_source and len(root_videos) == 1:
        return root_videos[0]
    raise HTTPException(
        422,
        "report.json 无法唯一匹配目录中的视频；请只选择单条分析结果目录",
    )


def require(store, kind, key):
    value = store.get(kind, key)
    if value is None:
        raise HTTPException(404, "记录不存在")
    return value


def probe(path: Path):
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path),
        ], capture_output=True, text=True, check=True, timeout=30)
        metadata = json.loads(result.stdout)
        video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
        duration = float(video.get("duration") or metadata["format"].get("duration") or 0)
        if not (0 < duration < 24 * 3600) or not video.get("width") or not video.get("height"):
            raise ValueError("invalid duration or dimensions")
        return {"durationSeconds": duration, "width": video["width"], "height": video["height"]}
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, StopIteration) as exc:
        raise HTTPException(422, f"无法读取视频 {path.name}；请检查文件与 ffprobe") from exc


def checked_file(path):
    result = Path(path)
    if not result.is_file():
        raise HTTPException(409, "文件已移动或不存在，请重新导入")
    return result


def material_record(
    path: Path, *, name=None, kind="video", category="本地导入",
    duration_seconds=None, size_bytes=None,
):
    info = (
        {"durationSeconds": duration_seconds}
        if duration_seconds is not None
        else probe(path)
    )
    return {
        "id": identifier("mat"), "name": name or path.name, "kind": kind,
        "category": category, "tone": 0, "durationSeconds": info["durationSeconds"],
        "sizeBytes": size_bytes if size_bytes is not None else path.stat().st_size,
        "createdAt": now(), "status": "ready",
        "scenes": [], "transcript": [], "source": "local", "_path": str(path.resolve()),
    }


def output_record(
    path: Path, *, task_id="", kind="final", material_id="", name=None,
    duration_seconds=None, width=None, height=None, size_bytes=None,
    content_sha256=None, **_,
):
    if kind == "draft":
        info = {"durationSeconds": duration_seconds or 0}
    elif duration_seconds is not None and width is not None and height is not None:
        info = {"durationSeconds": duration_seconds, "width": width, "height": height}
    else:
        info = probe(path)
    record = {
        "id": identifier("out"), "taskId": task_id, "name": name or path.name, "kind": kind,
        "materialId": material_id, **info,
        "sizeBytes": size_bytes if size_bytes is not None
        else path.stat().st_size if path.is_file() else None,
        "title": path.stem[:55], "caption": "", "_path": str(path.resolve()),
    }
    if kind != "draft" and path.is_file():
        record["_contentSha256"] = content_sha256 or file_digest(path)
    return record


def remove_frozen_publish_file(job):
    value = job.get("_path")
    if not value:
        return
    path = Path(value)
    try:
        path.unlink(missing_ok=True)
        path.parent.rmdir()
    except OSError:
        # The receipt remains terminal even if an external process temporarily holds the file.
        pass


def expire_leases(store):
    cleanup = []
    for job in store.all("receipts"):
        if (job["status"] in ACTIVE_PUBLISH and job.get("_leaseToken")
                and job.get("_leaseExpires", 0) <= time.time()):
            job["status"] = "unknown" if job["status"] == "submitting" else "blocked"
            job["message"] = "插件租约已到期，请核查平台页面；不会自动重试"
            job["updatedAt"] = now()
            store.put("receipts", job)
            cleanup.append(job)
    return cleanup


def invalidate_switched_account_leases(store, extension_id, account_uid):
    cleanup = []
    for job in store.all("receipts"):
        if (job.get("_extensionId") == extension_id and job.get("_leaseToken")
                and job["status"] in ACTIVE_PUBLISH and job.get("_accountUid") != account_uid):
            job["status"] = "unknown" if job["status"] == "submitting" else "blocked"
            job["message"] = "插件登录账号已切换，请核查平台页面；不会自动重试"
            job["updatedAt"] = now()
            store.put("receipts", job)
            cleanup.append(job)
    return cleanup


def dependency_info():
    values = []
    for command in ("ffmpeg", "ffprobe"):
        found = shutil.which(command)
        values.append({"name": command, "available": bool(found), "detail": found or "未安装"})
    for module in ("scenedetect", "whisper"):
        found = importlib.util.find_spec(module) is not None
        values.append({"name": module, "available": found, "detail": "已安装" if found else "未安装"})
    from src.core.semantic_scene_grouper import SemanticSceneConfig
    try:
        config = SemanticSceneConfig.load()
        semantic = bool(os.environ.get(config.api_key_env, "").strip())
        detail = f"{config.provider} · {config.model}" if semantic else f"需要环境变量 {config.api_key_env}"
    except (OSError, ValueError, TypeError) as exc:
        semantic, detail = False, str(exc)
    values.append({"name": "语义分镜", "available": semantic, "detail": detail})
    return values


def create_app(data_dir: Path | None = None, *, start_worker=True):
    data_dir = Path(data_dir or PROJECT_ROOT / "data" / "workbench").resolve()
    sessions = {}
    session_cookie = "qingxu_session"

    @asynccontextmanager
    async def lifespan(app):
        import fcntl
        from .workbench_jobs import JobRunner

        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_file = (data_dir / "service.lock").open("a")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_file.close()
            raise RuntimeError("该数据目录已有工作台服务运行")
        store = Store(data_dir)
        app.state.store = store
        with store.transaction():
            if not store.get("settings", "settings"):
                store.put("settings", {"id": "settings", **Settings().model_dump()})
        runner = JobRunner(store)
        app.state.runner = runner
        runner.recover()
        if start_worker:
            runner.start()
        try:
            yield
        finally:
            runner.stop()
            store.close()
            lock_file.close()

    app = FastAPI(title="青序本地工作台", version="1.0.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)

    def local_origin(origin):
        if not origin:
            return True
        try:
            parsed = urlparse(origin)
            port = parsed.port
        except ValueError:
            return False
        return (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
                and port in {8766, 5173})

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.url.hostname not in {"127.0.0.1", "localhost"}:
            return JSONResponse({"detail": "仅允许本机访问"}, status_code=403)
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        origin = request.headers.get("origin", "")
        is_extension = request.url.path.startswith("/api/extension/")
        chrome_origin = re.fullmatch(r"chrome-extension://[a-p]{32}", origin)
        if not local_origin(origin) and not (is_extension and chrome_origin):
            return JSONResponse({"detail": "拒绝跨站请求"}, status_code=403)
        if request.method == "OPTIONS" and is_extension and chrome_origin:
            return Response(headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Extension-Id, X-Lease-Token",
                "Vary": "Origin",
            })
        if not is_extension and request.url.path != "/api/session":
            session = sessions.get(request.cookies.get(session_cookie))
            if not session or session["expires"] <= time.time():
                return JSONResponse({"detail": "本地会话已过期，请刷新页面"}, status_code=401)
            if request.method not in {"GET", "HEAD"} and not secrets.compare_digest(
                request.headers.get("x-csrf-token", ""), session["csrf"]
            ):
                return JSONResponse({"detail": "本地会话校验失败"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if is_extension and chrome_origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response

    @app.post("/api/session")
    def session(request: Request, response: Response):
        if request.headers.get("x-workbench") != "1":
            raise HTTPException(403, "缺少本地工作台会话请求标识")
        existing = request.cookies.get(session_cookie)
        current = sessions.get(existing)
        if current and current["expires"] > time.time():
            return {"csrfToken": current["csrf"]}
        for key in list(sessions):
            if sessions[key]["expires"] <= time.time():
                del sessions[key]
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        sessions[token] = {"csrf": csrf, "expires": time.time() + 12 * 3600}
        response.set_cookie(session_cookie, token, httponly=True, samesite="strict",
                            max_age=12 * 3600, path="/")
        return {"csrfToken": csrf}

    def snapshot():
        store = app.state.store
        with store.transaction():
            cleanup = expire_leases(store)
            result = {kind: public(store.all(kind)) for kind in ("materials", "tasks", "outputs", "receipts")}
            for material in result["materials"]:
                material["fileUrl"] = f"/api/materials/{material['id']}/file"
            for output in result["outputs"]:
                if output["kind"] != "draft":
                    output["fileUrl"] = f"/api/outputs/{output['id']}/file"
            extensions = store.all("extensions")
            accounts = store.all("accounts")
            for extension in extensions:
                extension["connected"] = time.time() - extension.get("_lastSeen", 0) < 35
            by_id = {item["id"]: item for item in extensions}
            for account in accounts:
                ext = by_id.get(account["extensionId"], {})
                account["connected"] = (ext.get("connected", False)
                                        and ext.get("_accountUid") == account["uid"])
            result["accounts"] = public(accounts)
            result["service"] = {"mode": "live", "version": "1.0.0",
                                 "dependencies": dependency_info(), "extensions": public(extensions)}
            result["settings"] = public(store.get("settings", "settings"))
            result["settings"].pop("id", None)
        for job in cleanup:
            remove_frozen_publish_file(job)
        return result

    @app.get("/api/snapshot")
    def load_snapshot():
        return snapshot()

    async def import_uploads(files, outputs=False):
        if not files or len(files) > 100:
            raise HTTPException(422, "每次导入 1–100 个视频")
        created = []
        records = []
        try:
            for upload in files:
                name = Path((upload.filename or "").replace("\\", "/")).name
                if Path(name).suffix.lower() not in VIDEO_EXTENSIONS:
                    raise HTTPException(422, f"不支持该文件类型：{name}")
                if outputs and Path(name).suffix.lower() != ".mp4":
                    raise HTTPException(422, "发布成片请导入 MP4")
                folder = data_dir / "uploads" / secrets.token_hex(16)
                folder.mkdir(parents=True, mode=0o700)
                created.append(folder)
                path = folder / name
                total = 0
                with path.open("xb") as destination:
                    while chunk := await upload.read(1024 * 1024):
                        total += len(chunk)
                        if total > MAX_UPLOAD:
                            raise HTTPException(413, "单个文件最大 512 MiB")
                        destination.write(chunk)
                records.append(output_record(path) if outputs else material_record(path))
            with app.state.store.transaction():
                for record in records:
                    app.state.store.put("outputs" if outputs else "materials", record)
        except BaseException:
            for folder in created:
                shutil.rmtree(folder, ignore_errors=True)
            raise
        finally:
            for upload in files:
                await upload.close()
        return snapshot()

    @app.post("/api/materials/import")
    async def import_materials(files: list[UploadFile] = File(...)):
        return await import_uploads(files)

    @app.post("/api/outputs/import")
    async def import_outputs(files: list[UploadFile] = File(...)):
        return await import_uploads(files, True)

    @app.post("/api/materials/directory")
    def import_directory(body: DirectoryRequest):
        root = Path(body.path).expanduser().resolve()
        if not root.is_dir():
            raise HTTPException(422, "目录不存在")
        root_videos = [
            path
            for path in sorted(root.iterdir())
            if path.is_file()
            and path.suffix.lower() in VIDEO_EXTENSIONS
            and not path.name.startswith(".")
        ]
        candidates = list(root_videos)
        report_path = root / "report.json"
        report = None
        report_target = None
        report_scenes = []
        report_transcript = []
        if report_path.is_file():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                raise HTTPException(422, "report.json 无法读取") from exc
            report_scenes, report_transcript = parse_report_content(report)
            if root_videos:
                report_target = report_video_path(report, report_path, root_videos)
            scenes_dir = root / "scenes"
            if scenes_dir.is_dir():
                candidates += [p for p in sorted(scenes_dir.iterdir())
                               if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS]
        if not candidates:
            raise HTTPException(422, "目录内没有视频；请选择素材目录或单条分析结果目录")
        if len(candidates) > 500:
            raise HTTPException(422, "目录视频超过 500 个，请分批导入")

        with app.state.store.transaction() as store:
            existing = {
                item["_path"]: item
                for item in store.all("materials")
            }
        prepared = {}
        for path in candidates:
            resolved = str(path.resolve())
            if resolved in existing:
                continue
            prepared[resolved] = material_record(
                path,
                kind="shot" if path.parent.name == "scenes" else "video",
                category=root.name,
            )

        with app.state.store.transaction() as store:
            current = {
                item["_path"]: item
                for item in store.all("materials")
            }
            for path in candidates:
                resolved = str(path.resolve())
                material = current.get(resolved)
                if material is None:
                    material = prepared[resolved]
                    store.put("materials", material)
                    current[resolved] = material
                if report and path == report_target:
                    material["status"] = "analyzed"
                    material["_reportPath"] = str(report_path)
                    material["scenes"] = [
                        {"id": f"{material['id']}_{index}", **scene}
                        for index, scene in enumerate(report_scenes)
                    ]
                    material["transcript"] = report_transcript
                    store.put("materials", material)
        return snapshot()

    @app.get("/api/materials/{key}/file")
    def material_file(key: str):
        item = require(app.state.store, "materials", key)
        return FileResponse(checked_file(item["_path"]), filename=item["name"], content_disposition_type="inline")

    @app.get("/api/outputs/{key}/file")
    def output_file(key: str):
        item = require(app.state.store, "outputs", key)
        if item["kind"] == "draft":
            raise HTTPException(409, "剪映草稿保存在设置的本地目录中")
        return FileResponse(checked_file(item["_path"]), media_type="video/mp4",
                            filename=item["name"], content_disposition_type="inline")

    @app.post("/api/outputs/{key}/confirm")
    def confirm_output(key: str):
        with app.state.store.transaction() as store:
            item = require(store, "outputs", key)
            if item["kind"] == "draft":
                raise HTTPException(409, "请先在剪映导出 MP4 并导入成片")
            checked_file(item["_path"])
            item["kind"] = "final"
            store.put("outputs", item)
        return snapshot()

    def new_task(**values):
        return {"id": identifier("task"), "status": "queued", "progress": None,
                "stage": "等待处理", "createdAt": now(), "outputIds": [],
                "events": [{"at": now(), "message": "已加入本地处理队列"}],
                "_settings": app.state.store.get("settings", "settings"), **values}

    @app.post("/api/tasks")
    def create_tasks(body: ProcessingRequest):
        with app.state.store.transaction() as store:
            for key in dict.fromkeys(body.materialIds):
                material = require(store, "materials", key)
                checked_file(material["_path"])
                store.put("tasks", new_task(
                    name=f"{body.name} · {material['name']}", kind="analysis", materialIds=[key],
                    steps=list(dict.fromkeys(body.steps)), threshold=body.threshold, requestedOutputs=[],
                ))
        return snapshot()

    @app.post("/api/tasks/{key}/command")
    def command_task(key: str, body: CommandRequest):
        if body.command == "cancel":
            app.state.runner.cancel(key)
        else:
            if app.state.runner.is_active(key):
                raise HTTPException(409, "处理进程正在退出，请稍后重试")
            with app.state.store.transaction() as store:
                task = require(store, "tasks", key)
                if task["status"] not in {"failed", "interrupted", "cancelled"}:
                    raise HTTPException(409, "只有失败、中断或取消的任务可以重试")
                task.update(status="queued", progress=None, stage="等待重试")
                task.pop("error", None)
                task["events"].append({"at": now(), "message": "用户要求重试"})
                store.put("tasks", task)
        return snapshot()

    @app.post("/api/mix/plans")
    def create_plan(body: MixConfig):
        with app.state.store.transaction() as store:
            if body.materialIds is not None:
                pool = [require(store, "materials", key) for key in body.materialIds]
            else:
                pool = [m for m in store.all("materials")
                        if body.pool == "all" or m["kind"] == "shot"]
                pool.sort(key=lambda m: m["id"])
                random.Random(body.seed).shuffle(pool)
                pool = pool[:(3 if body.template == "teaching" else 5)]
            if not pool:
                raise HTTPException(422, "没有可用的素材，请先导入视频或分析结果目录")
            clips = []
            for material in pool:
                checked_file(material["_path"])
                clips.append({"materialId": material["id"], "label": material["name"],
                              "durationSeconds": material["durationSeconds"]})
            plan = {"id": identifier("plan"), "config": body.model_dump(exclude_none=True),
                    "clips": clips, "durationSeconds": sum(c["durationSeconds"] for c in clips)}
            store.put("plans", plan)
        return plan

    @app.post("/api/mix/tasks")
    def create_mix(body: MixRequest):
        with app.state.store.transaction() as store:
            plan = require(store, "plans", body.planId)
            if "draft" in body.outputs and not store.get("settings", "settings")["draftDirectory"].strip():
                raise HTTPException(422, "请先在设置中填写剪映草稿目录")
            for clip in plan["clips"]:
                checked_file(require(store, "materials", clip["materialId"])["_path"])
            store.put("tasks", new_task(
                kind="mix", name=f"顺序混剪 · {plan['config']['seed']}",
                materialIds=list(dict.fromkeys(c["materialId"] for c in plan["clips"])),
                steps=[], plan=plan, requestedOutputs=list(dict.fromkeys(body.outputs)),
            ))
        return snapshot()

    @app.put("/api/settings")
    def save_settings(body: Settings):
        values = body.model_dump()
        for key in ("sourceDirectory", "outputDirectory", "draftDirectory"):
            if values[key]:
                path = Path(values[key]).expanduser()
                if not path.is_absolute():
                    raise HTTPException(422, "目录请填写绝对路径")
                if path.exists() and not path.is_dir():
                    raise HTTPException(422, f"{key} 不是目录")
                values[key] = str(path.resolve())
        if not values["outputDirectory"]:
            raise HTTPException(422, "请填写输出目录")
        with app.state.store.transaction() as store:
            store.put("settings", {"id": "settings", **values})
        return snapshot()

    @app.post("/api/pairing")
    def create_pairing():
        code = secrets.token_hex(4).upper()
        expires = time.time() + 300
        with app.state.store.transaction() as store:
            for old in store.all("pairing"):
                store.delete("pairing", old["id"])
            store.put("pairing", {"id": digest(code), "_expires": expires})
        from datetime import datetime, timezone
        return {"code": code, "expiresAt": datetime.fromtimestamp(expires, timezone.utc).isoformat()}

    @app.delete("/api/pairing/{extension_id}")
    def revoke_pairing(extension_id: str):
        cleanup = []
        with app.state.store.transaction() as store:
            require(store, "extensions", extension_id)
            store.delete("extensions", extension_id)
            for account in store.all("accounts"):
                if account["extensionId"] == extension_id:
                    store.delete("accounts", account["id"])
            for job in store.all("receipts"):
                if job.get("_extensionId") == extension_id and job["status"] in ACTIVE_PUBLISH:
                    job.update(status="unknown" if job["status"] == "submitting" else "blocked",
                               message="插件配对已撤销，请核查平台页面", updatedAt=now())
                    store.put("receipts", job)
                    cleanup.append(job)
        for job in cleanup:
            remove_frozen_publish_file(job)
        return snapshot()

    @app.post("/api/extension/pair")
    def pair_extension(body: PairRequest, request: Request):
        origin = request.headers.get("origin", "")
        if origin.startswith("chrome-extension://") and origin != f"chrome-extension://{body.extensionId}":
            raise HTTPException(403, "扩展标识不匹配")
        with app.state.store.transaction() as store:
            code_id = digest(body.code.upper())
            pairing = store.get("pairing", code_id)
            if not pairing or pairing["_expires"] <= time.time():
                raise HTTPException(403, "配对码无效或已过期")
            token = secrets.token_urlsafe(40)
            store.put("extensions", {
                "id": body.extensionId, "name": body.name, "lastSeenAt": now(),
                "_lastSeen": time.time(), "_tokenHash": digest(token),
            })
            store.delete("pairing", code_id)
        return {"token": token}

    def extension(request):
        store = app.state.store
        key = request.headers.get("x-extension-id", "")
        ext = store.get("extensions", key)
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        origin = request.headers.get("origin", "")
        if origin.startswith("chrome-extension://") and origin != f"chrome-extension://{key}":
            raise HTTPException(403, "扩展来源不匹配")
        if not ext or not secrets.compare_digest(ext["_tokenHash"], digest(token)):
            raise HTTPException(401, "插件未配对或配对已撤销")
        return ext

    @app.post("/api/extension/heartbeat")
    def extension_heartbeat(body: HeartbeatRequest, request: Request):
        with app.state.store.transaction() as store:
            ext = extension(request)
            account_uid = body.account.uid if body.account else None
            cleanup = invalidate_switched_account_leases(
                store, ext["id"], account_uid
            )
            ext.update(lastSeenAt=now(), _lastSeen=time.time(),
                       _accountUid=account_uid)
            store.put("extensions", ext)
            if body.account:
                identity = body.account
                store.put("accounts", {
                    "id": f"douyin_{identity.uid}_{ext['id']}", "platform": "douyin",
                    "uid": identity.uid, "name": identity.nickname or "未命名账号",
                    "handle": identity.unique_id or identity.short_id,
                    "extensionId": ext["id"], "connected": True, "lastSeenAt": now(),
                })
        for job in cleanup:
            remove_frozen_publish_file(job)
        return {"ok": True}

    @app.post("/api/publish")
    def publish(body: PublishRequest):
        with app.state.store.transaction() as store:
            cleanup = expire_leases(store)
            output = require(store, "outputs", body.outputId)
            if output["kind"] == "draft":
                raise HTTPException(422, "草稿不能直接发布，请导出并导入 MP4")
            path = checked_file(output["_path"])
            source_size = path.stat().st_size
            if path.suffix.lower() != ".mp4" or source_size > MAX_UPLOAD:
                raise HTTPException(422, "请使用不超过 512 MiB 的 MP4")
            content_sha256 = output.get("_contentSha256")
            if not (
                isinstance(content_sha256, str)
                and re.fullmatch(r"[0-9a-f]{64}", content_sha256)
            ):
                raise HTTPException(
                    409, "该成片缺少内容校验信息，请重新导入后再发布"
                )
            account = require(store, "accounts", body.accountId)
            ext = store.get("extensions", account["extensionId"])
            if not ext:
                raise HTTPException(409, "目标账号的插件配对已撤销")
            account_snapshot = {
                "id": account["id"], "platform": account["platform"],
                "uid": account["uid"], "name": account["name"],
                "extensionId": account["extensionId"],
            }
            source_stat = path.stat()
            output_snapshot = {
                "path": str(path.resolve()),
                "name": output["name"],
                "contentSha256": content_sha256,
                "stat": (
                    source_stat.st_dev,
                    source_stat.st_ino,
                    source_stat.st_size,
                    source_stat.st_mtime_ns,
                    source_stat.st_ctime_ns,
                ),
            }
        for job in cleanup:
            remove_frozen_publish_file(job)

        # Copy and hash outside the global Store lock. A second transaction below
        # revalidates the referenced records before the immutable job is committed.
        job_id = identifier("pub")
        frozen_dir = data_dir / "publish" / job_id
        frozen_dir.mkdir(parents=True, mode=0o700)
        frozen = frozen_dir / "video.mp4"
        try:
            current_stat = path.stat()
            current_identity = (
                current_stat.st_dev,
                current_stat.st_ino,
                current_stat.st_size,
                current_stat.st_mtime_ns,
                current_stat.st_ctime_ns,
            )
            if current_identity != output_snapshot["stat"]:
                raise HTTPException(409, "发布成片在冻结前发生变化，请重新提交")
            expected_sha256 = output_snapshot["contentSha256"]
            shutil.copyfile(path, frozen)
            if path.stat().st_size != source_size or frozen.stat().st_size != source_size:
                raise HTTPException(409, "发布成片在冻结期间发生变化，请重新提交")
            content_sha256 = file_digest(frozen)
            if (
                content_sha256 != expected_sha256
                or file_digest(path) != expected_sha256
            ):
                raise HTTPException(409, "发布成片在冻结期间发生变化，请重新提交")
            fingerprint_values = body.model_dump(
                exclude={"confirmed", "accountId", "outputId"}
            )
            fingerprint_values["account"] = {
                "platform": account_snapshot["platform"],
                "uid": account_snapshot["uid"],
            }
            fingerprint_values["contentSha256"] = content_sha256
            fingerprint = digest(json.dumps(fingerprint_values, sort_keys=True))
            with app.state.store.transaction() as store:
                cleanup = expire_leases(store)
                current_output = require(store, "outputs", body.outputId)
                current_account = require(store, "accounts", body.accountId)
                if (str(Path(current_output["_path"]).resolve()) != output_snapshot["path"]
                        or current_account["uid"] != account_snapshot["uid"]
                        or current_account["extensionId"] != account_snapshot["extensionId"]
                        or not store.get("extensions", account_snapshot["extensionId"])):
                    raise HTTPException(409, "发布目标在冻结期间发生变化，请重新提交")
                if any(j.get("_fingerprint") == fingerprint and j["status"] != "cancelled"
                       for j in store.all("receipts")):
                    raise HTTPException(
                        409, "相同成片、账号和文案已有任务，请核查发布记录，避免重复发布"
                    )
                store.put("receipts", {
                    "id": job_id, **body.model_dump(exclude={"confirmed"}),
                    "createdAt": now(), "updatedAt": now(), "status": "queued", "simulated": False,
                    "accountName": account_snapshot["name"], "message": "等待插件领取",
                    "_extensionId": account_snapshot["extensionId"], "_accountUid": account_snapshot["uid"],
                    "_path": str(frozen), "_fileName": output_snapshot["name"], "_sizeBytes": frozen.stat().st_size,
                    "_fingerprint": fingerprint, "_contentSha256": content_sha256,
                })
            for job in cleanup:
                remove_frozen_publish_file(job)
        except BaseException:
            shutil.rmtree(frozen_dir, ignore_errors=True)
            raise
        return snapshot()

    @app.post("/api/publish/{key}/cancel")
    def cancel_publish(key: str):
        with app.state.store.transaction() as store:
            job = require(store, "receipts", key)
            if job["status"] not in {"queued", "blocked", "awaiting_confirmation"} or (
                job["status"] == "queued" and job.get("_leaseToken")
            ):
                raise HTTPException(409, "插件正在执行或已经提交，不能取消；请检查平台页面")
            job.update(status="cancelled", updatedAt=now(), message="本地队列已取消；平台上已有内容请手动检查")
            store.put("receipts", job)
        remove_frozen_publish_file(job)
        return snapshot()

    @app.post("/api/extension/claim")
    def claim(body: ClaimRequest, request: Request):
        claimed = None
        with app.state.store.transaction() as store:
            ext = extension(request)
            cleanup = expire_leases(store)
            jobs = store.all("receipts")
            if any(j.get("_extensionId") == ext["id"] and j.get("_leaseToken")
                   and j["status"] in ACTIVE_PUBLISH for j in jobs):
                jobs = []
            if ext.get("_accountUid") == body.accountUid:
                for job in reversed(jobs):
                    if (job["status"] == "queued" and job["_extensionId"] == ext["id"]
                            and job["_accountUid"] == body.accountUid and not job.get("_leaseToken")):
                        job["_leaseToken"] = secrets.token_urlsafe(32)
                        job["_leaseExpires"] = time.time() + 45
                        store.put("receipts", job)
                        claimed = {
                            key: job[key]
                            for key in (
                                "id", "outputId", "accountId",
                                "title", "caption", "mode",
                            )
                        } | {
                            "accountUid": job["_accountUid"],
                            "fileName": job["_fileName"],
                            "sizeBytes": job["_sizeBytes"],
                            "leaseToken": job["_leaseToken"],
                        }
                        break
        for job in cleanup:
            remove_frozen_publish_file(job)
        return {"job": claimed}

    def leased_job(store, key, token, ext):
        job = require(store, "receipts", key)
        if (job["_extensionId"] != ext["id"] or not token
                or not secrets.compare_digest(token, job.get("_leaseToken", ""))):
            raise HTTPException(403, "任务租约不匹配")
        if job["status"] not in ACTIVE_PUBLISH or job.get("_leaseExpires", 0) <= time.time():
            raise HTTPException(409, "任务租约已失效；请核查平台页面，不要重复提交")
        if ext.get("_accountUid") != job.get("_accountUid"):
            raise HTTPException(409, "插件登录账号已变化；请核查平台页面，不要继续当前任务")
        return job

    @app.post("/api/extension/jobs/{key}/heartbeat")
    def job_heartbeat(key: str, body: LeaseRequest, request: Request):
        with app.state.store.transaction() as store:
            job = leased_job(store, key, body.leaseToken, extension(request))
            job["_leaseExpires"] = time.time() + 45
            store.put("receipts", job)
        return {"ok": True}

    @app.get("/api/extension/jobs/{key}/file")
    def job_file(key: str, request: Request):
        with app.state.store.transaction() as store:
            job = leased_job(store, key, request.headers.get("x-lease-token", ""), extension(request))
            path = checked_file(job["_path"])
        return FileResponse(path, media_type="video/mp4", filename=job["_fileName"])

    @app.post("/api/extension/jobs/{key}/event")
    def job_event(key: str, body: EventRequest, request: Request):
        cleanup = None
        with app.state.store.transaction() as store:
            job = leased_job(store, key, body.leaseToken, extension(request))
            transitions = {
                "queued": {"uploading", "blocked"},
                "uploading": {"filling", "blocked"},
                "filling": {"awaiting_confirmation" if job["mode"] == "prefill" else "submitting", "blocked"},
                "submitting": {"submitted", "unknown"},
            }
            if body.status not in transitions[job["status"]]:
                raise HTTPException(409, "不允许该发布状态转换")
            if body.status == "submitted" and not body.evidence.strip():
                raise HTTPException(422, "确认提交需要平台成功证据")
            job.update(status=body.status, message=body.message, evidence=body.evidence, updatedAt=now())
            job["_leaseExpires"] = time.time() + 45
            store.put("receipts", job)
            if body.status in TERMINAL_PUBLISH:
                cleanup = job
        if cleanup:
            remove_frozen_publish_file(cleanup)
        return {"ok": True}

    dist = PROJECT_ROOT / "apps" / "workbench" / "dist"

    @app.get("/{path:path}")
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "接口不存在")
        candidate = (dist / path).resolve()
        if not candidate.is_relative_to(dist.resolve()):
            raise HTTPException(404)
        if path and candidate.is_file():
            return FileResponse(candidate)
        if (dist / "index.html").is_file():
            return FileResponse(dist / "index.html")
        return JSONResponse({"detail": "请先构建工作台：cd apps/workbench && npm ci && npm run build"},
                            status_code=503)

    return app
