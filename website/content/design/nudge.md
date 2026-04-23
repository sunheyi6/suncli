# Nudge Engine 设计

## 设计哲学

**Memory 和 Skill 都是存储系统，写入需要有人触发。Nudge Engine 就是这个触发器——运行时维护两个计数器，定时提醒 Agent 该停下来想想了。**

大多数 Agent 每次会话结束后就"失忆"了。Nudge Engine 保证学习循环不停转。

## 两个计数器

| 计数器 | 粒度 | 触发阈值 | 审查重点 |
|--------|------|----------|----------|
| Memory Nudge | 用户回合 | 每 10 个 user turn | 用户偏好、环境事实、纠正记录 |
| Skill Nudge | 工具迭代 | 每 10 个 tool iteration | 非平凡解题过程、新坑、修复经验 |

```python
# chat.py
self.nudge = NudgeEngine(
    client=self.client,
    config=self.config,
    memory_nudge_interval=10,
    skill_nudge_interval=10,
)
```

粒度不同是有道理的：
- Memory 的信息来自用户输入，按回合计
- Skill 的经验来自工具使用过程，按迭代计

## 计数器生命周期

```
User Turn  →  on_user_turn()  →  turns_since_memory += 1
Tool Iter  →  on_tool_iteration() →  iters_since_skill += 1
Memory Save → on_memory_saved() →  turns_since_memory = 0
Skill Manage → on_skill_managed() →  iters_since_skill = 0
```

Agent 主动调用了 `memory` 或 `skill_manage` 则重置计数器——已经在做了就不用催。

## 后台审查流程

```python
async def maybe_trigger_review(messages_snapshot):
    review_memory = turns_since_memory >= memory_nudge_interval
    review_skills = iters_since_skill >= skill_nudge_interval
    
    if review_memory or review_skills:
        asyncio.create_task(
            run_background_review(messages_snapshot, review_memory, review_skills)
        )
```

**关键设计：审查在响应发送给用户之后才触发。** 用户收到回复后该干嘛干嘛，Agent 在后台默默复盘。

## Review Agent 实现

```python
async def _run_background_review(messages, review_memory, review_skills):
    review_agent = ReviewAgent(client, config)
    
    if review_memory:
        result = await review_agent.review_memory(messages, current_memories)
        if result:
            await _apply_memory_result(result)
    
    if review_skills:
        result = await review_agent.review_skills(messages, current_skills)
        if result:
            await _apply_skill_result(result)
```

Review Agent 约束：
- 最多 8 次工具调用，不会无限消耗 API
- 禁用自身的 nudge（`memory_nudge_interval = 0`），避免无限递归
- 输出重定向到 `/dev/null`，用户完全无感知
- 和主 Agent 共享同一份 Memory/Skill，写入直接生效

## 审查提示词设计

**Memory Review Prompt** 关注 durable facts：

```
Review this conversation and decide if there are durable facts worth saving.
- Save user preferences, environment details, tool quirks
- Prioritize what reduces future user steering
- Write as declarative facts, not instructions
- If nothing is worth saving, say "Nothing to save."
```

**Skill Review Prompt** 关注 procedural knowledge：

```
Review this conversation and decide if there's procedural knowledge worth saving.
- Create when: complex task succeeded (5+ calls), errors overcome
- A skill should have: When to use, Steps, Pitfalls
- If user corrected your approach, that's valuable
- If nothing is worth saving, say "Nothing to save."
```

每个 prompt 都以 "If nothing is worth saving, just say 'Nothing to save.' and stop." 收尾——防止 review agent 每次都往里塞东西来"交差"。
