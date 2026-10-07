# 本地工作台 API / 发布插件协议

服务默认 `http://127.0.0.1:8766`，Vite 将 `/api` 代理到此地址。所有业务 API 使用 `/api`。
JSON 属性采用前端已有 camelCase。错误为 `{"detail":"可读说明"}`。

## 工作台

浏览器先 `POST /api/session`，头 `X-Workbench: 1`，返回 `{csrfToken}` 并设置 HttpOnly SameSite=Strict cookie。后续写请求带 `X-CSRF-Token`，同源 credentials。只接受本机 Host 和允许的本机 Origin，不开放通配 CORS。

- `GET /snapshot` 返回 WorkspaceSnapshot，原字段保留，增加 `accounts: Account[]` 和 `service: ServiceInfo`。
- `POST /materials/import` multipart `files`（可重复），实际复制文件并探测视频；返回 snapshot。
- `POST /materials/directory` JSON `{path}`，显式扫描目录视频及 report.json 导入已有分析（非递归）；返回 snapshot。
- `POST /tasks` ProcessingRequest，按素材创建 queued 任务；返回 snapshot。
- `POST /tasks/{id}/command` `{command}`，真实命令仅 `cancel`、`retry`；返回 snapshot。
- `POST /mix/plans` MixConfig，返回真实且已保存的 MixPlan。完整原始素材按 seed 选择，绝不固定截成示例秒数。保留 template/pool，增加可选 `materialIds: string[]`（给出时按此顺序组装全部素材）。
- `POST /mix/tasks` `{planId, outputs: ('preview'|'draft')[]}`；返回 snapshot。
- `POST /outputs/import` multipart `files`，导入实际成片；返回 snapshot。
- `POST /outputs/{id}/confirm` 将预览标记 final；返回 snapshot。
- `POST /publish` 原 PublishRequest，必须 confirmed、账号已配对、实际文件存在，创建持久发布队列；返回 snapshot。
- `POST /publish/{id}/cancel` 仅允许 queued/blocked/awaiting_confirmation，返回 snapshot。
- `PUT /settings` Settings；返回 snapshot。
- `POST /pairing` `{}`，返回 `{code, expiresAt}`，只在用户主动点击后生成。
- `DELETE /pairing/{extensionId}` 撤销配对；返回 snapshot。
- `GET /materials/{id}/file`、`GET /outputs/{id}/file` 实际媒体，支持 Range。Material/Output 增加可选 `fileUrl`；Output 增加可选 `width,height`。草稿没有视频 URL。

Snapshot 增加：

```ts
interface Account {
  id: string; platform: 'douyin'; uid: string; name: string; handle: string;
  extensionId: string; connected: boolean; lastSeenAt: string;
}
interface ServiceInfo {
  mode: 'live'; version: string;
  dependencies: {name: string; available: boolean; detail: string}[];
  extensions: {id: string; name: string; lastSeenAt: string; connected: boolean}[];
}
```

TaskStatus 增加 `cancelled | skipped | interrupted`。任务自动串行运行，不支持虚假的 advance/pause；未知进度 null。
PublishReceipt.simulated 改 boolean，status 增加 `queued | uploading | filling | submitting | blocked | unknown | cancelled`（保留 awaiting_confirmation/submitted）；增加 `accountName?: string; message?: string; updatedAt?: string; evidence?: string`。
ServiceInfo/accounts 在 demo 中可缺省。WorkspaceRepository.mode 为 demo|live；新方法可选，实时 adapter 必须实现。

## Chrome MV3 插件

扩展页 runner 持续执行，popup 只负责打开 runner，避免 Service Worker 休眠丢失任务。不经网站页面传递任何本地 token。

1. 工作台生成配对码，runner 用户输入。
2. `POST /api/extension/pair` `{code, extensionId: chrome.runtime.id, name}` → `{token}`，保存在扩展本地 storage。
3. 后续带 `Authorization: Bearer <token>` 与 `X-Extension-Id`，URL 固定本机 8766（可配置本机端口，禁止任意远端）。
4. `POST /api/extension/heartbeat` `{account?: {uid,nickname,unique_id,short_id}}` → `{ok:true}`。仅采集四个身份字段，服务生成 Account.id，返回 snapshot 可看。
5. `POST /api/extension/claim` `{accountUid}` → `{job:null}` 或 `{job:{id,outputId,accountId,accountUid,title,caption,mode,fileName,sizeBytes,leaseToken}}`。只领取匹配账号、绑定此扩展的 queued 任务，租期 45 秒。
6. 每 10 秒 `POST /api/extension/jobs/{id}/heartbeat` `{leaseToken}`。
7. `GET /api/extension/jobs/{id}/file` 带 `X-Lease-Token` 返回成片，只允许有效租约读取自己任务文件。
8. `POST /api/extension/jobs/{id}/event` `{leaseToken,status,message?,evidence?}` → `{ok:true}`。合法顺序 queued→uploading→filling→awaiting_confirmation 或 filling→submitting→submitted/unknown。非终态可 blocked；提交阶段只能 unknown/submitted，禁止回退和自动重试。
9. direct 提交前必须先成功持久化 submitting，再单次点击平台“发布”；submitted 必须有明确发布成功证据。导航/超时/断线视为 unknown，不能猜成功。租期到期：提交中 unknown，其余 blocked，不重新入队。

安全和平台约束：

- runner 手动选择一个已登录抖音 tab，启动后核验 uid；上传前、提交前再次核验。
- 账号信息通过 MAIN world 同源 `fetch('/web/api/media/user/info/', {credentials:'include'})` 的 status_code=0 响应，只返回 user 四个字段。
- 已验证真实上传页 `https://creator.douyin.com/creator-micro/content/upload` 存在 video input。
- 页面出现“你还有上次未发布的视频，是否继续编辑？”时停止，不点击继续或放弃旧草稿。
- 不猜测模糊选择器，不绕过验证码，不自动覆盖已有内容。未知 DOM 停 blocked 给出说明。
- 文件从 runner 下载后通过 256 KiB 消息分块给 content script，组装 File + DataTransfer 设置视频 input；设置合理大小上限并给出错误。
- prefill 停最终提交前；direct 仅执行工作台用户已逐条核对确认的冻结任务。
- 平台页面本身不接触配对 token、cookie 或本地文件路径。不得自动发布任何测试/旧素材。
