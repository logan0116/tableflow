---
name: tf-register
description: "按契约 classify 的五种情况分派一条需求落在哪张表并完成登记：in_place（改未验收规格）/ change（改已验收规格开变更单）/ cross（横切多份）/ new_spec（新能力）/ out_of_board（不进看板）。取代已废弃的 tf-update。触发词：tf-register、登记需求、开变更单、classify、落哪张表、新规格。"
---

# tf-register：这条需求落在哪张表？

登记入口。取代 `tf-update`。

## 分派规则（契约 `classify.order`）

| 判定 | 条件 | 动作 |
|---|---|---|
| `in_place` | 给了 `--spec`，该规格尚未 accepted | 不新建行，只更新该独立需求的条款 |
| `change` | 给了 `--spec`，该规格已 accepted | 依赖需求表建行，挂该规格 |
| `cross` | 给了多份 `--spec` | 依赖需求表建一行，关联多份规格 |
| `new_spec` | 没给 `--spec` | 独立需求表建行 |
| `out_of_board` | 显式 `--kind out_of_board` | 不进看板，记入版本变更说明 |

`--kind` 可强制指定，其余情况自动判定。

## 用法

```bash
export TF_BASE=http://localhost:8090 TF_PROJECT=tableflow TF_AGENT=agent-tf-role

# 先看会怎么分派（不写）
python3 skills/tf-register/scripts/tf_register.py --version v0.8.0 \
  --clause "..." --spec 026-AR --dry-run

# 新规格
python3 skills/tf-register/scripts/tf_register.py --version v0.8.0 \
  --clause "..." --id 043-AR --dir specs/043-xxx/

# 变更单（可多份规格）
python3 skills/tf-register/scripts/tf_register.py --version v0.8.0 \
  --clause "..." --spec 026-AR --spec 027-AR --id DEP-07-BR \
  --impact "..." --affected "026-AR US1-AS1"
```

## 规则预检

发请求前先查明显冲突（规格未验收却要开变更单 C4、重复挂载 C1/C2），
**判定仍由引擎执行**——技能不复制规则，只转述引擎返回的规则号（040 的同源原则）。

## 不做

- 不写 `run`/`bug`/`case`。
- 不推进任何版本节点。
- 不改 `验收状态`、`回归状态`。
