"""Compose ordered directories into one MP4 and an optional editable draft."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from dataclasses import asdict
from datetime import datetime
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import sys
from tempfile import TemporaryDirectory
import uuid

from src.composition.directory_composer import DirectoryStage, compose_directories
from src.exporters.jianying import DEFAULT_TEMPLATE_DIR, export_to_jianying_draft, resolve_draft_root
from src.exporters.video import render_timeline
from src.models import AnalysisArtifacts, probe_media


def _count(value: str) -> int | None:
    if value == "all":
        return None
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("数量必须为正整数或 all") from exc
    if count <= 0:
        raise argparse.ArgumentTypeError("数量必须为正整数或 all")
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.sh compose",
        description="按目录顺序组装完整镜头，生成 MP4；默认仅预览计划，--execute 才写入。",
    )
    for role, label in [("head", "头"), ("body", "身"), ("tail", "尾")]:
        parser.add_argument(f"--{role}-dir", help=f"视频{label}素材目录（递归扫描视频和照片）")
        parser.add_argument(f"--{role}-count", type=_count, default=argparse.SUPPRESS,
                            help="抽取数量，默认 1；all 表示全部")
    parser.add_argument("--part", nargs=2, action="append", metavar=("DIR", "COUNT"),
                        help="按参数顺序添加任意段，可重复；不可与 head/body/tail 参数混用")
    parser.add_argument("--selection", choices=["random", "ordered"], default="random",
                        help="random 随机选片；ordered 按文件路径排序选片")
    parser.add_argument("--seed", type=int, help="可复现选片的随机种子；未指定时自动生成并打印")
    parser.add_argument("--clip-start", type=float, default=0, help="显式视频截取起点，单位秒（默认 0）")
    parser.add_argument("--clip-duration", type=float, help="显式视频最长截取秒数（默认使用剩余全长）")
    parser.add_argument("--photo-duration", type=float, default=2, help="照片展示秒数（默认 2）")
    parser.add_argument("--width", type=int, default=1920, help="画布宽，正偶数（默认 1920）")
    parser.add_argument("--height", type=int, default=1080, help="画布高，正偶数（默认 1080）")
    parser.add_argument("--fps", type=int, default=30, help="输出帧率，正整数（默认 30）")
    parser.add_argument("--bgm", help="本地配乐，自动循环至成片结束")
    parser.add_argument("--bgm-volume", type=float, default=0.35, help="配乐音量 0–1（默认 0.35）")
    parser.add_argument("--mute-source", action="store_true", help="关闭素材原声")
    parser.add_argument("-o", "--output", help="输出 MP4 路径，默认 output/compose_<时间>_<唯一标识>.mp4")
    parser.add_argument("--export-jianying", action="store_true", help="同时导出 basic 样式剪映草稿")
    parser.add_argument("--draft-root", help="剪映草稿箱根目录")
    parser.add_argument("--draft-name", help="草稿名称（已有同名草稿时另建目录）")
    parser.add_argument("--template-dir", default=str(DEFAULT_TEMPLATE_DIR), help="剪映草稿模板目录")
    parser.add_argument("--execute", action="store_true", help="实际生成 MP4、JSON 清单和可选草稿")
    return parser


def _stages(args) -> list[DirectoryStage]:
    named = any(getattr(args, f"{role}_dir") is not None or hasattr(args, f"{role}_count")
                for role in ("head", "body", "tail"))
    if args.part:
        if named:
            raise ValueError("--part 不可与 head/body/tail 目录或数量参数混用")
        if any(not path.strip() for path, _ in args.part):
            raise ValueError("--part 目录不可为空")
        return [DirectoryStage(Path(path), _count(count), f"part-{i}")
                for i, (path, count) in enumerate(args.part, 1)]
    stages = []
    for role in ("head", "body", "tail"):
        directory = getattr(args, f"{role}_dir")
        if directory is not None and not directory.strip():
            raise ValueError(f"--{role}-dir 不可为空")
        if directory:
            stages.append(DirectoryStage(Path(directory), getattr(args, f"{role}_count", 1), role))
        elif hasattr(args, f"{role}_count"):
            raise ValueError(f"--{role}-count 需要 --{role}-dir")
    return stages


def _clip_records(clips):
    return [{**asdict(clip), "source_path": str(clip.source_path)} for clip in clips]


def _validate_paths_and_options(args, output_path: Path, manifest_path: Path):
    if args.width <= 0 or args.height <= 0 or args.width % 2 or args.height % 2 or args.fps <= 0:
        raise ValueError("width/height 必须为正偶数，fps 必须为正整数")
    if not math.isfinite(args.bgm_volume) or not 0 <= args.bgm_volume <= 1:
        raise ValueError("bgm-volume 必须在 0–1 之间")
    if output_path.suffix.lower() != ".mp4":
        raise ValueError("输出路径必须以 .mp4 结尾")
    for path in (output_path, manifest_path):
        if path.exists() or path.is_symlink():
            raise ValueError(f"拒绝覆盖已有文件: {path}")
    if args.bgm:
        bgm = Path(args.bgm).expanduser().resolve()
        if not bgm.is_file():
            raise ValueError(f"找不到配乐: {bgm}")
        try:
            metadata = probe_media(bgm)
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"无法读取配乐: {bgm}") from exc
        if not metadata.has_audio or metadata.duration_us <= 0:
            raise ValueError(f"配乐没有有效音轨: {bgm}")
    if args.export_jianying:
        template = Path(args.template_dir).expanduser()
        if not (template / "draft_info.json").is_file():
            raise ValueError(f"模板缺少 draft_info.json: {template}")
        if args.draft_root:
            root = Path(args.draft_root).expanduser()
            if root.exists() and not root.is_dir():
                raise ValueError(f"draft-root 不是目录: {root}")


def _execute(args, clips, plan, output_path, manifest_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Keep intermediate material alive until the existing draft exporter has copied it.
    with TemporaryDirectory(prefix=".compose-", dir=output_path.parent) as temp:
        work = Path(temp)
        rendered = render_timeline(
            clips, work / "result.mp4", work_dir=work,
            width=args.width, height=args.height, fps=args.fps,
            bgm_path=Path(args.bgm).expanduser().resolve() if args.bgm else None,
            bgm_volume=args.bgm_volume, mute_source=args.mute_source,
        )
        duration = sum(clip.timeline_duration_us for clip in rendered.clips)
        if args.export_jianying:
            if args.draft_root:
                Path(args.draft_root).expanduser().mkdir(parents=True, exist_ok=True)
            with redirect_stdout(sys.stderr):
                root = resolve_draft_root(args.draft_root)
                artifacts = AnalysisArtifacts(
                    output_dir=work, video_name=output_path.stem,
                    original_video_path=rendered.video_path, processed_video_path=rendered.video_path,
                    report_path=None, audio_path=rendered.audio_path,
                    audio_metadata=probe_media(rendered.audio_path), scenes=(), transcript_segments=(),
                )
                draft = export_to_jianying_draft(
                    artifacts, timeline_clips=list(rendered.clips), draft_root=root,
                    template_dir=args.template_dir, draft_name=args.draft_name or output_path.stem,
                    style_template="basic", fps=args.fps,
                )
            plan["draft_path"] = str(draft)
        plan["executed"] = True
        plan["rendered_duration_us"] = duration
        # Original paths stay useful after temporary normalized media is cleaned up.
        plan["rendered_clips"] = [
            {**source, "timeline_start_us": normalized.timeline_start_us,
             "timeline_duration_us": normalized.timeline_duration_us}
            for source, normalized in zip(plan["clips"], rendered.clips)
        ]
        manifest = work / "result.json"
        manifest.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        # Atomic no-replace publication on the same filesystem, including racing writers.
        os.link(rendered.video_path, output_path)
        try:
            os.link(manifest, manifest_path)
        except OSError:
            output_path.unlink()
            raise


def main(argv=None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    try:
        stages = _stages(args)
        seed = args.seed if args.seed is not None else secrets.randbits(63)
        output_path = Path(args.output or (
            f"output/compose_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:10]}.mp4"
        )).expanduser().absolute()
        manifest_path = output_path.with_suffix(".json")
        _validate_paths_and_options(args, output_path, manifest_path)
        clips = compose_directories(
            stages, seed=seed, selection=args.selection, photo_duration=args.photo_duration,
            clip_start=args.clip_start, clip_duration=args.clip_duration,
        )
        plan = {
            "seed": seed, "executed": False, "output_path": str(output_path),
            "manifest_path": str(manifest_path), "draft_path": None,
            "duration_us": sum(c.timeline_duration_us for c in clips),
            "stages": [{**asdict(s), "directory": str(s.directory.expanduser().resolve())} for s in stages],
            "options": vars(args), "clips": _clip_records(clips),
        }
    except (ValueError, argparse.ArgumentTypeError) as exc:
        print(f"参数错误: {exc}", file=sys.stderr)
        return 2
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"素材检查失败: {exc}", file=sys.stderr)
        return 1
    if args.execute:
        try:
            _execute(args, clips, plan, output_path, manifest_path)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            print(f"合成失败: {exc}", file=sys.stderr)
            return 1
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0
