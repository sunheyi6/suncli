# Skill 系统 v2 设计

## 设计哲学

**Memory 是"我知道什么"，Skill 是"我会做什么"。**

旧版 Skill 是"命令拦截器"——基于 `trigger_keywords` 字符串匹配后接管输入。新版 Skill 是"经验资产"——可复用的任务手册，由 LLM 通过工具调用按需读取。

## Skill 文件格式

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
- User mentions K8s, kubectl, or container deployment

## Steps
1. Create Dockerfile with gunicorn (not dev server)
2. Build and push image to registry BEFORE creating deployment
3. Write deployment.yaml with livenessProbe pointing to /health
4. Write service.yaml with correct port mapping
5. kubectl apply both files
6. Verify with kubectl get pods and kubectl logs

## Pitfalls
- MUST push image to registry before kubectl apply, otherwise ImagePullBackOff
- Flask 默认没有 /health 端点，需要手动添加
- Django 需要额外设置 ALLOWED_HOSTS 环境变量
- livenessProbe path 必须返回 200，不能用需要认证的路径
```

## 渐进式加载

**重型背包模式 vs 动态图书馆模式**

| | OpenClaw | Sun CLI Skill v2 |
|--|----------|------------------|
| 加载方式 | 全量加载 | 只放索引 |
| 系统提示词 | SOUL.md + IDENTITY.md + 设定 | 仅名字+一句话描述 |
| Token 消耗 | 随设定增加而膨胀 | 恒定轻量 |
| 注意力稀释 | 严重 | 无 |

系统提示词中的 Skills 部分：

```
<skills>
Available skills (use skill_view to load full content):
  devops:
    - flask-k8s-deploy: Deploy a Flask app to Kubernetes with health checks
    - nginx-reverse-proxy: Configure Nginx reverse proxy with SSL
  software-development:
    - fix-pytest-fixtures: Debug and fix pytest fixture scope issues
</skills>
```

Agent 判断某个 Skill 与当前任务相关时，才通过 `skill_view` 加载完整内容。

## 自动创建触发条件

由 `skill_manage` 工具的 Schema Description 引导：

> Create when: complex task succeeded (5+ tool calls), errors overcome, user-corrected approach worked, non-trivial workflow discovered, or user asks you to remember a procedure.

创建的门槛设得比较清楚：
- 工具调用超过 5 次才值得创建（简单任务不记）
- 踩过坑再修复的经验才有价值
- 用户纠正过的做法要铭记

## 自我修补

当 Agent 按照已有 Skill 执行，但中途发现步骤有遗漏或者踩了新坑时：

```json
{"tool": "skill_manage", "args": {
  "action": "patch",
  "name": "flask-k8s-deploy",
  "old_string": "- livenessProbe path 必须返回 200",
  "new_string": "- livenessProbe path 必须返回 200，不能用需要认证的路径\n- Django 需要额外设置 ALLOWED_HOSTS 环境变量"
}}
```

实现细节：
1. **模糊匹配**：容忍 Agent 给出的 `old_string` 与原文有格式差异
2. **修改前备份**：自动复制 `.md.bak`
3. **修改后扫描**：`_security_scan_skill()` 检查新内容
4. **不通过则回滚**：恢复备份文件

## 目录结构

```
.skills/
├── INDEX.md              # 自动维护的索引
├── devops/
│   └── flask-k8s-deploy/
│       ├── SKILL.md
│       ├── references/   # 参考文档
│       └── templates/    # 模板文件
└── software-development/
    └── fix-pytest-fixtures/
        └── SKILL.md
```
