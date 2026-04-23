# 数据流与演进示例

## 完整案例：从"不会"到"精通"的三次会话

### 第 1 次会话：冷启动

```
用户: 帮我把这个 Flask 应用部署到 K8s 集群
```

Memory 和 Skills 都是空的，Agent 靠基座知识摸索，12 次工具调用，踩了两个坑：

```
iter 1:  terminal("kubectl version")         → 确认集群版本
iter 2:  read_file("app.py")                 → 读取应用代码
iter 3:  write_file("Dockerfile")            → 创建 Dockerfile
iter 4:  terminal("docker build -t myapp .") → 构建镜像
iter 5:  write_file("deployment.yaml")       → 编写 K8s 部署文件
iter 6:  terminal("kubectl apply -f deployment.yaml")
         → 💥 ImagePullBackOff！忘记推镜像到 registry
iter 7:  terminal("docker push myregistry.azurecr.io/myapp")
iter 8:  terminal("kubectl apply -f deployment.yaml") → 重新部署
iter 9:  write_file("service.yaml")          → 编写 Service
iter 10: terminal("kubectl apply -f service.yaml")
iter 11: terminal("kubectl get pods")
         → 💥 CrashLoopBackOff！livenessProbe 路径不对
iter 12: 修改 deployment.yaml → 重新部署 → ✅ 成功
```

12 次迭代触发 Skill Review，Review Agent 看到两次报错和修复过程，创建了一个 Skill：

```
Review Agent 执行:
 → skill_manage(action="create", name="flask-k8s-deploy", category="devops",
     content="""
     ---
     name: flask-k8s-deploy
     description: Deploy a Flask app to Kubernetes with health checks
     ---
     ## Steps
     1. Create Dockerfile with gunicorn
     2. Build and push image to registry BEFORE kubectl apply
     3. Write deployment.yaml with livenessProbe → /health
     ...
     ## Pitfalls
     - MUST push image to registry first, otherwise ImagePullBackOff
     - Flask 默认没有 /health 端点，需手动添加
     - livenessProbe path 必须返回 200
     """
   )
```

安全扫描通过后写入磁盘，用户对这一切毫不知情。

---

### 第 2 次会话：Skill 复用 + 自我修补

```
用户: 帮我再部署一个 Django 应用到 K8s
```

系统提示词里多了 Skills 索引，Agent 加载 `flask-k8s-deploy` 后照着步骤做：

```
iter 1:  skill_view("flask-k8s-deploy") → 加载完整 Skill
iter 2:  read_file("manage.py")          → 确认 Django 项目结构
iter 3:  write_file("Dockerfile")        → 用 gunicorn（Skill 指示）
iter 4:  添加 /health 端点（Skill Pitfalls 提醒）
iter 5:  terminal("docker build && docker push")
         → 先 push 再 apply（Skill Steps 第 2 步）
iter 6:  write_file("deployment.yaml")   → livenessProbe → /health
iter 7:  terminal("kubectl apply")
         → 💥 DisallowedHost 错误！Django 特有的问题，Skill 没覆盖
iter 8:  修改 deployment.yaml 添加 ALLOWED_HOSTS env
iter 9:  terminal("kubectl apply")       → ✅ 成功
```

从 12 次调用降到 9 次，已知坑被绕过，但遇到 Django 特有的新坑。

Review Agent 一口气做了三件事：
1. 写入用户画像（记住用户用 Django）
2. 记住 registry 地址（project memory）
3. patch Skill 补上 ALLOWED_HOSTS 坑

---

### 第 3 次会话：零错误，一次搞定

```
用户: 帮我部署一个新的 FastAPI 微服务
```

Agent 已经知道你是谁、registry 在哪、集群在哪，Skill 里也包含了 ALLOWED_HOSTS 的坑：

```
iter 1: skill_view("flask-k8s-deploy") → 加载已修补版本
iter 2: read_file("main.py")           → 确认 FastAPI 结构
iter 3: write_file("Dockerfile")       → 用 uvicorn
iter 4: 添加 /health 端点
iter 5: terminal("docker build && push")
iter 6: terminal("kubectl apply")      → ✅ 成功
```

6 次调用，零错误。

---

## 三次对比

| 维度 | 会话 1 (冷启动) | 会话 2 (Skill 复用) | 会话 3 (全协同) |
|------|----------------|-------------------|---------------|
| 工具调用 | 12 次 | 9 次 | 6 次 |
| 错误数 | 2 | 1 | 0 |
| Memory | 无 | 触发写入 | 系统提示词注入 |
| Skill | 触发创建 | 复用 + 自我修补 | 复用已修补版本 |
| 用户感知 | 正常对话 | 正常对话 | 正常对话 |
| 后台活动 | Skill 创建 | Skill patch + Memory save | 无（计数器未达阈值）|

---

## 设计取舍一览

| 设计决策 | 表面效果 | 背后的考量 |
|----------|----------|------------|
| Memory 限 2200 chars | 迫使 Agent 挑重要的记 | 低质量 Memory 注入系统提示词 = 每次 API 调用都带噪声 |
| 声明式事实 vs 操作步骤分离 | Memory 存事实，Skill 存步骤 | 两者更新频率、触发条件、安全风险完全不同 |
| 冻结快照模式 | 系统提示词会话内不变 | 保护前缀缓存，避免每轮 API 调用重新计费 |
| 后台 fork 审查 | 用户感知不到 review 过程 | 自省不应占用用户任务的 attention budget |
| Nudge 计数器可配置 | 默认 10 | 太频繁浪费 API 成本，太稀疏错过学习机会 |
| patch 优先于全量重写 | 局部修复 Skill | 保留已验证的稳定部分，只改需要改的 |
| 安全扫描 + 自动回滚 | 拒绝恶意写入 | Memory/Skill 最终进入系统提示词，是一等安全边界 |
