"""
场景检测模块 - 负责视频分镜检测和分割
"""
import os
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
from scenedetect.video_splitter import split_video_ffmpeg


class SceneDetector:
    """视频场景检测器"""
    
    def __init__(self, threshold=27.0):
        """
        初始化场景检测器
        
        Args:
            threshold: 场景检测阈值 (0-255)，值越小越敏感
        """
        self.threshold = threshold
    
    def detect_scenes(self, video_path):
        """
        检测视频中的场景
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            list: 场景列表，每个场景包含开始和结束时间
        """
        video_manager = VideoManager([video_path])
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=self.threshold))
        
        video_manager.start()
        scene_manager.detect_scenes(frame_source=video_manager)
        scene_list = scene_manager.get_scene_list()
        video_manager.release()
        
        # 转换为更友好的格式
        scenes_info = []
        for i, scene in enumerate(scene_list, start=1):
            start_time = scene[0].get_seconds()
            end_time = scene[1].get_seconds()
            duration = end_time - start_time
            
            scene_data = {
                "scene_number": i,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "start_timecode": scene[0].get_timecode(),
                "end_timecode": scene[1].get_timecode()
            }
            scenes_info.append(scene_data)
        
        return scenes_info, scene_list
    
    def split_video(self, video_path, scene_list, output_dir):
        """
        根据场景列表分割视频
        
        Args:
            video_path: 视频文件路径
            scene_list: 场景列表（来自 detect_scenes）
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        output_template = os.path.join(output_dir, "Scene-$SCENE_NUMBER.mp4")
        
        split_video_ffmpeg(
            video_path,
            scene_list,
            output_file_template=output_template,
            show_progress=True
        )
