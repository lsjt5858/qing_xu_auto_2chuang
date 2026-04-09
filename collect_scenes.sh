#!/bin/bash
# 从 output 目录收集分镜视频：
#   Scene-001 → 视频头
#   其余 Scene → 视频身

HEAD_DIR="/Volumes/xiong_home/哼哼猫下载/情绪/视频头"
BODY_DIR="/Volumes/xiong_home/哼哼猫下载/情绪/视频身"
OUTPUT_DIR="$(cd "$(dirname "$0")" && pwd)/output"

mkdir -p "$HEAD_DIR" "$BODY_DIR"

head_count=0
body_count=0

for project_dir in "$OUTPUT_DIR"/*/; do
    [ -d "$project_dir/scenes" ] || continue
    project_name=$(basename "$project_dir")

    for scene_file in "$project_dir/scenes/"Scene-*.mp4; do
        [ -f "$scene_file" ] || continue
        scene_name=$(basename "$scene_file" .mp4)

        if [ "$scene_name" = "Scene-001" ]; then
            dest_name="${project_name}_${scene_name}.mp4"
            cp "$scene_file" "$HEAD_DIR/$dest_name"
            echo "[头] $dest_name"
            head_count=$((head_count + 1))
        else
            dest_name="${project_name}_${scene_name}.mp4"
            cp "$scene_file" "$BODY_DIR/$dest_name"
            body_count=$((body_count + 1))
        fi
    done
done

echo ""
echo "完成！视频头: ${head_count} 个 → $HEAD_DIR"
echo "      视频身: ${body_count} 个 → $BODY_DIR"