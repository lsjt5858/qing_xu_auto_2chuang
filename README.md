# 视频分析工具

一个强大的视频分析工具，支持：
- 🎬 自动分镜：智能检测场景变化，分割成独立视频
- 🎵 音频提取：提取视频中的音频轨道
- 📝 语音转文字：使用 AI 将音频转换为文字文案（支持中文）
- 📦 批量处理：支持一次处理多个视频
- 🌐 视频下载：支持从抖音、YouTube、B站等平台下载视频

## 快速开始

### 安装

```bash
# 1. 克隆项目
git clone https://github.com/lsjt5858/chai_shi_pin.git
cd chai_shi_pin

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装 ffmpeg（macOS）
brew install ffmpeg
```

### 基本使用

#### 1. 分析本地视频
```bash
./run.sh video.mp4
```

#### 2. 从链接下载并分析

**注意：抖音下载需要登录，推荐使用方式 3**

```bash
# YouTube 视频（无需登录）
./run.sh https://www.youtube.com/watch?v=xxx -d

# B站视频（无需登录）
./run.sh https://www.bilibili.com/video/BVxxx -d
```

#### 3. 批量处理（推荐）

**方式 A：使用抖音官方下载**
1. 在抖音 App 中：分享 → 保存本地
2. 将下载的视频放到项目目录
3. 运行：
```bash
./run.sh video1.mp4 video2.mp4
```

**方式 B：从链接下载（仅支持 YouTube、B站等无需登录的平台）**
1. 创建 `urls.txt` 文件：
```txt
# YouTube 视频
https://www.youtube.com/watch?v=xxx

# B站视频
https://www.bilibili.com/video/BVxxx

# 本地文件
video.mp4
```

2. 运行：
```bash
./run.sh --list urls.txt -d
```

## 常用命令

```bash
# 完整分析（分镜+音频+文案）
./run.sh video.mp4

# 批量处理（使用通配符）
./run.sh test_videos/*.mp4

# 使用列表文件
./run.sh --list urls.txt

# 只下载视频
./run.sh https://www.youtube.com/watch?v=xxx --download-only

# 只分割场景
./run.sh video.mp4 --scenes-only

# 只提取音频和文案
./run.sh video.mp4 --audio-only

# 使用更精确的语音识别
./run.sh video.mp4 --whisper-model medium

# 调整场景检测灵敏度
./run.sh video.mp4 -t 15  # 更多分镜
./run.sh video.mp4 -t 35  # 更少分镜
```

## 参数说明

- `videos`: 输入视频文件路径或链接（可以多个）
- `-l, --list`: 包含视频路径/链接列表的文本文件
- `-d, --download`: 启用下载功能
- `--download-only`: 只下载视频，不进行分析
- `-o, --output`: 输出根目录（默认: output）
- `-t, --threshold`: 场景检测阈值 0-255（默认: 27）
- `--scenes-only`: 只分割场景
- `--audio-only`: 只提取音频和文案
- `--whisper-model`: 语音识别模型
  - `tiny`: 最快，准确度较低
  - `base`: 平衡（默认）
  - `small`: 较准确
  - `medium`: 很准确
  - `large`: 最准确，但很慢

## 输出结构

```
downloads/                  # 下载的视频（使用 -d 时）
├── 视频标题1.mp4
└── 视频标题2.mp4

output/                     # 分析结果
├── video1_20260406_143022/
│   ├── scenes/            # 分镜视频
│   │   ├── Scene-001.mp4
│   │   ├── Scene-002.mp4
│   │   └── ...
│   ├── audio.mp3          # 音频
│   ├── transcript.txt     # 完整文案
│   ├── transcript_detailed.json  # 带时间戳的文案
│   └── report.json        # 分析报告
└── video2_20260406_143045/
    └── ...
```

## 支持的平台

### 完全支持（无需登录）
- ✅ YouTube
- ✅ B站（Bilibili）
- ✅ Vimeo
- ✅ 以及其他 1000+ 平台

### 不支持在线下载（需要手动下载）
- ❌ 抖音（Douyin）- 请使用官方下载功能
- ❌ 快手 - 请使用官方下载功能
- ❌ 小红书 - 请使用官方下载功能

### 推荐方式：手动下载 + 本工具分析
1. 在 App 中使用官方下载功能（分享 → 保存本地）
2. 将下载的视频用本工具分析

## 项目结构

```
video-analyzer/
├── main.py                 # 主入口
├── src/                    # 源代码
│   ├── core/              # 核心功能（场景检测、音频提取、转录、下载）
│   ├── utils/             # 工具函数（批量处理、文件操作）
│   └── cli.py             # 命令行接口
├── config/                # 配置文件
├── tests/                 # 测试文件
└── docs/                  # 文档
```

## 作为 Python 包使用

```python
from src.core import VideoAnalyzer, VideoDownloader

# 下载视频
downloader = VideoDownloader()
video_path = downloader.download("https://v.douyin.com/xxx/")

# 分析视频
analyzer = VideoAnalyzer(video_path)
scenes = analyzer.analyze_scenes(threshold=27.0)
audio = analyzer.extract_audio()
transcript = analyzer.transcribe_audio(audio, model_size="base")
report = analyzer.generate_report(scenes, transcript)
```

## 常见问题

### Q: 第一次运行很慢？
A: Whisper 模型首次使用时需要下载（约 150MB），之后会缓存到本地

### Q: 下载抖音视频失败？
A: 抖音平台限制，无法直接下载。请使用：
1. **抖音官方下载**（推荐）：在 App 中点击分享 → 保存本地
2. **第三方下载工具**：使用专门的抖音下载器
3. 下载后使用本工具分析：`./run.sh video.mp4`

### Q: 下载功能需要什么？
A: 工具会自动安装 yt-dlp。如果失败，手动运行：`pip install -U yt-dlp`

### Q: 如何提高语音识别准确度？
A: 使用更大的模型，如 `--whisper-model medium`

### Q: 分镜太多或太少？
A: 调整 `-t` 参数，值越小分镜越多，值越大分镜越少

### Q: 可以直接粘贴抖音分享文本吗？
A: 工具会尝试提取链接，但抖音无法直接下载。建议使用官方下载功能后再分析

## 文档

- [架构文档](docs/ARCHITECTURE.md) - 项目架构和扩展指南
- [API 文档](docs/API.md) - 编程接口文档
- [贡献指南](docs/CONTRIBUTING.md) - 如何贡献代码

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License
