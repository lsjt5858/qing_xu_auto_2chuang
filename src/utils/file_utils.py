"""
文件处理工具函数
"""
import os


def read_video_list(list_file):
    """
    从文件读取视频路径列表
    
    Args:
        list_file: 列表文件路径
        
    Returns:
        list: 视频路径列表
    """
    videos = []
    with open(list_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 跳过空行和注释
            if line and not line.startswith('#'):
                videos.append(line)
    return videos


def ensure_dir(directory):
    """
    确保目录存在，不存在则创建
    
    Args:
        directory: 目录路径
    """
    os.makedirs(directory, exist_ok=True)
