"""
视频字幕去除模块 - 去除底部黑边中的烧录字幕，并清理底部区域的固定半透明水印
"""
import os
import shutil
import statistics
import subprocess
import tempfile

import cv2
import numpy as np


class SubtitleRemover:
    """通过 ffmpeg 滤镜链清理底部字幕黑边和底部固定半透明水印"""

    WATERMARK_SEARCH_START_RATIO = 0.62
    WATERMARK_SEARCH_HEIGHT_RATIO = 0.22
    WATERMARK_SEARCH_BOTTOM_MARGIN = 6
    WATERMARK_VOTE_RATIO = 0.45
    WATERMARK_GRAY_MIN = 55
    WATERMARK_GRAY_MAX = 235
    WATERMARK_SAT_MAX = 120
    WATERMARK_TOPHAT_MIN = 6
    WATERMARK_MIN_COMPONENT_AREA = 4
    WATERMARK_MAX_COMPONENT_RATIO = 0.01
    WATERMARK_MAX_COMPONENT_WIDTH_RATIO = 0.35
    WATERMARK_MAX_COMPONENT_HEIGHT_RATIO = 0.8
    WATERMARK_COMPONENT_LINK_X_RATIO = 0.02
    WATERMARK_COMPONENT_LINK_Y_RATIO = 0.06

    def __init__(
        self,
        sample_frames=12,
        dark_threshold=20,
        dark_pixel_ratio=0.9,
        min_bar_height=30,
        max_bar_ratio=0.25,
        enable_watermark_cleanup=True,
        watermark_mask_min_area=120,
        watermark_mask_max_area=3000
    ):
        self.sample_frames = sample_frames
        self.dark_threshold = dark_threshold
        self.dark_pixel_ratio = dark_pixel_ratio
        self.min_bar_height = min_bar_height
        self.max_bar_ratio = max_bar_ratio
        self.enable_watermark_cleanup = enable_watermark_cleanup
        self.watermark_mask_min_area = watermark_mask_min_area
        self.watermark_mask_max_area = watermark_mask_max_area

    @staticmethod
    def _build_sample_positions(frame_count, sample_frames):
        """根据总帧数生成均匀采样位置。"""
        if frame_count <= 0:
            return [0]

        step = max(frame_count // sample_frames, 1)
        positions = list(range(0, frame_count, step))[:sample_frames]
        if (frame_count - 1) not in positions:
            positions.append(frame_count - 1)
        return positions

    @staticmethod
    def _scale_rect(rect, frame_width, frame_height):
        """把相对坐标矩形转换成当前分辨率下的像素矩形。"""
        x = max(0, int(round(frame_width * rect["x"])))
        y = max(0, int(round(frame_height * rect["y"])))
        width = max(1, int(round(frame_width * rect["w"])))
        height = max(1, int(round(frame_height * rect["h"])))

        width = min(width, frame_width - x)
        height = min(height, frame_height - y)
        return x, y, width, height

    @staticmethod
    def _escape_ffmpeg_filter_value(value):
        """转义 ffmpeg 滤镜参数中的特殊字符。"""
        escaped = (
            value
            .replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace(",", "\\,")
            .replace(";", "\\;")
            .replace("[", "\\[")
            .replace("]", "\\]")
        )
        return f"'{escaped}'"

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
        sample_positions = self._build_sample_positions(frame_count, self.sample_frames)

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

    def _build_watermark_search_window(self, frame_width, frame_height, subtitle_bar_height=0):
        """在底部区域中生成水印搜索窗口。"""
        search_bottom = max(
            0,
            frame_height - max(int(subtitle_bar_height or 0), 0) - self.WATERMARK_SEARCH_BOTTOM_MARGIN
        )
        search_top = max(
            int(frame_height * self.WATERMARK_SEARCH_START_RATIO),
            search_bottom - int(frame_height * self.WATERMARK_SEARCH_HEIGHT_RATIO)
        )

        search_height = search_bottom - search_top
        if search_height < 20:
            return None

        return (0, search_top, int(frame_width), search_height)

    def _build_watermark_candidate_mask(self, roi):
        """从底部搜索窗口内提取可能属于水印的细亮笔画。"""
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (0, 0), 5)
        tophat = cv2.subtract(gray, blur)

        gray_mask = cv2.inRange(gray, self.WATERMARK_GRAY_MIN, self.WATERMARK_GRAY_MAX)
        sat_mask = cv2.inRange(hsv[:, :, 1], 0, self.WATERMARK_SAT_MAX)
        tophat_mask = cv2.inRange(tophat, self.WATERMARK_TOPHAT_MIN, 255)
        return cv2.bitwise_and(cv2.bitwise_and(gray_mask, sat_mask), tophat_mask)

    def _select_best_watermark_cluster(self, mask, search_width, search_height):
        """从候选掩码里选出最像固定水印的一组连通组件。"""
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
        components = []

        max_component_area = int(search_width * search_height * self.WATERMARK_MAX_COMPONENT_RATIO)
        max_component_width = int(search_width * self.WATERMARK_MAX_COMPONENT_WIDTH_RATIO)
        max_component_height = int(search_height * self.WATERMARK_MAX_COMPONENT_HEIGHT_RATIO)

        for component_index in range(1, num_labels):
            x, y, width, height, area = stats[component_index]
            if area < self.WATERMARK_MIN_COMPONENT_AREA or area > max_component_area:
                continue
            if width > max_component_width or height > max_component_height:
                continue

            components.append({
                "idx": component_index,
                "x": int(x),
                "y": int(y),
                "w": int(width),
                "h": int(height),
                "area": int(area),
                "cx": float(centroids[component_index][0]),
                "cy": float(centroids[component_index][1])
            })

        if not components:
            return np.zeros_like(mask)

        expand_x = max(10, int(search_width * self.WATERMARK_COMPONENT_LINK_X_RATIO))
        expand_y = max(6, int(search_height * self.WATERMARK_COMPONENT_LINK_Y_RATIO))
        parents = list(range(len(components)))

        def find(index):
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left, right):
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        for left_index, left_component in enumerate(components):
            left_box = (
                left_component["x"] - expand_x,
                left_component["y"] - expand_y,
                left_component["x"] + left_component["w"] + expand_x,
                left_component["y"] + left_component["h"] + expand_y
            )
            for right_index in range(left_index + 1, len(components)):
                right_component = components[right_index]
                right_box = (
                    right_component["x"] - expand_x,
                    right_component["y"] - expand_y,
                    right_component["x"] + right_component["w"] + expand_x,
                    right_component["y"] + right_component["h"] + expand_y
                )

                if not (
                    left_box[2] < right_box[0]
                    or right_box[2] < left_box[0]
                    or left_box[3] < right_box[1]
                    or right_box[3] < left_box[1]
                ):
                    union(left_index, right_index)

        groups = {}
        for component_index, component in enumerate(components):
            root = find(component_index)
            groups.setdefault(root, []).append(component)

        best_group = None
        for group in groups.values():
            total_area = sum(component["area"] for component in group)
            weighted_y = sum(component["cy"] * component["area"] for component in group) / total_area
            score = (total_area, weighted_y)
            if best_group is None or score > best_group["score"]:
                best_group = {
                    "components": group,
                    "score": score
                }

        selected_mask = np.zeros_like(mask)
        if not best_group:
            return selected_mask

        for component in best_group["components"]:
            selected_mask[labels == component["idx"]] = 255

        return cv2.dilate(selected_mask, np.ones((3, 3), dtype=np.uint8), iterations=1)

    def create_watermark_mask(self, video_path, temp_dir, subtitle_bar_height=0):
        """
        自动从采样帧中生成底部固定半透明水印掩码文件。

        Args:
            video_path: 视频路径
            temp_dir: 临时文件保存目录
            subtitle_bar_height: 已检测到底部黑边高度

        Returns:
            dict | None: 掩码信息，未检测到则返回 None
        """
        if not self.enable_watermark_cleanup:
            return None

        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")

        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        sample_positions = self._build_sample_positions(frame_count, min(self.sample_frames, 8))
        search_window = self._build_watermark_search_window(
            frame_width,
            frame_height,
            subtitle_bar_height=subtitle_bar_height
        )

        if search_window is None:
            capture.release()
            return None

        _, search_top, search_width, search_height = search_window
        candidate_votes = []

        try:
            for frame_index in sample_positions:
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                success, frame = capture.read()
                if not success or frame is None:
                    continue

                roi = frame[search_top:search_top + search_height, 0:search_width]
                if roi.size == 0:
                    continue
                candidate_votes.append(self._build_watermark_candidate_mask(roi) > 0)
        finally:
            capture.release()

        if len(candidate_votes) < 3:
            return None

        vote_threshold = max(
            3,
            int(np.ceil(len(candidate_votes) * self.WATERMARK_VOTE_RATIO))
        )
        persistent_mask = (
            np.stack(candidate_votes).sum(axis=0) >= vote_threshold
        ).astype(np.uint8) * 255

        selected_mask = self._select_best_watermark_cluster(
            persistent_mask,
            search_width,
            search_height
        )
        mask_area = int(cv2.countNonZero(selected_mask))
        if not (self.watermark_mask_min_area <= mask_area <= self.watermark_mask_max_area):
            return None

        full_mask = np.zeros((frame_height, frame_width), dtype=np.uint8)
        full_mask[search_top:search_top + search_height, 0:search_width] = selected_mask

        os.makedirs(temp_dir, exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".png",
            prefix="watermark_mask_",
            dir=temp_dir,
            delete=False
        )
        temp_file.close()

        if not cv2.imwrite(temp_file.name, full_mask):
            os.unlink(temp_file.name)
            raise RuntimeError("生成水印掩码文件失败。")

        return {
            "path": temp_file.name,
            "mask_area": mask_area
        }

    @classmethod
    def build_watermark_cleanup_filters(cls, mask_path, video_width, video_height):
        """
        构建底部固定水印清理滤镜。

        Args:
            mask_path: removelogo 使用的掩码文件
            video_width: 视频宽度
            video_height: 视频高度

        Returns:
            list[str]: ffmpeg 滤镜列表
        """
        del video_width
        del video_height
        return [f"removelogo=f={cls._escape_ffmpeg_filter_value(mask_path)}"]

    @staticmethod
    def normalize_bar_height(subtitle_bar_height):
        """把黑边高度归一为偶数，避免 yuv420p 编码时输出尺寸被截断。"""
        if not subtitle_bar_height or subtitle_bar_height <= 0:
            return 0
        return int(subtitle_bar_height) if subtitle_bar_height % 2 == 0 else int(subtitle_bar_height) + 1

    @staticmethod
    def build_video_filter(subtitle_bar_height, pre_filters=None):
        """
        构建 ffmpeg 视频滤镜

        Args:
            subtitle_bar_height: 需要移除的底部高度
            pre_filters: 追加在裁剪前的滤镜列表

        Returns:
            str: ffmpeg filter 字符串
        """
        filters = list(pre_filters or [])

        if subtitle_bar_height and subtitle_bar_height > 0:
            normalized_height = SubtitleRemover.normalize_bar_height(subtitle_bar_height)
            filters.extend([
                f"crop=iw:ih-{normalized_height}:0:0",
                f"pad=iw:ih+{normalized_height}:0:0:black"
            ])

        if not filters:
            raise ValueError("至少需要一个有效的视频处理滤镜。")

        return ",".join(filters)

    def remove(self, video_path, output_path, subtitle_bar_height=None):
        """
        生成去字幕/去水印视频

        Args:
            video_path: 原视频路径
            output_path: 输出视频路径
            subtitle_bar_height: 手动指定字幕黑边高度

        Returns:
            dict: 输出结果
        """
        output_dir = os.path.dirname(output_path) or "."
        os.makedirs(output_dir, exist_ok=True)

        detected_height = subtitle_bar_height
        if detected_height is None:
            detected_height = self.detect_subtitle_bar_height(video_path)

        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")

        video_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        video_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        capture.release()

        watermark_info = self.create_watermark_mask(
            video_path,
            output_dir,
            subtitle_bar_height=self.normalize_bar_height(detected_height)
        )
        pre_filters = []
        temp_files = []

        try:
            if watermark_info:
                pre_filters = self.build_watermark_cleanup_filters(
                    watermark_info["path"],
                    video_width,
                    video_height
                )
                temp_files.append(watermark_info["path"])

            if not pre_filters and (not detected_height or detected_height <= 0):
                shutil.copy2(video_path, output_path)
                return {
                    "output_path": output_path,
                    "subtitle_bar_height": 0,
                    "watermark_removed": False,
                    "watermark_mask_area": 0,
                    "processing_skipped": True
                }

            cmd = [
                "ffmpeg",
                "-y",
                "-i", video_path,
                "-vf", self.build_video_filter(detected_height, pre_filters=pre_filters),
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
                raise RuntimeError(f"ffmpeg 去字幕/去水印失败: {error[:500]}")
        finally:
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

        return {
            "output_path": output_path,
            "subtitle_bar_height": int(detected_height or 0),
            "watermark_removed": bool(pre_filters),
            "watermark_mask_area": int(watermark_info["mask_area"]) if watermark_info else 0,
            "processing_skipped": False
        }
