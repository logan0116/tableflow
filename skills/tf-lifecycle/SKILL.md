---
name: tf-lifecycle
description: "执行独立需求的生命周期动作：drop（先摘版本再置 dropped，写理由与时间）、split（新建承接需求并写拆分记录）、cleanup（跨版本重复只保留首次出现）。前置条件由引擎强制。触发词：tf-lifecycle、放弃需求、终止需求、拆分需求、去重、清理重复挂载、dropped。"
---

# tf-lifecycle：拆分、放弃、清理

## 三个动作

| 动作 | 做什么 | 前置（引擎强制） |
|---|---|---|
| `drop` | 先把该需求从所有版本摘除，再置 `dropped` 并写理由与时间 | L3：仍在版本里的需求不能放弃 |
| `split` | 新建承接方，在原需求写拆分记录 | L6：已 accepted 不得拆分 |
| `cleanup` | 同一需求跨版本重复，只保留首次出现 | 036 已生效（执行记录表有「放行标记」字段） |

## 用法

```bash
export TF_BASE=http://localhost:8090 TF_PROJECT=tableflow TF_AGENT=agent-tf-role

# 放弃（默认 dry-run）
python3 skills/tf-lifecycle/scripts/tf_lifecycle.py --version v0.8.0 \
  --action drop --spec 043-AR --reason "能力取消" --dry-run
python3 skills/tf-lifecycle/scripts/tf_lifecycle.py --version v0.8.0 \
  --action drop --spec 043-AR --reason "能力取消" --apply

# 拆分
python3 skills/tf-lifecycle/scripts/tf_lifecycle.py --version v0.8.0 \
  --action split --spec 043-AR --to 044-AR --clauses "US3、US4"

# 历史去重
python3 skills/tf-lifecycle/scripts/tf_lifecycle.py --version v0.8.0 --action cleanup --dry-run
```

`cleanup` 不针对单个版本，`--version` 只是满足统一参数，可传任一存在的版本号。

## 为什么 cleanup 要求 036 先生效

摘掉某版本的独立需求关联后，「独立需求是否完成」会变成空集为真。如果测试验收仍按旧口径
（只看执行过、不看执行结果），一个失败过的版本会因此翻绿。036 生效后结论按执行结果
判定，摘除才不会改变红灯。

## 不做

- 不删行（`dropped` 是终态，不是删除）。
- 不改已发布版本的历史结论。
