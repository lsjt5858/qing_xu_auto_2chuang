# 代码重构计划

## 当前结构评估

当前项目结构：
```
src/
├── core/
│   ├── video_analyzer.py      # 主控制器
│   ├── scene_detector.py      # 场景检测
│   ├── audio_extractor.py     # 音频提取
│   ├── transcriber.py         # 语音转文字
│   ├── subtitle_remover.py    # 字幕去除
│   └── video_downloader.py    # 视频下载
└── utils/
    ├── batch_processor.py     # 批量处理
    └── file_utils.py          # 文件工具
```

## 优化建议

### 方案 A：保持现有结构 + 功能扩展（推荐）

保持当前简洁的结构，按需添加新模块：

```
src/
├── core/
│   ├── video_analyzer.py          # 主控制器（保持不变）
│   ├── scene_detector.py          # 场景检测（保持不变）
│   ├── audio_extractor.py         # 音频提取（保持不变）
│   ├── transcriber.py             # 语音转文字（保持不变）
│   ├── subtitle_remover.py        # 字幕去除（保持不变）
│   ├── video_downloader.py        # 视频下载（保持不变）
│   │
│   # 新增模块（按需添加）
│   ├── subtitle_generator.py      # 字幕生成（SRT/ASS）
│   ├── subtitle_translator.py     # 字幕翻译
│   ├── video_compressor.py        # 视频压缩
│   ├── video_enhancer.py          # 视频增强（亮度/对比度/降噪）
│   ├── audio_processor.py         # 音频处理（降噪/分离/标准化）
│   ├── content_analyzer.py        # 内容分析（人脸/物体/OCR）
│   ├── smart_editor.py            # 智能剪辑（去静音/去重复）
│   └── format_converter.py        # 格式转换
│
├── utils/
│   ├── batch_processor.py         # 批量处理（保持不变）
│   ├── file_utils.py              # 文件工具（保持不变）
│   ├── platform_adapter.py        # 平台适配（多平台尺寸）
│   ├── export_utils.py            # 导出工具（GIF/缩略图）
│   └── stats_generator.py         # 统计报告生成
│
└── web/                           # Web UI（未来添加）
    ├── app.py                     # Flask/FastAPI 应用
    ├── routes.py                  # 路由
    └── templates/                 # 模板
```

**优点**：
- 保持现有代码不变，向后兼容
- 结构简单清晰，易于理解
- 按需添加，不会过度设计

**缺点**：
- core 目录可能会变得较大
- 功能分类不够明确

---

### 方案 B：按功能领域分组（适合大型项目）

将功能按领域细分为子模块：

```
src/
├── core/
│   ├── video_analyzer.py          # 主控制器
│   │
│   ├── video/                     # 视频处理
│   │   ├── __init__.py
│   │   ├── scene_detector.py
│   │   ├── compressor.py
│   │   ├── enhancer.py
│   │   ├── converter.py
│   │   └── downloader.py
│   │
│   ├── audio/                     # 音频处理
│   │   ├── __init__.py
│   │   ├── extractor.py
│   │   ├── transcriber.py
│   │   ├── processor.py           # 降噪/分离/标准化
│   │   └── music_recognizer.py
│   │
│   ├── subtitle/                  # 字幕处理
│   │   ├── __init__.py
│   │   ├── remover.py
│   │   ├── generator.py
│   │   └── translator.py
│   │
│   ├── ai/                        # AI 分析
│   │   ├── __init__.py
│   │   ├── content_analyzer.py    # 人脸/物体/OCR
│   │   ├── sentiment_analyzer.py  # 情感分析
│   │   └── summarizer.py          # 智能摘要
│   │
│   └── editor/                    # 智能编辑
│       ├── __init__.py
│       ├── smart_cutter.py        # 去静音/去重复
│       └── keyframe_extractor.py
│
├── utils/
│   ├── batch_processor.py
│   ├── file_utils.py
│   ├── platform_adapter.py
│   ├── export_utils.py
│   └── stats_generator.py
│
└── web/
    └── ...
```

**优点**：
- 功能分类清晰
- 易于团队协作
- 适合大型项目

**缺点**：
- 需要重构现有代码
- 目录层级增加
- 可能过度设计

---

## 推荐方案

**采用方案 A**，理由：
1. 当前项目规模适中，不需要过度分层
2. 保持向后兼容，不破坏现有代码
3. 按需添加新功能，避免过度设计
4. 如果未来项目变大，可以再重构为方案 B

## 实施步骤

### 第一阶段：添加功能入口占位符

为 TODO 中的功能创建占位符模块，预留接口：

1. 创建新模块文件（空实现）
2. 在 `VideoAnalyzer` 中添加方法入口
3. 更新文档

### 第二阶段：逐步实现功能

按优先级实现各个功能：
1. 字幕生成（高需求）
2. 视频压缩/转换（高需求）
3. Web UI（提升用户体验）
4. AI 分析功能（高级功能）

### 第三阶段：性能优化

1. 添加并行处理支持
2. 优化内存使用
3. 添加缓存机制

## 兼容性保证

所有新功能都通过 `VideoAnalyzer` 统一调用，保持接口一致性：

```python
analyzer = VideoAnalyzer(video_path)

# 现有功能（保持不变）
analyzer.remove_subtitles()
analyzer.analyze_scenes()
analyzer.extract_audio()
analyzer.transcribe_audio()

# 新功能（逐步添加）
analyzer.generate_subtitles()      # 字幕生成
analyzer.translate_subtitles()     # 字幕翻译
analyzer.compress_video()          # 视频压缩
analyzer.enhance_video()           # 视频增强
analyzer.analyze_content()         # 内容分析
analyzer.smart_edit()              # 智能剪辑
```

## 下一步行动

1. ✅ 创建此重构计划文档
2. ⬜ 创建功能入口占位符
3. ⬜ 更新 VideoAnalyzer 添加新方法
4. ⬜ 更新架构文档
5. ⬜ 按优先级实现功能
