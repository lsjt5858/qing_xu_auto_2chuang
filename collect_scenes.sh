#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/output"
HEAD_DIR=""
BODY_DIR=""
EXECUTE=0

usage() {
    cat <<'EOF'
用法:
  ./collect_scenes.sh --head-dir DIR --body-dir DIR [选项]

选项:
  --output-dir DIR  分析结果根目录，默认使用项目 output/
  --head-dir DIR    Scene-001 的目标目录
  --body-dir DIR    其余 Scene 的目标目录
  --execute         实际复制；默认只预览操作
  -h, --help        显示帮助
EOF
}

usage_error() {
    printf '错误: %s\n\n' "$1" >&2
    usage >&2
    exit 2
}

while (($# > 0)); do
    case "$1" in
        --output-dir|--head-dir|--body-dir)
            (($# >= 2)) || usage_error "$1 缺少目录参数"
            case "$1" in
                --output-dir) OUTPUT_DIR="$2" ;;
                --head-dir) HEAD_DIR="$2" ;;
                --body-dir) BODY_DIR="$2" ;;
            esac
            shift 2
            ;;
        --execute)
            EXECUTE=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage_error "未知参数: $1"
            ;;
    esac
done

[[ -n "$HEAD_DIR" ]] || usage_error "必须指定 --head-dir"
[[ -n "$BODY_DIR" ]] || usage_error "必须指定 --body-dir"
[[ "$HEAD_DIR" != "$BODY_DIR" ]] || usage_error "--head-dir 和 --body-dir 不能相同"

if [[ ! -d "$OUTPUT_DIR" ]]; then
    printf '错误: 输出目录不存在: %s\n' "$OUTPUT_DIR" >&2
    exit 1
fi

if ((EXECUTE)); then
    if ! mkdir -p "$HEAD_DIR" "$BODY_DIR"; then
        printf '错误: 无法创建目标目录\n' >&2
        exit 1
    fi
fi

head_count=0
body_count=0
copied_count=0
skipped_count=0
failed_count=0

for project_dir in "$OUTPUT_DIR"/*/; do
    [[ -d "$project_dir/scenes" ]] || continue
    project_name="${project_dir%/}"
    project_name="${project_name##*/}"

    for scene_file in "$project_dir"scenes/Scene-*.mp4; do
        [[ -f "$scene_file" ]] || continue
        scene_name="${scene_file##*/}"
        scene_name="${scene_name%.mp4}"
        dest_name="${project_name}_${scene_name}.mp4"

        if [[ "$scene_name" == "Scene-001" ]]; then
            destination="$HEAD_DIR/$dest_name"
            kind="头"
            head_count=$((head_count + 1))
        else
            destination="$BODY_DIR/$dest_name"
            kind="身"
            body_count=$((body_count + 1))
        fi

        if ((!EXECUTE)); then
            printf '[DRY-RUN][%s] %s -> %s\n' "$kind" "$scene_file" "$destination"
        elif [[ -e "$destination" ]]; then
            printf '[SKIP][%s] 目标已存在: %s\n' "$kind" "$destination"
            skipped_count=$((skipped_count + 1))
        elif cp "$scene_file" "$destination"; then
            printf '[COPY][%s] %s\n' "$kind" "$dest_name"
            copied_count=$((copied_count + 1))
        else
            printf '[ERROR][%s] 复制失败: %s\n' "$kind" "$scene_file" >&2
            failed_count=$((failed_count + 1))
        fi
    done
done

printf '\n模式: %s\n' "$([[ "$EXECUTE" -eq 1 ]] && printf '执行' || printf '预览')"
printf '视频头: %d，视频身: %d，已复制: %d，已跳过: %d，失败: %d\n' \
    "$head_count" "$body_count" "$copied_count" "$skipped_count" "$failed_count"

((failed_count == 0))
