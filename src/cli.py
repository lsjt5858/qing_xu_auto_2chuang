"""
命令行接口 - 处理命令行参数和执行流程
"""
import argparse
import os
from pathlib import Path

from .utils.file_utils import read_video_list
from .utils.batch_processor import BatchProcessor
from .core.video_downloader import VideoDownloader
from .exporters.jianying import resolve_draft_root


def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="视频分析工具 - 去字幕/去底部水印、分镜分割、音频提取、语音转文字（支持批量处理）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 分析本地视频
  python main.py video.mp4

  # 只导出去字幕视频
  python main.py video.mp4 --remove-subtitles-only
  
  # 从链接下载并分析
  python main.py https://v.douyin.com/xxx/ -d
  
  # 批量下载多个视频链接
  python main.py https://url1.com https://url2.com -d
  
  # 从文件读取链接批量下载和分析
  python main.py --list urls.txt -d
  
  # 只下载视频，不分析
  python main.py https://v.douyin.com/xxx/ --download-only
  
  # 混合本地文件和链接
  python main.py video.mp4 https://url.com -d
  
  # 只分割场景
  python main.py video.mp4 --scenes-only
  
  # 使用更精确的语音识别
  python main.py video.mp4 --whisper-model medium

urls.txt 格式示例:
  # 支持视频链接
  https://v.douyin.com/xxx/
  https://www.youtube.com/watch?v=xxx
  # 也支持本地文件
  /path/to/video.mp4
        """
    )
    
    parser.add_argument("videos", nargs="*", help="输入视频文件路径或视频链接（可以多个）")
    parser.add_argument("-l", "--list", help="包含视频路径/链接列表的文本文件")
    parser.add_argument("-d", "--download", action="store_true", help="从链接下载视频")
    parser.add_argument("--download-only", action="store_true", help="只下载视频，不进行分析")
    parser.add_argument("-o", "--output", default="output", help="输出根目录 (默认: output)")
    parser.add_argument("-t", "--threshold", type=float, default=27.0, 
                       help="场景检测阈值 0-255 (默认: 27)")
    parser.add_argument("--scenes-only", action="store_true", help="只分割场景，不处理音频")
    parser.add_argument("--audio-only", action="store_true", help="只提取音频和文案，不分割场景")
    parser.add_argument("--whisper-model", default="base", 
                       choices=["tiny", "base", "small", "medium", "large"],
                       help="Whisper 模型大小 (默认: base)")
    parser.add_argument("--remove-subtitles", action="store_true",
                       help="先移除视频底部烧录字幕，并清理底部区域的固定半透明水印，再继续后续处理")
    parser.add_argument("--remove-subtitles-only", action="store_true",
                       help="只导出去字幕/去水印后的预处理视频，不执行其他分析步骤")
    parser.add_argument("--subtitle-bar-height", type=int,
                       help="手动指定底部字幕黑边高度（像素）")
    parser.add_argument("--semantic-scenes", action="store_true",
                       help="调用视觉模型把连续原始切镜聚合为剧情语义分镜，并同时保留两级结果")
    parser.add_argument("--semantic-scenes-config", default="config/semantic_scenes.json",
                       help="AI 语义分镜配置文件 (默认: config/semantic_scenes.json)")
    parser.add_argument("--export-jianying", action="store_true",
                       help="分析完成后自动导出为剪映草稿")
    parser.add_argument("--compose-with-pool",
                       help="使用视频池重组尾部镜头后再导出剪映草稿")
    parser.add_argument("--head-mode", choices=["first-scene", "fixed-seconds", "none"],
                       default="first-scene",
                       help="组合模式下保留原视频头部的规则 (默认: first-scene)")
    parser.add_argument("--head-duration", type=float,
                       help="当 --head-mode=fixed-seconds 时，保留头部秒数")
    parser.add_argument("--compose-seed", type=int,
                       help="组合模式下随机选镜头的随机种子")
    parser.add_argument("--draft-root",
                       help="剪映草稿箱根目录，默认使用本机剪映目录")
    parser.add_argument("--template-dir",
                       help="剪映草稿模板目录，默认使用项目内置模板")
    parser.add_argument("--draft-name",
                       help="导出的剪映草稿名称")
    parser.add_argument("--style-template",
                       choices=["emotion", "basic"],
                       default="emotion",
                       help="剪映导出使用的样式模板 (默认: emotion)")
    
    return parser


def is_url(path):
    """判断是否为 URL"""
    return path.startswith(('http://', 'https://', 'www.'))


def collect_directory_inputs(directory, include_existing_outputs=False):
    """扫描目录中的源视频；语义模式下同时识别已有分析结果目录。"""
    root = Path(directory)
    result_dirs = []

    if include_existing_outputs:
        if (
            (root / "report.json").is_file()
            and (root / BatchProcessor.TARGET_VIDEO_FILENAME).is_file()
        ):
            return [], [str(root)]

        result_dirs = sorted(
            str(child)
            for child in root.iterdir()
            if child.is_dir()
            and (child / "report.json").is_file()
            and (child / BatchProcessor.TARGET_VIDEO_FILENAME).is_file()
        )

    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.ts'}
    videos = sorted(
        str(child)
        for child in root.iterdir()
        if child.is_file()
        and not child.name.startswith('._')
        and child.suffix.lower() in video_extensions
    )
    return videos, result_dirs


def validate_semantic_scene_credentials(config_path):
    """在任何耗时视频处理前校验 AI 配置和密钥。"""
    from .core.semantic_scene_grouper import SemanticSceneConfig

    config = SemanticSceneConfig.load(config_path)
    if not os.getenv(config.api_key_env, "").strip():
        raise RuntimeError(
            f"启用 AI 语义分镜需要先设置环境变量 {config.api_key_env}；"
            "本次未开始视频处理。"
        )
    return config


def main():
    """主函数"""
    parser = create_parser()
    args = parser.parse_args()

    if args.remove_subtitles_only:
        args.remove_subtitles = True

    if args.compose_with_pool:
        args.export_jianying = True

    if getattr(args, "export_jianying", False) or getattr(args, "compose_with_pool", None):
        draft_root = resolve_draft_root(getattr(args, "draft_root", None))
        args.draft_root = str(draft_root)
        print(f"✓ 剪映草稿箱路径已确认: {draft_root}")
    
    # 收集所有要处理的视频/链接，以及可复用的已有分析结果目录
    video_list = []
    existing_output_dirs = []
    
    if args.list:
        # 从文件读取视频列表
        try:
            video_list.extend(read_video_list(args.list))
            print(f"从 '{args.list}' 读取到 {len(video_list)} 个项目")
        except FileNotFoundError:
            print(f"错误: 找不到列表文件 '{args.list}'")
            return
    
    if args.videos:
        for item in args.videos:
            item = item.strip()
            if os.path.isdir(item):
                dir_videos, dir_outputs = collect_directory_inputs(
                    item,
                    include_existing_outputs=getattr(args, "semantic_scenes", False),
                )
                if dir_videos:
                    print(f"从目录 '{item}' 扫描到 {len(dir_videos)} 个视频文件")
                    video_list.extend(dir_videos)
                if dir_outputs:
                    print(f"从目录 '{item}' 扫描到 {len(dir_outputs)} 个已有分析结果")
                    existing_output_dirs.extend(dir_outputs)
                if not dir_videos and not dir_outputs:
                    print(f"警告: 目录 '{item}' 中未找到视频文件或可复用的分析结果")
            else:
                video_list.append(item)
    
    if not video_list and not existing_output_dirs:
        print("错误: 请提供至少一个视频文件/链接、已有分析结果目录，或使用 --list 指定列表文件")
        parser.print_help()
        return
    
    # 去重
    video_list = list(dict.fromkeys(video_list))
    existing_output_dirs = list(dict.fromkeys(existing_output_dirs))
    
    # 分离 URL 和本地文件
    urls = [item for item in video_list if is_url(item)]
    local_files = [item for item in video_list if not is_url(item)]
    
    # 如果有 URL 且启用了下载，先下载
    if urls and args.download:
        downloader = VideoDownloader(output_dir="downloads")
        
        print(f"\n检测到 {len(urls)} 个视频链接，开始下载...")
        downloaded_files = downloader.download_batch(urls)
        local_files.extend(downloaded_files)
        
        if args.download_only:
            print(f"\n下载完成！文件保存在 downloads/ 目录")
            return
    elif urls and not args.download:
        print(f"\n警告: 检测到 {len(urls)} 个视频链接，但未启用下载功能")
        print("请添加 -d 或 --download 参数来下载视频")
        print("示例: ./run.sh --list urls.txt -d")
        return
    
    if not local_files and not existing_output_dirs:
        print("错误: 没有可处理的视频文件或已有分析结果")
        return
    
    processor = BatchProcessor(output_dir=args.output)

    if getattr(args, "semantic_scenes", False):
        pending_local_files = any(
            os.path.exists(video_path)
            and processor._find_existing_target_video(video_path) is None
            for video_path in local_files
        )
        pending_output_dirs = any(
            not (Path(output_dir) / "semantic_scenes.json").is_file()
            for output_dir in existing_output_dirs
        )
        if pending_local_files or pending_output_dirs:
            try:
                validate_semantic_scene_credentials(args.semantic_scenes_config)
            except (OSError, ValueError, RuntimeError) as exc:
                print(f"错误: {exc}")
                return

    if existing_output_dirs:
        print(f"\n开始复用 {len(existing_output_dirs)} 个已有分析结果生成 AI 剧情语义分镜...")
        for output_dir in existing_output_dirs:
            processor.process_existing_output_directory(output_dir, args)

    if local_files:
        result = processor.process_batch(local_files, args)
        processor.print_summary(result)


if __name__ == "__main__":
    main()
