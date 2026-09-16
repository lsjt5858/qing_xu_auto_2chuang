"""
视频分析器 - 整合所有功能的主类
"""
import os
import json
from pathlib import Path
from datetime import datetime

from config.settings import DEFAULT_OUTPUT_DIR, OUTPUT, TRANSCRIPTION

from .scene_detector import SceneDetector
from .audio_extractor import AudioExtractor
from .transcriber import Transcriber
from .subtitle_remover import SubtitleRemover


class VideoAnalyzer:
    """视频分析器 - 整合分镜、音频提取、语音转文字"""
    
    def __init__(self, video_path, base_output_dir=DEFAULT_OUTPUT_DIR):
        """
        初始化视频分析器
        
        Args:
            video_path: 视频文件路径
            base_output_dir: 输出根目录
        """
        self.original_video_path = video_path
        self.video_path = video_path
        self.video_name = Path(video_path).stem
        
        # 为每个视频创建独立的输出文件夹
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = os.path.join(base_output_dir, f"{self.video_name}_{timestamp}")
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.scene_detection_config = None
        
        print(f"\n{'='*60}")
        print(f"视频: {self.video_name}")
        print(f"输出目录: {self.output_dir}")
        print(f"{'='*60}")

    def remove_subtitles(self, subtitle_bar_height=None):
        """
        去除底部烧录字幕，并清理底部区域的固定透明水印

        Args:
            subtitle_bar_height: 手动指定字幕黑边像素高度

        Returns:
            str: 预处理后的视频路径
        """
        print("\n=== 步骤 0: 去除底部字幕/水印 ===")

        output_path = os.path.join(self.output_dir, "video_no_subtitles.mp4")
        remover = SubtitleRemover()
        result = remover.remove(self.video_path, output_path, subtitle_bar_height)

        self.video_path = result["output_path"]

        if result.get("processing_skipped", False):
            print("✓ 未检测到可处理的字幕黑边或固定水印，已保留原画面并继续分解")
        else:
            if result["subtitle_bar_height"] > 0:
                print(f"✓ 检测到底部字幕黑边高度: {result['subtitle_bar_height']} 像素")
            else:
                print("✓ 未检测到底部字幕黑边，已跳过黑边裁切")

            if result["watermark_removed"]:
                print(f"✓ 已清理底部固定透明水印（掩码面积: {result['watermark_mask_area']} 像素）")
            else:
                print("✓ 未检测到底部固定透明水印，已跳过去水印")

        print(f"✓ 预处理视频已保存到: {self.video_path}")

        return self.video_path
    
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
        
        self.scene_detection_config = dict(detector.detection_config)
        
        print(f"✓ 检测到 {len(scenes_info)} 个场景")
        
        for scene in scenes_info:
            print(f"  场景 {scene['scene_number']}: {scene['start_timecode']} -> "
                  f"{scene['end_timecode']} (时长: {scene['duration']:.2f}秒)")
        
        # 分割视频
        if scene_list:
            scenes_dir = os.path.join(self.output_dir, OUTPUT["scenes_folder"])
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
        
        audio_path = os.path.join(self.output_dir, OUTPUT["audio_filename"])
        extractor = AudioExtractor()
        
        result = extractor.extract(self.video_path, audio_path)
        
        if result:
            print(f"✓ 音频已保存到: {audio_path}")
        else:
            print("✗ 视频没有音频轨道")
        
        return result
    
    def transcribe_audio(self, audio_path, model_size=TRANSCRIPTION["model"]):
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
        transcript_path = os.path.join(self.output_dir, OUTPUT["transcript_filename"])
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(result["text"])
        print(f"✓ 完整文案已保存到: {transcript_path}")
        
        # 保存带时间戳的文案
        detailed_path = os.path.join(self.output_dir, OUTPUT["transcript_detailed_filename"])
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
            "original_video_path": self.original_video_path,
            "processed_video_path": self.video_path,
            "subtitle_removed": self.original_video_path != self.video_path,
            "output_directory": self.output_dir,
            "total_scenes": len(scenes_info) if scenes_info else 0,
            "scene_detection": self.scene_detection_config,
            "scenes": scenes_info or [],
            "transcript": transcript_result["text"] if transcript_result else None,
            "transcript_segments": transcript_result["segments"] if transcript_result else []
        }
        
        report_path = os.path.join(self.output_dir, OUTPUT["report_filename"])
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 完整报告已保存到: {report_path}")
        return report
    
    # ========== 新功能入口（待实现） ==========
    
    def generate_subtitles(self, transcript_segments, format="srt", style=None):
        """
        生成字幕文件
        
        Args:
            transcript_segments: 带时间戳的文案片段
            format: 字幕格式（'srt' 或 'ass'）
            style: 字幕样式（仅 ASS 格式）
            
        Returns:
            str: 生成的字幕文件路径
        """
        print("\n=== 生成字幕文件 ===")
        from .subtitle_generator import SubtitleGenerator

        generator = SubtitleGenerator()
        
        output_path = os.path.join(self.output_dir, f"subtitle.{format}")
        
        if format == "srt":
            return generator.generate_srt(transcript_segments, output_path)
        elif format == "ass":
            return generator.generate_ass(transcript_segments, output_path, style)
        else:
            raise ValueError(f"不支持的字幕格式: {format}")
    
    def translate_subtitles(self, subtitle_path, target_language):
        """
        翻译字幕
        
        Args:
            subtitle_path: 原字幕文件路径
            target_language: 目标语言代码
            
        Returns:
            str: 翻译后的字幕文件路径
        """
        print(f"\n=== 翻译字幕到 {target_language} ===")
        from .subtitle_translator import SubtitleTranslator

        translator = SubtitleTranslator()
        
        output_path = os.path.join(
            self.output_dir, 
            f"subtitle_{target_language}.{Path(subtitle_path).suffix}"
        )
        
        return translator.translate(subtitle_path, target_language, output_path)
    
    def compress_video(self, quality="medium", target_size_mb=None):
        """
        压缩视频
        
        Args:
            quality: 压缩质量
            target_size_mb: 目标文件大小（MB）
            
        Returns:
            dict: 压缩结果信息
        """
        print("\n=== 压缩视频 ===")
        from .video_compressor import VideoCompressor

        compressor = VideoCompressor()
        
        output_path = os.path.join(self.output_dir, "video_compressed.mp4")
        
        return compressor.compress(self.video_path, output_path, quality, target_size_mb)
    
    def convert_format(self, target_format, resolution=None, bitrate=None):
        """
        转换视频格式
        
        Args:
            target_format: 目标格式
            resolution: 目标分辨率
            bitrate: 目标码率
            
        Returns:
            str: 转换后的视频路径
        """
        print(f"\n=== 转换格式到 {target_format} ===")
        from .format_converter import FormatConverter

        converter = FormatConverter()
        
        output_path = os.path.join(self.output_dir, f"video.{target_format}")
        
        return converter.convert(self.video_path, output_path, target_format, resolution, bitrate)
    
    def enhance_video(self, auto=True, brightness=0, contrast=1.0, denoise=False, stabilize=False):
        """
        增强视频质量
        
        Args:
            auto: 是否自动增强
            brightness: 亮度调整
            contrast: 对比度调整
            denoise: 是否降噪
            stabilize: 是否稳定画面
            
        Returns:
            str: 增强后的视频路径
        """
        print("\n=== 增强视频质量 ===")
        from .video_enhancer import VideoEnhancer

        enhancer = VideoEnhancer()
        
        output_path = os.path.join(self.output_dir, "video_enhanced.mp4")
        
        if auto:
            return enhancer.auto_enhance(self.video_path, output_path)
        
        # TODO: 支持更多自定义增强选项
        return output_path
    
    def process_audio(self, separate_vocals=False, denoise=False, normalize=False):
        """
        处理音频
        
        Args:
            separate_vocals: 是否分离人声
            denoise: 是否降噪
            normalize: 是否标准化音量
            
        Returns:
            dict: 处理结果
        """
        print("\n=== 处理音频 ===")
        from .audio_processor import AudioProcessor

        processor = AudioProcessor()
        
        audio_path = os.path.join(self.output_dir, "audio.mp3")
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError("请先提取音频")
        
        result = {}
        
        if separate_vocals:
            vocals_path = os.path.join(self.output_dir, "audio_vocals.mp3")
            music_path = os.path.join(self.output_dir, "audio_music.mp3")
            result["vocals"] = processor.separate_vocals(audio_path, vocals_path, music_path)
        
        if denoise:
            denoised_path = os.path.join(self.output_dir, "audio_denoised.mp3")
            result["denoised"] = processor.denoise(audio_path, denoised_path)
        
        if normalize:
            normalized_path = os.path.join(self.output_dir, "audio_normalized.mp3")
            result["normalized"] = processor.normalize_volume(audio_path, normalized_path)
        
        return result
    
    def analyze_content(self, detect_faces=False, detect_objects=False, extract_text=False):
        """
        分析视频内容
        
        Args:
            detect_faces: 是否检测人脸
            detect_objects: 是否识别物体
            extract_text: 是否提取文字（OCR）
            
        Returns:
            dict: 分析结果
        """
        print("\n=== 分析视频内容 ===")
        from .content_analyzer import ContentAnalyzer

        analyzer = ContentAnalyzer()
        
        result = {}
        
        if detect_faces:
            result["faces"] = analyzer.detect_faces(self.video_path)
        
        if detect_objects:
            result["objects"] = analyzer.detect_objects(self.video_path)
        
        if extract_text:
            result["text"] = analyzer.extract_text_ocr(self.video_path)
        
        return result
    
    def smart_edit(self, remove_silence=False, remove_duplicates=False, extract_keyframes=False):
        """
        智能编辑
        
        Args:
            remove_silence: 是否去除静音
            remove_duplicates: 是否去除重复
            extract_keyframes: 是否提取关键帧
            
        Returns:
            dict: 编辑结果
        """
        print("\n=== 智能编辑 ===")
        from .smart_editor import SmartEditor

        editor = SmartEditor()
        
        result = {}
        
        if remove_silence:
            output_path = os.path.join(self.output_dir, "video_no_silence.mp4")
            result["no_silence"] = editor.remove_silence(self.video_path, output_path)
        
        if remove_duplicates:
            output_path = os.path.join(self.output_dir, "video_no_duplicates.mp4")
            result["no_duplicates"] = editor.remove_duplicates(self.video_path, output_path)
        
        if extract_keyframes:
            keyframes_dir = os.path.join(self.output_dir, "keyframes")
            result["keyframes"] = editor.extract_keyframes(self.video_path, keyframes_dir)
        
        return result
