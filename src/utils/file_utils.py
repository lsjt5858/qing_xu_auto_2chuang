"""
文件处理工具函数
"""
import os


def read_video_list(list_file):
    """
    从文件读取视频路径列表，支持提取抖音分享链接
    
    Args:
        list_file: 列表文件路径
        
    Returns:
        list: 视频路径/链接列表
    """
    import re
    videos = []
    
    with open(list_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 按行处理，但保留完整的分享文本
    lines = content.split('\n')
    current_text = ""
    
    for line in lines:
        line = line.strip()
        
        # 跳过空行和注释
        if not line or line.startswith('#'):
            # 如果之前有累积的文本，处理它
            if current_text:
                process_line(current_text, videos)
                current_text = ""
            continue
        
        # 累积文本（处理多行分享文本）
        current_text += " " + line if current_text else line
        
        # 如果包含 URL，处理并清空
        if re.search(r'https?://', current_text):
            process_line(current_text, videos)
            current_text = ""
    
    # 处理最后一行
    if current_text:
        process_line(current_text, videos)
    
    return videos


def process_line(text, videos):
    """
    处理单行文本，提取 URL 或文件路径
    
    Args:
        text: 文本内容
        videos: 视频列表（会被修改）
    """
    import re
    
    # 尝试提取 URL
    url_match = re.search(r'https?://[^\s]+', text)
    if url_match:
        url = url_match.group(0)
        # 清理末尾可能的标点符号和特殊字符
        url = re.sub(r'[.,;!?\s]+$', '', url)
        videos.append(url)
    else:
        # 如果没有找到 URL，当作本地文件路径
        # 但要确保不是分享文本的碎片
        if not any(keyword in text for keyword in ['复制', '打开', '抖音', '看看', '作品']):
            videos.append(text)


def ensure_dir(directory):
    """
    确保目录存在，不存在则创建
    
    Args:
        directory: 目录路径
    """
    os.makedirs(directory, exist_ok=True)
