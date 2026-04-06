# 视频分析工具

一个强大的视频分析工具，支持：
- 🎬 自动分镜：智能检测场景变化，分割成独立视频
- 🎵 音频提取：提取视频中的音频轨道
- 📝 语音转文字：使用 AI 将音频转换为文字文案（支持中文）
- 📦 批量处理：支持一次处理多个视频

## 项目结构

```
video-analyzer/
├── main.py                 # 主入口
├── src/                    # 源代码
│   ├── core/              # 核心功能（场景检测、音频提取、转录）
│   ├── utils/             # 工具函数（批量处理、文件操作）
│   └── cli.py             # 命令行接口
├── config/                # 配置文件
├── tests/                 # 测试文件
└── docs/                  # 文档
```

详细架构请查看 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 功能特点

- 自动检测视频场景变化并分割
- 提取高质量音频文件
- AI 语音识别（基于 OpenAI Whisper）
- 生成带时间戳的文案
- 输出完整的 JSON 分析报告
- 支持批量处理多个视频
- 每个视频独立输出文件夹

## 快速开始

### 安装

1. 创建虚拟环境：
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 安装 ffmpeg（macOS）：
```bash
brew install ffmpeg
```

### 使用

#### 单个视频
```bash
./run.sh your_video.mp4
```

#### 批量处理
```bash
# 方式 1: 命令行直接指定
./run.sh video1.mp4 video2.mp4 video3.mp4

# 方式 2: 使用视频列表文件
./run.sh --list videos.txt
```

更多使用方法请查看 [QUICK_START.md](QUICK_START.md) 和 [USAGE.md](USAGE.md)

## 参数说明

- `videos`: 输入视频文件路径（可以多个）
- `-l, --list`: 包含视频路径列表的文本文件
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

## 输出文件结构

每个视频都会创建独立的文件夹：

```
output/
├── video1_20260406_143022/          # 视频1的输出文件夹
│   ├── scenes/                      # 分镜视频
│   │   ├── Scene-001.mp4
│   │   ├── Scene-002.mp4
│   │   └── ...
│   ├── audio.mp3                    # 音频
│   ├── transcript.txt               # 完整文案
│   ├── transcript_detailed.json     # 带时间戳的文案
│   └── report.json                  # 分析报告
└── video2_20260406_143045/          # 视频2的输出文件夹
    └── ...
```

## 工作原理

1. **场景检测**：分析视频帧之间的内容差异，识别镜头切换
2. **音频提取**：使用 ffmpeg 提取高质量音频
3. **语音识别**：使用 OpenAI Whisper AI 模型转录音频

## 开发

### 运行测试
```bash
python -m unittest discover tests
```

### 作为 Python 包使用
```python
from src.core import VideoAnalyzer

analyzer = VideoAnalyzer("video.mp4")
scenes = analyzer.analyze_scenes()
audio = analyzer.extract_audio()
transcript = analyzer.transcribe_audio(audio)
```

查看 [docs/API.md](docs/API.md) 了解完整 API 文档。

## 文档

- [快速开始](QUICK_START.md) - 快速上手指南
- [使用文档](USAGE.md) - 详细使用说明
- [架构文档](docs/ARCHITECTURE.md) - 项目架构和扩展指南
- [API 文档](docs/API.md) - 编程接口文档
- [贡献指南](docs/CONTRIBUTING.md) - 如何贡献代码
- [更新日志](CHANGELOG.md) - 版本更新记录

## 贡献

欢迎提交 Issue 和 Pull Request！

查看 [CONTRIBUTING.md](docs/CONTRIBUTING.md) 了解如何贡献。

## 许可证

MIT License
