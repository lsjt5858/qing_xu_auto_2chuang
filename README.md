# 镜流工坊

镜流工坊是一套面向短视频二创的本地处理流水线。它可以把原始视频清洗、拆镜、转录并整理成统一产物，也可以基于镜头池重新编排画面，或按多个目录的顺序组装成 MP4，并生成可继续编辑的剪映草稿。

> 当前仓库名为 `qing_xu_auto_2chuang`。代码中仍保留少量历史命名，例如 `CHAI_FLAG_*` 和默认草稿名前缀 `chai_`。

## 核心能力

| 能力 | 当前实现 |
| --- | --- |
| 视频清洗 | 自动检测并移除底部字幕黑边，识别底部固定半透明水印并尝试清理 |
| 原始切镜 | 使用 PySceneDetect 自适应检测真实画面切换，保留长镜头 |
| 音频与文案 | 提取 `audio.mp3`，使用 Whisper 生成简体中文全文和时间戳分段 |
| AI 语义分镜 | 使用智谱或火山方舟视觉模型，将连续原始切镜聚合为剧情段落 |
| 镜头池混剪 | 保留原视频头部，按字幕节奏从镜头池补齐后续画面 |
| 多目录成片 | `run.sh compose` 按目录顺序选取完整视频/照片，生成 MP4，可加本地配乐和剪映草稿 |
| 剪映草稿 | 写入视频、音频、字幕和草稿索引，可直接在剪映中继续编辑 |
| 批量与下载 | 支持多个文件、目录、列表文件和 `yt-dlp` 视频链接 |

默认完整流程：

```text
输入视频
  -> 底部字幕黑边 / 固定水印清理
  -> 自适应切镜
  -> 音频提取
  -> Whisper 转录
  -> 可选：AI 剧情语义分镜
  -> 可选：镜头池重组
  -> 可选：剪映草稿
```

## 环境要求

- Python 3.10+
- FFmpeg 和 FFprobe
- macOS 上安装剪映专业版后可使用草稿导出
- AI 语义分镜需要智谱或火山方舟 API Key

安装：

```bash
git clone https://github.com/lsjt5858/qing_xu_auto_2chuang.git
cd qing_xu_auto_2chuang

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

brew install ffmpeg
```

`yt-dlp` 已包含在 `requirements.txt` 中。`run.sh` 会自动定位项目内的
`venv/bin/python`，因此可以从任意工作目录调用，但项目根目录必须存在名为
`venv` 的虚拟环境。

## 快速开始

### Web 工作台

React 工作台已连接本地 Python 服务、SQLite 任务队列和 Chrome 发布插件。
需要 Node.js 22.13+（22.x）或 24+，先安装并构建：

```bash
venv/bin/python -m pip install -r requirements-web.txt
npm --prefix apps/workbench ci
npm --prefix apps/workbench run build
./run.sh workbench --execute
```

打开 <http://127.0.0.1:8766>，即可导入本地视频、提交分镜/转录任务、
执行完整片段混剪、预览和下载成片。数据持久保存在 `data/workbench/`。
不加 `--execute` 仅显示启动配置。

抖音发布通过本机 Chrome 插件复用登录态，默认上传预填后等待人工确认；
直接发布需要逐条确认成片、文案和账号。插件安装、配对、真实发布的适配边界与验证范围见
[完整运行说明](docs/WORKBENCH_RUNTIME.md)；前端开发见
[工作台前端文档](apps/workbench/README.md)。

### 多个目录组装成片

例如 A 放视频头、B 放视频身、C 放视频尾。先预览选片计划：

```bash
./run.sh compose \
  --head-dir "/path/to/A" --head-count 1 \
  --body-dir "/path/to/B" --body-count 3 \
  --tail-dir "/path/to/C" --tail-count 1 \
  --seed 42 -o output/result.mp4
```

在同一命令末尾加 `--execute`，实际生成 `output/result.mp4` 和 `output/result.json`。
默认随机选择素材，**每条视频从开头完整使用**，总时长为选中视频和照片的时长之和。
`--seed` 只影响选片，不会随机截取视频内部位置；未指定时会自动生成并打印种子。

