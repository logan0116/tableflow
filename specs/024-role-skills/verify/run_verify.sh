#!/usr/bin/env bash
# 024 角色技能验证：临时库 + 本地后端 + HTTP 建表夹具，跑六个技能的只读与写回读。
#
# 不碰真实库：TABLEFLOW_DB 指向 mktemp 目录；技能只经 HTTP 访问该临时实例。
# 产物：specs/024-role-skills/verify/evidence/*.json 与 run.log。
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
VERIFY="$ROOT/specs/024-role-skills/verify"
EVID="$VERIFY/evidence"
mkdir -p "$EVID"
rm -f "$EVID"/*.json "$EVID"/run.log

PORT="${TF024_PORT:-18090}"
BASE_URL="http://127.0.0.1:${PORT}"
PROJECT_ID="tf024verify"
AGENT_ID="agent-tf-role"
PYTHON="${TF024_PYTHON:-$ROOT/backend/.venv/bin/python}"
VERSION="v0.7.0"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/tf024.XXXXXX")
DB="$TMP/tf024.db"
SERVER_LOG="$TMP/server.log"
SERVER_PID=""

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

echo "[024] repo=$ROOT"
echo "[024] temp db=$DB port=$PORT"

echo "[024] protocol unit checks（不访问网络）"
"$PYTHON" "$VERIFY/check_protocol.py" | tee "$EVID/00-protocol-check.json"
: > "$DB"
PYTHONPATH="$ROOT/backend/src" TABLEFLOW_DB="$DB" \
  "$PYTHON" -m uvicorn tableflow.app:app --host 127.0.0.1 --port "$PORT" \
  > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 100); do
  if curl -fsS "$BASE_URL/api/health" > /dev/null 2>&1; then
    break
  fi
  sleep 0.1
done
curl -fsS "$BASE_URL/api/health" > /dev/null
echo "[024] server up"

export TF_BASE="$BASE_URL" TF_PROJECT="$PROJECT_ID" TF_AGENT="$AGENT_ID" TF_REPO_ROOT="$ROOT"
echo "[024] seed fixture"
"$PYTHON" "$VERIFY/seed_board4_fixture.py" | tee "$EVID/00-fixture.json"

run_skill() {
  local out="$1"
  local script="$2"
  shift 2
  echo
  echo "+ $script $*"
  "$PYTHON" "$script" "$@" | tee "$EVID/$out"
}

assert_json() {
  "$PYTHON" - "$1" "$2" <<'PYASSERT'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
expression = sys.argv[2]
assert eval(expression, {"data": data, "all": all, "len": len}), expression
print(f"[assert] {sys.argv[1]}: {expression}")
PYASSERT
}

audit_count() {
  "$PYTHON" - "$DB" <<'PYAUDIT'
import sqlite3
import sys

conn = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
print(conn.execute("SELECT count(*) FROM write_audit").fetchone()[0])
conn.close()
PYAUDIT
}

expect_no_write() {
  local before="$1"
  local after
  after=$(audit_count)
  if [ "$before" != "$after" ]; then
    echo "[024][FAIL] 只读运行新增了写审计：$before -> $after" >&2
    exit 1
  fi
  echo "[024] 只读运行前后 write_audit=$after（未变）"
}

# ---------- 1. 版本需求设计 ----------
BEFORE_AUDIT=$(audit_count)
run_skill "01-dev-plan-dryrun.json" "$ROOT/skills/tf-dev-plan/scripts/tf_dev_plan.py" \
  --version "$VERSION" --dry-run
assert_json "$EVID/01-dev-plan-dryrun.json" 'data["result"]=="success" and all(w["state"]=="skipped" for w in data["writes"])'
expect_no_write "$BEFORE_AUDIT"

run_skill "01-dev-plan-apply.json" "$ROOT/skills/tf-dev-plan/scripts/tf_dev_plan.py" \
  --version "$VERSION"
assert_json "$EVID/01-dev-plan-apply.json" 'data["result"]=="success" and data["readback"]["ver/v0.7.0#nodes"]["版本需求设计"]=="done"'

# ---------- 2. 测试设计（含幂等两次） ----------
BEFORE_AUDIT=$(audit_count)
run_skill "02-test-plan-dryrun.json" "$ROOT/skills/tf-test-plan/scripts/tf_test_plan.py" \
  --version "$VERSION" --spec 019-AR --dry-run
assert_json "$EVID/02-test-plan-dryrun.json" 'data["result"]=="success" and all(w["state"]=="skipped" for w in data["writes"]) and data["counts"]["created_cases"]>0'
expect_no_write "$BEFORE_AUDIT"

run_skill "02-test-plan-apply-1.json" "$ROOT/skills/tf-test-plan/scripts/tf_test_plan.py" \
  --version "$VERSION" --spec 019-AR
assert_json "$EVID/02-test-plan-apply-1.json" 'data["result"]=="success" and data["counts"]["created_cases"]>0 and data["counts"]["created_runs"]>0'

run_skill "02-test-plan-apply-2.json" "$ROOT/skills/tf-test-plan/scripts/tf_test_plan.py" \
  --version "$VERSION" --spec 019-AR
assert_json "$EVID/02-test-plan-apply-2.json" 'data["result"]=="success" and data["counts"]["created_cases"]==0 and data["counts"]["created_runs"]==0 and data["readback"]["ver/v0.7.0#nodes"]["测试设计"]=="done"'

# ---------- 3. 开发 ----------
BEFORE_AUDIT=$(audit_count)
run_skill "03-dev-implement-dryrun.json" "$ROOT/skills/tf-dev-implement/scripts/tf_dev_implement.py" \
  --version "$VERSION" --spec 017-AR --dry-run
assert_json "$EVID/03-dev-implement-dryrun.json" 'data["result"]=="success" and all(w["state"]=="skipped" for w in data["writes"])'
expect_no_write "$BEFORE_AUDIT"

run_skill "03-dev-implement-apply.json" "$ROOT/skills/tf-dev-implement/scripts/tf_dev_implement.py" \
  --version "$VERSION" --spec 017-AR
assert_json "$EVID/03-dev-implement-apply.json" 'data["result"]=="success" and data["readback"]["indep/017-AR"]["ok"] and data["readback"]["ver/v0.7.0#nodes"]["开发"]=="done"'

# ---------- 4. 开发验收 ----------
BEFORE_AUDIT=$(audit_count)
run_skill "04-dev-check-dryrun.json" "$ROOT/skills/tf-dev-check/scripts/tf_dev_check.py" \
  --version "$VERSION" --dry-run
assert_json "$EVID/04-dev-check-dryrun.json" 'data["result"]=="success" and all(w["state"]=="skipped" for w in data["writes"])'
expect_no_write "$BEFORE_AUDIT"

run_skill "04-dev-check-apply.json" "$ROOT/skills/tf-dev-check/scripts/tf_dev_check.py" \
  --version "$VERSION"
assert_json "$EVID/04-dev-check-apply.json" 'data["result"]=="success" and data["readback"]["ver/v0.7.0#nodes"]["开发验收"]=="done"'

# ---------- 5. 测试执行 ----------
BEFORE_AUDIT=$(audit_count)
run_skill "05-test-implement-dryrun.json" "$ROOT/skills/tf-test-implement/scripts/tf_test_implement.py" \
  --version "$VERSION" --all-pending --result pass --evidence .tmp-shots/024/ --dry-run
assert_json "$EVID/05-test-implement-dryrun.json" 'data["result"]=="success" and all(w["state"]=="skipped" for w in data["writes"]) and data["counts"]["pending"]>0'
expect_no_write "$BEFORE_AUDIT"

run_skill "05-test-implement-apply.json" "$ROOT/skills/tf-test-implement/scripts/tf_test_implement.py" \
  --version "$VERSION" --all-pending --result pass --evidence .tmp-shots/024/ --executor agent-tf-role
assert_json "$EVID/05-test-implement-apply.json" 'data["result"]=="success" and data["counts"]["pending"]==0 and data["readback"]["ver/v0.7.0#nodes"]["测试"]=="done"'

# ---------- 6. 测试验收 ----------
BEFORE_AUDIT=$(audit_count)
run_skill "06-test-check-dryrun.json" "$ROOT/skills/tf-test-check/scripts/tf_test_check.py" \
  --version "$VERSION" --dry-run
assert_json "$EVID/06-test-check-dryrun.json" 'data["result"]=="success" and all(w["state"]=="skipped" for w in data["writes"])'
expect_no_write "$BEFORE_AUDIT"

run_skill "06-test-check-apply.json" "$ROOT/skills/tf-test-check/scripts/tf_test_check.py" \
  --version "$VERSION"
assert_json "$EVID/06-test-check-apply.json" 'data["result"]=="success" and data["gate"]["stage_done"] is True and all(v=="done" for v in data["readback"]["ver/v0.7.0#nodes"].values())'

# ---------- 汇总 ----------
"$PYTHON" - "$EVID" "$ROOT" <<'PY' | tee "$EVID/summary.json"
import json
import sys
from pathlib import Path

evid = Path(sys.argv[1])
root = Path(sys.argv[2])
results = {}
for path in sorted(evid.glob("*.json")):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        continue
    if isinstance(data, dict) and "skill" in data:
        results[path.name] = {
            "skill": data.get("skill"),
            "mode": data.get("mode"),
            "result": data.get("result"),
            "counts": data.get("counts", {}),
            "writes": len(data.get("writes", [])),
            "skipped_writes": sum(1 for w in data.get("writes", []) if w.get("state") == "skipped"),
        }
common = {
    name: __import__("hashlib").sha256(
        (root / "skills" / name / "scripts" / "_tf_common.py").read_bytes()
    ).hexdigest()
    for name in [
        "tf-dev-plan", "tf-test-plan", "tf-dev-implement",
        "tf-dev-check", "tf-test-implement", "tf-test-check",
    ]
}
print(json.dumps({
    "ok": True,
    "skills": results,
    "common_sha256": common,
    "checks": {
        "six_skills_readonly_ok": len([r for r in results.values() if r["mode"] == "dry-run" and r["result"] == "success"]) == 6,
        "second_derive_zero": results.get("02-test-plan-apply-2.json", {}).get("counts", {}).get("created_cases") == 0,
        "six_nodes_done": True,
    },
}, ensure_ascii=False, indent=1))
PY

echo
echo "[024] OK：六个技能只读运行通过；tf-test-plan 第二次派生新建 0 条；六节点全部 done。"
