"""看板规则清单（040）：契约 YAML 表达不了的规则，在这里编号、说明、指向实现。

这是**唯一来源**。引擎按这些规则判定，文档 `specs/019-test-contract/rules.md` 由
`backend/scripts/render_rules.py` 从本文件生成，技能只转述引擎返回的规则号，不复制判定。

每条规则四个要素（040 FR-002）：

- ``id``          规则号，出现在所有拒绝信息里；
- ``meaning``     一句话含义；
- ``expr``        判定式，能照着写测试；
- ``impl``        实现位置（模块.函数）；
- ``counterexample`` 一个应被拒绝的具体输入，便于人工与自动化回归。

``enforced`` 说明由谁执行：``engine`` 表示写入期拦截（任何路径都绕不过），
``skill`` 表示只在技能流程里校验。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    meaning: str
    expr: str
    impl: str
    counterexample: str
    enforced: str
    since: str


RULES: tuple[Rule, ...] = (
    # ---------- 交付唯一性与先后（033） ----------
    Rule(
        id="C1",
        title="独立需求跨版本唯一",
        meaning="同一独立需求在所有版本的「独立需求管理」中最多出现一次。",
        expr="count({ver | spec_id ∈ ver.specs}) ≤ 1",
        impl="board_rules._validate_version_row / _check_once",
        counterexample="026-AR 已属 v0.7.1，再把它加入 v0.8.0 的独立需求管理",
        enforced="engine",
        since="033",
    ),
    Rule(
        id="C2",
        title="依赖需求跨版本唯一",
        meaning="同一依赖需求在所有版本的「依赖需求管理」中最多出现一次。",
        expr="count({ver | dep_id ∈ ver.changes}) ≤ 1",
        impl="board_rules._validate_version_row / _check_once",
        counterexample="DEP-06-BR 已属 v0.7.3，再把它加入另一个版本",
        enforced="engine",
        since="033",
    ),
    Rule(
        id="C3",
        title="依赖需求不早于其独立需求",
        meaning="依赖需求所在版本不得早于其关联的任一独立需求所在版本；允许同版本。",
        expr="ver(dep) ≥ max(ver(indep) | indep ∈ dep.specs)",
        impl="board_rules._check_dep_after_spec",
        counterexample="026-AR 交付于 v0.7.1，把关联它的依赖需求挂到 v0.7.0",
        enforced="engine",
        since="033",
    ),
    Rule(
        id="C4",
        title="依赖需求只关联已验收的规格",
        meaning="依赖需求的前提是目标规格已 accepted；未验收时按 in_place 直接改规格。",
        expr="∀spec ∈ dep.specs: spec.acceptance == accepted",
        impl="spec_lifecycle._validate_dep",
        counterexample="034-AR 仍是 pending，为它新开一条依赖需求",
        enforced="engine",
        since="033",
    ),
    # ---------- 独立需求生命周期（034） ----------
    Rule(
        id="L1",
        title="dropped 是终态",
        meaning="已放弃的独立需求不得改回 pending/accepted/rejected。",
        expr="previous.acceptance == dropped ⇒ merged.acceptance == dropped",
        impl="spec_lifecycle._validate_indep",
        counterexample="034-AR 已 dropped，再把它改成 accepted",
        enforced="engine",
        since="034",
    ),
    Rule(
        id="L2",
        title="放弃须写理由与时间",
        meaning="置 dropped 时必须同时给出放弃理由与放弃时间。",
        expr="merged.acceptance == dropped ⇒ 放弃理由 ≠ '' ∧ 放弃时间 ≠ null",
        impl="spec_lifecycle._validate_indep",
        counterexample="只把验收状态改成 dropped，不给理由和时间",
        enforced="engine",
        since="034",
    ),
    Rule(
        id="L3",
        title="放弃前须摘除版本关联",
        meaning="仍在某个版本里的独立需求不能直接放弃。",
        expr="merged.acceptance == dropped ⇒ {ver | spec ∈ ver.specs} == ∅",
        impl="spec_lifecycle._versions_holding",
        counterexample="034-AR 还挂在 v0.8.0，就直接置 dropped",
        enforced="engine",
        since="034",
    ),
    Rule(
        id="L4",
        title="已放弃的需求不得挂版本",
        meaning="dropped 的独立需求不能再加入任何版本。",
        expr="merged.acceptance == dropped ⇒ spec ∉ ver.specs",
        impl="spec_lifecycle._validate_version",
        counterexample="把已 dropped 的 034-AR 加入 v0.8.0",
        enforced="engine",
        since="034",
    ),
    Rule(
        id="L5",
        title="已放弃的规格不得新开依赖需求",
        meaning="能力未建立时没有可修改的对象，要重做请新建独立需求。",
        expr="∀spec ∈ dep.specs: spec.acceptance ≠ dropped",
        impl="spec_lifecycle._validate_dep",
        counterexample="为已 dropped 的 034-AR 新建 DEP-09-BR",
        enforced="engine",
        since="034",
    ),
    Rule(
        id="L6",
        title="拆分只在未验收时允许",
        meaning="已 accepted 的需求不接受拆分，范围变化走依赖需求。",
        expr="拆分记录 ≠ '' ∧ previous ≠ '' ⇒ merged.acceptance ≠ accepted",
        impl="spec_lifecycle._validate_indep",
        counterexample="036-AR 已 accepted，还给它写拆分记录",
        enforced="engine",
        since="034",
    ),
    # ---------- 阶段证据（038） ----------
    Rule(
        id="S1",
        title="阶段置 done 须有证据",
        meaning="阶段状态从非 done 变为 done 时，阶段证据必须有对应的非空行。",
        expr="merged.stage[k] == done ∧ previous.stage[k] ≠ done ⇒ evidence[k] ≠ ''",
        impl="stage_evidence.validate_row_write",
        counterexample="speckit-plan状态 从 todo 改为 done，阶段证据里没有 plan= 开头的行",
        enforced="engine",
        since="038",
    ),
    Rule(
        id="S2",
        title="复用产物的来源版本必须有效",
        meaning="复用既有产物时，来源版本与当前宪法版本不一致的，必须在证据行写明「已重新确认仍适用」。",
        expr="evidence[k].startswith('reused:') ⇒ @<version> == 宪法版本 ∨ 行内包含重新确认标记",
        impl="stage_evidence._check_reuse",
        counterexample="宪法版本已升到 v2，证据仍写 reused:.specify/memory/constitution.md@v1 且没有确认说明",
        enforced="engine",
        since="038",
    ),
    # ---------- 依赖需求变更流（037） ----------
    Rule(
        id="D1",
        title="回归置 passed 须完成完整变更",
        meaning="受影响条款、一致性检查、集成验收三项都必须非空。",
        expr="merged.regress == passed ∧ previous.regress ≠ passed ⇒ 三项均非空",
        impl="change_flow.validate_row_write",
        counterexample="DEP-A 从 doing 改成 passed，三项流程字段全空",
        enforced="engine",
        since="037",
    ),
    Rule(
        id="D2",
        title="规格修订 not_needed 须写判定依据",
        meaning="声明本次改动不产生规格内容变化时，必须写明依据。",
        expr="merged.spec_revision == not_needed ∧ previous ≠ not_needed ⇒ 证据 ≠ ''",
        impl="change_flow.validate_row_write",
        counterexample="规格修订选 not_needed，证据为空",
        enforced="engine",
        since="037",
    ),
)

BY_ID: dict[str, Rule] = {rule.id: rule for rule in RULES}


def get(rule_id: str) -> Rule | None:
    return BY_ID.get(rule_id)


def as_dicts(prefix: str | None = None) -> list[dict[str, object]]:
    """列出规则；``prefix`` 可按规则号前缀过滤（如 ``C`` 只看交付唯一性）。"""
    items = RULES if not prefix else tuple(r for r in RULES if r.id.startswith(prefix))
    return [asdict(rule) for rule in items]
