"""CLI: ./run.sh workbench --execute."""
import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="青序本地工作台与发布队列")
    parser.add_argument("--execute", action="store_true", help="实际启动服务；否则仅显示启动配置")
    parser.add_argument("--data-dir", type=Path, default=Path("data/workbench"),
                        help="持久数据库及上传文件目录")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    data_dir = args.data_dir.expanduser().resolve()
    print("工作台：http://127.0.0.1:8766", flush=True)
    print(f"本地数据：{data_dir}", flush=True)
    if not args.execute:
        print("当前为 dry-run；添加 --execute 实际启动。")
        return
    if not (root / "apps/workbench/dist/index.html").is_file():
        parser.error("前端尚未构建。请执行 cd apps/workbench && npm ci && npm run build")
    try:
        import uvicorn
        from .workbench_api import create_app
    except ImportError:
        parser.error("缺少服务依赖，请执行 venv/bin/python -m pip install -r requirements-web.txt")
    os.umask(0o077)
    uvicorn.run(create_app(data_dir), host="127.0.0.1", port=8766, log_level="info")


if __name__ == "__main__":
    main()
