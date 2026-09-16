"""
场景检测模块 - 负责视频分镜检测和分割
"""
import os
from types import MappingProxyType
from config.settings import SCENE_DETECTION


class SceneDetector:
    """视频场景检测器 - 使用自适应阈值检测真实画面切换"""

    def __init__(
        self,
        threshold: float | None = None,
        adaptive_threshold: float | None = None,
        min_scene_length: float | None = None,
    ):
        """
        初始化场景检测器

        Args:
            threshold: 内容变化最低阈值 (0-255)，值越小越敏感
            adaptive_threshold: 自适应变化倍率，默认 3.0
            min_scene_length: 最短镜头时长（秒），小于此时长的误检片段会被合并
        """
        self.content_threshold = (
            float(threshold) if threshold is not None else float(SCENE_DETECTION["threshold"])
        )
        self.adaptive_threshold = (
            float(adaptive_threshold)
            if adaptive_threshold is not None
            else float(SCENE_DETECTION["adaptive_threshold"])
        )
        self.min_scene_length = (
            float(min_scene_length)
            if min_scene_length is not None
            else float(SCENE_DETECTION["min_scene_length"])
        )

    @property
    def detection_config(self) -> MappingProxyType:
        """返回检测配置的只读快照，用于写入报告"""
        return MappingProxyType(
            {
                "detector_type": "adaptive",
                "content_threshold": self.content_threshold,
                "adaptive_threshold": self.adaptive_threshold,
                "min_scene_length": self.min_scene_length,
            }
        )

    @property
    def threshold(self) -> float:
        """向后兼容：旧代码访问 threshold 时返回 content_threshold"""
        return self.content_threshold

    def detect_scenes(self, video_path):
        """
        检测视频中的真实画面切换点

        Args:
            video_path: 视频文件路径

        Returns:
            tuple: (scenes_info, scene_list) 场景信息列表和 PySceneDetect 场景列表
        """
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import AdaptiveDetector

        video = open_video(str(video_path))
        scene_manager = SceneManager()

        fps = video.frame_rate or 30.0
        min_scene_len_frames = max(1, int(round(self.min_scene_length * fps)))

        scene_manager.add_detector(
            AdaptiveDetector(
                adaptive_threshold=self.adaptive_threshold,
                min_content_val=self.content_threshold,
                min_scene_len=min_scene_len_frames,
            )
        )

        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        if not scene_list:
            from scenedetect.frame_timecode import FrameTimecode

            end_timecode = FrameTimecode(
                timecode=video.duration.get_seconds(),
                fps=video.frame_rate,
            )
            scene_list = [(video.base_timecode, end_timecode)]

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
                "end_timecode": scene[1].get_timecode(),
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
        from scenedetect.video_splitter import split_video_ffmpeg

        os.makedirs(output_dir, exist_ok=True)
        output_template = os.path.join(output_dir, "Scene-$SCENE_NUMBER.mp4")

        split_video_ffmpeg(
            video_path,
            scene_list,
            output_file_template=output_template,
            show_progress=True,
        )
