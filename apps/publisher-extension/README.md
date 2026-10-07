# 镜流发布插件

本目录构建独立 Chrome Manifest V3 插件。插件只连接本机工作台，并在用户手动选择的抖音创作者标签页中执行单条发布任务。

## 构建与安装

```bash
npm --prefix apps/publisher-extension ci
npm --prefix apps/publisher-extension test
npm --prefix apps/publisher-extension run build
```

在 Chrome 打开 `chrome://extensions`，启用开发者模式，选择“加载已解压的扩展程序”，目录使用：

```text
apps/publisher-extension/dist
```

点击插件图标打开 runner。在工作台“设置”生成配对码，完成配对后手动打开并选择已登录的抖音创作者上传页，再绑定账号和开始领取。

## 执行边界

- runner 页面持有本地配对 token；content script 不接触 token、Cookie 或本地文件路径。
- 每次只执行一条任务。账号切换、页面导航、验证码、旧草稿、未知编辑器、租约失效或结果不明确都会停止。
- `prefill` 上传并填写后停止；`direct` 仅处理工作台逐条确认的任务。
- 提交中断或缺少成功证据会记录为 `unknown`，不会自动重试。
- 自动化测试使用合成页面和本地 API，不会登录平台或真实发布。页面结构变更后必须重新实站核验选择器。
