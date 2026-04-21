# 🌞 Sun CLI

一个由 AI 驱动的类 Claude 命令行工具，使用 Python 构建。

## 功能特性

- 💬 交互式聊天，支持流式响应
- 🤖 **多轮工具调用** - AI 可读写文件、执行 Shell 命令、搜索网络等
- 🛡️ **路径安全沙箱** - 所有文件操作限制在工作区内
- 📝 基于 Markdown 的提示词系统（灵感来自 OpenClaw）
- 🧠 **跨会话记忆** - AI 记住你的偏好，下次聊天依然有效
- 📋 **计划模式** - 在执行前审查和批准实施计划
- 📋 **任务板** - 持久化任务图，支持依赖关系追踪
- 🔄 **后台任务** - 长时间运行的命令不阻塞主聊天循环
- ⏰ **定时调度** - Cron 风格的任务调度
- 👥 **团队协作** - 生成队友并协调多智能体工作流
- 🌲 **Git Worktree 隔离** - 为不同任务创建独立的工作区
- 🔌 **MCP 支持** - 连接外部 Model Context Protocol 服务器
- 🔥 **智能 Git 工作流** - AI 驱动的提交，支持自动拉取和冲突解决
- 🔔 任务完成时的桌面通知
- 🔊 成功操作的音效提示
- ⚙️ 简单的配置管理
- 🎨 使用 Rich 的精美终端 UI
- 🔧 执行本地 Shell 命令而不调用 AI
- 🇨🇳 为中国大陆用户提供中文语言支持
- 🌐 支持国内 AI 服务（Kimi、通义千问、智谱 AI、DeepSeek）
- 🎛️ **模型预设** - 内置 8 家提供商预设，支持交互式向导配置
- 📝 **输入历史** - 按 ↑/↓ 键在历史中导航
- 🐛 **调试模式** - `--debug` 输出详细日志

## 安装

```bash
# 克隆并安装
pip install -e .

# 或从源码安装
pip install .
```

## 快速开始

1. **配置 API：**

   **交互式配置（推荐）：**
   ```bash
   suncli models --setup
   ```
   
   **Kimi API（Moonshot）：**
   ```bash
   # Kimi K2.5（国际平台 platform.kimi.ai）
   suncli config --api-key <your-kimi-api-key> --base-url https://api.moonshot.ai/v1 --model kimi-k2.5

   # Moonshot v1（国内平台 platform.kimi.com）
   suncli config --api-key <your-kimi-api-key> --base-url https://api.moonshot.cn/v1 --model moonshot-v1-128k
   ```
   
   **OpenAI API：**
   ```bash
   suncli config --api-key <your-openai-api-key> --base-url https://api.openai.com/v1 --model gpt-4o-mini
   ```

2. **开始聊天：**
   ```bash
   suncli
   ```

## 🤖 AI 工具

Sun CLI 可以在对话中调用丰富的工具集，AI 会根据你的请求自动决定使用哪些工具。

### 文件与 Shell 工具

| 工具 | 描述 |
|------|------|
| `read` | 读取文件内容（支持 offset/limit） |
| `write` | 写入或覆盖文件（自动创建父目录） |
| `edit` | 精确字符串替换编辑 |
| `bash` | 执行 Shell 命令（Windows 下为 PowerShell，Linux/Mac 下为 bash） |

### 扩展工具

| 工具 | 描述 |
|------|------|
| `web_search` | 网络搜索（DuckDuckGo 或 Kimi 原生搜索） |
| `weather_now` | 实时天气查询（wttr.in） |
| `subagent` | 生成子代理，用独立上下文处理子任务 |
| `background_run` | 在后台运行命令 |
| `background_check` | 检查后台任务状态和输出 |
| `schedule_create` | 创建 Cron 定时任务 |
| `schedule_list` | 列出定时任务 |
| `schedule_remove` | 删除定时任务 |
| `save_memory` | 保存跨会话记忆 |
| `load_memory` | 加载已存储的记忆 |
| `team_spawn` | 创建一个队友智能体 |
| `team_send` | 向队友发送消息 |
| `team_list` | 列出所有队友 |
| `worktree_create` | 创建 Git Worktree 隔离工作区 |
| `worktree_enter` | 进入 Worktree 目录 |
| `worktree_closeout` | 关闭 Worktree（保留或删除） |

