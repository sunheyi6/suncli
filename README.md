# 🌞 Sun CLI

A Claude-like CLI tool powered by AI, built with Python.

## Features

- 💬 Interactive chat with streaming responses
- 🤖 **Multi-round tool calling** - AI can read/write files, execute shell commands, search the web, and more
- 🛡️ **Path sandbox** - All file operations are restricted to the workspace for safety
- 📝 Markdown-based prompt system (inspired by OpenClaw)
- 🧠 **Persistent memory** - AI remembers your preferences across sessions
- 📋 **Plan Mode** - Review and approve implementation plans before execution
- 📋 **Task board** - Persistent task graph with dependency tracking
- 🔄 **Background tasks** - Run long commands without blocking the chat
- ⏰ **Task scheduling** - Cron-based scheduled prompts
- 👥 **Team collaboration** - Spawn teammates and coordinate multi-agent workflows
- 🌿 **Git worktree isolation** - Create isolated workspaces for different tasks
- 🔌 **MCP support** - Connect to external Model Context Protocol servers
- 🔥 **Smart Git Workflow** - AI-powered commit with auto-pull & conflict resolution
- 🔔 Desktop notifications for task completion
- 🔊 Sound effects for successful operations
- ⚙️ Simple configuration management
- 🎨 Beautiful terminal UI with Rich
- 🔧 Execute local shell commands without calling AI
- 🇨🇳 Chinese language support for users in mainland China
- 🌐 Support for domestic AI services (Kimi, Qwen, GLM, DeepSeek)
- 🎛️ **Model presets** - Built-in presets for 8 providers, interactive setup wizard
- 📝 **Input history** - Navigate previous inputs with arrow keys
- 🐛 **Debug mode** - Detailed logging with `--debug`

## Installation

```bash
# Clone and install
pip install -e .

# Or install from source
pip install .
```

## Quick Start

1. **Configure API:**
   
   **Interactive setup (recommended):**
   ```bash
   suncli models --setup
   ```
   
   **For Kimi API (Moonshot):**
   ```bash
   suncli config --api-key <your-kimi-api-key> --base-url https://api.moonshot.cn/v1 --model moonshot-v1-128k
   ```
   
   **For OpenAI API:**
   ```bash
   suncli config --api-key <your-openai-api-key> --base-url https://api.openai.com/v1 --model gpt-4o-mini
   ```

2. **Start chatting:**
   ```bash
   suncli
   ```

## 🤖 AI Tools

Sun CLI can invoke a rich set of tools during conversations. The AI automatically decides which tools to use based on your requests.

### File & Shell Tools

| Tool | Description |
|------|-------------|
| `read` | Read file contents (supports offset/limit) |
| `write` | Write or overwrite files (auto-creates parent directories) |
| `edit` | Precise string replacement editing |
| `bash` | Execute shell commands (PowerShell on Windows, bash on Linux/Mac) |

### Extended Tools

| Tool | Description |
|------|-------------|
| `web_search` | Search the web (DuckDuckGo or Kimi native search) |
| `weather_now` | Current weather query (wttr.in) |
| `subagent` | Spawn a subagent with fresh context for sub-tasks |
| `background_run` | Run commands in the background |
| `background_check` | Check background task status and output |
| `schedule_create` | Create cron-based scheduled tasks |
| `schedule_list` | List scheduled tasks |
| `schedule_remove` | Remove a scheduled task |
| `save_memory` | Save cross-session memories |
| `load_memory` | Load stored memories |
| `team_spawn` | Create a teammate agent |
| `team_send` | Send messages to teammates |
| `team_list` | List all teammates |
| `worktree_create` | Create a Git worktree for isolated work |
| `worktree_enter` | Enter a worktree directory |
| `worktree_closeout` | Close a worktree (keep or remove) |

---

## 📋 Plan Mode

Plan Mode allows you to review and approve implementation plans before AI executes them. This is especially useful for complex tasks that involve multiple steps or code changes.

### Using Plan Mode

```bash
$ suncli

You: /plan
Enter your task to create a plan:

You: Add user authentication to the application

📋 Plan Preview
# Add User Authentication

Plan for: Add user authentication to the application

## Implementation Steps

⏳ **Step 1:** Create user model with password hashing
⏳ **Step 2:** Implement JWT token generation and validation
⏳ **Step 3:** Add login and logout API endpoints
⏳ **Step 4:** Create authentication middleware
⏳ **Step 5:** Add tests for authentication flow

Commands:
  /approve - Approve and execute the plan
  /modify  - Request plan modifications
  /cancel  - Cancel plan mode

You: /approve
✅ Plan Approved!

Proceeding with implementation...
[AI executes each step...]
```

