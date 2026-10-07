"""
音频提取模块 - 负责从视频中提取音频
"""
import os


class AudioExtractor:
    """音频提取器"""
    
    def extract(self, video_path, output_path):
        """
        从视频中提取音频
        
        Args:
            video_path: 视频文件路径
            output_path: 输出音频文件路径
            
        Returns:
            str: 音频文件路径，如果视频没有音频则返回 None
        """
        # MoviePy probes ffplay during import. On some macOS FFmpeg builds,
        # invoking ffplay without arguments never exits. Audio extraction does
        # not use ffplay, so route that probe to the already-required ffmpeg.
        os.environ.setdefault("FFPLAY_BINARY", "ffmpeg")
        from moviepy import VideoFileClip

        video = VideoFileClip(video_path)
        
        if video.audio is None:
            video.close()
            return None
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        video.audio.write_audiofile(output_path, logger=None)
        video.close()
        
        return output_path
