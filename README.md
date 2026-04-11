# 柴视频

批量视频混剪素材处理工具。自动清洗源视频、拆分镜、提取文案，为二次混剪生产准备好素材。

## 它做什么

将一批原始短视频（如抖音情绪类视频）自动处理成可直接混剪的素材：

```
原始视频 → 去字幕/去水印 → 分镜拆分 → 音频提取 → 语音转文字 → 剪映草稿
                ↓                ↓
         干净的源素材        可组合的分镜片段
```

## 核心功能

- **去字幕/去水印** — 自动检测并裁切底部烧录字幕，清理固定半透明水印
- **分镜检测** — 基于场景变化自动拆分为独立片段（Scene-001、Scene-002...）
- **音频提取 + 语音转文字** — Whisper 转录，输出完整文案和带时间戳的详细文案
- **分镜收集** — `collect_scenes.sh` 自动将 Scene-001 归为「视频头」，其余归为「视频身」
- **剪映草稿导出** — 将分镜结果直接导出为剪映可编辑的草稿工程
- **批量处理** — 支持多文件、整个目录、URL 列表文件

## 安装

```bash
git clone https://github.com/lsjt5858/chai_shi_pin.git
cd chai_shi_pin

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
brew install ffmpeg   # macOS
```

## 快速开始

### 完整处理流程

```bash
# 处理单个视频（去字幕 → 分镜 → 音频 → 文案）
./run.sh video.mp4

# 处理整个目录
./run.sh test_videos/

# 批量处理多个文件
./run.sh video1.mp4 video2.mp4 video3.mp4
```

### 只跑部分步骤

```bash
./run.sh video.mp4 --remove-subtitles-only   # 只去字幕/去水印
./run.sh video.mp4 --scenes-only              # 去字幕 + 分镜（不处理音频）
./run.sh video.mp4 --audio-only               # 去字幕 + 音频 + 文案（不分镜）
```

### 调参

```bash
./run.sh video.mp4 -t 15                     # 更多分镜（阈值越小分镜越多）
./run.sh video.mp4 -t 35                     # 更少分镜
./run.sh video.mp4 --whisper-model medium    # 更准确的语音识别
./run.sh video.mp4 --subtitle-bar-height 80  # 手动指定字幕区域高度（像素）
```

### 收集分镜素材

处理完一批视频后，一键收集所有分镜：

```bash
./collect_scenes.sh
# Scene-001 → 视频头目录（开场片段）
# 其余 Scene → 视频身目录（正文片段）
```

### 导入剪映

```bash
# 将分镜导出为剪映草稿工程
python -m src.utils.jianying_draft_exporter output/某个视频目录
```

### 下载视频

```bash
# YouTube / B站等无需登录的平台
./run.sh https://www.youtube.com/watch?v=xxx -d
./run.sh https://www.bilibili.com/video/BVxxx -d

# 只下载不分析
./run.sh https://www.youtube.com/watch?v=xxx --download-only

# 从列表文件批量下载
./run.sh --list urls.txt -d
```

> **抖音/快手/小红书无法在线下载**，请在 App 中「分享 → 保存本地」后用 `./run.sh video.mp4` 处理。

## 参数一览

| 参数 | 说明 |
|------|------|
| `videos` | 视频文件路径、目录或链接（可多个） |
| `-l, --list` | 包含路径/链接的文本文件 |
| `-d, --download` | 启用下载 |
| `--download-only` | 只下载，不分析 |
| `-o, --output` | 输出根目录（默认 `output`） |
| `-t, --threshold` | 场景检测阈值 0–255（默认 27，越小分镜越多） |
| `--remove-subtitles` | 启用去字幕/去水印（`run.sh` 已默认启用） |
| `--remove-subtitles-only` | 只输出去字幕视频 |
| `--subtitle-bar-height` | 手动指定字幕黑边高度（像素） |
| `--scenes-only` | 只做分镜（仍会先去字幕） |
| `--audio-only` | 只做音频+文案（仍会先去字幕） |
| `--whisper-model` | `tiny` / `base`（默认）/ `small` / `medium` / `large` |

## 输出结构

```
output/{视频名}_{时间戳}/
├── video_no_subtitles.mp4      # 清洗后的视频（已去字幕、去水印）
├── scenes/                     # 分镜片段（可直接用于混剪）
│   ├── Scene-001.mp4
│   ├── Scene-002.mp4
│   └── ...
├── audio.mp3                   # 提取的音频
├── transcript.txt              # 完整文案
├── transcript_detailed.json    # 带时间戳的文案
└── report.json                 # 分析报告
```

## 混剪工作流

典型的混剪生产流程：

1. **收集源视频** — 从抖音 App 保存到本地
2. **批量清洗** — `./run.sh *.mp4` 自动去字幕、去水印、分镜、提文案
3. **收集分镜** — `./collect_scenes.sh` 将所有视频的开场和正文分镜分类归档
4. **导入剪映** — 用 `jianying_draft_exporter.py` 导出为剪映草稿，或手动挑选分镜组合
5. **二次创作** — 在剪映中组合分镜、替换文案、添加配乐

## 项目结构

```
main.py                        # 入口
run.sh                         # 激活 venv + 默认启用去字幕
collect_scenes.sh              # 收集分镜到外部目录
src/
├── cli.py                     # 命令行参数、流程调度
├── core/
│   ├── video_analyzer.py      # 主控类，串联处理步骤
│   ├── subtitle_remover.py    # 去字幕 + 去水印
│   ├── scene_detector.py      # 分镜检测与分割
│   ├── audio_extractor.py     # 音频提取
│   ├── transcriber.py         # Whisper 语音转文字
│   └── video_downloader.py    # yt-dlp 下载
└── utils/
    ├── batch_processor.py     # 批量处理
    ├── file_utils.py          # 文件工具
    └── jianying_draft_exporter.py  # 剪映草稿导出
```

## 常见问题

**首次运行慢？** Whisper 模型首次下载约 150MB，之后会缓存。

**抖音下载失败？** 抖音无法直接下载，请在 App 中「分享 → 保存本地」后处理。

**分镜太多/太少？** 调整 `-t` 参数，值越小分镜越多。

**路径含空格报错？** 用英文双引号包裹整个路径：`./run.sh "path/with spaces/video.mp4"`

## 技术栈

Python 3.12 · OpenCV (scenedetect) · OpenAI Whisper · MoviePy · pydub · yt-dlp

## 许可证

MIT License
