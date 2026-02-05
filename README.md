# 🌞 Sun CLI

A Claude-like CLI tool powered by AI, built with Python.

## Features

- 💬 Interactive chat with streaming responses
- 📝 Markdown-based prompt system (inspired by OpenClaw)
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

### Example: Customizing Identity

```bash
$ suncli prompt --edit identity
```

Edit `identity.md`:

```markdown
# Code Reviewer

You are an expert code reviewer focused on:
- Clean code principles
- Performance optimization
- Security best practices

## Style

- Be direct and constructive
- Provide specific examples
- Always suggest improvements, don't just criticize
```

Next time you start `suncli`, the AI will use this identity!

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