---

## 📋 计划模式

计划模式允许您在 AI 执行之前审查和批准实施计划。这对于涉及多个步骤或代码更改的复杂任务特别有用。

### 使用计划模式

```bash
$ suncli

You: /plan
Enter your task to create a plan:

You: 为应用程序添加用户认证

📋 计划预览
# 添加用户认证

计划：为应用程序添加用户认证

## 实施步骤

⏳ **步骤 1：** 创建用户模型并实现密码哈希
⏳ **步骤 2：** 实现 JWT 令牌生成和验证
⏳ **步骤 3：** 添加登录和注销 API 端点
⏳ **步骤 4：** 创建身份验证中间件
⏳ **步骤 5：** 为身份验证流程添加测试

命令：
  /approve - 批准并执行计划
  /modify  - 请求修改计划
  /cancel  - 取消计划模式

You: /approve
✅ 计划已批准！

正在执行实施...
[AI 执行每个步骤...]
```

### 计划模式命令

| 命令 | 描述 |
|---------|-------------|
| `/plan` | 为复杂任务进入计划模式 |
| `/approve` | 批准并执行当前计划 |
| `/modify` | 请求修改计划 |
| `/cancel` | 取消计划模式 |

### 何时使用计划模式

- **复杂重构** - 在进行更改之前审查重构计划
- **功能实现** - 在编写代码之前了解所有步骤
- **多文件更改** - 提前查看完整的更改范围
- **学习** - 了解 AI 如何处理复杂问题

## 🔥 智能 Git 工作流

Sun CLI 的智能 Git 工作流让代码提交变得简单：

### 使用方法

```bash
$ suncli

You: 提交代码

智能 Git 工作流
1. 拉取远程代码
2. 检测冲突
3. 生成提交信息
4. 提交并推送

正在拉取远程代码...
Already up to date.

正在生成提交信息...

建议的提交信息:
┌─────────────────────────────────────────┐
│ feat: add user authentication module    │
│                                         │
│ - Implement JWT token validation        │
│ - Add login/logout endpoints            │
│ - Update user model with password hash  │
└─────────────────────────────────────────┘

确认提交? [Y/n]: y
提交成功
推送成功
```

### 支持的指令

自然语言触发：
- "提交代码"
- "保存并推送"
- "commit code"
- "push code"
- ...等等

### 工作流流程

1. **自动拉取** - `git pull --rebase` 先拉取远程代码
2. **冲突检测** - 自动检测是否有合并冲突
3. **冲突解决** - 交互式冲突解决界面（如果出现冲突）
4. **生成提交信息** - AI 根据代码变更生成规范的 commit message
5. **自动提交** - `git commit` 提交代码
6. **自动推送** - `git push` 推送到远程

### 冲突解决界面

```
⚠️ 检测到 2 个冲突文件

正在处理: src/auth.py

选项 1: 保留当前分支 (HEAD/ours)
┌────────────────────────────────────┐
│ 1  def login_user(username):       │
│ 2      # TODO: implement           │
│ 3      return validate_token()     │
└────────────────────────────────────┘

选项 2: 保留远程分支 (incoming/theirs)
┌────────────────────────────────────┐
│ 1  def login_user(username):       │
│ 2      user = get_user(username)   │
│ 3      return check_password(user) │
└────────────────────────────────────┘

选项:
  1 - 保留当前分支的修改 (ours)
  2 - 保留远程分支的修改 (theirs)
  3 - 保留双方修改 (合并)
  e - 手动编辑文件
  s - 跳过此文件
  a - 中止 rebase

选择解决方案 [1/2/3/e/s/a]: 
```

## 提示词系统（基于 Markdown）

