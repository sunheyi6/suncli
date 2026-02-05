# 🌞 Sun CLI

A Claude-like CLI tool powered by AI, built with Python.

## Features

- 💬 Interactive chat with streaming responses
- 📝 Markdown-based prompt system (inspired by OpenClaw)
- 🔥 **Smart Git Workflow** - AI-powered commit with auto-pull & conflict resolution
- ⚙️ Simple configuration management
- 🎨 Beautiful terminal UI with Rich
- 🔧 Execute local shell commands without calling AI

## Installation

```bash
# Clone and install
pip install -e .

# Or install from source
pip install .
```

## Quick Start

1. **Configure API Key:**
   ```bash
   suncli config --api-key <your-openai-api-key>
   ```

2. **Start chatting:**
   ```bash
   suncli
   ```

## 🔥 Smart Git Workflow

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
- "commit changes"
- "push code"
- "上传代码"
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

## Prompt System (Markdown-based)

Sun CLI uses a Markdown-based prompt system inspired by [OpenClaw](https://liruifengv.com/posts/openclaw-prompts/). Customize AI behavior by editing prompt files:

```
%APPDATA%/sun-cli/prompts/     (Windows)
~/.config/sun-cli/prompts/     (Linux/Mac)
```

### Default Prompt Files

| File | Purpose |
|------|---------|
| `system.md` | Workspace guidelines, safety rules, memory management |
| `identity.md` | AI personality, communication style, core traits |
| `user.md` | User preferences, context, working environment |
| `memory.md` | Long-term memory, lessons learned, curated notes |

### Managing Prompts

```bash
# List all prompt files
suncli prompt --list

# View a prompt
suncli prompt --show system
suncli prompt --show identity

# Edit a prompt (opens in default editor)
suncli prompt --edit identity
suncli prompt --edit user

# Preview combined system prompt
suncli prompt

# Show prompts directory location
suncli prompt --path
```

## Usage Example

```bash
$ suncli
+---------------- Sun CLI v0.1.0 -----------------+
| Welcome to Sun CLI                              |
| Model: gpt-4o-mini                              |
| Type /help for commands | exit or /quit to exit |
+-------------------------------------------------+

You: Hello!

Sun CLI: Hello! How can I help you today?

You: !dir
$ dir
[Directory listing shows here]

You: 提交代码
[Smart Git workflow executes...]

You: exit
Goodbye!
```

## Commands

| Command | Description |
|---------|-------------|
| `suncli` | Start interactive chat session |
| `suncli config` | Configure settings (API key, model) |
| `suncli config --show` | Show current configuration |
| `suncli prompt` | Preview combined system prompt |
| `suncli prompt --list` | List all prompt files |
| `suncli prompt --show <name>` | View a specific prompt |
| `suncli prompt --edit <name>` | Edit a prompt file |
| `suncli prompt --path` | Show prompts directory |
| `suncli --version` | Show version |

## Chat Commands

During an interactive chat session:

| Command | Description |
|---------|-------------|
| `exit`, `quit` | Exit Sun CLI |
| `/help` | Show help |
| `/clear` | Clear conversation history (system prompt preserved) |
| `/new` | Start a new conversation |
| `/config` | Show current configuration |

## Shell Commands

Execute local shell commands without calling AI by prefixing with `!`:

```
You: !dir                    # Windows: List files
You: !ls -la                 # Linux/Mac: List files
You: !cd ..                  # Change directory
You: !pwd                    # Show current directory
You: !echo hello             # Print text
You: !python script.py       # Run Python script
```

Commands starting with `!` are executed locally and **NOT** sent to AI.

## Configuration

Configuration can be set via:

1. **Environment variables:** `SUN_API_KEY`, `SUN_MODEL`, etc.
2. **Config file:** `%APPDATA%/sun-cli/.env` (Windows) or `~/.config/sun-cli/.env` (Linux/Mac)
3. **CLI:** `suncli config --api-key <key>`

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SUN_API_KEY` | OpenAI API key | - |
| `SUN_MODEL` | Model to use | `gpt-4o-mini` |
| `SUN_BASE_URL` | Custom API base URL | `https://api.openai.com/v1` |
| `SUN_TEMPERATURE` | Sampling temperature | `0.7` |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run linting
ruff check .
ruff format .
```

## License

MIT
