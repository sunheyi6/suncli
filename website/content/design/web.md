# Web 服务层设计

## 设计目标

将 Sun CLI 的核心能力暴露为 HTTP API，支持部署到 Vercel 等 Serverless 平台。

## 架构

```
Client (Browser/Curl)
    │
    ▼ HTTP
┌─────────────────┐
│  Vercel Edge    │
│  (FastAPI/ASGI) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ChatSession    │
│  (console-less) │
└─────────────────┘
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 + 功能状态 |
| `/api/chat` | POST | 发送消息，返回完整响应 |
| `/api/skills` | GET | 列出所有 Skill + 统计 |
| `/api/memories` | GET | 列出所有 Memory |
| `/api/config` | GET | 当前配置（脱敏） |

### Chat 请求/响应

```bash
POST /api/chat
Content-Type: application/json

{
  "message": "帮我把 Flask 应用部署到 K8s",
  "conversation_id": "optional-id"
}
```

```json
{
  "response": "部署完成...",
  "conversation_id": "abc123",
  "tool_calls_used": 6
}
```

## 关键技术点

### Console 输出抑制

ChatSession 依赖 rich.Console 进行终端输出。在 Web 模式下：

```python
string_io = io.StringIO()
console = Console(file=string_io, force_terminal=False, color_system=None)
session = ChatSession(console=console)
```

所有终端输出被重定向到 `StringIO`，不会污染 HTTP 响应。

### 多会话支持

```python
_sessions: dict[str, ChatSession] = {}

def _get_or_create_session(conversation_id: str) -> ChatSession:
    if conversation_id in _sessions:
        return _sessions[conversation_id]
    session = ChatSession(console=console)
    _sessions[conversation_id] = session
    return session
```

生产环境建议替换为 Redis 存储会话状态。

### Vercel 部署配置

```json
{
  "version": 2,
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    { "src": "/api/(.*)", "dest": "api/index.py" },
    { "src": "/(.*)", "dest": "api/index.py" }
  ]
}
```

## 已知限制

1. **执行时间**：Vercel Serverless Functions 有 ~30s 超时限制，长对话可能超时
2. **状态存储**：内存中的 `_sessions` 在实例回收后丢失
3. **流式响应**：当前版本返回完整响应，未来可升级为 SSE/WebSocket 流式
