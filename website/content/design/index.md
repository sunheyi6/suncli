# 设计思路

> 本文档按层级展开 Sun CLI 自进化系统（s20）的完整设计。

---

## 目录

1. [架构总览](/design/architecture)
2. [Memory 系统设计](/design/memory)
3. [Skill 系统 v2 设计](/design/skill)
4. [Nudge Engine 设计](/design/nudge)
5. [安全机制设计](/design/security)
6. [生命周期设计](/design/lifecycle)
7. [Web 服务层设计](/design/web)
8. [数据流与演进示例](/design/flow)

---

## 设计目标

让 Sun CLI 从"人喂什么会什么"升级为"用得越久，能力越强"的自进化 Agent。

核心指标：
- **冷启动**：首次遇到新任务，靠基座模型能力解决
- **经验沉淀**：踩过的坑自动变成 Skill，下次同类任务直接调用
- **记忆压缩**：有限容量的 Memory 迫使 Agent 主动整理信息
- **静默学习**：后台 Review Agent 复盘，用户无感知

---

## 核心原则

1. **声明式事实 vs 操作步骤分离**
   - Memory 存事实（"User prefers tabs"）
   - Skill 存步骤（"Steps: 1. Create Dockerfile..."）
   - 两者更新频率、触发条件、安全风险完全不同

2. **容量倒逼压缩**
   - Memory 不设上限 = 无限追加的噪声
   - 超限失败 → 返回当前条目 → 模型主动整理
   - 这本身就是一次"自我反思"

3. **渐进式加载**
   - 重型背包模式：每次会话全量加载 = Token 浪费 + 注意力稀释
   - 动态图书馆模式：系统提示词只放索引，相关时才加载全文

4. **自省不占用用户注意力**
   - 后台 fork 独立 Agent 做审查
   - 用户收到回复后该干嘛干嘛
   - "干活"和"反思"拆成两个实例
