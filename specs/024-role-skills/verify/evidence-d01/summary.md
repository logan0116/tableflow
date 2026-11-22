# D-01 `--apply` 回放结果

- 总判定：**通过**
- 六技能接受 `--apply`：True（tf-dev-check, tf-dev-implement, tf-dev-plan, tf-test-check, tf-test-implement, tf-test-plan）
- 无 exit 2 / unrecognized arguments：True / True
- `--dry-run` 优先于 `--apply`：True

| AS | 命令 | 退出码 | result | 关键输出 |
|---|---|---|---|---|
| US3-AS5 | `python3 skills/tf-test-plan/scripts/tf_test_plan.py --version v0.7.0 --spec 019-AR --apply` | 1 | failed | {"result": "failed", "writes": 0, "error": "前序节点未完成，不能推进「测试设计」：版本需求设计=todo"} |
| PREREQ-dev-plan | `python3 skills/tf-dev-plan/scripts/tf_dev_plan.py --version v0.7.0 --apply` | 0 | success | {"result": "success", "counts": {"specs": 3, "changes": 0}, "errors": []} |
| US3-AS1 | `python3 skills/tf-test-plan/scripts/tf_test_plan.py --version v0.7.0 --spec 019-AR --apply` | 0 | success | {"created_cases": 27, "created_runs": 27, "derived_cases": 27, "sample_ids": ["019-US1-AS1", "019-US1-AS2", "019-US1-AS3"], "source_ok": true} |
| US3-AS2 | `python3 skills/tf-test-plan/scripts/tf_test_plan.py --version v0.7.0 --spec 019-AR --apply` | 0 | success | {"created_cases": 0, "created_runs": 0, "updated_cases": 1, "case_name_after": "存在 `ver`/`indep`/`dep`/`case`/`run`/`bug` 六张表，每张表的字段数、字段名、类型、顺序与契约一致。"} |
| US3-AS3 | `python3 skills/tf-test-plan/scripts/tf_test_plan.py --version v0.7.0 --spec 019-AR --apply` | 0 | success | {"orphans": ["019-US9-AS1"], "orphan_still_exists": true} |
| US3-AS4 | `python3 specs/024-role-skills/verify/d01_ops.py assert US3-AS4 us3-as3.json` | 0 | success | {"derived_cases": 27, "runs_todo_ok": 27, "ver_runs": 27, "plan_tables": [], "case_fields_ok": true} |
| US4-AS1 | `python3 skills/tf-dev-implement/scripts/tf_dev_implement.py --version v0.7.0 --spec 099-AR --apply` | 1 | failed | {"result": "failed", "writes": 0, "dev_node": "todo", "error": "开发节点未满足：099-AR 有 1 条未完成任务"} |
| US4-AS2 | `python3 skills/tf-dev-implement/scripts/tf_dev_implement.py --version v0.7.0 --spec 017-AR --apply` | 0 | success | {"result": "success", "dev_node": "done", "indep_017_ok": true} |
| US4-AS3 | `python3 skills/tf-dev-check/scripts/tf_dev_check.py --version v0.7.0 --apply` | 1 | failed | {"result": "failed", "writes": 0, "dev_accept": "todo", "error": "开发验收未满足：099-AR 验收状态=pending；099-AR 实现状态=todo"} |
| US4-AS4 | `python3 skills/tf-dev-check/scripts/tf_dev_check.py --version v0.7.0 --apply` | 0 | success | {"result": "success", "dev_accept": "done"} |
| SMOKE-test-implement | `python3 skills/tf-test-implement/scripts/tf_test_implement.py --version v0.7.0 --all-pending --result pass --evidence .tmp-shots/024/ --apply` | 0 | success | {"result": "success", "counts": {"executed": 27, "pending": 0, "runs": 27}, "errors": []} |
| SMOKE-test-check | `python3 skills/tf-test-check/scripts/tf_test_check.py --version v0.7.0 --apply` | 0 | success | {"result": "success", "counts": {}, "errors": []} |
| FLAG-DRY-PRIORITY | `python3 skills/tf-test-check/scripts/tf_test_check.py --version v0.7.0 --apply --dry-run` | 0 | success | {"mode": "dry-run", "apply": true, "writes": 0, "apply_ignored_by": "dry-run"} |