超过三段或混用视频、照片目录时，重复使用 `--part 目录 数量`，严格保持参数顺序：

```bash
./run.sh compose \
  --part "/path/to/开头" 1 \
  --part "/path/to/课堂视频" 3 \
  --part "/path/to/作品照片" 3 \
  --part "/path/to/作品视频" 3 \
  --part "/path/to/结尾照片" 1 \
  --photo-duration 2 \
  --bgm "/path/to/music.mp3" --bgm-volume 0.35 \
  --seed 42 -o output/montage.mp4 --execute
```

`--part` 与 head/body/tail 参数互斥。数量默认为 1（命名目录用法），`all` 选取全部；
`--selection ordered` 按文件路径排序选片，默认 `random`。每个目录内选片不重复。
目录递归扫描，忽略隐藏文件和隐藏子目录；素材不足或选中素材损坏会报错。

同时导出剪映草稿：

```bash
./run.sh compose \
  --head-dir "/path/to/A" --body-dir "/path/to/B" --tail-dir "/path/to/C" \
  --body-count 3 --seed 42 \
  --bgm "/path/to/music.mp3" --mute-source \
  --export-jianying --draft-root "/path/to/剪映草稿箱" --draft-name "目录混剪" \
  -o output/result_with_draft.mp4 --execute
```

成片和草稿使用相同的标准化片段与完整混音，短配乐会循环到结尾。草稿使用 `basic` 模板，
不需要语音识别或翻译；同名草稿会另建唯一目录。默认保留素材原声，`--mute-source` 可关闭。
照片默认展示 2 秒；输出默认 1920×1080、30fps，可用 `--width/--height/--fps` 调整，
宽高须为正偶数。不同画幅按比例缩放并补黑边。

仅当明确需要裁剪时，添加 `--clip-start 1 --clip-duration 3`：
所有选中视频从第 1 秒开始，最多取 3 秒；短视频取剩余时长，起点超过片长时报错。照片不受视频裁剪参数影响。

不加 `--execute` 不创建输出目录、不生成音视频、不写草稿或本机剪映配置。
未指定 `-o` 时生成带唯一标识的文件名；显式输出 MP4 或同名 JSON 已存在时拒绝覆盖。
JSON 清单记录种子、输入目录、源路径、截取范围、原始计划、按输出帧率对齐后的时间线及草稿路径。
参数错误返回 `2`，执行失败返回 `1`，成功或预览返回 `0`。

### 处理单个视频

```bash
./run.sh "/path/to/video.mp4"
```

默认执行视频清洗、原始切镜、音频提取和 Whisper 转录，结果写入：

```text
output/<视频名>_<YYYYMMDD_HHMMSS>/
```

### 批量处理

处理目录第一层中的全部视频：

```bash
./run.sh "/path/to/video_dir"
```

目录输入不会递归扫描子目录，支持：

```text
.mp4 .avi .mov .mkv .flv .wmv .webm .m4v .ts
```

一次处理多个文件：

```bash
./run.sh \
  "/path/to/a.mp4" \
  "/path/to/b.mp4" \
  "/path/to/c.mp4"
```

从列表文件读取本地路径或链接，空行和 `#` 注释会被忽略：

```bash
./run.sh --list urls.txt -d
```

### 下载视频

下载后继续分析：

```bash
./run.sh "https://example.com/video" -d
```

只下载，不分析：

```bash
./run.sh "https://example.com/video" --download-only
```

下载文件保存在 `downloads/`。抖音和 TikTok 链接会尝试读取 Chrome Cookie，因此需要浏览器中已有可用登录态；其他站点能力取决于 `yt-dlp`。

CLI 退出码约定：

- `0`：全部处理成功
- `1`：下载、分析或语义分镜执行失败，包括批量任务部分失败
- `2`：参数、输入路径或配置错误

## 按需执行

只清洗视频：

```bash
./run.sh "/path/to/video.mp4" --remove-subtitles-only
```

只清洗并拆镜，不提取音频和文案：

