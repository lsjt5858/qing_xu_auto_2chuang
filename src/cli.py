"""
命令行接口 - 处理命令行参数和执行流程
"""
import argparse

from .utils.file_utils import read_video_list
from .utils.batch_processor import BatchProcessor


def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="视频分析工具 - 分镜分割、音频提取、语音转文字（支持批量处理）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 分析单个视频
  python main.py video.mp4
  
  # 分析多个视频
  python main.py video1.mp4 video2.mp4 video3.mp4
  
  # 从文件读取视频列表批量处理
  python main.py --list videos.txt
  
  # 只分割场景
  python main.py video.mp4 --scenes-only
  
  # 只提取音频和文案
  python main.py video.mp4 --audio-only
  
  # 使用更精确的语音识别模型
  python main.py video.mp4 --whisper-model medium

videos.txt 格式示例:
  /path/to/video1.mp4
  /path/to/video2.mp4
  # 这是注释，会被忽略
  /path/to/video3.mp4
        """
    )
    
    parser.add_argument("videos", nargs="*", help="输入视频文件路径（可以多个）")
    parser.add_argument("-l", "--list", help="包含视频路径列表的文本文件")
    parser.add_argument("-o", "--output", default="output", help="输出根目录 (默认: output)")
    parser.add_argument("-t", "--threshold", type=float, default=27.0, 
                       help="场景检测阈值 0-255 (默认: 27)")
    parser.add_argument("--scenes-only", action="store_true", help="只分割场景，不处理音频")
    parser.add_argument("--audio-only", action="store_true", help="只提取音频和文案，不分割场景")
    parser.add_argument("--whisper-model", default="base", 
                       choices=["tiny", "base", "small", "medium", "large"],
                       help="Whisper 模型大小 (默认: base)")
    
    return parser


def main():
    """主函数"""
    parser = create_parser()
    args = parser.parse_args()
    
    # 收集所有要处理的视频
    video_list = []
    
    if args.list:
        # 从文件读取视频列表
        try:
            video_list.extend(read_video_list(args.list))
            print(f"从 '{args.list}' 读取到 {len(video_list)} 个视频")
        except FileNotFoundError:
            print(f"错误: 找不到列表文件 '{args.list}'")
            return
    
    if args.videos:
        # 从命令行参数添加视频
        video_list.extend(args.videos)
    
    if not video_list:
        print("错误: 请提供至少一个视频文件或使用 --list 指定视频列表文件")
        parser.print_help()
        return
    
    # 去重
    video_list = list(dict.fromkeys(video_list))
    
    # 批量处理
    processor = BatchProcessor(output_dir=args.output)
    result = processor.process_batch(video_list, args)
    processor.print_summary(result)


if __name__ == "__main__":
    main()
