#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    printf '错误: 未找到项目虚拟环境解释器: %s\n' "$PYTHON" >&2
    printf '请先在项目目录执行: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt\n' >&2
    exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/main.py" --remove-subtitles "$@"
