# 快速开始指南

## 安装

```bash
# 1. 克隆或下载项目
cd video-analyzer

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装 ffmpeg（macOS）
brew install ffmpeg
```

## 基本使用

### 单个视频

```bash
# 完整分析
./run.sh video.mp4

# 只分镜
./run.sh video.mp4 --scenes-only

# 只音频+文案
./run.sh video.mp4 --audio-only
```

### 批量处理

#### 方式 1: 命令行
```bash
./run.sh video1.mp4 video2.mp4 video3.mp4
```

#### 方式 2: 列表文件（推荐）
1. 创建 `videos.txt`:
```txt
video1.mp4
video2.mp4
video3.mp4
```

2. 运行:
```bash
./run.sh --list videos.txt
```

## 输出结构

```
output/
├── video1_20260406_143022/
│   ├── scenes/
│   │   ├── Scene-001.mp4
│   │   ├── Scene-002.mp4
│   │   └── ...
│   ├── audio.mp3
│   ├── transcript.txt
│   ├── transcript_detailed.json
│   └── report.json
└── video2_20260406_143045/
    └── ...
```

## 常用参数

```bash
# 更多分镜（更敏感）
./run.sh video.mp4 -t 15

# 更少分镜（不敏感）
./run.sh video.mp4 -t 35

# 更准确的语音识别
./run.sh video.mp4 --whisper-model medium

# 自定义输出目录
./run.sh video.mp4 -o my_output
```

## 完整示例

```bash
# 批量处理，使用精确识别，更多分镜
./run.sh --list videos.txt --whisper-model medium -t 20
```

## 作为 Python 包使用

```python
from src.core import VideoAnalyzer

# 创建分析器
analyzer = VideoAnalyzer("video.mp4")

# 分析场景
scenes = analyzer.analyze_scenes(threshold=27.0)

# 提取音频
audio = analyzer.extract_audio()

# 转录音频
transcript = analyzer.transcribe_audio(audio, model_size="base")

# 生成报告
report = analyzer.generate_report(scenes, transcript)
```

## 下一步

- 查看 [USAGE.md](USAGE.md) 了解详细使用方法
- 查看 [docs/API.md](docs/API.md) 了解编程接口
- 查看 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 了解项目架构

## 常见问题

### Q: 第一次运行很慢？
A: Whisper 模型首次使用时需要下载（约 150MB），之后会缓存到本地

### Q: 如何提高语音识别准确度？
A: 使用更大的模型，如 `--whisper-model medium`

### Q: 视频没有音频怎么办？
A: 工具会自动检测，如果没有音频会跳过音频处理步骤

### Q: 分镜太多或太少？
A: 调整 `-t` 参数，值越小分镜越多，值越大分镜越少

## 获取帮助

```bash
# 查看帮助信息
./run.sh --help

# 或
python main.py --help
```
