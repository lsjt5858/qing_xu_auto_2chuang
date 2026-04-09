"""
视频下载模块 - 支持从多个平台下载视频
"""
import os
import subprocess
from pathlib import Path


class VideoDownloader:
    """视频下载器 - 支持抖音、YouTube 等平台"""
    
    def __init__(self, output_dir="downloads"):
        """
        初始化下载器
        
        Args:
            output_dir: 下载目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def check_yt_dlp(self):
        """检查 yt-dlp 是否已安装"""
        try:
            result = subprocess.run(
                ["yt-dlp", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def install_yt_dlp(self):
        """安装 yt-dlp"""
        print("正在安装 yt-dlp...")
        try:
            subprocess.run(
                ["pip", "install", "-U", "yt-dlp"],
                check=True
            )
            print("✓ yt-dlp 安装成功")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ yt-dlp 安装失败: {e}")
            return False
    
    def download(self, url, filename=None):
        """
        下载单个视频
        
        Args:
            url: 视频链接
            filename: 自定义文件名（可选）
            
        Returns:
            str: 下载的视频文件路径，失败返回 None
        """
        if not self.check_yt_dlp():
            print("未检测到 yt-dlp，正在安装...")
            if not self.install_yt_dlp():
                print("请手动安装 yt-dlp: pip install -U yt-dlp")
                return None
        
        print(f"\n正在下载: {url}")
        
        # 构建下载命令
        cmd = [
            "yt-dlp",
            "--no-playlist",  # 不下载播放列表
            "-o", os.path.join(self.output_dir, "%(title)s.%(ext)s"),  # 输出模板
        ]
        
        # 如果是抖音链接，添加特殊处理
        if 'douyin.com' in url or 'tiktok.com' in url:
            # 使用浏览器 cookies
            cmd.extend(["--cookies-from-browser", "chrome"])
        
        # 如果指定了文件名
        if filename:
            cmd[-1] = os.path.join(self.output_dir, filename)
        
        cmd.append(url)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                # 查找下载的文件
                files = [f for f in Path(self.output_dir).glob("*") if not f.name.startswith('._')]
                if files:
                    latest_file = max(files, key=lambda x: x.stat().st_mtime)
                    print(f"✓ 下载成功: {latest_file.name}")
                    return str(latest_file)
                else:
                    print("✗ 下载失败: 找不到下载的文件")
                    return None
            else:
                error_msg = result.stderr
                
                # 检查是否是 cookies 问题
                if "cookies" in error_msg.lower() or "login" in error_msg.lower():
                    print(f"✗ 下载失败: 需要登录")
                    print("\n解决方法：")
                    print("1. 在浏览器中登录抖音")
                    print("2. 重新运行命令")
                    print("或者使用其他下载工具（如：抖音官方下载、第三方下载器）")
                else:
                    print(f"✗ 下载失败: {error_msg[:200]}")
                return None
                
        except subprocess.TimeoutExpired:
            print("✗ 下载超时")
            return None
        except Exception as e:
            print(f"✗ 下载出错: {str(e)}")
            return None
    
    def download_batch(self, urls):
        """
        批量下载视频
        
        Args:
            urls: 视频链接列表
            
        Returns:
            list: 成功下载的视频文件路径列表
        """
        downloaded_files = []
        
        print(f"\n{'='*60}")
        print(f"批量下载模式 - 共 {len(urls)} 个视频")
        print(f"{'='*60}\n")
        
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] 正在处理...")
            file_path = self.download(url)
            if file_path:
                downloaded_files.append(file_path)
        
        print(f"\n{'='*60}")
        print(f"下载完成！")
        print(f"成功: {len(downloaded_files)}/{len(urls)}")
        print(f"{'='*60}\n")
        
        return downloaded_files
