# 🌞 Sun CLI

一个由 AI 驱动的类 Claude 命令行工具，使用 Python 构建。

## 功能特性

- 💬 交互式聊天，支持流式响应
- 📝 基于 Markdown 的提示词系统（灵感来自 OpenClaw）
- 🔥 **智能 Git 工作流** - AI 驱动的提交，支持自动拉取和冲突解决
- � **计划模式** - 在执行前审查和批准实施计划
- � 任务完成时的桌面通知
- 🔊 成功操作的音效提示
- ⚙️ 简单的配置管理
- 🎨 使用 Rich 的精美终端 UI
- 🔧 执行本地 Shell 命令而不调用 AI
- 🇨🇳 为中国大陆用户提供中文语言支持
- 🌐 支持国内 AI 服务（Kimi、通义千问、智谱 AI、DeepSeek）

## 安装

```bash
# 克隆并安装
pip install -e .

# 或从源码安装
pip install .
```

## 快速开始

1. **配置 API：**
   
   **Kimi API（Moonshot）：**
   ```bash
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
| `suncli prompt` | 预览组合的系统提示词 |
| `suncli prompt --list` | 列出所有提示词文件 |
| `suncli prompt --show <name>` | 查看特定提示词 |
| `suncli prompt --edit <name>` | 编辑提示词文件 |
| `suncli prompt --path` | 显示提示词目录 |
| `suncli --version` | 显示版本 |

## 聊天命令

在交互式聊天会话中：

| 命令 | 描述 |
|---------|-------------|
| `exit`, `quit` | 退出 Sun CLI |
| `/help` | 显示帮助 |
| `/clear` | 清除对话历史（保留系统提示词） |
| `/new` | 开始新对话 |
| `/config` | 显示当前配置 |
| `/plan` | 为复杂任务进入计划模式 |
| `/approve` | 批准并执行当前计划 |
| `/modify` | 请求修改计划 |
| `/cancel` | 取消计划模式 |

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

```bash
suncli config --api-key sk-xxx --base-url https://api.moonshot.cn/v1 --model moonshot-v1-128k
```

可用的 Kimi 模型：
- `moonshot-v1-8k` - 8K 上下文
- `moonshot-v1-32k` - 32K 上下文
- `moonshot-v1-128k` - 128K 上下文（推荐）

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
