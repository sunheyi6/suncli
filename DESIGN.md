# Sun CLI Self-Improving Architecture Design

> 本文档记录 Sun CLI 自进化系统（s20）的完整设计思路与实现方案。
>
> 参考文章：[OpenClaw 对不起，我先转 Hermes 了——Hermes 源码拆解：Self-Improving 闭环怎么跑？](https://mp.weixin.qq.com/s/Qi68ptxQRyiA932JU49SYQ)

---

## 1. 设计目标

让 Sun CLI 从"人喂什么会什么"升级为"用得越久，能力越强"的自进化 Agent。

核心指标：
- **冷启动**：首次遇到新任务，靠基座模型能力解决
- **经验沉淀**：踩过的坑自动变成 Skill，下次同类任务直接调用
- **记忆压缩**：有限容量的 Memory 迫使 Agent 主动整理信息
- **静默学习**：后台 Review Agent 复盘，用户无感知

---

## 2. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        User Input                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    ChatSession (主 Agent)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Tool Loop   │  │ NudgeEngine │  │ SkillManagerV2      │  │
│  │ (10 iter)   │  │ (计数器)     │  │ (渐进式加载)         │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────┘  │
│         │                │                                    │
│         ▼                ▼                                    │
│  ┌─────────────────────────────────────────────────────┐     │
│  │              Background Review Agent                 │     │
│  │  (fork 子 Agent，静默分析 → save_memory/skill_manage) │     │
│  └─────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Persistent Storage                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ .memory/     │  │ .skills/     │  │ SecurityScanner  │   │
│  │ (容量受限)    │  │ (经验手册)    │  │ (威胁检测+回滚)   │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 四个子系统详解

### 3.1 Memory 系统（改造后）

**设计哲学**：容量有限 → 信息压缩 → 高密度事实

| 特性 | 实现 |
|------|------|
| 存储位置 | `.memory/{user,feedback,project,reference}/` |
| 容量上限 | `user`: 1375 chars, `project/reference`: 2200 chars |
| 超限处理 | 拒绝写入，返回当前条目列表，引导模型主动整理 |
| 内容格式 | 声明式事实（"User prefers tabs"）而非命令（"Always use tabs"） |
| 安全扫描 | 保存前扫描 prompt injection / exfiltration 模式 |
| 会话注入 | 启动时冻结快照，保护前缀缓存 |

**关键代码**：
- `sun_cli/memory/manager.py` — `MemoryManager.save()` 容量检查
- `sun_cli/security/scanner.py` — `scan_memory_content()`

---

### 3.2 Skill 系统 v2（核心新增）

**设计哲学**：Memory 存"我知道什么"，Skill 存"我会做什么"

**Skill 文件格式**：
```markdown
---
name: flask-k8s-deploy
description: Deploy a Flask app to Kubernetes with health checks
version: 1.0.0
category: devops
last_used: 2024-01-15T10:30:00
use_count: 5
success_rate: 0.95
---
# Flask K8s Deployment

## When to use
- User wants to deploy a Flask/Python app to Kubernetes

## Steps
1. Create Dockerfile with gunicorn
2. Build and push image BEFORE kubectl apply
...

## Pitfalls
- MUST push image first, otherwise ImagePullBackOff
```

**渐进式加载**：
- 系统提示词只放索引：`flask-k8s-deploy: Deploy a Flask app...`
- Agent 判断相关时，调用 `skill_view(name)` 加载全文
- 避免 Token 浪费和注意力稀释

**自动创建触发条件**（由 Tool Schema 描述引导）：
- 复杂任务成功（5+ 工具调用）
- 踩坑后修复的经验
- 用户纠正过的做法
- 非平凡工作流发现

**自我修补**：
- `skill_manage(action="patch", old_string="...", new_string="...")`
- 模糊匹配容忍格式差异
- 修改前自动备份 → 安全扫描 → 不通过则回滚

**生命周期元数据**（Phase 4）：
- `use_count`: 使用次数
- `success_rate`: 成功率（贝叶斯更新）
- `last_used`: 最后使用时间
- `archived`: 归档标志（超过 90 天未用且使用 < 3 次自动归档）

**关键代码**：
- `sun_cli/skills_v2/skill.py` — `SkillEntry` 数据模型
- `sun_cli/skills_v2/manager.py` — `SkillManagerV2`
- `sun_cli/skills_v2/tools.py` — `skill_view` / `skill_manage` 工具处理器

---

### 3.3 Nudge Engine（核心新增）

**设计哲学**：谁来提醒 Agent "该学习了"

**两个计数器**：

| 计数器 | 粒度 | 触发条件 | 审查重点 |
|--------|------|----------|----------|
| Memory Nudge | 用户回合 | 每 10 个 user turn | 用户偏好、环境事实、纠正记录 |
| Skill Nudge | 工具迭代 | 每 10 个 tool iteration | 非平凡解题过程、新坑、修复经验 |

**后台审查流程**：
1. 用户收到最终回复后，触发审查
2. 后台 `asyncio.create_task()` 启动 Review Agent
3. Review Agent 拿到对话快照，独立分析
4. 如果有值得保存的，调用 `save_memory` / `skill_manage`
5. 用户完全无感知

**Review Agent 约束**：
- 最多 8 次工具调用（防止无限消耗）
- 禁用自身的 nudge（防止无限递归）
- 输出重定向到 `/dev/null`
- 保守策略："If nothing is worth saving, say 'Nothing to save.'"

**关键代码**：
- `sun_cli/nudge/engine.py` — `NudgeEngine`
- `sun_cli/nudge/review_agent.py` — `ReviewAgent`

---

### 3.4 安全机制（核心新增）

**设计哲学**：Agent 能往自己"脑子"里写东西，攻击面必须受控

**两层防护**：

1. **Memory 内容扫描**
   - 检测 prompt injection（"ignore previous instructions"）
   - 检测 deception（"do not tell the user"）
   - 检测 exfiltration（curl 带密钥）
   - 检测系统提示词覆盖

2. **Skill 安全扫描**
   - 继承 Memory 全部规则
   - 增加 destructive command 检测（`rm -rf /`, `mkfs`）
   - 增加 privilege escalation 检测
   - patch 时扫描新内容，不通过则回滚

**自动回滚**：
- 修改前备份 `.md.bak`
- 扫描失败 → 恢复备份
- 所有写操作原子化

**关键代码**：
- `sun_cli/security/scanner.py` — `SecurityScanner`

---

## 4. Web 服务层（Vercel 部署）

### 4.1 架构

```
┌─────────────┐     HTTP      ┌─────────────────┐
│   Client    │ ────────────► │  Vercel Edge    │
│  (Browser)  │ ◄──────────── │  (FastAPI/ASGI) │
└─────────────┘               └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │  ChatSession    │
                              │  (console-less) │
                              └─────────────────┘
```

### 4.2 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 + 功能状态 |
| `/api/chat` | POST | 发送消息，返回完整响应 |
| `/api/skills` | GET | 列出所有 Skill + 统计 |
| `/api/memories` | GET | 列出所有 Memory |
| `/api/config` | GET | 当前配置（脱敏） |

### 4.3 部署配置

- `api/index.py` — Vercel Serverless 入口
- `vercel.json` — 路由与构建设置
- `requirements.txt` — 依赖清单

**关键技术点**：
- Console 输出重定向到 `io.StringIO()`，避免 Web 环境 TTY 问题
- `sys.path` 注入确保包可导入
- 多会话支持（内存存储，生产环境建议换 Redis）

---

## 5. 配置项

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `SUN_SELF_IMPROVING` | `true` | 启用自进化系统 |
| `SUN_MEMORY_NUDGE_INTERVAL` | `10` | 用户回合审查间隔 |
| `SUN_SKILL_NUDGE_INTERVAL` | `10` | 工具迭代审查间隔 |
| `SUN_MEMORY_CHAR_LIMIT` | `2200` | project/reference 容量上限 |
| `SUN_USER_CHAR_LIMIT` | `1375` | user 容量上限 |

---

## 6. 数据流示例：三次会话演进

### 会话 1：冷启动

```
User: 帮我把 Flask 应用部署到 K8s
Agent: [12 次工具调用，踩 2 个坑]
       → ImagePullBackOff（忘记推镜像）
       → CrashLoopBackOff（livenessProbe 路径不对）
       → 修复后成功

后台 Review Agent 触发：
  → skill_manage(action="create", name="flask-k8s-deploy", ...)
  → 创建 Skill，包含 Steps 和 Pitfalls
```

### 会话 2：Skill 复用 + 自我修补

```
User: 部署 Django 应用到 K8s
Agent: [加载 flask-k8s-deploy Skill]
       → 9 次调用（比之前少 3 次）
       → 已知坑被绕过
       → 遇到 Django 新坑：DisallowedHost
       → 修复成功

后台 Review Agent：
  → skill_manage(action="patch", old_string="...", new_string="...")
  → 在 Pitfalls 中补上 ALLOWED_HOSTS
  → save_memory(name="registry", type="project", ...)
```

### 会话 3：零错误

```
User: 部署 FastAPI 微服务
Agent: [6 次调用，零错误]
       → Skill 已包含所有已知坑
       → Memory 已知 registry 地址
```

---

## 7. 与原有系统的兼容

| 原有模块 | 改动 | 兼容策略 |
|----------|------|----------|
| `skills/` (v1) | 无改动 | 保留作为命令拦截器，与新 Skill v2 并存 |
| `memory/manager.py` | 增加容量限制 + 安全扫描 | 向后兼容，超限返回结构化错误 |
| `chat.py` | 集成 Nudge + Skill v2 | 原有逻辑不变，新增 hook 点 |
| `tools/definitions.py` | 新增 `skill_view` / `skill_manage` | 原有工具不变 |
| `config.py` | 新增 5 个配置项 | 有默认值，不影响旧配置 |

---

## 8. 已知限制与未来方向

### 当前限制
1. **Review Agent 成本**：每 10 轮触发一次 LLM 调用，有 API 成本
2. **Skill 模糊匹配**：当前 patch 的 fuzzy replace 较简单，复杂替换可能失败
3. **Vercel 超时**：Serverless Functions 有执行时间限制（~30s），长对话可能超时
4. **单点存储**：Memory/Skill 存储在本地磁盘，多实例部署需共享存储

### 未来方向
1. **生命周期管理**：基于 `use_count` / `success_rate` 自动降权、归档、过时检测
2. **技能组合**：识别经常一起使用的 Skill，自动合成为 Workflow
3. **创建透明度**：Skill 创建后给用户简短通知，允许审核和纠正
4. **团队治理**：写操作需二次确认，每一次会话可追溯、可审计
5. **向量检索**：Skill 索引改用向量相似度匹配，而非纯字符串索引

---

## 9. 参考文章与框架

### 核心参考

1. **[Hermes Agent 源码拆解：Self-Improving 闭环](https://mp.weixin.qq.com/s/Qi68ptxQRyiA932JU49SYQ)**
   - 原文作者：阿里云开发者社区
   - 核心参考：Memory 容量限制、Skill 渐进式加载、Nudge Engine 后台审查、安全扫描机制
   - 仓库：`github.com/NousResearch/hermes-agent`

### 相关框架与项目

2. **[OpenClaw / RDSClaw](https://openclaw.ai/)**
   - 对比基准：Skill 是手写 Markdown，Agent 不会自主学习
   - 迁移路径：`hermes claw migrate` 命令设计理念来源

3. **[Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview)**
   - Sun CLI 原始灵感来源：多轮工具调用、计划模式、上下文收集

4. **[MemGPT / Letta](https://github.com/cpacker/MemGPT)**
   - 参考：分层记忆管理（core vs archival memory）、记忆自动整理

5. **[AutoGPT](https://github.com/Significant-Gravitas/AutoGPT)**
   - 参考：Agent 自主循环、长期记忆持久化

6. **[LangChain / LangGraph](https://github.com/langchain-ai/langchain)**
   - 参考：工具调用抽象、Agent 执行图

7. **[Vercel Python Runtime](https://vercel.com/docs/functions/runtimes/python)**
   - 部署参考：ASGI 应用部署、Serverless Functions 配置

### 学术论文与概念

8. **"Data Is the Final Moat"**（Hacker News 讨论）
   - 核心理念：当模型智能被商品化，真正的护城河是 Agent 在工作中积累的领域知识

9. **Self-Referential Learning / Meta-Learning**
   - 理论基础：Agent 不仅学习任务，还学习"如何学习"

10. **Prefix Caching (LLM Inference Optimization)**
    - 工程参考：冻结 Memory 快照以保护系统提示词前缀缓存，降低 API 成本

---

## 10. 文件清单

### 新增文件

```
sun_cli/skills_v2/
├── __init__.py          # 模块入口
├── skill.py             # SkillEntry 数据模型
├── manager.py           # SkillManagerV2（CRUD + 渐进加载 + 生命周期）
└── tools.py             # skill_view / skill_manage 工具处理器

sun_cli/nudge/
├── __init__.py          # 模块入口
├── engine.py            # NudgeEngine（计数器 + 后台审查触发）
└── review_agent.py      # ReviewAgent（静默分析 + 提取学习）

sun_cli/security/
├── __init__.py          # 模块入口
└── scanner.py           # SecurityScanner（Memory/Skill 威胁检测）

sun_cli/web/
├── __init__.py          # 模块入口
└── server.py            # FastAPI 应用（REST API）

api/
└── index.py             # Vercel Serverless 入口

vercel.json              # Vercel 部署配置
requirements.txt         # 依赖清单（含 fastapi/uvicorn）
DESIGN.md                # 本文档
```

### 修改文件

```
sun_cli/tools/definitions.py   # 新增 SKILL_VIEW_TOOL / SKILL_MANAGE_TOOL
sun_cli/chat.py                # 集成 NudgeEngine + SkillManagerV2 + 工具处理器
sun_cli/memory/manager.py      # 容量限制 + 安全扫描 + 结构化返回
sun_cli/skills_v2/manager.py   # 安全扫描 + 自动备份回滚
sun_cli/config.py              # 新增 5 个自进化配置项
```

---

*文档版本: 0.3.0*  
*最后更新: 2026-04-23*
