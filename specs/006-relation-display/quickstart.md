# Quickstart / 验收记录：关联条目显示字段配置化（v0.4.1）

**日期**: 2026-11-10
**环境**: 本地 8000/5173 + 线上 155:8090，Chrome 1280×800

## 1. 复现命令

```bash
# 类型与回归
cd frontend && npx tsc --noEmit
cd backend && .venv/bin/pytest -q

# 合规：不应再有硬编码列名
grep -rn "TITLE_NAMES\|STATUS_NAMES" frontend/src

# 迁移（幂等；--dry-run 先看映射）
python3 data/migrate_relation_display.py --base http://<host>:8090 --dry-run
python3 data/migrate_relation_display.py --base http://<host>:8090
```

## 2. 结果

| 项 | 结果 |
|---|---|
| `npx tsc --noEmit` | 零错误 |
| `.venv/bin/pytest -q` | 97 passed |
| 合规 grep | 命中 0 |
| 迁移覆盖 | 6 个项目 19 个 relation 字段，全部写入成功 |
| 迁移幂等 | 第二次运行「待变更 0 个」 |
| 线上弹层（tableflow/版本管理 → 需求关联（依赖）） | 三列：编号 / 条款 / 回归状态；「通过」为绿色标签 |
| 改前同位置 | 第三列空白（目标表「状态」为 text 类型，enumItems 返回空） |

## 3. 迁移映射（全部 19 条）

规则：`display_field` 取目标表第 2 个 text 字段（第 1 个是编号），`status_field` 取目标表第 1 个 enum 字段。

| 项目 | relation 字段 | 目标表 | display | status |
|---|---|---|---|---|
| cnc_nexus | cn-ver.cn-v-indep | cn-indep | 条款 | speckit-implement状态 |
| cnc_nexus | cn-ver.cn-v-dep | cn-dep | 条款 | 回归状态 |
| cnc_nexus | cn-dep.cn-d-indep | cn-indep | 条款 | speckit-implement状态 |
| fd_system | fd-ver.v-indep | fd-indep | 条款 | speckit-implement状态 |
| fd_system | fd-ver.v-dep | fd-dep | 条款 | 回归状态 |
| fd_system | fd-dep.d-indep | fd-indep | 条款 | speckit-implement状态 |
| im_kg_desktop | imkg-ver.imkg-v-indep | imkg-indep | 条款 | speckit-implement状态 |
| im_kg_desktop | imkg-ver.imkg-v-dep | imkg-dep | 条款 | 回归状态 |
| im_kg_desktop | imkg-dep.imkg-d-indep | imkg-indep | 条款 | speckit-implement状态 |
| im_kg_desktop | imkg-dep.imkg-d-prereq | imkg-dep | 条款 | 回归状态 |
| jishu_cloud | jishu_cloud-ver.jishu_cloud-v-indep | jishu_cloud-indep | 条款 | speckit-implement状态 |
| jishu_cloud | jishu_cloud-ver.jishu_cloud-v-dep | jishu_cloud-dep | 条款 | 回归状态 |
| jishu_cloud | jishu_cloud-dep.jishu_cloud-d-indep | jishu_cloud-indep | 条款 | speckit-implement状态 |
| jishu_edge | jishu_edge-ver.jishu_edge-v-indep | jishu_edge-indep | 条款 | speckit-implement状态 |
| jishu_edge | jishu_edge-ver.jishu_edge-v-dep | jishu_edge-dep | 条款 | 回归状态 |
| jishu_edge | jishu_edge-dep.jishu_edge-d-indep | jishu_edge-indep | 条款 | speckit-implement状态 |
| tableflow | tf-ver.tf-v-indep | tf-indep | 条款 | speckit-implement状态 |
| tableflow | tf-ver.tf-v-dep | tf-dep | 条款 | 回归状态 |
| tableflow | tf-dep.tf-d-indep | tf-indep | 条款 | speckit-implement状态 |

## 4. 回退方式

某个 relation 字段想恢复旧行为：把 `options.display_field` / `options.status_field` 删掉即可，弹层退化为只显示编号列，不报错。整批回退需先备份 `fields.options`。

## 5. 遗留

- 关联条目列表最多三列（编号 + 名称 + 状态），多列配置仍属宪法非目标。
- 迁移按「第 2 个 text 字段」推导，若未来新增表结构不符合此约定，需人工指定配置。