### Plan Mode Commands

| Command | Description |
|---------|-------------|
| `/plan` | Enter plan mode for complex tasks |
| `/approve` | Approve and execute the current plan |
| `/modify` | Request plan modifications |
| `/cancel` | Cancel plan mode |

### When to Use Plan Mode

- **Complex refactoring** - Review the refactoring plan before making changes
- **Feature implementation** - Understand all steps before code is written
- **Multi-file changes** - See the full scope of changes upfront
- **Learning** - Understand how AI approaches complex problems

## 🔥 Smart Git Workflow

Sun CLI's intelligent Git workflow makes code commits simple:

### Usage

```bash
$ suncli

You: commit code

Smart Git Workflow
1. Pull from remote
2. Detect conflicts
3. Generate commit message
4. Commit and push

Pulling from remote...
Already up to date.

Generating commit message...

Suggested commit message:
┌─────────────────────────────────────────┐
│ feat: add user authentication module    │
│                                         │
│ - Implement JWT token validation        │
│ - Add login/logout endpoints            │
│ - Update user model with password hash  │
└─────────────────────────────────────────┘

Confirm commit? [Y/n]: y
Commit successful
Push successful
```

### Supported Commands

Natural language triggers:
- "commit code"
- "save and push"
- "提交代码"
- "保存并推送"
- ...and more

### Workflow Steps

1. **Auto Pull** - `git pull --rebase` to fetch remote changes first
2. **Conflict Detection** - Automatically detect merge conflicts
3. **Conflict Resolution** - Interactive conflict resolution UI (if conflicts occur)
4. **Generate Commit Message** - AI generates conventional commit message based on changes
5. **Auto Commit** - `git commit` to commit changes
6. **Auto Push** - `git push` to push to remote

### Conflict Resolution UI

```
⚠️ Detected 2 conflicted files

Processing: src/auth.py

Option 1: Keep current branch (HEAD/ours)
┌────────────────────────────────────┐
│ 1  def login_user(username):       │
│ 2      # TODO: implement           │
│ 3      return validate_token()     │
└────────────────────────────────────┘

Option 2: Keep remote branch (incoming/theirs)
┌────────────────────────────────────┐
│ 1  def login_user(username):       │
│ 2      user = get_user(username)   │
│ 3      return check_password(user) │
└────────────────────────────────────┘

Options:
  1 - Keep current branch changes (ours)
  2 - Keep remote branch changes (theirs)
  3 - Keep both changes (merge)
  e - Edit file manually
  s - Skip this file
  a - Abort rebase

Select resolution [1/2/3/e/s/a]: 
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

## 🎛️ Model Management

Sun CLI includes built-in presets for 8 popular AI providers:

| Provider | Example Models |
|----------|----------------|
| OpenAI | GPT-4o, GPT-4o-mini |
| Anthropic | Claude 3.5 Sonnet, Claude 3 Opus |
| Google | Gemini 2.0 Pro |
| Kimi (International) | Kimi K2.5, Kimi K2 |
| Kimi (Domestic) | moonshot-v1-128k/32k/8k |
| Qwen | Qwen-Max, Qwen-Plus, Qwen-Turbo |
| Zhipu (GLM) | GLM-4-Plus, GLM-4, GLM-4-Air |
| DeepSeek | DeepSeek-V3, DeepSeek-R1 |

### Commands

```bash
# Interactive model setup wizard
suncli models --setup

# List all available presets
suncli models --list

# Filter by provider
suncli models --provider Kimi

# Set model by preset name or model ID
suncli models --set "GPT-4o"
suncli models --set moonshot-v1-128k
```

## 📋 Task Board

Sun CLI maintains a persistent task board (stored in `.tasks/`) that tracks work items with dependency chains.

### Chat Commands

| Command | Description |
|---------|-------------|
| `/tasks` | Show the persistent task board |
| `/task <id> <status>` | Update task status (`pending` / `in_progress` / `completed`) |

## 📝 Input History

Your inputs are automatically saved and can be navigated with the **↑** and **↓** arrow keys during chat.

| Command | Description |
|---------|-------------|
| `/history` | Show recent input history (last 20 entries) |
| `/history clear` | Clear all input history |

## 🐛 Debug Mode

Enable detailed logging to troubleshoot issues:

```bash
suncli --debug
# or
suncli -d
```

This prints detailed logs including API requests, tool calls, context compression events, and more.

## Usage Example

```bash
$ suncli
+---------------- Sun CLI v0.2.0 -----------------+
| Welcome to Sun CLI                              |
| Model: gpt-4o-mini                              |
| Type /help for commands | exit or /quit to exit |
+-------------------------------------------------+

