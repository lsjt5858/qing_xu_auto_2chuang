#!/bin/bash
# 激活虚拟环境并运行视频分析工具

source venv/bin/activate
python main.py "$@"
