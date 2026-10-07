# 发布扩展实施记录

目标：依照 `docs/WORKBENCH_API.md` 实现独立 MV3 扩展，只写当前目录。

架构：popup 打开 runner；runner 独占 Web Lock、持久配对及任务记录、轮询串行领取。MAIN world 只执行同源身份读取，content script 只接收任务字段与视频块，不接触本地凭据。页面 profile 必须经实站核验才可启用。

技术：TypeScript、esbuild、Vitest、jsdom，所有依赖本地安装。

## 实施顺序

1. `src/protocol.ts`、`src/api.ts`、`src/identity.ts`：固定本机端口、四字段白名单、严格任务校验、512 MiB 上限、无重试请求。先写 `tests/protocol.test.ts`、`tests/api.test.ts`。
2. `src/dom.ts`、`src/transfer.ts`：旧草稿/验证码/歧义/已有内容阻断、SPA 等待、顺序分块、原生 File/DataTransfer。先写 DOM fixture 和对应测试。未核验编辑 profile 列表保持空。
3. `src/engine.ts`：45 秒租约及每 10 秒续租；先存 submitting 再单次点击；恢复/断线只终止，不重放。用可控 API 与页面边界测量真实状态迁移。
4. `src/bridge.ts`、`src/content.ts`、`src/runner.ts`、`src/popup.ts`：手动 tab 绑定、documentId 固定、消息来源校验、持久状态显示。不得导航或操作真实页面作测试。
5. `public/`、`build.mjs`、`README.md`：可加载 dist、CSP、本地操作说明和能力限制。

验证命令在当前目录运行：`npm test`、`npm run build`、`npm run test:coverage`。检查 dist 中 manifest 引用均存在、无外部脚本、无 token 进入 content bundle。

## 测试范围

TARGETS：protocol / api / identity / dom / transfer / engine / bridge。
BUG_MAP 初始为空：无既有扩展源码，不把尚未实现的需求描述为已证实缺陷。
fixture 分为契约已确认事实的最小 DOM 重建与明确标注的合成编辑页，不伪称采集了真实网站完整 DOM。

## 工具限制

测试 skill 的全局 utree 安装和遥测不运行：会越过用户限定写入目录。测试采用同仓库已有 Vitest 风格，不创建全局配置，不改其他 agent 的文件。不创建 worktree 或 git commit。
