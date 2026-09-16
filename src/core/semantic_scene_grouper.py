"""AI 语义分镜：将连续原始切镜聚合为剧情语义段。"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "semantic_scenes.json"


@dataclass(frozen=True)
class SemanticSceneConfig:
    provider: str
    base_url: str
    model: str
    api_key_env: str
    timeout_seconds: int = 120
    max_retries: int = 2
    frames_per_scene: int = 3
    max_tokens: int = 1600
    temperature: float = 0.1

    @classmethod
    def _select_provider(cls, data: dict[str, Any]) -> dict[str, Any]:
        providers = data.get("providers")
        if providers is None:
            return data
        if not isinstance(providers, dict) or not providers:
            raise ValueError("语义分镜配置中的 providers 必须是非空对象。")

        provider_env = str(
            data.get("provider_env", "SEMANTIC_SCENE_PROVIDER")
        ).strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", provider_env):
            raise ValueError("provider_env 必须填写合法的环境变量名。")

        selected_name = os.getenv(provider_env, "").strip()
        if not selected_name:
            for name, provider_data in providers.items():
                if not isinstance(provider_data, dict):
                    continue
                api_key_env = str(provider_data.get("api_key_env", "")).strip()
                if api_key_env and os.getenv(api_key_env, "").strip():
                    selected_name = name
                    break
        if not selected_name:
            selected_name = str(data.get("default_provider", "")).strip()
        if selected_name not in providers:
            available = ", ".join(providers)
            raise ValueError(
                f"未知的语义分镜厂商 '{selected_name}'，可选值: {available}"
            )

        provider_data = providers[selected_name]
        if not isinstance(provider_data, dict):
            raise ValueError(f"厂商 '{selected_name}' 的配置必须是对象。")
        selected = {
            key: value
            for key, value in data.items()
            if key in cls.__dataclass_fields__
        }
        selected.update(provider_data)
        selected.setdefault("provider", selected_name)

        model_env = str(selected.pop("model_env", "")).strip()
        if model_env:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", model_env):
                raise ValueError("model_env 必须填写合法的环境变量名。")
            model = os.getenv(model_env, "").strip()
            if not model:
                raise ValueError(
                    f"厂商 '{selected_name}' 需要先设置模型环境变量 {model_env}。"
                )
            selected["model"] = model
        return selected

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> "SemanticSceneConfig":
        config_path = Path(path) if path else DEFAULT_CONFIG_PATH
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"找不到语义分镜配置文件: {config_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"语义分镜配置不是合法 JSON: {config_path}: {exc}") from exc

        data = cls._select_provider(data)
        required = ("provider", "base_url", "model", "api_key_env")
        missing = [key for key in required if not str(data.get(key, "")).strip()]
        if missing:
            raise ValueError(f"语义分镜配置缺少字段: {', '.join(missing)}")
        api_key_env = str(data["api_key_env"]).strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", api_key_env):
            raise ValueError(
                "api_key_env 必须填写环境变量名（例如 ZAI_API_KEY），不能填写真实 API Key。"
            )
        return cls(**{key: data[key] for key in cls.__dataclass_fields__ if key in data})

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


class SemanticSceneGrouper:
    """使用视觉模型把相邻切镜按剧情连续性聚合，并导出聚合视频。"""

    def __init__(self, config: SemanticSceneConfig):
        self.config = config

    @classmethod
    def from_config(cls, path: str | os.PathLike[str] | None = None) -> "SemanticSceneGrouper":
        return cls(SemanticSceneConfig.load(path))

    def group_and_export(
        self,
        video_path: str,
        scenes_info: list[dict[str, Any]],
        transcript_segments: list[dict[str, Any]] | None,
        output_dir: str,
    ) -> list[dict[str, Any]]:
        if not scenes_info:
            return []

        api_key = os.getenv(self.config.api_key_env, "").strip()
        if not api_key:
            raise RuntimeError(
                f"启用 AI 语义分镜需要先设置环境变量 {self.config.api_key_env}；"
                "API Key 不应写入配置文件。"
            )

        output_root = Path(output_dir)
        contact_sheet_path = output_root / "semantic_scene_contact_sheet.jpg"
        scene_payload = self._build_scene_payload(
            video_path,
            scenes_info,
            transcript_segments or [],
            contact_sheet_path,
        )
        raw_groups = self._request_groups(api_key, scene_payload, contact_sheet_path)
        groups = self.normalize_groups(raw_groups, scenes_info)
        exported = self._export_groups(video_path, groups, output_root / "semantic_scenes")

        metadata_path = output_root / "semantic_scenes.json"
        metadata_path.write_text(
            json.dumps(exported, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return exported

    def _build_scene_payload(
        self,
        video_path: str,
        scenes_info: list[dict[str, Any]],
        transcript_segments: list[dict[str, Any]],
        contact_sheet_path: Path,
    ) -> list[dict[str, Any]]:
        frames = self._extract_representative_frames(video_path, scenes_info)
        frames_root = frames[0].parent if frames else None
        try:
            self._make_contact_sheet(frames, contact_sheet_path)
        finally:
            if frames_root:
                shutil.rmtree(frames_root, ignore_errors=True)

        payload = []
        for scene in scenes_info:
            start = float(scene["start_time"])
            end = float(scene["end_time"])
            text = " ".join(
                str(segment.get("text", "")).strip()
                for segment in transcript_segments
                if float(segment.get("end", 0.0)) > start
                and float(segment.get("start", 0.0)) < end
                and str(segment.get("text", "")).strip()
            )
            payload.append(
                {
                    "scene_number": int(scene["scene_number"]),
                    "start_time": start,
                    "end_time": end,
                    "transcript": text,
                }
            )
        return payload

    def _extract_representative_frames(
        self,
        video_path: str,
        scenes_info: list[dict[str, Any]],
    ) -> list[Path]:
        temp_dir = Path(tempfile.mkdtemp(prefix="semantic_scene_frames_"))
        frame_paths: list[Path] = []
        frames_per_scene = max(1, int(self.config.frames_per_scene))
        for scene in scenes_info:
            number = int(scene["scene_number"])
            start = float(scene["start_time"])
            end = float(scene["end_time"])
            duration = max(0.001, end - start)
            for index in range(frames_per_scene):
                ratio = (index + 1) / (frames_per_scene + 1)
                timestamp = start + duration * ratio
                frame_path = temp_dir / f"scene_{number:04d}_{index + 1}.jpg"
                result = subprocess.run(
                    [
                        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-ss", f"{timestamp:.6f}", "-i", video_path,
                        "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "3",
                        str(frame_path),
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0 or not frame_path.is_file():
                    raise RuntimeError(
                        f"提取第 {number} 个切镜代表帧失败: "
                        f"{(result.stderr or result.stdout).strip()[:300]}"
                    )
                frame_paths.append(frame_path)
        return frame_paths

    def _make_contact_sheet(self, frame_paths: list[Path], output_path: Path) -> None:
        if not frame_paths:
            raise ValueError("没有可用于语义分镜的代表帧。")
        columns = max(1, int(self.config.frames_per_scene))
        inputs: list[str] = []
        for frame_path in frame_paths:
            inputs.extend(["-i", str(frame_path)])
        filter_graph = (
            f"xstack=inputs={len(frame_paths)}:grid={columns}x"
            f"{(len(frame_paths) + columns - 1) // columns}:fill=black"
        )
        result = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                *inputs, "-filter_complex", filter_graph, "-frames:v", "1",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not output_path.is_file():
            raise RuntimeError(
                "生成切镜联系表失败: "
                f"{(result.stderr or result.stdout).strip()[:300]}"
            )

    def _request_groups(
        self,
        api_key: str,
        scenes: list[dict[str, Any]],
        contact_sheet_path: Path,
    ) -> list[dict[str, Any]]:
        image_data = base64.b64encode(contact_sheet_path.read_bytes()).decode("ascii")
        prompt = (
            "你是专业影视剪辑师。图片是原视频各个硬切镜头的联系表：每一行对应一个原始切镜，"
            "每行按时间顺序有若干代表帧；行号从1开始，与下面 scene_number 一致。\n"
            "请把相邻原始切镜聚合成剧情语义分镜。即使机位、景别、说话人正反打发生变化，"
            "只要人物、地点、事件、动作目标或表达目的仍连续，就必须归入同一分镜；"
            "只有核心事件、人物关系、地点时间或表达目的明显改变时才开始新分镜。"
            "分组必须覆盖全部 scene_number，保持顺序，连续且不重叠，禁止跳号。\n"
            "只返回 JSON，不要 Markdown："
            '{"groups":[{"start_scene":1,"end_scene":3,"reason":"...","summary":"..."}]}\n'
            f"原始切镜与台词：{json.dumps(scenes, ensure_ascii=False)}"
        )
        body = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                        },
                    ],
                }
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        encoded = json.dumps(body).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                http_request = request.Request(
                    self.config.endpoint,
                    data=encoded,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with request.urlopen(http_request, timeout=self.config.timeout_seconds) as response:
                    response_data = json.loads(response.read().decode("utf-8"))
                content = response_data["choices"][0]["message"]["content"]
                parsed = self._parse_json_content(content)
                groups = parsed.get("groups")
                if not isinstance(groups, list):
                    raise ValueError("AI 响应缺少 groups 数组。")
                return groups
            except (error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    break
                time.sleep(min(2 ** attempt, 4))
        raise RuntimeError(f"AI 语义分镜请求失败: {last_error}")

    @staticmethod
    def _parse_json_content(content: Any) -> dict[str, Any]:
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", "")) if isinstance(item, dict) else str(item)
                for item in content
            )
        text = str(content).strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1)
        else:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end >= start:
                text = text[start:end + 1]
        return json.loads(text)

    @staticmethod
    def normalize_groups(
        raw_groups: list[dict[str, Any]],
        scenes_info: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not scenes_info:
            return []
        scene_by_number = {
            int(scene["scene_number"]): scene for scene in scenes_info
        }
        expected = sorted(scene_by_number)
        if expected != list(range(1, len(expected) + 1)):
            raise ValueError("原始切镜编号必须从 1 开始连续递增。")

        normalized = []
        next_scene = 1
        for index, group in enumerate(raw_groups, start=1):
            start_scene = int(group["start_scene"])
            end_scene = int(group["end_scene"])
            if start_scene != next_scene or end_scene < start_scene or end_scene > len(expected):
                raise ValueError("AI 返回的语义分镜存在漏段、重叠、乱序或越界。")
            first = scene_by_number[start_scene]
            last = scene_by_number[end_scene]
            normalized.append(
                {
                    "semantic_scene_number": index,
                    "start_scene": start_scene,
                    "end_scene": end_scene,
                    "source_scenes": list(range(start_scene, end_scene + 1)),
                    "start_time": float(first["start_time"]),
                    "end_time": float(last["end_time"]),
                    "duration": float(last["end_time"]) - float(first["start_time"]),
                    "reason": str(group.get("reason", "")).strip(),
                    "summary": str(group.get("summary", "")).strip(),
                }
            )
            next_scene = end_scene + 1
        if next_scene != len(expected) + 1:
            raise ValueError("AI 返回的语义分镜没有覆盖全部原始切镜。")
        return normalized

    @staticmethod
    def _export_groups(
        video_path: str,
        groups: list[dict[str, Any]],
        output_dir: Path,
    ) -> list[dict[str, Any]]:
        output_dir.mkdir(parents=True, exist_ok=True)
        exported = []
        for group in groups:
            output_path = output_dir / f"SemanticScene-{group['semantic_scene_number']:03d}.mp4"
            result = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{group['start_time']:.6f}",
                    "-to", f"{group['end_time']:.6f}",
                    "-i", video_path,
                    "-map", "0:v:0", "-map", "0:a?",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-c:a", "aac", "-movflags", "+faststart", str(output_path),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0 or not output_path.is_file():
                raise RuntimeError(
                    f"导出语义分镜 {group['semantic_scene_number']} 失败: "
                    f"{(result.stderr or result.stdout).strip()[:300]}"
                )
            item = dict(group)
            item["output_path"] = str(output_path)
            exported.append(item)
        return exported
