"""
批量处理器 - 处理多个视频
"""
import os
import time
from pathlib import Path

from ..core.video_analyzer import VideoAnalyzer


class BatchProcessor:
    """批量视频处理器"""
    
    def __init__(self, output_dir="output"):
        """
        初始化批量处理器
        
        Args:
            output_dir: 输出根目录
        """
        self.output_dir = output_dir
        self.success_count = 0
        self.failed_videos = []
    
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
            analyzer = VideoAnalyzer(video_path, self.output_dir)
            
            scenes_info = None
            audio_path = None
            transcript_result = None
            
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
            
            # 生成报告
            if scenes_info or transcript_result:
                analyzer.generate_report(scenes_info, transcript_result)
            
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
