#!/bin/bash
# 清理脚本 - 移除旧版本文件

echo "清理旧版本文件..."

# 创建备份目录
mkdir -p backup

# 备份旧文件
if [ -f "video_analyzer.py" ]; then
    echo "备份 video_analyzer.py..."
    mv video_analyzer.py backup/
fi

if [ -f "scene_splitter.py" ]; then
    echo "备份 scene_splitter.py..."
    mv scene_splitter.py backup/
fi

# 清理 Python 缓存
echo "清理 Python 缓存..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
find . -type f -name "*.pyo" -delete 2>/dev/null

echo "✓ 清理完成！"
echo "旧文件已备份到 backup/ 目录"
