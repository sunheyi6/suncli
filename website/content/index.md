# Sun CLI

> 一个会自己进化的 AI Agent。Memory 记住你是谁，Skill 记住怎么做事，Nudge Engine 保证这个循环不停转。

---

## 核心亮点

### 01 — 自进化 Memory

容量受限的持久记忆系统（project/reference: 2200 chars, user: 1375 chars）。超限后拒绝写入并返回当前条目列表，倒逼 Agent 主动整理信息，只保留高密度事实。写入前经过安全扫描，防止 Prompt Injection。

### 02 — Skill 系统 v2

将踩坑经验自动提炼为可复用的任务手册。每个 Skill 包含 **When to use**、**Steps**、**Pitfalls** 三个核心部分。系统提示词只放索引（名字+一句话描述），Agent 判断相关时通过 `skill_view` 按需加载全文，避免 Token 浪费。

### 03 — Nudge Engine

两个独立计数器定时触发后台 Review Agent：
- **Memory Nudge**：每 10 个用户回合审查用户偏好、纠正记录
- **Skill Nudge**：每 10 个工具迭代审查非平凡解题过程

Review Agent 在后台静默运行，用户完全无感知。发现值得保存的内容时自动调用 `save_memory` 或 `skill_manage`。

### 04 — 安全机制

Agent 能往自己"脑子"里写东西，攻击面必须受控：
- **Memory 扫描**：Prompt Injection、Deception、Exfiltration 检测
- **Skill 扫描**：继承 Memory 规则 + Destructive Commands、Privilege Escalation 检测
- **自动回滚**：修改前自动备份 `.md.bak`，扫描不通过立即恢复

### 05 — 多 Agent 协作

支持 spawn 持久化队友（coder / tester / reviewer / researcher / docs），通过 JSONL Mailbox 系统异步通信。主 Agent 可以并行分发子任务，每个 teammate 拥有独立的 Message History 和角色提示词。

### 06 — 生命周期管理

每个 Skill 自动追踪 `use_count`、`success_rate`、`last_used`：
- 贝叶斯更新成功率：`(old_rate * (n-1) + result) / n`
- 超过 90 天未用且使用 < 3 次自动归档
- 防止"经验负债"——不维护的 Skill 比没有更糟

---

## 自进化闭环

```
User Task → Agent Execution → Errors & Fixes
                                    ↓
                    ┌─────────────────────────┐
                    │    Nudge Engine         │
                    │  (counters threshold)   │
                    └───────────┬─────────────┘
                                ↓
                    ┌─────────────────────────┐
                    │   Review Agent          │
                    │  (silent background)    │
                    └───────────┬─────────────┘
                                ↓
              ┌─────────────────┼─────────────────┐
              ↓                 ↓                 ↓
        save_memory      skill_manage       skill_manage
        (facts)          (create)           (patch)
              ↓                 ↓                 ↓
           .memory/         .skills/          .skills/
              └─────────────────┴─────────────────┘
                                ↓
                        Next Session
                        (faster & fewer errors)
```

**三次会话对比**：

| 维度 | 会话 1 (冷启动) | 会话 2 (Skill 复用) | 会话 3 (全协同) |
|------|----------------|-------------------|---------------|
| 工具调用 | 12 次 | 9 次 | 6 次 |
| 错误数 | 2 | 1 | 0 |
| Memory | 无 | 触发写入 | 系统提示词注入 |
| Skill | 触发创建 | 复用 + 自我修补 | 复用已修补版本 |

---

## 技术统计

| 指标 | 数值 |
|------|------|
| 内置工具 | 19 种 |
| 上下文压缩 | 3 层 (Micro / Auto / Manual) |
| Memory 容量 | 2200 / 1375 chars |
| Skill 加载 | 渐进式 (索引 → 按需全文) |
| Nudge 间隔 | 10 回合 / 10 迭代 |
| 用户打扰 | 0 (后台静默) |

---

## 理念

> 你的时间应该花在让 Agent 做事上，而不是给 Agent 做运维上。
>
> 当模型智能被商品化，真正的护城河是 Agent 在工作中积累的领域知识。