```bash
./run.sh "/path/to/video.mp4" --scenes-only
```

只清洗、提取音频和文案，不拆镜：

```bash
./run.sh "/path/to/video.mp4" --audio-only
```

调整切镜敏感度：

```bash
./run.sh "/path/to/video.mp4" --threshold 22
```

`threshold` 越小越敏感，越容易产生更多切镜。检测器还会使用自适应阈值，并合并短于默认最短时长的误检片段。

指定 Whisper 模型：

```bash
./run.sh "/path/to/video.mp4" --whisper-model medium
```

可选模型为 `tiny`、`base`、`small`、`medium`、`large`，默认 `base`。首次运行会下载对应模型。

## AI 剧情语义分镜

AI 语义分镜不会替代原始切镜：

- `scenes/` 保留按真实画面变化检测出的原始切镜
- AI 读取每个切镜的代表帧、时间范围和对应台词
- 连续且属于同一人物、地点、事件或表达目的的切镜会被聚合
- `semantic_scenes/` 保存聚合视频
- `semantic_scenes.json` 保存分组原因和原始切镜映射

使用智谱：

```bash
ZAI_API_KEY="你的 API Key" \
  ./run.sh "/path/to/video.mp4" --semantic-scenes
```

使用火山方舟：

```bash
SEMANTIC_SCENE_PROVIDER="volcengine" \
ARK_API_KEY="你的 API Key" \
ARK_MODEL="ep-xxxxxxxx" \
  ./run.sh "/path/to/video.mp4" --semantic-scenes
```

供应商配置位于：

```text
config/semantic_scenes.json
```

不要把真实 API Key 写入配置文件。配置中只保存环境变量名、模型地址和非敏感参数。

未设置 `SEMANTIC_SCENE_PROVIDER` 时，程序按以下顺序选择供应商：

1. 优先选择已设置对应 API Key 的供应商
2. 都未设置时使用 `default_provider`

给已有分析结果补做语义分镜：

```bash
./run.sh "output/<已有结果目录>" --semantic-scenes
```

如果 `semantic_scenes.json` 已存在，该目录会被跳过。

## 剪映草稿

### 分析后直接导出

```bash
./run.sh "/path/to/video.mp4" --export-jianying
```

### 从已有结果导出

```bash
python3 src/utils/jianying_draft_exporter.py \
  "output/<已有结果目录>"
```

默认使用 `emotion` 样式：

- 中文字幕来自 `transcript_detailed.json`
- 没有英文字幕时，会基于音频调用 Whisper 生成英文翻译
- 中英文默认合并到同一文本轨，中文在上、英文在下
- 生成的英文结果会保存为 `transcript_english.txt` 和 `transcript_english_detailed.json`

只需要基础中文字幕时：

```bash
python3 src/utils/jianying_draft_exporter.py \
  "output/<已有结果目录>" \
  --style-template basic
```

草稿箱路径会按以下顺序确定：

1. 命令行 `--draft-root`
2. 项目本地缓存 `.jianying_config.json`
3. 自动检测本机剪映草稿目录
4. 交互式要求输入路径

模板来自项目内置目录：

```text
templates/jianying/
```

导出器会创建草稿目录并更新草稿箱根索引。剪映正在运行时，导出后建议完全退出并重新打开。

## 镜头池混剪

处理新视频并使用镜头池补尾：

```bash
./run.sh "/path/to/video.mp4" \
  --compose-with-pool "/path/to/shot_pool"
```

从已有结果直接组合并导出：

```bash
python3 src/utils/jianying_draft_exporter.py \
  "output/<已有结果目录>" \
  --compose-with-pool "/path/to/shot_pool"
```

当前组合策略：

- 默认保留第一个原始切镜作为视频头
- 按字幕结束时间构造后续画面槽位
- 默认从池素材的开头截取槽位所需长度；只有 `--pool-clip-start random` 才随机选择内部起点
- 镜头池递归扫描子目录
- 优先选择时长接近、近期未使用、素材组和素材集合更分散的镜头
- 镜头短于槽位时继续补下一条，避免延长最后一帧
- 生成 `composition_plan.json` 后写入剪映草稿

