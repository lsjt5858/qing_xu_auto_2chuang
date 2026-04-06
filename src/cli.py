"""
命令行接口 - 处理命令行参数和执行流程
"""
import argparse
import os

from .utils.file_utils import read_video_list
from .utils.batch_processor import BatchProcessor
from .core.video_downloader import VideoDownloader


def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="视频分析工具 - 分镜分割、音频提取、语音转文字（支持批量处理）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 分析本地视频
  python main.py video.mp4
  
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
    
    return parser


def is_url(path):
    """判断是否为 URL"""
    return path.startswith(('http://', 'https://', 'www.'))


def main():
    """主函数"""
    parser = create_parser()
    args = parser.parse_args()
    
    # 收集所有要处理的视频/链接
    video_list = []
    
    if args.list:
        # 从文件读取视频列表
        try:
            video_list.extend(read_video_list(args.list))
            print(f"从 '{args.list}' 读取到 {len(video_list)} 个项目")
        except FileNotFoundError:
            print(f"错误: 找不到列表文件 '{args.list}'")
            return
    
    if args.videos:
        # 从命令行参数添加视频
        video_list.extend(args.videos)
    
    if not video_list:
        print("错误: 请提供至少一个视频文件/链接或使用 --list 指定列表文件")
        parser.print_help()
        return
    
    # 去重
    video_list = list(dict.fromkeys(video_list))
    
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
    
    if not local_files:
        print("错误: 没有可处理的视频文件")
        return
    
    # 批量处理
    processor = BatchProcessor(output_dir=args.output)
    result = processor.process_batch(local_files, args)
    processor.print_summary(result)


if __name__ == "__main__":
    main()
