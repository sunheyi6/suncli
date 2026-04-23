# Memory 系统设计

## 设计哲学

**容量有限 → 信息压缩 → 高密度事实**

OpenClaw 的 MEMORY.md 是纯追加模式，用几个月就膨胀成几万行的怪兽文件。Sun CLI 的做法反过来：容量有限就倒逼 Agent 做信息整理，过时的自然被挤掉，留下的都是高密度事实。

## 存储结构

```
.memory/
├── MEMORY.md              # 自动维护的索引
├── user/
│   └── prefer_tabs.md
├── feedback/
│   └── avoid_mock.md
├── project/
│   └── conventions.md
└── reference/
    └── external_resources.md
```

## 容量限制

| 类型 | 上限 | 存储内容 |
|------|------|----------|
| `user` | 1375 chars | 用户偏好、沟通风格 |
| `feedback` | 2200 chars | 纠正记录、用户反馈 |
| `project` | 2200 chars | 项目约定、环境事实 |
| `reference` | 2200 chars | 外部资源、工具怪癖 |

## 超限处理

当 `save_memory` 会导致超限时，系统不静默丢弃，而是返回结构化错误：

```json
{
  "success": false,
  "error": "Memory at 2100/2200 chars. Adding this entry (200 chars) would exceed the limit. Replace or remove existing entries first.",
  "current_entries": [
    {"name": "pytest_config", "chars": 450},
    {"name": "registry_url", "chars": 120}
  ],
  "usage": "2100/2200"
}
```

错误信息中的 "Replace or remove existing entries first" 引导模型调用 `edit` 或 `bash` 来整理现有条目。模型看到所有条目后，自己决定哪些过时了该删、哪些可以合并压缩。这本身就是一次"自我反思"。

## 内容边界

**Memory 存事实，Skill 存步骤。**

- **GOOD**: `"User prefers concise responses"` — 声明式事实，可被当前上下文覆盖
- **BAD**: `"Always respond concisely"` — 命令式指令，限制 Agent 灵活性
- **GOOD**: `"Project uses pytest with xdist"` — 环境事实
- **BAD**: `"Run tests with pytest -n 4"` — 操作步骤，应存为 Skill

## 冻结快照机制

每次会话启动时，Memory 加载后立刻捕获一份快照：

```python
self._system_prompt_snapshot = {
    "memory": self._render_block("memory", self.memory_entries),
    "user": self._render_block("user", self.user_entries),
}
```

快照注入系统提示词后，会话内不再变动。为什么"冻结"而不是实时更新？因为系统提示词会话内不变就能共享前缀缓存（Prefix Cache），省掉重复计费。新写入的内容只改磁盘，下一个会话才刷新进来。

## 安全扫描

Memory 内容最终会注入系统提示词，是一等安全边界。保存前扫描：

- `ignore (previous|all|above|prior) instructions` — Prompt Injection
- `do not tell (the )?user` — Deception
- `system prompt override` — 系统提示词覆盖
- `curl .*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD)` — 数据外泄
- `forget (everything|all|your) instructions` — 指令遗忘攻击
