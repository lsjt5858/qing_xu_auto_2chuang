"""
Utility package exports.

Avoid importing the full processing pipeline at package import time.
"""

from .file_utils import ensure_dir, read_video_list

__all__ = ["read_video_list", "ensure_dir", "BatchProcessor"]


def __getattr__(name):
    if name == "BatchProcessor":
        from .batch_processor import BatchProcessor

        return BatchProcessor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
