# 本地 Web 服务

工作台前端已独立放在 [`apps/workbench`](../../apps/workbench/README.md)，
使用 React + TypeScript + Vite，默认通过 HTTP 连接本地 Python 服务。
本目录不放前端模板或构建依赖。

服务代码位于 `src/services/`：FastAPI、SQLite 持久化队列与受管子进程。
前端轮询任务快照；刷新网页不终止处理。启动命令：

```bash
./run.sh workbench --execute
```

首次安装、前端构建、插件配对与限制见
[`WORKBENCH_RUNTIME.md`](../../docs/WORKBENCH_RUNTIME.md)，接口见
[`WORKBENCH_API.md`](../../docs/WORKBENCH_API.md)。
