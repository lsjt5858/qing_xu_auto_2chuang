# 工作台与发布插件运行说明

## 启动工作台

```bash
venv/bin/python -m pip install -r requirements-web.txt
npm --prefix apps/workbench ci
npm --prefix apps/workbench run build
./run.sh workbench --execute
```

打开 <http://127.0.0.1:8766>。服务只监听本机，数据保存在 `data/workbench/`。

## 安装发布插件

```bash
npm --prefix apps/publisher-extension ci
npm --prefix apps/publisher-extension run build
```

在 `chrome://extensions` 启用开发者模式，加载 `apps/publisher-extension/dist`。

1. 在工作台“设置”生成配对码。
2. 点击插件图标打开 runner，填写本机端口和配对码。
3. 手动打开已登录的抖音创作者视频上传页。
4. 在 runner 刷新标签页列表、绑定账号，再开始领取任务。
5. 每条任务结束后重新确认页面为空白并重新开始。

## 状态处理

- `awaiting_confirmation`：预填完成，保留页面等待人工确认。
- `submitted`：插件取得明确成功证据。
- `blocked`：提交前因账号、页面、验证码、旧内容或租约问题停止。
- `unknown`：已进入提交阶段但无法确认结果。必须人工核查平台页面，不要重复发布。

插件不会绕过登录、验证码或平台限制，不会恢复旧草稿，也不会对 `unknown` 任务自动重试。自动化验证使用本地合成视频与合成 DOM，不包含真实平台发布。

## 升级兼容

- 旧版本导入、但没有内容摘要的成片不能直接发布；请重新导入 MP4 后再提交。
- 旧版本生成、但没有来源内容指纹的分析缓存不会自动复用；首次处理会重新分析并写入安全指纹。