固定保留前 3 秒：

```bash
./run.sh "/path/to/video.mp4" \
  --compose-with-pool "/path/to/shot_pool" \
  --head-mode fixed-seconds \
  --head-duration 3
```

不保留原视频头部：

```bash
./run.sh "/path/to/video.mp4" \
  --compose-with-pool "/path/to/shot_pool" \
  --head-mode none
```

需要可复现的选片结果时：

```bash
./run.sh "/path/to/video.mp4" \
  --compose-with-pool "/path/to/shot_pool" \
  --compose-seed 42
```

直接导出器中的对应参数名是 `--seed 42`。

这里的 `--compose-with-pool` 仍按原视频音频/字幕时长编排，输出剪映草稿。
按 A/B/C 目录组装完整镜头并导出 MP4，请使用上面的 `./run.sh compose`。

## 跳过与续跑规则

批处理器会在 `output/` 下查找名称符合以下格式的目录：

```text
<源视频文件名>_<YYYYMMDD_HHMMSS>/
```

只要其中存在 `video_no_subtitles.mp4`，再次从同名源视频运行时就会跳过该视频的全部处理，包括语义分镜和剪映导出。

因此：

- 给已有结果补做 AI 语义分镜时，直接传入结果目录
- 给已有结果导出剪映时，使用 `src/utils/jianying_draft_exporter.py`
- 想从源视频完整重跑时，先移动对应结果目录，或使用新的 `--output` 根目录

AI 阶段开始前会先保存基础 `report.json`。如果 AI 调用失败，可直接对该结果目录重新执行 `--semantic-scenes`，不必重新清洗、拆镜和转录。

## 输出结构

```text
output/<视频名>_<时间戳>/
├── video_no_subtitles.mp4
├── scenes/
│   ├── Scene-001.mp4
│   ├── Scene-002.mp4
│   └── ...
├── audio.mp3
├── transcript.txt
├── transcript_detailed.json
├── report.json
├── semantic_scene_contact_sheet.jpg   # 启用 AI 语义分镜
├── semantic_scenes.json               # 启用 AI 语义分镜
├── semantic_scenes/                   # 启用 AI 语义分镜
│   ├── SemanticScene-001.mp4
│   └── ...
├── transcript_english.txt             # emotion 导出时按需生成
├── transcript_english_detailed.json   # emotion 导出时按需生成
└── composition_plan.json              # 镜头池组合时生成
```

`report.json` 是基础分析契约，包含：

- 原始视频和处理后视频路径
- 原始切镜及 `scene_detection` 参数
- 完整文案和时间戳分段
- AI 语义分镜结果

## 常用参数

| 参数 | 说明 |
| --- | --- |
| `-l, --list` | 从文本文件读取视频路径或链接 |
| `-d, --download` | 使用 `yt-dlp` 下载链接 |
| `--download-only` | 只下载，不分析；会自动启用下载 |
| `-o, --output` | 输出根目录，默认 `output` |
| `-t, --threshold` | 原始切镜阈值，默认 `27`，越小越敏感 |
| `--scenes-only` | 不提取音频和文案 |
| `--audio-only` | 不执行原始切镜 |
| `--whisper-model` | Whisper 模型，默认 `base` |
| `--remove-subtitles-only` | 只生成清洗后视频 |
| `--subtitle-bar-height` | 手动指定底部字幕黑边高度，单位为像素 |
| `--semantic-scenes` | 生成 AI 剧情语义分镜 |
| `--semantic-scenes-config` | 指定语义分镜配置文件 |
| `--export-jianying` | 分析完成后导出剪映草稿 |
| `--compose-with-pool` | 使用镜头池组合后导出剪映草稿 |
| `--head-mode` | `first-scene`、`fixed-seconds` 或 `none` |
| `--head-duration` | `fixed-seconds` 模式下保留的秒数 |
| `--compose-seed` | 主入口中的随机选片种子 |
| `--pool-clip-start` | 池素材截取起点：`start`（默认）或显式 `random` |
| `--style-template` | `emotion` 或 `basic`，默认 `emotion` |
| `--draft-root` | 剪映草稿箱根目录 |
| `--template-dir` | 自定义剪映草稿模板目录 |
| `--draft-name` | 自定义草稿名称 |

