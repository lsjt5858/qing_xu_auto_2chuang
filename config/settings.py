"""
全局配置设置
"""

# 默认配置
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_THRESHOLD = 27.0
DEFAULT_WHISPER_MODEL = "base"

# 场景检测配置
SCENE_DETECTION = {
    "threshold": DEFAULT_THRESHOLD,
    "min_scene_length": 0.5,  # 最小场景长度（秒）
}

# 音频配置
AUDIO = {
    "format": "mp3",
    "bitrate": "192k",
}

# 转录配置
TRANSCRIPTION = {
    "model": DEFAULT_WHISPER_MODEL,
    "language": "zh",  # 默认中文
}

# 输出配置
OUTPUT = {
    "scenes_folder": "scenes",
    "audio_filename": "audio.mp3",
    "transcript_filename": "transcript.txt",
    "transcript_detailed_filename": "transcript_detailed.json",
    "report_filename": "report.json",
}
