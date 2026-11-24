# 看板规则清单

本文件由 `backend/scripts/render_rules.py` 从 `backend/src/tableflow/rules.py` 生成，
**不要手改**。新增或修改规则时改代码，再重新生成本文件；`--check` 会把它纳入回归。

契约 YAML 能表达的（字段类型、枚举取值、计算字段）不在这里；这里只收
**契约写不下、必须在写入期或技能流程里判定的规则**。

- `engine`：写入期拦截，任何写入路径都绕不过
- `skill`：只在技能流程里校验

规则号会出现在所有拒绝信息里，照着规则号就能查到含义、判定式与反例。


共 14 条。

## 需求 033

### C1 独立需求跨版本唯一

- **含义**：同一独立需求在所有版本的「独立需求管理」中最多出现一次。
- **判定式**：`count({ver | spec_id ∈ ver.specs}) ≤ 1`
- **实现位置**：`board_rules._validate_version_row / _check_once`
- **反例**：026-AR 已属 v0.7.1，再把它加入 v0.8.0 的独立需求管理
- **执行方**：engine

### C2 依赖需求跨版本唯一

- **含义**：同一依赖需求在所有版本的「依赖需求管理」中最多出现一次。
- **判定式**：`count({ver | dep_id ∈ ver.changes}) ≤ 1`
- **实现位置**：`board_rules._validate_version_row / _check_once`
- **反例**：DEP-06-BR 已属 v0.7.3，再把它加入另一个版本
- **执行方**：engine

### C3 依赖需求不早于其独立需求

- **含义**：依赖需求所在版本不得早于其关联的任一独立需求所在版本；允许同版本。
- **判定式**：`ver(dep) ≥ max(ver(indep) | indep ∈ dep.specs)`
- **实现位置**：`board_rules._check_dep_after_spec`
- **反例**：026-AR 交付于 v0.7.1，把关联它的依赖需求挂到 v0.7.0
- **执行方**：engine

### C4 依赖需求只关联已验收的规格

- **含义**：依赖需求的前提是目标规格已 accepted；未验收时按 in_place 直接改规格。
- **判定式**：`∀spec ∈ dep.specs: spec.acceptance == accepted`
- **实现位置**：`spec_lifecycle._validate_dep`
- **反例**：034-AR 仍是 pending，为它新开一条依赖需求
- **执行方**：engine

## 需求 034

### L1 dropped 是终态

- **含义**：已放弃的独立需求不得改回 pending/accepted/rejected。
- **判定式**：`previous.acceptance == dropped ⇒ merged.acceptance == dropped`
- **实现位置**：`spec_lifecycle._validate_indep`
- **反例**：034-AR 已 dropped，再把它改成 accepted
- **执行方**：engine

### L2 放弃须写理由与时间

- **含义**：置 dropped 时必须同时给出放弃理由与放弃时间。
- **判定式**：`merged.acceptance == dropped ⇒ 放弃理由 ≠ '' ∧ 放弃时间 ≠ null`
- **实现位置**：`spec_lifecycle._validate_indep`
- **反例**：只把验收状态改成 dropped，不给理由和时间
- **执行方**：engine

### L3 放弃前须摘除版本关联

- **含义**：仍在某个版本里的独立需求不能直接放弃。
- **判定式**：`merged.acceptance == dropped ⇒ {ver | spec ∈ ver.specs} == ∅`
- **实现位置**：`spec_lifecycle._versions_holding`
- **反例**：034-AR 还挂在 v0.8.0，就直接置 dropped
- **执行方**：engine

### L4 已放弃的需求不得挂版本

- **含义**：dropped 的独立需求不能再加入任何版本。
- **判定式**：`merged.acceptance == dropped ⇒ spec ∉ ver.specs`
- **实现位置**：`spec_lifecycle._validate_version`
- **反例**：把已 dropped 的 034-AR 加入 v0.8.0
- **执行方**：engine

### L5 已放弃的规格不得新开依赖需求

- **含义**：能力未建立时没有可修改的对象，要重做请新建独立需求。
- **判定式**：`∀spec ∈ dep.specs: spec.acceptance ≠ dropped`
- **实现位置**：`spec_lifecycle._validate_dep`
- **反例**：为已 dropped 的 034-AR 新建 DEP-09-BR
- **执行方**：engine

### L6 拆分只在未验收时允许

- **含义**：已 accepted 的需求不接受拆分，范围变化走依赖需求。
- **判定式**：`拆分记录 ≠ '' ∧ previous ≠ '' ⇒ merged.acceptance ≠ accepted`
- **实现位置**：`spec_lifecycle._validate_indep`
- **反例**：036-AR 已 accepted，还给它写拆分记录
- **执行方**：engine

## 需求 037

### D1 回归置 passed 须完成完整变更

- **含义**：受影响条款、一致性检查、集成验收三项都必须非空。
- **判定式**：`merged.regress == passed ∧ previous.regress ≠ passed ⇒ 三项均非空`
- **实现位置**：`change_flow.validate_row_write`
- **反例**：DEP-A 从 doing 改成 passed，三项流程字段全空
- **执行方**：engine

### D2 规格修订 not_needed 须写判定依据

- **含义**：声明本次改动不产生规格内容变化时，必须写明依据。
- **判定式**：`merged.spec_revision == not_needed ∧ previous ≠ not_needed ⇒ 证据 ≠ ''`
- **实现位置**：`change_flow.validate_row_write`
- **反例**：规格修订选 not_needed，证据为空
- **执行方**：engine

## 需求 038

### S1 阶段置 done 须有证据

- **含义**：阶段状态从非 done 变为 done 时，阶段证据必须有对应的非空行。
- **判定式**：`merged.stage[k] == done ∧ previous.stage[k] ≠ done ⇒ evidence[k] ≠ ''`
- **实现位置**：`stage_evidence.validate_row_write`
- **反例**：speckit-plan状态 从 todo 改为 done，阶段证据里没有 plan= 开头的行
- **执行方**：engine

### S2 复用产物的来源版本必须有效

- **含义**：复用既有产物时，证据必须写明来源版本，且来源版本必须等于当前宪法版本；不存在重新确认豁免。
- **判定式**：`evidence[k].startswith('reused:') ⇒ @<version> == 宪法版本`
- **实现位置**：`stage_evidence._check_reuse`
- **反例**：宪法版本已升到 v2，证据仍写 reused:.specify/memory/constitution.md@v1
- **执行方**：engine
