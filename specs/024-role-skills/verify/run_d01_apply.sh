#!/usr/bin/env bash
# D-01 回放：按 024 spec 的字面命令（带 --apply）重跑评审列出的 9 条 AS。
#
# 9 条：US3-AS1..AS5、US4-AS1..AS4。临时库 + 本地后端 + HTTP 建表夹具；
# 技能只走 HTTP，不碰真实库。产物：specs/024-role-skills/verify/evidence-d01/。
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
VERIFY="$ROOT/specs/024-role-skills/verify"
EVID="$VERIFY/evidence-d01"
mkdir -p "$EVID"
rm -f "$EVID"/*.json "$EVID"/*.tsv "$EVID"/*.err "$EVID"/run.log

PORT="${TF024_D01_PORT:-18091}"
BASE_URL="http://127.0.0.1:${PORT}"
PROJECT_ID="tf024verify"
AGENT_ID="agent-tf-role"
PYTHON="${TF024_PYTHON:-$ROOT/backend/.venv/bin/python}"
VERSION="v0.7.0"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/tf024d01.XXXXXX")
DB="$TMP/tf024d01.db"
SERVER_LOG="$TMP/server.log"
SERVER_PID=""
STEPS="$EVID/steps.tsv"
: > "$STEPS"

cleanup() {
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  cp "$SERVER_LOG" "$EVID/server.log" 2>/dev/null || true
  rm -rf "$TMP"
}
trap cleanup EXIT

exec > >(tee -a "$EVID/run.log") 2>&1

echo "[d01] repo=$ROOT temp=$TMP port=$PORT"
: > "$DB"
PYTHONPATH="$ROOT/backend/src" TABLEFLOW_DB="$DB" \
  "$PYTHON" -m uvicorn tableflow.app:app --host 127.0.0.1 --port "$PORT" \
  > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 100); do
  if curl -fsS "$BASE_URL/api/health" > /dev/null 2>&1; then break; fi
  sleep 0.1
done
curl -fsS "$BASE_URL/api/health" > /dev/null

export TF_BASE="$BASE_URL" TF_PROJECT="$PROJECT_ID" TF_AGENT="$AGENT_ID" TF_REPO_ROOT="$ROOT"
export TF024_WITH_099=1
echo "[d01] seed（含 099-AR：未勾任务 + 待验收）"
"$PYTHON" "$VERIFY/seed_board4_fixture.py" | tee "$EVID/00-fixture.json"

audit_count() {
  "$PYTHON" - "$DB" <<'PYAUDIT'
import sqlite3
import sys

conn = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
print(conn.execute("SELECT count(*) FROM write_audit").fetchone()[0])
conn.close()
PYAUDIT
}

run_step() {
  local as_id="$1"
  local expected="$2"
  local file="$3"
  local script="$4"
  shift 4
  local display="python3 ${script#"$ROOT"/} $*"
  set +e
  "$PYTHON" "$script" "$@" > "$EVID/$file" 2> "$EVID/$file.err"
  local code=$?
  set -e
  printf '%s\t%s\t%s\t%s\n' "$as_id" "$display" "$code" "$file" >> "$STEPS"
  echo
  echo "[$as_id] exit=$code（期望 $expected）"
  echo "+ $display"
  if [ "$code" -ne "$expected" ]; then
    echo "[d01][FAIL] $as_id 退出码不符" >&2
    cat "$EVID/$file" >&2 || true
    cat "$EVID/$file.err" >&2 || true
    exit 1
  fi
}

run_assert() {
  local as_id="$1"
  local file="$2"
  set +e
  "$PYTHON" "$VERIFY/d01_ops.py" assert "$as_id" "$EVID/$file" > "$EVID/$as_id.assert.json" 2>&1
  local code=$?
  set -e
  echo "[$as_id][assert] $(cat "$EVID/$as_id.assert.json")"
  if [ "$code" -ne 0 ]; then
    echo "[d01][FAIL] $as_id 断言未通过" >&2
    exit 1
  fi
}

record_state_as() {
  local as_id="$1"
  local file="$2"
  local display="python3 specs/024-role-skills/verify/d01_ops.py assert $as_id $file"
  set +e
  "$PYTHON" "$VERIFY/d01_ops.py" assert "$as_id" "$EVID/$file" > "$EVID/$as_id.assert.json" 2>&1
  local code=$?
  set -e
  printf '%s\t%s\t%s\t%s\n' "$as_id" "$display" "$code" "$file" >> "$STEPS"
  echo "[$as_id][assert] $(cat "$EVID/$as_id.assert.json")"
  if [ "$code" -ne 0 ]; then
    echo "[d01][FAIL] $as_id 断言未通过" >&2
    exit 1
  fi
}

printf '%-9s %-9s %s\n' "AS" "退出码" "命令"
echo "----------------------------------------------------------------------"

# US3-AS5：第 1 节点未 done 时 tf-test-plan --apply 必须 failed 且零写入（放在最前）
run_step US3-AS5 1 us3-as5.json "$ROOT/skills/tf-test-plan/scripts/tf_test_plan.py" \
  --version "$VERSION" --spec 019-AR --apply
run_assert US3-AS5 us3-as5.json

# 前置（非 AS）：把第 1 节点推到 done，才能验证后面的派生
run_step PREREQ-dev-plan 0 prereq-dev-plan.json "$ROOT/skills/tf-dev-plan/scripts/tf_dev_plan.py" \
  --version "$VERSION" --apply

# US3-AS1：派生 N 条、id=场景号、来源规格正确
run_step US3-AS1 0 us3-as1.json "$ROOT/skills/tf-test-plan/scripts/tf_test_plan.py" \
  --version "$VERSION" --spec 019-AR --apply
run_assert US3-AS1 us3-as1.json

# US3-AS2：第二次派生 0/0；名称有变化的用例就地更新（夹具先改一条用例名）
"$PYTHON" "$VERIFY/d01_ops.py" corrupt-case | tee "$EVID/setup-us3-as2.json"
run_step US3-AS2 0 us3-as2.json "$ROOT/skills/tf-test-plan/scripts/tf_test_plan.py" \
  --version "$VERSION" --spec 019-AR --apply
run_assert US3-AS2 us3-as2.json

# US3-AS3：源场景消失要报 orphans，不静默删除（夹具加一条孤儿用例）
"$PYTHON" "$VERIFY/d01_ops.py" add-orphan | tee "$EVID/setup-us3-as3.json"
run_step US3-AS3 0 us3-as3.json "$ROOT/skills/tf-test-plan/scripts/tf_test_plan.py" \
  --version "$VERSION" --spec 019-AR --apply
run_assert US3-AS3 us3-as3.json

# US3-AS4：每条用例都有 run（todo）+ ver.runs，且没有测试计划表
record_state_as US3-AS4 us3-as3.json

# US4-AS1：099 任务未勾完 → failed 列任务、零变更
run_step US4-AS1 1 us4-as1.json "$ROOT/skills/tf-dev-implement/scripts/tf_dev_implement.py" \
  --version "$VERSION" --spec 099-AR --apply
run_assert US4-AS1 us4-as1.json

# US4-AS2：017 任务全完成 → implement/dev 读回 done
run_step US4-AS2 0 us4-as2.json "$ROOT/skills/tf-dev-implement/scripts/tf_dev_implement.py" \
  --version "$VERSION" --spec 017-AR --apply
run_assert US4-AS2 us4-as2.json

# US4-AS3：099 未 accepted → failed 列规格、开发验收不变
run_step US4-AS3 1 us4-as3.json "$ROOT/skills/tf-dev-check/scripts/tf_dev_check.py" \
  --version "$VERSION" --apply
run_assert US4-AS3 us4-as3.json

# US4-AS4：放开 099 验收后 → dev_accept done
"$PYTHON" "$VERIFY/d01_ops.py" accept-099 | tee "$EVID/setup-us4-as4.json"
run_step US4-AS4 0 us4-as4.json "$ROOT/skills/tf-dev-check/scripts/tf_dev_check.py" \
  --version "$VERSION" --apply
run_assert US4-AS4 us4-as4.json

# 六个技能都能接受 --apply：补 test-implement / test-check 两条（非 9 AS）
run_step SMOKE-test-implement 0 smoke-test-implement.json "$ROOT/skills/tf-test-implement/scripts/tf_test_implement.py" \
  --version "$VERSION" --all-pending --result pass --evidence .tmp-shots/024/ --apply
run_step SMOKE-test-check 0 smoke-test-check.json "$ROOT/skills/tf-test-check/scripts/tf_test_check.py" \
  --version "$VERSION" --apply

# --dry-run 优先于 --apply：只读、writes 全 skipped、写审计不增
BEFORE_AUDIT=$(audit_count)
run_step FLAG-DRY-PRIORITY 0 flag-dry.json "$ROOT/skills/tf-test-check/scripts/tf_test_check.py" \
  --version "$VERSION" --apply --dry-run
AFTER_AUDIT=$(audit_count)
if [ "$BEFORE_AUDIT" != "$AFTER_AUDIT" ]; then
  echo "[d01][FAIL] --apply --dry-run 仍产生写审计：$BEFORE_AUDIT -> $AFTER_AUDIT" >&2
  exit 1
fi
echo "[FLAG-DRY-PRIORITY] write_audit=$AFTER_AUDIT（未变）"
run_assert FLAG-DRY-PRIORITY flag-dry.json

# ---------- 汇总 ----------
"$PYTHON" - "$EVID" <<'PYSUMMARY' | tee "$EVID/results.json"
import json
import re
import sys
from pathlib import Path

evid = Path(sys.argv[1])
rows = []
for line in (evid / "steps.tsv").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    as_id, command, code, file = line.split("\t")
    report_path = evid / file
    report = {}
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except ValueError:
            report = {}
    assert_path = evid / f"{as_id}.assert.json"
    assertion = {}
    if assert_path.exists():
        try:
            assertion = json.loads(assert_path.read_text(encoding="utf-8"))
        except ValueError:
            assertion = {}
    rows.append(
        {
            "as": as_id,
            "command": command,
            "exit_code": int(code),
            "evidence": file,
            "result": report.get("result"),
            "counts": report.get("counts", {}),
            "writes": len(report.get("writes", [])),
            "errors": report.get("errors", []),
            "assert": assertion,
        }
    )

as_required = [f"US3-AS{i}" for i in range(1, 6)] + [f"US4-AS{i}" for i in range(1, 5)]
by_as = {row["as"]: row for row in rows}
missing = [item for item in as_required if item not in by_as]
as_ok = all(
    by_as.get(item, {}).get("assert", {}).get("ok") is True for item in as_required
)
skills = set()
for row in rows:
    if "--apply" not in row["command"]:
        continue
    match = re.search(r"skills/(tf-[a-z-]+)/scripts/", row["command"])
    if match:
        skills.add(match.group(1))
stderr_bad = [
    path.name
    for path in evid.glob("*.err")
    if "unrecognized arguments" in path.read_text(encoding="utf-8", errors="replace")
]
checks = {
    "nine_as_assert_ok": as_ok and not missing,
    "six_skills_accept_apply": len(skills) == 6,
    "no_exit_2": all(row["exit_code"] != 2 for row in rows),
    "no_unrecognized_arguments": not stderr_bad,
    "dry_run_priority_readonly": by_as.get("FLAG-DRY-PRIORITY", {}).get("assert", {}).get("ok") is True,
}
result = {
    "ok": all(checks.values()),
    "checks": checks,
    "apply_parsed_skills": sorted(skills),
    "missing_as": missing,
    "stderr_unrecognized": stderr_bad,
    "steps": rows,
}
(evid / "results.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
)

lines = [
    "# D-01 `--apply` 回放结果",
    "",
    f"- 总判定：**{'通过' if result['ok'] else '失败'}**",
    f"- 六技能接受 `--apply`：{checks['six_skills_accept_apply']}（{', '.join(sorted(skills))}）",
    f"- 无 exit 2 / unrecognized arguments：{checks['no_exit_2']} / {checks['no_unrecognized_arguments']}",
    f"- `--dry-run` 优先于 `--apply`：{checks['dry_run_priority_readonly']}",
    "",
    "| AS | 命令 | 退出码 | result | 关键输出 |",
    "|---|---|---|---|---|",
]
for row in rows:
    key = row["assert"].get("key") if row["assert"] else None
    if key is None:
        key = {"result": row["result"], "counts": row["counts"], "errors": row["errors"]}
    cell = json.dumps(key, ensure_ascii=False).replace("|", "\\|")
    lines.append(
        f"| {row['as']} | `{row['command']}` | {row['exit_code']} | {row['result']} | {cell} |"
    )
(evid / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

print(json.dumps(result, ensure_ascii=False, indent=1))
raise SystemExit(0 if result["ok"] else 1)
PYSUMMARY

echo
echo "[d01] OK：9 条 AS 以字面 --apply 命令复跑通过；六个技能均接受 --apply；--dry-run 优先；无 unrecognized arguments。"