Sun CLI 使用基于 Markdown 的提示词系统，灵感来自 [OpenClaw](https://liruifengv.com/posts/openclaw-prompts/)。通过编辑提示词文件自定义 AI 行为：

```
%APPDATA%/sun-cli/prompts/     (Windows)
~/.config/sun-cli/prompts/     (Linux/Mac)
```

### 默认提示词文件

| 文件 | 用途 |
|------|---------|
| `system.md` | 工作区指南、安全规则、记忆管理 |
| `identity.md` | AI 个性、沟通风格、核心特征 |
| `user.md` | 用户偏好、上下文、工作环境 |
| `memory.md` | 长期记忆、经验教训、精选笔记 |

### 管理提示词

```bash
# 列出所有提示词文件
suncli prompt --list

# 查看提示词
suncli prompt --show system
suncli prompt --show identity

# 编辑提示词（在默认编辑器中打开）
suncli prompt --edit identity
suncli prompt --edit user

# 预览组合的系统提示词
suncli prompt

# 显示提示词目录位置
suncli prompt --path
```

## 🎛️ 模型管理

Sun CLI 内置了 8 家主流 AI 提供商的模型预设：

| 提供商 | 示例模型 |
|----------|----------------|
| OpenAI | GPT-4o, GPT-4o-mini |
| Anthropic | Claude 3.5 Sonnet, Claude 3 Opus |
| Google | Gemini 2.0 Pro |
| Kimi（国际） | Kimi K2.5, Kimi K2 |
| Kimi（国内） | moonshot-v1-128k/32k/8k |
| 通义千问 | Qwen-Max, Qwen-Plus, Qwen-Turbo |
| 智谱 AI（GLM） | GLM-4-Plus, GLM-4, GLM-4-Air |
| DeepSeek | DeepSeek-V3, DeepSeek-R1 |

### 命令

```bash
# 交互式模型配置向导
suncli models --setup

# 列出所有可用预设
suncli models --list

# 按提供商筛选
suncli models --provider Kimi

# 按预设名或模型 ID 设置模型
suncli models --set "GPT-4o"
suncli models --set moonshot-v1-128k
```

## 📋 任务板

Sun CLI 维护一个持久化的任务板（存储在 `.tasks/` 目录），支持任务依赖链追踪。

### 聊天命令

| 命令 | 描述 |
|---------|-------------|
| `/tasks` | 显示持久化任务板 |
| `/task <id> <status>` | 更新任务状态（`pending` / `in_progress` / `completed`） |

## 📝 输入历史

你的输入会自动保存，聊天时可通过 **↑** 和 **↓** 键在历史中导航。

| 命令 | 描述 |
|---------|-------------|
| `/history` | 显示最近的输入历史（最近 20 条） |
| `/history clear` | 清除所有输入历史 |

## 🐛 调试模式

启用详细日志以排查问题：

```bash
suncli --debug
# 或
suncli -d
```

这会输出包括 API 请求、工具调用、上下文压缩事件等详细信息。

## 使用示例

```bash
$ suncli
+---------------- Sun CLI v0.2.0 -----------------+
| 欢迎使用 Sun CLI                              |
| 模型: gpt-4o-mini                              |
| 输入 /help 查看命令 | exit 或 /quit 退出 |
+-------------------------------------------------+

You: 你好！

Sun CLI: 你好！今天我能帮你做什么？

You: !dir
$ dir
[目录列表显示在这里]

You: 提交代码
[智能 Git 工作流执行中...]

You: exit
再见！
```

## 命令

| 命令 | 描述 |
|---------|-------------|
| `suncli` | 启动交互式聊天会话 |
| `suncli config --api-key <key>` | 设置 API 密钥 |
| `suncli config --base-url <url>` | 设置 API 基础 URL |
| `suncli config --model <model>` | 设置模型 |
| `suncli config --show` | 显示当前配置 |
| `suncli config --yolo` | 启用自动确认模式（跳过所有确认） |
| `suncli config --no-yolo` | 禁用自动确认模式 |
| `suncli models --setup` | 交互式模型选择向导 |
| `suncli models --list` | 列出所有可用模型预设 |
| `suncli models --provider <name>` | 按提供商筛选模型 |
| `suncli models --set <preset>` | 按预设名或模型 ID 设置模型 |
| `suncli prompt` | 预览组合的系统提示词 |
| `suncli prompt --list` | 列出所有提示词文件 |
| `suncli prompt --show <name>` | 查看特定提示词 |
| `suncli prompt --edit <name>` | 编辑提示词文件 |
| `suncli prompt --path` | 显示提示词目录 |
| `suncli --version` | 显示版本 |
| `suncli --debug` | 启用调试模式，输出详细日志 |

## 聊天命令

在交互式聊天会话中：

| 命令 | 描述 |
|---------|-------------|
| `exit`, `quit` | 退出 Sun CLI |
| `/help` | 显示帮助 |
| `/clear` | 清除对话历史（保留系统提示词） |
| `/new` | 开始新对话 |
| `/config` | 显示当前配置 |
| `/history` | 显示最近的输入历史 |
| `/history clear` | 清除所有输入历史 |
| `/plan` | 为复杂任务进入计划模式 |
| `/approve` | 批准并执行当前计划 |
| `/modify` | 请求修改计划 |
| `/cancel` | 取消计划模式 |
| `/tasks` | 显示持久化任务板 |
| `/task <id> <status>` | 更新任务状态（`pending` / `in_progress` / `completed`） |
| `/next` | 中断当前输出，切换到下一条排队消息 |
| `Ctrl+O` | 快捷键：中断并切换到下一条排队消息 |

## Shell 命令

通过前缀 `!` 执行本地 Shell 命令而不调用 AI：

```
You: !dir                    # Windows: 列出文件
You: !ls -la                 # Linux/Mac: 列出文件
You: !cd ..                  # 切换目录
You: !pwd                    # 显示当前目录
You: !echo hello             # 打印文本
You: !python script.py       # 运行 Python 脚本
```

以 `!` 开头的命令在本地执行，**不会**发送给 AI。

## 配置

可以通过以下方式设置配置：

1. **环境变量：** `SUN_API_KEY`、`SUN_MODEL`、`SUN_BASE_URL` 等
2. **配置文件：** `%APPDATA%/sun-cli/.env` (Windows) 或 `~/.config/sun-cli/.env` (Linux/Mac)
3. **命令行：** `suncli config --api-key <key> --base-url <url> --model <model>`

### Kimi API（Moonshot）配置

> ⚠️ **重要**：Moonshot 有两个独立的平台，账号和 API Key 不互通！

**国际平台（platform.kimi.ai）— 支持 K2.5：**
```bash
suncli config --api-key sk-xxx --base-url https://api.moonshot.ai/v1 --model kimi-k2.5
```

**国内平台（platform.kimi.com）— 仅支持 v1 系列：**
```bash
suncli config --api-key sk-xxx --base-url https://api.moonshot.cn/v1 --model moonshot-v1-128k
```

| 平台 | Base URL | 可用模型 |
|------|----------|---------|
| 国际平台 | `https://api.moonshot.ai/v1` | `kimi-k2.5`、`kimi-k2-thinking`、`kimi-k2` |
| 国内平台 | `https://api.moonshot.cn/v1` | `moonshot-v1-8k/32k/128k`、`kimi-k2-turbo-preview` |

### OpenAI API 配置

```bash
suncli config --api-key sk-xxx --base-url https://api.openai.com/v1 --model gpt-4o-mini
```

### 环境变量

| 变量 | 描述 | 默认值 |
|----------|-------------|---------|
| `SUN_API_KEY` | API 密钥 | - |
| `SUN_BASE_URL` | API 基础 URL | `https://api.openai.com/v1` |
| `SUN_MODEL` | 使用的模型 | `gpt-4o-mini` |
| `SUN_TEMPERATURE` | 采样温度 | `0.7` |

## 高级功能

### 上下文压缩

对于长对话，Sun CLI 会自动压缩较早的消息以保持在 Token 限制内，同时保留系统提示词和近期上下文。

### 速率限制重试

当 API 返回 429（速率限制）错误时，Sun CLI 会自动以指数退避策略进行重试。

### 自动确认模式（Yolo 模式）

跳过所有确认提示，实现全自动工作流：

```bash
suncli config --yolo
```

⚠️ **警告：** 此模式下文件修改和 Git 操作将直接执行，不再询问确认。请谨慎使用！

### 项目上下文检测

启动时，Sun CLI 会自动检测你的项目类型并加载相关上下文。如果项目根目录存在 `AGENTS.md` 文件，其指令会自动加载到系统提示词中。

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行代码检查
ruff check .
ruff format .
```

## 许可证

MIT
