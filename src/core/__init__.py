"""
Core package exports.

Keep imports lazy so utility scripts are not forced to import heavy optional
dependencies such as scenedetect or whisper.
"""

__all__ = [
    "VideoAnalyzer",
    "SceneDetector",
    "AudioExtractor",
    "Transcriber",
    "VideoDownloader",
    "SubtitleRemover",
]


def __getattr__(name):
    if name == "VideoAnalyzer":
        from .video_analyzer import VideoAnalyzer

        return VideoAnalyzer
    if name == "SceneDetector":
        from .scene_detector import SceneDetector

        return SceneDetector
    if name == "AudioExtractor":
        from .audio_extractor import AudioExtractor

        return AudioExtractor
    if name == "Transcriber":
        from .transcriber import Transcriber

        return Transcriber
    if name == "VideoDownloader":
        from .video_downloader import VideoDownloader

        return VideoDownloader
    if name == "SubtitleRemover":
        from .subtitle_remover import SubtitleRemover

        return SubtitleRemover
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