查看完整参数：

```bash
python3 main.py --help
./run.sh compose --help
python3 src/utils/jianying_draft_exporter.py --help
```

## 收集分镜素材

`collect_scenes.sh` 会把每个结果目录中的：

- `Scene-001` 复制到视频头目录
- 其他 `Scene-*` 复制到视频身目录

脚本默认只预览，不会创建目录或复制文件：

```bash
./collect_scenes.sh \
  --head-dir "/path/to/head_pool" \
  --body-dir "/path/to/body_pool"
```

确认预览结果后实际执行：

```bash
./collect_scenes.sh \
  --head-dir "/path/to/head_pool" \
  --body-dir "/path/to/body_pool" \
  --execute
```

指定其他分析结果目录：

```bash
./collect_scenes.sh \
  --output-dir "/path/to/output" \
  --head-dir "/path/to/head_pool" \
  --body-dir "/path/to/body_pool" \
  --execute
```

## Feature Flags

当前内置开关均默认启用：

| 环境变量 | 作用 |
| --- | --- |
| `CHAI_FLAG_SEGMENT_ALIGNED_BILINGUAL_TRANSLATION` | 按中文字幕时间段生成英文翻译 |
| `CHAI_FLAG_SINGLE_TRACK_BILINGUAL_SUBTITLES` | 将中英文合并到同一字幕轨 |
| `CHAI_FLAG_PREVENT_VIDEO_FRAME_EXTENSION` | 短镜头不足时继续补片，避免延长末帧 |
| `CHAI_FLAG_SHOT_POOL_COLLECTION_DIVERSITY` | 优先从不同素材集合选片 |

临时关闭示例：

```bash
CHAI_FLAG_SHOT_POOL_COLLECTION_DIVERSITY=false \
  ./run.sh "/path/to/video.mp4" \
  --compose-with-pool "/path/to/shot_pool"
```

## 项目结构

```text
main.py
run.sh
collect_scenes.sh
config/
├── settings.py
├── feature_flags.py
└── semantic_scenes.json
src/
├── cli.py
├── commands/
│   └── compose.py
├── core/
│   ├── video_analyzer.py
│   ├── subtitle_remover.py
│   ├── scene_detector.py
│   ├── audio_extractor.py
│   ├── transcriber.py
│   ├── semantic_scene_grouper.py
│   └── video_downloader.py
├── composition/
│   ├── shot_pool.py
│   ├── directory_composer.py
│   └── head_tail_composer.py
├── exporters/
│   ├── jianying.py
│   ├── video.py
│   └── jianying_styles.py
├── models/
│   └── artifacts.py
└── utils/
    ├── batch_processor.py
    └── jianying_draft_exporter.py
templates/
└── jianying/
tests/
```

设计边界：

- `output/` 是分析、组合和导出之间的统一产物契约
- 组合器只读取产物，不依赖前序处理内部状态
- 剪映导出器只负责将素材和时间线写成草稿
- 重依赖采用惰性导入，尽量避免轻量命令被 Whisper 等依赖拖慢

## 测试

```bash
python3 -m unittest discover tests
```

## 已知限制

- 分析/镜头池模式导出剪映草稿；`compose` 支持直接渲染 MP4
- 字幕清理仅针对底部黑边中的字幕，不会擦除直接压在活动画面上的动态字幕
- 水印清理仅针对底部区域中位置固定、跨采样帧稳定出现的半透明水印
- 镜头池目前主要按时长和多样性选片，尚未按画幅或内容语义过滤
- 分析模式源视频目录只扫描第一层；镜头池和 `compose` 的素材目录递归扫描
- 抖音和 TikTok 下载依赖浏览器 Cookie，平台规则变化可能导致下载失败
- 路径中包含空格时，需要用双引号包住完整路径
