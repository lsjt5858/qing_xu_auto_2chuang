"""
视频下载模块 - 支持从多个平台下载视频
"""
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit


class VideoDownloader:
    """视频下载器 - 支持抖音、YouTube 等平台"""
    
    def __init__(self, output_dir="downloads"):
        """
        初始化下载器
        
        Args:
            output_dir: 下载目录
        """
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_url(url):
        """移除复制自 shell 命令时残留在 URL 中的常见转义符。"""
        return re.sub(r"\\([?&=])", r"\1", str(url).strip())
    
    def check_yt_dlp(self):
        """检查 yt-dlp 是否已安装"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "yt_dlp", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
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
        url = self._normalize_url(url)
        parsed_url = url if "://" in url else f"https://{url}"
        parsed = urlsplit(parsed_url)
        hostname = (parsed.hostname or "").lower()
        is_douyin = hostname == "douyin.com" or hostname.endswith(".douyin.com")

        if is_douyin and parsed.path.startswith("/search/"):
            print("✗ 下载失败: 当前不支持抖音搜索页")
            print("请提供单个视频链接，例如 https://www.douyin.com/video/作品ID 或抖音分享短链")
            return None

        if not self.check_yt_dlp():
            print("✗ 当前 Python 环境未安装 yt-dlp")
            print("请执行: pip install -r requirements.txt")
            return None
        
        print(f"\n正在下载: {url}")

        output_template = self.output_dir / (filename or "%(title)s.%(ext)s")
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--no-playlist",
            "--no-simulate",
            "--no-progress",
            "--print",
            "after_move:filepath",
            "-o",
            str(output_template),
        ]

        uses_browser_cookies = any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in ("douyin.com", "tiktok.com")
        )
        if uses_browser_cookies:
            cmd.extend(["--cookies-from-browser", "chrome"])

        cmd.append(url)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                for line in reversed(result.stdout.splitlines()):
                    candidate = Path(line.strip()).expanduser()
                    if not candidate.is_absolute():
                        candidate = self.output_dir / candidate
                    candidate = candidate.resolve()
                    if candidate.is_file():
                        print(f"✓ 下载成功: {candidate.name}")
                        return str(candidate)
                print("✗ 下载失败: yt-dlp 未返回有效的下载文件路径")
                return None
            else:
                error_msg = (result.stderr or result.stdout or "").strip()
                error_lower = error_msg.lower()
                
                if is_douyin and (
                    "fresh cookies" in error_lower
                    or "http error 403" in error_lower
                ):
                    print("✗ 下载失败: 抖音返回 HTTP 403；Chrome Cookie 已读取，但请求仍被拒绝")
                    print("可能原因: Chrome 登录资料不匹配、抖音风控或签名校验失败")
                    print("\n解决方法：")
                    print("1. 确认当前 Chrome 用户资料中可以正常播放该视频")
                    print("2. 若网页可播放但仍返回 403，说明当前 yt-dlp 路径被抖音风控拦截")
                    print("3. 不要把 Cookie 粘贴到命令、配置文件或聊天中")
                elif "cookies" in error_lower or "login" in error_lower:
                    print(f"✗ 下载失败: 需要登录")
                    print("\n解决方法：")
                    print("1. 在浏览器中登录抖音")
                    print("2. 重新运行命令")
                    print("或者使用其他下载工具（如：抖音官方下载、第三方下载器）")
                else:
                    print(f"✗ 下载失败: {error_msg[:500]}")
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

        failed_count = len(urls) - len(downloaded_files)
        print(f"\n{'='*60}")
        if not failed_count:
            print("下载完成！")
        elif not downloaded_files:
            print("下载失败！")
        else:
            print("批量下载结束，部分链接失败！")
        print(f"成功: {len(downloaded_files)}/{len(urls)}")
        if failed_count:
            print(f"失败: {failed_count}/{len(urls)}")
        print(f"{'='*60}\n")
        
        return downloaded_files
