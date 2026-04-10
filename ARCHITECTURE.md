# Sun CLI 架构文档

本文档描述了 Sun CLI 的完整架构，实现了从 s01 到 s19 的所有高级功能。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface                          │
│                     (cli.py, chat.py)                        │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    ChatSession                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Agent Loop  │  │ Tool Router │  │ Context Compression │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼─────┐ ┌───▼────┐ ┌────▼─────┐
│   Native    │ │ Sub-   │ │ Background│
│   Tools     │ │ agent  │ │  Tasks    │
└───────┬─────┘ └───┬────┘ └────┬─────┘
        │           │           │
┌───────▼───────────▼───────────▼─────┐
│         Extension Systems              │
│  ┌────────┐ ┌────────┐ ┌──────────┐  │
│  │ Memory │ │  Team  │ │ Worktree │  │
│  └────────┘ └────────┘ └──────────┘  │
│  ┌────────┐ ┌────────┐ ┌──────────┐  │
│  │Schedule│ │  MCP   │ │  Plugin  │  │
│  └────────┘ └────────┘ └──────────┘  │
└───────────────────────────────────────┘
```

## 核心功能实现 (s01-s19)

### s01: Agent Loop
**文件**: `chat.py` - `_run_tool_loop()`

核心循环实现:
```python
while iteration < max_iterations:
    response = call_llm(messages)
    if not has_tool_calls(response):
        return response  # Done
    results = execute_tools(response)
    messages.append(tool_results)  # Feed back to model
```

### s02: 工具路由 + 路径安全
**文件**: `tools/sandbox.py`, `tools/executor.py`

- `PathSandbox` - 确保所有文件操作在工作区内
- `ToolExecutor` - 可扩展的工具注册表
- 标准化工具定义 Schema

### s03: TodoWrite / 计划模式
**文件**: `plan_mode.py`

- 计划创建和步骤追踪
- 用户审批工作流
- 持久化任务图

### s04: Subagents
**文件**: `subagent.py`

```python
async def run_subagent(prompt: str) -> str:
    # Fresh context, no parent history
    sub_messages = [{"role": "user", "content": prompt}]
    # Run sub-loop
    # Return summary only
