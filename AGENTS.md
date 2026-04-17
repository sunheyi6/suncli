# Sun CLI 项目规范

## 项目概述

Sun CLI 是一个类似 Claude Code 的 AI 驱动的命令行工具，支持多种 AI 模型提供商。

## 技术栈

- Python 3.10+
- Typer - CLI 框架
- Rich - 终端富文本显示
- httpx - HTTP 客户端
- Pydantic - 数据验证

## 项目结构

```
sun_cli/
├── __init__.py          # 版本信息
├── __main__.py          # 入口点
├── cli.py               # 主 CLI 逻辑
├── chat.py              # 聊天会话
├── config.py            # 配置管理
├── context_collector.py # 项目上下文收集
├── models.py            # 数据模型
├── prompts/             # 提示词管理
├── skills/              # 技能系统
└── tools/               # 工具定义
```

## 开发规范

### 代码规范
1. 优先使用 Python 文件进行开发
2. 遵循 PEP 8 代码规范
3. 使用 `typer` 定义 CLI 命令
4. 使用 `rich` 进行美观的终端输出

### 依赖管理
1. 依赖安装时优先使用最新版本
2. 优先使用国内代理源安装依赖
3. 国内代理源不可用时，再使用官方源

### 模型支持
- 支持多种模型提供商（OpenAI、Kimi、DeepSeek 等）

## 关键文件

- `pyproject.toml` - 项目配置和依赖
- `sun_cli/cli.py` - 主 CLI 入口
- `sun_cli/chat.py` - 聊天会话管理
- `sun_cli/context_collector.py` - 项目上下文收集（支持 AGENTS.md）
