"""
视频字幕去除模块 - 去除底部黑边中的烧录字幕
"""
import os
import statistics
import subprocess

import cv2


class SubtitleRemover:
    """通过裁剪底部字幕黑边再补回纯黑背景的方式去除字幕"""

    def __init__(
        self,
        sample_frames=12,
        dark_threshold=20,
        dark_pixel_ratio=0.9,
        min_bar_height=30,
        max_bar_ratio=0.25
    ):
        self.sample_frames = sample_frames
        self.dark_threshold = dark_threshold
        self.dark_pixel_ratio = dark_pixel_ratio
        self.min_bar_height = min_bar_height
        self.max_bar_ratio = max_bar_ratio

    @staticmethod
    def estimate_bottom_black_bar_height(frame, dark_threshold=20, dark_pixel_ratio=0.9):
        """
        估算单帧底部连续黑边的高度

        Args:
            frame: 视频帧
            dark_threshold: 判定为黑色的像素阈值
            dark_pixel_ratio: 每行中需满足黑色像素的比例

        Returns:
            int: 底部黑边高度
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        row_dark_ratio = (gray < dark_threshold).mean(axis=1)

        bar_height = 0
        for ratio in row_dark_ratio[::-1]:
            if ratio >= dark_pixel_ratio:
                bar_height += 1
            else:
                break

        return int(bar_height)

    def detect_subtitle_bar_height(self, video_path):
        """
        自动检测视频底部字幕黑边高度

        Args:
            video_path: 视频路径

        Returns:
            int: 检测到的黑边高度，若未检测到则返回 0
        """
        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")

        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        video_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        max_bar_height = int(video_height * self.max_bar_ratio) if video_height else 0

        if frame_count <= 0:
            sample_positions = [0]
        else:
            step = max(frame_count // self.sample_frames, 1)
            sample_positions = list(range(0, frame_count, step))[:self.sample_frames]
            if (frame_count - 1) not in sample_positions:
                sample_positions.append(frame_count - 1)

        heights = []

        try:
            for frame_index in sample_positions:
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                success, frame = capture.read()
                if not success or frame is None:
                    continue

                bar_height = self.estimate_bottom_black_bar_height(
                    frame,
                    dark_threshold=self.dark_threshold,
                    dark_pixel_ratio=self.dark_pixel_ratio
                )

                if max_bar_height:
                    bar_height = min(bar_height, max_bar_height)

                if bar_height >= self.min_bar_height:
                    heights.append(bar_height)
        finally:
            capture.release()

        if not heights:
            return 0

        detected_height = int(statistics.median(heights))
        return detected_height if detected_height >= self.min_bar_height else 0

    @staticmethod
    def build_video_filter(subtitle_bar_height):
        """
        构建 ffmpeg 视频滤镜

        Args:
            subtitle_bar_height: 需要移除的底部高度

        Returns:
            str: ffmpeg filter 字符串
        """
        return (
            f"crop=iw:ih-{subtitle_bar_height}:0:0,"
            f"pad=iw:ih+{subtitle_bar_height}:0:0:black"
        )

    def remove(self, video_path, output_path, subtitle_bar_height=None):
        """
        生成去字幕视频

        Args:
            video_path: 原视频路径
            output_path: 输出视频路径
            subtitle_bar_height: 手动指定字幕黑边高度

        Returns:
            dict: 输出结果
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        detected_height = subtitle_bar_height
        if detected_height is None:
            detected_height = self.detect_subtitle_bar_height(video_path)

        if not detected_height or detected_height <= 0:
            raise ValueError(
                "未检测到底部字幕黑边，请使用 --subtitle-bar-height 手动指定像素高度。"
            )

        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vf", self.build_video_filter(detected_height),
            "-map", "0:v:0",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-sn",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"ffmpeg 去字幕失败: {error[:500]}")

        return {
            "output_path": output_path,
            "subtitle_bar_height": int(detected_height)
        }