You: Hello!

Sun CLI: Hello! How can I help you today?

You: !dir
$ dir
[Directory listing shows here]

You: commit code
[Smart Git workflow executes...]

You: exit
Goodbye!
```

## Commands

| Command | Description |
|---------|-------------|
| `suncli` | Start interactive chat session |
| `suncli config --api-key <key>` | Set API key |
| `suncli config --base-url <url>` | Set API base URL |
| `suncli config --model <model>` | Set model |
| `suncli config --show` | Show current configuration |
| `suncli config --yolo` | Enable auto-confirm mode (skip all confirmations) |
| `suncli config --no-yolo` | Disable auto-confirm mode |
| `suncli models --setup` | Interactive model selection wizard |
| `suncli models --list` | List all available model presets |
| `suncli models --provider <name>` | Filter models by provider |
| `suncli models --set <preset>` | Set model by preset name or ID |
| `suncli prompt` | Preview combined system prompt |
| `suncli prompt --list` | List all prompt files |
| `suncli prompt --show <name>` | View a specific prompt |
| `suncli prompt --edit <name>` | Edit a prompt file |
| `suncli prompt --path` | Show prompts directory |
| `suncli --version` | Show version |
| `suncli --debug` | Enable debug mode with detailed logging |

## Chat Commands

During an interactive chat session:

| Command | Description |
|---------|-------------|
| `exit`, `quit` | Exit Sun CLI |
| `/help` | Show help |
| `/clear` | Clear conversation history (system prompt preserved) |
| `/new` | Start a new conversation |
| `/config` | Show current configuration |
| `/history` | Show recent input history |
| `/history clear` | Clear all input history |
| `/plan` | Enter plan mode for complex tasks |
| `/approve` | Approve and execute the current plan |
| `/modify` | Request plan modifications |
| `/cancel` | Cancel plan mode |
| `/tasks` | Show the persistent task board |
| `/task <id> <status>` | Update task status (`pending` / `in_progress` / `completed`) |
| `/next` | Interrupt current output and switch to next queued message |
| `Ctrl+O` | Shortcut to interrupt and switch to next queued message |

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

1. **Environment variables:** `SUN_API_KEY`, `SUN_MODEL`, `SUN_BASE_URL`, etc.
2. **Config file:** `%APPDATA%/sun-cli/.env` (Windows) or `~/.config/sun-cli/.env` (Linux/Mac)
3. **CLI:** `suncli config --api-key <key> --base-url <url> --model <model>`

### Kimi API (Moonshot) Configuration

```bash
suncli config --api-key sk-xxx --base-url https://api.moonshot.cn/v1 --model moonshot-v1-128k
```

Available Kimi models:
- `moonshot-v1-8k` - 8K context
- `moonshot-v1-32k` - 32K context
- `moonshot-v1-128k` - 128K context (recommended)

### OpenAI API Configuration

```bash
suncli config --api-key sk-xxx --base-url https://api.openai.com/v1 --model gpt-4o-mini
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SUN_API_KEY` | API key | - |
| `SUN_BASE_URL` | API base URL | `https://api.openai.com/v1` |
| `SUN_MODEL` | Model to use | `gpt-4o-mini` |
| `SUN_TEMPERATURE` | Sampling temperature | `0.7` |

## Advanced Features

### Context Compression

For long conversations, Sun CLI automatically compresses older messages to stay within token limits, while preserving the system prompt and recent context.

### Rate Limit Retry

If the API returns a 429 (rate limited) error, Sun CLI automatically retries with exponential backoff.

### Auto-Confirm Mode (Yolo Mode)

Skip all confirmation prompts for fully automated workflows:

```bash
suncli config --yolo
```

⚠️ **Warning:** In this mode, file modifications and Git operations execute without asking. Use with caution!

### Project Context Detection

On startup, Sun CLI automatically detects your project type and loads relevant context. If an `AGENTS.md` file exists in your project root, its instructions are automatically loaded into the system prompt.

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
