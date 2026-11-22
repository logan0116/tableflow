# 024 角色技能验证夹具

本目录只服务 `specs/024-role-skills/spec.md` 的验收，不替代 T1 的正式迁移，也永远不碰真实库。

## 为什么需要夹具

T1（六表迁移）/ T3（写协议）/ T7（六节点校验）与本需求并行开发。技能必须在 board@4 上验证，但验证时线上项目可能尚未迁移或六节点尚未齐备。夹具做三件事：

1. 在 `mktemp` 临时库上启动一个本地后端（`TABLEFLOW_DB` 指向临时文件）；
2. 经 **Agent 写接口** 建六表、字段、一条 `planned` 版本与两份规格（`017-AR`、`019-AR`）；
3. 按节点顺序驱动六个技能：先 `--dry-run` 证明只读，再 `--apply` 证明写后回读。

夹具只造「技能需要的最小 plain-field 投影」：不建计算字段（技能在客户端复算）、不造测试计划（board@4 明确没有）。

## 运行

```bash
bash specs/024-role-skills/verify/run_verify.sh
```

依赖：`backend/.venv`（fastapi/uvicorn）、`curl`、Python 3.11+。默认端口 `18090`，可用 `TF024_PORT=18091` 覆盖。

## D-01（`--apply`）回放

```bash
bash specs/024-role-skills/verify/run_d01_apply.sh
```

在独立临时库上按 024 spec 的字面命令（带 `--apply`）复跑评审列出的 9 条 AS：US3-AS1..AS5、US4-AS1..AS4。产物在 `evidence-d01/`：

- `results.json`：逐条 `as` / `command` / `exit_code` / `result` / `counts` / `assert`，以及 `six_skills_accept_apply`、`no_exit_2`、`no_unrecognized_arguments`、`dry_run_priority_readonly` 四项汇总断言。
- `us3-*.json`、`us4-*.json`：技能原始报告；`*.assert.json`：逐场景断言输出。

其中 `US3-AS2` 由夹具先把一条用例名改脏再重跑，证明「变化就地更新」；`US3-AS3` 由夹具加一条 `019-US9-AS1` 孤儿用例，证明报告 `orphans` 且不静默删除；`US4-AS1/AS3` 用 `fixtures/099-d01/` 的「未勾任务 + 待验收」规格证明开发与开发验收被拦住。

## 检查项

| 检查 | 期望 |
|---|---|
| 六个技能各 `--dry-run` | `result=success`，`writes` 全部 `state=skipped` |
| `tf-test-plan` 连续两次 `--apply` | 第二次 `created_cases=0`、`created_runs=0` |
| `tf-test-plan` 派生 | 019-AR 27 条场景 → 27 条 `case`、27 条 `run`、`ver.runs` 27 条 |
| 六节点串行 | 六个技能按 1→6 推进后，六节点全 `done`、`stage_done=true` |
| 写后回读 | 每个写报告都有 `readback`，逐字段 `expect/actual/ok` |
| 表作用域 | 每个技能只解析自己允许的表；越权读写由客户端拒绝 |
| 凭据 | 报告与日志不含 `TF_API_KEY`/`X-API-Key` 值 |

## 证据

`evidence/` 下的 JSON 是每次运行的原始报告，`summary.json` 是汇总断言，`run.log` 是完整命令与输出。重新运行会覆盖这些文件。

## 真实实例的只读冒烟

T1 已把六表迁到线上后，可对真实项目做只读冒烟（不写）：

```bash
TF_BASE=http://localhost:8090 TF_PROJECT=tableflow TF_AGENT=agent-tf-role \
  python3 skills/tf-dev-plan/scripts/tf_dev_plan.py --version v0.7.0 --dry-run
```

2026-11-22 实测：读表与字段解析正常；因当时 `022-AR`/`025-AR` 的 `spec.md` 尚未交付，技能按预期 `failed` 并指名缺失文件，零写入。等 022/025 规格落地后重跑即可通过，这就是「技能只依赖真源」的直接体现。
