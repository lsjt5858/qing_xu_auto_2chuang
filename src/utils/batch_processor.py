"""
批量处理器 - 处理多个视频
"""
import json
import os
import re
import time
from pathlib import Path

from src.composition import CompositionSettings, HeadTailComposer, ShotPoolIndex
from src.exporters import export_to_jianying_draft
from src.models import load_analysis_artifacts

from ..core.video_analyzer import VideoAnalyzer


class BatchProcessor:
    """批量视频处理器"""

    TARGET_VIDEO_FILENAME = "video_no_subtitles.mp4"
    
    def __init__(self, output_dir="output"):
        """
        初始化批量处理器
        
        Args:
            output_dir: 输出根目录
        """
        self.output_dir = output_dir
        self.success_count = 0
        self.failed_videos = []

    def _find_existing_target_video(self, video_path):
        output_root = Path(self.output_dir)
        if not output_root.is_dir():
            return None

        video_name = Path(video_path).stem
        output_name_pattern = re.compile(
            rf"{re.escape(video_name)}_\d{{8}}_\d{{6}}"
        )

        for candidate_dir in sorted(output_root.iterdir(), reverse=True):
            if (
                candidate_dir.is_dir()
                and output_name_pattern.fullmatch(candidate_dir.name)
            ):
                target_video = candidate_dir / self.TARGET_VIDEO_FILENAME
                if target_video.is_file():
                    return target_video

        return None

    def _find_existing_analysis(self, video_path):
        """查找同名视频可复用的完整分析报告和可读视频。"""
        output_root = Path(self.output_dir)
        if not output_root.is_dir():
            return None

        video_name = Path(video_path).stem
        output_name_pattern = re.compile(
            rf"{re.escape(video_name)}_\d{{8}}_\d{{6}}"
        )
        for candidate_dir in sorted(output_root.iterdir(), reverse=True):
            if not (
                candidate_dir.is_dir()
                and output_name_pattern.fullmatch(candidate_dir.name)
            ):
                continue
            report_path = candidate_dir / "report.json"
            if not report_path.is_file():
                continue
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not report.get("scenes"):
                continue
            candidates = [candidate_dir / self.TARGET_VIDEO_FILENAME]
            for key in ("processed_video_path", "original_video_path"):
                value = report.get(key)
                if value:
                    candidates.append(Path(value).expanduser())
            candidates.append(Path(video_path))
            for candidate_video in candidates:
                if candidate_video.is_file():
                    return candidate_dir, candidate_video
        return None

    def _complete_semantic_scenes_from_existing(self, existing_video, args, output_dir=None):
        output_dir = Path(output_dir) if output_dir else Path(existing_video).parent
        semantic_metadata = output_dir / "semantic_scenes.json"
        if semantic_metadata.is_file():
            print(f"✓ 跳过 AI 语义分镜: 结果已存在于 {semantic_metadata}")
            return True

        report_path = output_dir / "report.json"
        if not report_path.is_file():
            return False

        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"无法读取已有分析报告 {report_path}: {exc}") from exc

        scenes_info = report.get("scenes") or []
        if not scenes_info:
            return False

        from ..core.semantic_scene_grouper import SemanticSceneGrouper

        print(f"✓ 复用已有基础分析结果: {output_dir}")
        print("\n=== 步骤 4: AI 剧情语义分镜 ===")
        grouper = SemanticSceneGrouper.from_config(
            getattr(args, "semantic_scenes_config", None)
        )
        semantic_scenes = grouper.group_and_export(
            str(existing_video),
            scenes_info,
            report.get("transcript_segments") or [],
            str(output_dir),
        )
        report["semantic_scene_count"] = len(semantic_scenes)
        report["semantic_scenes"] = semantic_scenes
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            f"✓ 已将 {len(scenes_info)} 个原始切镜聚合为 "
            f"{len(semantic_scenes)} 个剧情语义分镜"
        )
        print(f"✓ 语义分镜已保存到: {output_dir / 'semantic_scenes'}")
        return True

    def process_existing_output_directory(self, output_dir, args):
        """复用已有分析结果，只补做 AI 剧情语义分镜。"""
        output_path = Path(output_dir)
        existing_target = output_path / self.TARGET_VIDEO_FILENAME
        if not existing_target.is_file():
            print(f"✗ 错误: 结果目录中缺少 {self.TARGET_VIDEO_FILENAME}: {output_path}")
            return False
        try:
            return self._complete_semantic_scenes_from_existing(
                existing_target,
                args,
                output_dir=output_path,
            )
        except Exception as exc:
            print(f"\n✗ 处理已有结果目录 '{output_path}' 时出错: {exc}\n")
            return False

    def _maybe_export_jianying(self, analyzer, video_path, args):
        should_export = getattr(args, "export_jianying", False) or getattr(args, "compose_with_pool", None)
        if not should_export:
            return None

        artifacts = load_analysis_artifacts(analyzer.output_dir)
        timeline = None

        if getattr(args, "compose_with_pool", None):
            shot_pool = ShotPoolIndex.from_directory(args.compose_with_pool)
            settings = CompositionSettings(
                head_mode=getattr(args, "head_mode", "first-scene"),
                head_duration_us=(
                    int(round(getattr(args, "head_duration", 0) * 1_000_000))
                    if getattr(args, "head_duration", None) is not None
                    else None
                ),
                random_seed=getattr(args, "compose_seed", None),
            )
            composer = HeadTailComposer(shot_pool, settings)
            timeline = composer.compose(artifacts)
            composer.save_plan(
                Path(analyzer.output_dir) / "composition_plan.json",
                timeline,
            )

        export_kwargs = {"timeline_clips": timeline}
        if getattr(args, "draft_root", None):
            export_kwargs["draft_root"] = args.draft_root
        if getattr(args, "template_dir", None):
            export_kwargs["template_dir"] = args.template_dir
        if getattr(args, "draft_name", None):
            export_kwargs["draft_name"] = args.draft_name
        if getattr(args, "style_template", None):
            export_kwargs["style_template"] = args.style_template

        draft_dir = export_to_jianying_draft(artifacts, **export_kwargs)
        print(f"✓ 剪映草稿已导出到: {draft_dir}")
        return draft_dir
    
    def process_video(self, video_path, args):
        """
        处理单个视频
        
        Args:
            video_path: 视频文件路径
            args: 命令行参数对象
            
        Returns:
            bool: 是否成功
        """
        if not os.path.exists(video_path):
            print(f"✗ 错误: 找不到视频文件 '{video_path}'")
            return False

        try:
            existing_target = self._find_existing_target_video(video_path)
            if existing_target is not None:
                print(
                    f"✓ 跳过 '{Path(video_path).name}': "
                    f"目标视频已存在于 {existing_target}"
                )
                return True

            if getattr(args, "semantic_scenes", False):
                existing_analysis = self._find_existing_analysis(video_path)
                if existing_analysis is not None:
                    existing_output_dir, existing_video = existing_analysis
                    if self._complete_semantic_scenes_from_existing(
                        existing_video,
                        args,
                        output_dir=existing_output_dir,
                    ):
                        return True

            analyzer = VideoAnalyzer(video_path, self.output_dir)
            
            scenes_info = None
            audio_path = None
            transcript_result = None

            if getattr(args, "remove_subtitles", False):
                analyzer.remove_subtitles(
                    getattr(args, "subtitle_bar_height", None)
                )

                if getattr(args, "remove_subtitles_only", False):
                    print(f"\n{'='*60}")
                    print(f"✓ 视频 '{Path(video_path).name}' 去字幕完成！")
                    print(f"输出目录: {analyzer.output_dir}")
                    print(f"{'='*60}\n")
                    return True
            
            # 分割场景
            if not args.audio_only:
                scenes_info = analyzer.analyze_scenes(args.threshold)
            
            # 提取音频和转录
            if not args.scenes_only:
                audio_path = analyzer.extract_audio()
                if audio_path:
                    transcript_result = analyzer.transcribe_audio(
                        audio_path, 
                        args.whisper_model
                    )
            
            semantic_scenes = None

            # 先保存基础分析结果，保证 AI 阶段失败后可以直接续跑。
            if scenes_info or transcript_result:
                analyzer.generate_report(scenes_info, transcript_result)

            if getattr(args, "semantic_scenes", False):
                if not scenes_info:
                    raise ValueError("AI 语义分镜需要先完成原始切镜检测，不能与 --audio-only 同时使用。")
                from ..core.semantic_scene_grouper import SemanticSceneGrouper

                print("\n=== 步骤 4: AI 剧情语义分镜 ===")
                grouper = SemanticSceneGrouper.from_config(
                    getattr(args, "semantic_scenes_config", None)
                )
                semantic_scenes = grouper.group_and_export(
                    analyzer.video_path,
                    scenes_info,
                    transcript_result["segments"] if transcript_result else [],
                    analyzer.output_dir,
                )
                print(
                    f"✓ 已将 {len(scenes_info)} 个原始切镜聚合为 "
                    f"{len(semantic_scenes)} 个剧情语义分镜"
                )
                print(f"✓ 语义分镜已保存到: {Path(analyzer.output_dir) / 'semantic_scenes'}")

            # AI 成功后更新报告中的语义分镜信息；未启用时基础报告已在上方保存。
            if semantic_scenes is not None:
                analyzer.generate_report(
                    scenes_info,
                    transcript_result,
                    semantic_scenes=semantic_scenes,
                )
            if scenes_info or transcript_result:
                self._maybe_export_jianying(analyzer, video_path, args)
            
            print(f"\n{'='*60}")
            print(f"✓ 视频 '{Path(video_path).name}' 分析完成！")
            print(f"输出目录: {analyzer.output_dir}")
            print(f"{'='*60}\n")
            
            return True
            
        except Exception as e:
            print(f"\n✗ 处理视频 '{video_path}' 时出错: {str(e)}\n")
            return False
    
    def process_batch(self, video_list, args):
        """
        批量处理视频列表
        
        Args:
            video_list: 视频路径列表
            args: 命令行参数对象
            
        Returns:
            dict: 处理结果统计
        """
        start_time = time.time()
        self.success_count = 0
        self.failed_videos = []
        
        print(f"\n{'='*60}")
        print(f"视频分析工具 - 批量处理模式")
        print(f"{'='*60}")
        print(f"待处理视频数量: {len(video_list)}")
        print(f"输出根目录: {self.output_dir}")
        print(f"{'='*60}\n")
        
        for i, video_path in enumerate(video_list, 1):
            print(f"\n[{i}/{len(video_list)}] 正在处理: {video_path}")
            
            if self.process_video(video_path, args):
                self.success_count += 1
            else:
                self.failed_videos.append(video_path)
        
        elapsed_time = time.time() - start_time
        
        return {
            "total": len(video_list),
            "success": self.success_count,
            "failed": len(self.failed_videos),
            "failed_videos": self.failed_videos,
            "elapsed_time": elapsed_time
        }
    
    def print_summary(self, result):
        """
        打印处理结果摘要
        
        Args:
            result: 处理结果字典
        """
        print(f"\n{'='*60}")
        print(f"批量处理完成！")
        print(f"{'='*60}")
        print(f"总视频数: {result['total']}")
        print(f"成功: {result['success']}")
        print(f"失败: {result['failed']}")
        print(f"总耗时: {result['elapsed_time']:.1f} 秒")
        
        if result['failed_videos']:
            print(f"\n失败的视频:")
            for video in result['failed_videos']:
                print(f"  - {video}")
        
        print(f"\n所有结果已保存到: {self.output_dir}")
        print(f"{'='*60}")
