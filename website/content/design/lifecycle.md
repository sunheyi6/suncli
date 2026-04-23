# 生命周期设计

## 设计哲学

**Skills that aren't maintained become liabilities.**

不维护的 Skill 比没有更糟——过时的步骤会引导 Agent 走向错误方向。生命周期管理确保 Skill 库保持健康。

## 元数据字段

每个 Skill 的 YAML frontmatter 包含：

```yaml
---
name: flask-k8s-deploy
description: Deploy a Flask app to Kubernetes with health checks
version: 1.0.0
category: devops
last_used: 2024-01-15T10:30:00
use_count: 5
success_rate: 0.95
created_at: 2024-01-01T00:00:00
updated_at: 2024-01-15T10:30:00
archived: false
---
```

## 自动更新机制

### 1. 使用记录（use_count + last_used）

每次 `skill_view` 被调用时自动更新：

```python
def record_usage(self, name: str, success: bool = True):
    self.use_count += 1
    self.last_used = datetime.now().isoformat()
    # 贝叶斯更新成功率
    self.success_rate = (
        self.success_rate * (self.use_count - 1) + (1.0 if success else 0.0)
    ) / self.use_count
```

### 2. 成功率（success_rate）

- 初始值：1.0（对新 Skill 持乐观态度）
- 更新公式：`(old_rate * (n-1) + result) / n`
- 低成功率的 Skill 在索引中可被标注，提醒 Agent 谨慎使用

### 3. 自动归档

```python
def archive_stale(self, max_age_days: int = 90, min_use_count: int = 3):
    """Auto-archive skills that are old and rarely used."""
    for skill in self.list_skills(include_archived=False):
        if skill.use_count >= min_use_count:
            continue
        if skill.last_used:
            last = datetime.fromisoformat(skill.last_used)
            age = (datetime.now() - last).days
            if age > max_age_days:
                skill.archived = True
                skill.updated_at = datetime.now().isoformat()
                # 写入磁盘
```

归档条件：
- 超过 90 天未使用
- 且使用次数少于 3 次

归档后的 Skill 不会出现在系统提示词的索引中，但保留在磁盘上，可随时手动恢复。

## 统计面板

```python
def get_stats(self) -> dict:
    skills = self.list_skills(include_archived=True)
    active = [s for s in skills if not s.archived]
    archived = [s for s in skills if s.archived]
    
    return {
        "total": len(skills),
        "active": len(active),
        "archived": len(archived),
        "total_uses": sum(s.use_count for s in skills),
        "avg_success_rate": round(
            sum(s.success_rate for s in skills) / len(skills), 2
        ) if skills else 0,
    }
```

## 未来方向

1. **自动降权**：基于 `success_rate` 在索引中标注风险等级
2. **过时检测**：对比 Skill 中的工具版本号与实际环境版本
3. **技能组合**：识别经常一起使用的 Skill，自动合成 Workflow
4. **创建透明度**：Skill 创建后给用户简短通知，允许审核和纠正