```

### s05: Skills
**文件**: `skills/`

- 模块化技能系统
- Git、Prompt、Config 等内置技能
- 动态加载

### s06: 三层上下文压缩
**文件**: `chat.py` - `_micro_compact()`, `_maybe_compact_context()`

Layer 1: Micro-compact - 替换旧 tool_result 为占位符  
Layer 2: Auto-compact - Token 超阈值时 LLM 摘要  
Layer 3: Manual compact - 显式 compact 工具

### s07: 任务图
**文件**: `task_manager.py`

- 文件化任务存储 (`.tasks/`)
- 依赖关系 (`depends_on`)
- 状态管理 (pending -> in_progress -> completed)

### s08/s13: 后台任务
**文件**: `background.py`

```python
background_run("npm install")  # Returns immediately
check_notifications()  # Before each LLM call
```

- 线程池执行
- 通知队列
- 持久化输出

### s09: Memory
**文件**: `memory/manager.py`

存储位置: `.memory/`
- `user/` - 用户偏好
- `feedback/` - 纠正记录
- `project/` - 项目约定
- `reference/` - 外部资源

### s14: 定时调度
**文件**: `task/scheduler.py`

- Cron 表达式支持
- 持久化调度记录
- 自动触发注入

### s15-s17: 团队系统
**文件**: `team/`

```
.team/
├── config.json      # 团队名册
├── inbox/           # 邮箱系统
│   ├── alice.jsonl
│   └── bob.jsonl
└── requests/        # 协议请求
```

- Teammate: 持久化智能体，独立消息历史
- Mailbox: JSONL 文件收件箱
- Protocol: 结构化请求-响应 (request_id)
- Auto-claim: 空闲时自动认领任务

### s18: Worktree 隔离
**文件**: `worktree/manager.py`

```
.worktrees/
├── index.json       # 注册表
├── events.jsonl     # 生命周期日志
├── auth-refactor/   # 隔离工作目录
└── ui-login/
```

- Git worktree 管理
- 任务绑定
- 显式 closeout (keep/remove)

### s19: MCP / Plugin
**文件**: `mcp/`

- MCP 客户端协议
- 外部工具服务器连接
- Plugin 发现和加载 (`.claude-plugin/`)

## 新增工具列表

| 工具 | 功能 | 章节 |
|------|------|------|
| `subagent` | 委派子任务 | s04 |
| `background_run` | 后台执行 | s13 |
| `background_check` | 检查后台任务 | s13 |
| `schedule_create` | 创建定时任务 | s14 |
| `schedule_list` | 列出定时任务 | s14 |
| `schedule_remove` | 删除定时任务 | s14 |
| `team_spawn` | 创建队友 | s15 |
| `team_send` | 发送消息 | s15 |
| `team_list` | 列出队友 | s15 |
| `request_approval` | 请求审批 | s16 |
| `worktree_create` | 创建工作树 | s18 |
| `worktree_enter` | 进入工作树 | s18 |
| `worktree_closeout` | 关闭工作树 | s18 |
| `save_memory` | 保存记忆 | s09 |
| `load_memory` | 加载记忆 | s09 |

## 目录结构

```
sun_cli/
├── cli.py                 # 主 CLI 入口
├── chat.py                # 增强版 ChatSession
├── config.py              # 配置管理
├── models.py              # 数据模型
├── subagent.py            # s04: Subagent
├── background.py          # s13: 后台任务
├── plan_mode.py           # s03: 计划模式
├── task_manager.py        # s07: 任务图
├── context_collector.py   # 上下文收集
│
├── tools/                 # 工具系统
│   ├── __init__.py
│   ├── sandbox.py         # s02: 路径安全
│   ├── definitions.py     # 工具定义
│   └── executor.py        # 工具执行器
│
├── memory/                # s09: Memory
│   ├── __init__.py
│   └── manager.py
│
├── team/                  # s15-s17: 团队
│   ├── __init__.py
│   ├── teammate.py        # 队友实现
│   ├── mailbox.py         # 邮箱系统
│   ├── protocol.py        # s16: 协议
│   └── manager.py         # 团队管理
│
├── worktree/              # s18: Worktree
│   ├── __init__.py
│   └── manager.py
│
├── mcp/                   # s19: MCP
│   ├── __init__.py
│   ├── client.py          # MCP 客户端
│   └── plugin.py          # Plugin 加载
│
├── task/                  # s14: 调度
│   ├── __init__.py
│   └── scheduler.py
│
├── prompts/               # 提示词系统
├── skills/                # 技能系统
└── ...
```

## 使用示例

### Subagent
```
You: 使用 subagent 分析所有 Python 文件的依赖关系
```

### 后台任务
```
You: 在后台运行 pytest
AI: <tool name="background_run">
  <arg name="command">pytest -v</arg>
  <arg name="description">Run all tests</arg>
</tool>
```

### 团队
```
You: 创建一个 coder 队友叫 alice
AI: <tool name="team_spawn">
  <arg name="name">alice</arg>
  <arg name="role">coder</arg>
  <arg name="prompt">You are a Python expert...</arg>
</tool>
```

### Worktree
```
You: 为任务 12 创建 worktree "auth-refactor"
AI: <tool name="worktree_create">
  <arg name="name">auth-refactor</arg>
  <arg name="task_id">12</arg>
</tool>
```

### Memory
```
You: 记住我喜欢用 tabs 而不是空格
AI: <tool name="save_memory">
  <arg name="name">prefer_tabs</arg>
  <arg name="mem_type">user</arg>
  <arg name="content">User prefers tabs for indentation</arg>
</tool>
```

## 安全特性

1. **路径沙箱** - 所有文件操作必须通过 `safe_path()`
2. **工具白名单** - 可配置允许的工具
3. **审批流程** - 高风险操作需用户确认
4. **超时保护** - 命令执行有默认超时

## 扩展性

添加新工具的步骤:

1. 在 `tools/definitions.py` 定义工具 schema
2. 在 `ChatSession._register_custom_tools()` 注册处理器
3. 在处理器中实现业务逻辑

## 相关教程

本项目实现了 https://learn.shareai.run/ 的完整教程系列:
- s01-s07: 核心 Agent 循环
- s08-s12: 并发和隔离
- s13-s14: 后台和调度
- s15-s18: 多智能体团队
- s19: MCP 扩展
