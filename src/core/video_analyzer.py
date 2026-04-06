"""
视频分析器 - 整合所有功能的主类
"""
import os
import json
from pathlib import Path
from datetime import datetime

from .scene_detector import SceneDetector
from .audio_extractor import AudioExtractor
from .transcriber import Transcriber


class VideoAnalyzer:
    """视频分析器 - 整合分镜、音频提取、语音转文字"""
    
    def __init__(self, video_path, base_output_dir="output"):
        """
        初始化视频分析器
        
        Args:
            video_path: 视频文件路径
            base_output_dir: 输出根目录
        """
        self.video_path = video_path
        self.video_name = Path(video_path).stem
        
        # 为每个视频创建独立的输出文件夹
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = os.path.join(base_output_dir, f"{self.video_name}_{timestamp}")
        os.makedirs(self.output_dir, exist_ok=True)
        
        print(f"\n{'='*60}")
        print(f"视频: {self.video_name}")
        print(f"输出目录: {self.output_dir}")
        print(f"{'='*60}")
    
    def analyze_scenes(self, threshold=27.0):
        """
        分析并分割视频场景
        
        Args:
            threshold: 场景检测阈值
            
        Returns:
            list: 场景信息列表
        """
        print("\n=== 步骤 1: 分析视频场景 ===")
        
        detector = SceneDetector(threshold=threshold)
        scenes_info, scene_list = detector.detect_scenes(self.video_path)
        
        print(f"✓ 检测到 {len(scenes_info)} 个场景")
        
        for scene in scenes_info:
            print(f"  场景 {scene['scene_number']}: {scene['start_timecode']} -> "
                  f"{scene['end_timecode']} (时长: {scene['duration']:.2f}秒)")
        
        # 分割视频
        if scene_list:
            scenes_dir = os.path.join(self.output_dir, "scenes")
            detector.split_video(self.video_path, scene_list, scenes_dir)
            print(f"✓ 场景视频已保存到: {scenes_dir}")
        
        return scenes_info
    
    def extract_audio(self):
        """
        提取视频音频
        
        Returns:
            str: 音频文件路径，如果没有音频则返回 None
        """
        print("\n=== 步骤 2: 提取音频 ===")
        
        audio_path = os.path.join(self.output_dir, "audio.mp3")
        extractor = AudioExtractor()
        
        result = extractor.extract(self.video_path, audio_path)
        
        if result:
            print(f"✓ 音频已保存到: {audio_path}")
        else:
            print("✗ 视频没有音频轨道")
        
        return result
    
    def transcribe_audio(self, audio_path, model_size="base"):
        """
        转录音频为文字
        
        Args:
            audio_path: 音频文件路径
            model_size: Whisper 模型大小
            
        Returns:
            dict: 转录结果
        """
        if audio_path is None:
            return None
        
        print("\n=== 步骤 3: 语音转文字 ===")
        
        transcriber = Transcriber(model_size=model_size)
        result = transcriber.transcribe(audio_path)
        
        # 保存完整文案
        transcript_path = os.path.join(self.output_dir, "transcript.txt")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(result["text"])
        print(f"✓ 完整文案已保存到: {transcript_path}")
        
        # 保存带时间戳的文案
        detailed_path = os.path.join(self.output_dir, "transcript_detailed.json")
        with open(detailed_path, "w", encoding="utf-8") as f:
            json.dump(result["segments"], f, ensure_ascii=False, indent=2)
        print(f"✓ 详细文案（带时间戳）已保存到: {detailed_path}")
        
        # 打印预览
        print("\n文案预览:")
        print("-" * 50)
        preview = result["text"][:300] + ("..." if len(result["text"]) > 300 else "")
        print(preview)
        print("-" * 50)
        
        return result
    
    def generate_report(self, scenes_info, transcript_result):
        """
        生成分析报告
        
        Args:
            scenes_info: 场景信息列表
            transcript_result: 转录结果
            
        Returns:
            dict: 完整报告
        """
        print("\n=== 生成分析报告 ===")
        
        report = {
            "video_name": self.video_name,
            "video_path": self.video_path,
            "output_directory": self.output_dir,
            "total_scenes": len(scenes_info) if scenes_info else 0,
            "scenes": scenes_info or [],
            "transcript": transcript_result["text"] if transcript_result else None,
            "transcript_segments": transcript_result["segments"] if transcript_result else []
        }
        
        report_path = os.path.join(self.output_dir, "report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 完整报告已保存到: {report_path}")
        return report
