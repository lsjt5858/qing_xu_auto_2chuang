# 贡献指南

感谢你对本项目的关注！

## 开发环境设置

1. Fork 并克隆仓库
```bash
git clone https://github.com/your-username/qing_xu_auto_2chuang.git
cd qing_xu_auto_2chuang
```

2. 创建虚拟环境
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

## 代码规范

- 遵循 PEP 8 代码风格
- 使用有意义的变量和函数名
- 添加必要的注释和文档字符串
- 每个函数都应该有清晰的文档说明

## 提交代码

1. 创建新分支
```bash
git checkout -b feature/your-feature-name
```

2. 编写代码和测试
```bash
python -m unittest discover tests
```

3. 提交更改
```bash
git add .
git commit -m "描述你的更改"
```

4. 推送到 GitHub
```bash
git push origin feature/your-feature-name
```

5. 创建 Pull Request

## 添加新功能

参考 `docs/ARCHITECTURE.md` 了解项目结构，然后：

1. 在 `src/core/` 或 `src/utils/` 创建新模块
2. 编写测试用例
3. 更新文档
4. 提交 PR

## 报告问题

使用 GitHub Issues 报告 bug 或提出功能建议。

## 代码审查

所有 PR 都需要经过代码审查才能合并。
