"""tableflow 角色技能共用运行时（board@4，规格 024）。

六个技能共用同一套纪律，本文件是唯一实现：

- 只经 HTTP 读写：读 ``/api/...``，写 ``/api/agent/...``；不连 SQLite、不碰 ``data/``。
- 三态判定严格按 ``specs/012-protocol/spec.md`` P-024：
  200+``result=success`` → success；400/401/404/405/422 → failed；
  503（含 ``detail`` 信封）、其他 5xx、超时、非 JSON → unknown。
- 写后必须回读：只有回读逐字段一致才允许报 success；``unknown`` 先回读，
  回读不能定案才按 100ms 起退避重试，最多 3 次。
- 不打印任何凭据：``TF_API_KEY`` 只进请求头，报告里永远不出现。

本文件在每个技能目录的 ``scripts/`` 下各有一份完全相同的副本，便于技能单独打包。
可用 ``sha256sum skills/tf-*/scripts/_tf_common.py`` 检查副本是否漂移。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=8))

# 契约表级名称（board@4 tables[*].name），按名称解析，不硬编码表 id。
TABLE_NAMES = {
    "ver": "版本管理",
    "indep": "独立规格需求",
    "dep": "依赖变更需求",
    "case": "测试用例",
    "run": "用例执行情况",
    "bug": "缺陷",
}

# 版本表六节点，顺序即串行推进顺序（board@4 rules.version_stage_serial）。
NODE_FIELDS = ["版本需求设计", "测试设计", "开发", "开发验收", "测试", "测试验收"]

RUN_STATE_VALUES = {"todo", "done"}
RUN_RESULT_VALUES = {"pass", "fail", "blocked", "skip"}
RUN_VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")

STORY_RE = re.compile(
    r"^### User Story (\d+) - (.+?)(?:\s*\(Priority:\s*([A-Za-z0-9]+)\))?\s*$"
)
SCENARIO_RE = re.compile(
    r"^(\d+)\.\s+\*\*Given\*\*\s*(.+?)\s*\*\*When\*\*\s*(.+?)\s*\*\*Then\*\*\s*(.+?)\s*$"
)


class SkillFailure(Exception):
    """技能主动中止；``state`` 是 012 三态之一，默认 failed。"""

    def __init__(self, message: str, *, state: str = "failed"):
        super().__init__(message)
        self.state = state if state in ("success", "failed", "unknown") else "failed"


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _redact(text: object, limit: int = 400) -> str:
    """错误文本截断；不包含请求头，因此不会带出凭据。"""
    value = str(text or "")
    return value[:limit]


def normalize(value: object) -> object:
    """比较用的归一化：空值三种形态等价；relation 数组按集合比较。"""
    if value is None or value == "" or value == []:
        return []
    if isinstance(value, list):
        return sorted(str(item) for item in value)
    return value


def same_value(left: object, right: object) -> bool:
    return normalize(left) == normalize(right)


def classify(http: int, payload: object) -> str:
    """012 P-024 三态判定。"""
    if http <= 0:
        # 请求未得到 HTTP 响应（连接中断/超时/DNS）：请求可能已离开客户端。
        return "unknown"
    if http == 200:
        if isinstance(payload, dict) and payload.get("result") == "success":
            return "success"
        if isinstance(payload, dict) and payload.get("result") in ("failed", "unknown"):
            return payload["result"]
        # 200 但不是协议信封（网关改写/非 JSON）：无法确认，按 unknown。
        return "unknown" if payload is None else "failed"
    if http in (400, 401, 404, 405, 422):
        return "failed"
    if http == 503:
        return "unknown"
    if 500 <= http < 600:
        return "unknown"
    return "failed"


def error_text(resp: dict) -> str:
    payload = resp.get("payload")
    if isinstance(payload, dict):
        for key in ("error", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return _redact(value)
            if isinstance(value, list):
                return _redact(json.dumps(value, ensure_ascii=False))
    raw = resp.get("raw")
    return _redact(raw) if raw else "无响应体"


class Client:
    """tableflow HTTP 客户端；``allowed`` 是技能的表作用域（键见 TABLE_NAMES）。"""

    def __init__(
        self,
        *,
        base: str | None,
        project: str,
        agent: str,
        allowed: set[str],
        timeout: float = 20.0,
    ):
        if not base:
            raise SkillFailure("未设置 TF_BASE（看板实例地址），拒绝运行")
        self.base = base.rstrip("/")
        self.project = project
        self.agent = agent or "agent-tf-role"
        self.origin = os.environ.get("TF_ORIGIN", "human-request")
        if self.origin not in ("agent", "human-request", "seed"):
            raise SkillFailure("TF_ORIGIN 只能是 agent/human-request/seed")
        self._api_key = os.environ.get("TF_API_KEY") or ""
        self.allowed = set(allowed)
        self.timeout = timeout
        self._table_ids: dict[str, str] | None = None
        self._tables: dict[str, "Table"] = {}

    # ---------- 传输与三态 ----------

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        headers = {
            "Accept": "application/json",
            "X-Agent-Id": self.agent,
            "X-Origin": self.origin,
        }
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self._api_key:
            # 只发送，不记录、不打印。
            headers["X-API-Key"] = self._api_key
        request = urllib.request.Request(
            self.base + path, data=data, method=method, headers=headers
        )
        http = 0
        raw = ""
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                http = response.status
                raw = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            http = exc.code
            raw = exc.read().decode("utf-8", "replace")
        except Exception as exc:  # 连接中断/超时/DNS：请求可能已离开客户端 → unknown
            return {
                "http": 0,
                "state": "unknown",
                "payload": None,
                "raw": None,
                "error": f"{type(exc).__name__}: {_redact(exc)}",
            }
        payload = None
        if raw:
            try:
                payload = json.loads(raw)
            except ValueError:
                payload = None
        state = classify(http, payload)
        result = {"http": http, "state": state, "payload": payload, "raw": raw}
        if state != "success":
            result["error"] = error_text(result)
        return result

    def get(self, path: str) -> dict:
        resp = self._request("GET", path)
        if resp["http"] == 200 and isinstance(resp.get("payload"), dict):
            return resp["payload"]
        raise SkillFailure(
            f"读接口 {path} 失败（HTTP {resp['http']}）：{error_text(resp)}",
            state="unknown" if resp["state"] == "unknown" else "failed",
        )

    # ---------- 表与字段 ----------

    def table_ids(self) -> dict[str, str]:
        if self._table_ids is None:
            data = self.get(f"/api/projects/{self.project}/tables")
            by_name = {
                item.get("name"): item.get("id")
                for item in data.get("tables", [])
                if isinstance(item, dict)
            }
            resolved: dict[str, str] = {}
            for key in self.allowed:
                name = TABLE_NAMES.get(key)
                if name is None:
                    raise SkillFailure(f"内部错误：未知表键 {key!r}")
                if name not in by_name:
                    missing = sorted(TABLE_NAMES[k] for k in self.allowed if TABLE_NAMES[k] not in by_name)
                    raise SkillFailure(
                        f"项目「{self.project}」缺少表：{'、'.join(missing)}；"
                        "项目未迁到 board@4，请先完成六表迁移"
                    )
                resolved[key] = by_name[name]
            self._table_ids = resolved
        return self._table_ids

    def table(self, key: str, *, refresh: bool = False) -> "Table":
        if key not in self.allowed:
            raise SkillFailure(
                f"越权访问：技能只允许表 {sorted(self.allowed)}，拒绝读取/写入「{TABLE_NAMES.get(key, key)}」"
            )
        if refresh or key not in self._tables:
            table_id = self.table_ids()[key]
            self._tables[key] = Table(self, key, table_id, self.get(f"/api/tables/{table_id}/table"))
        return self._tables[key]

    def get_row(self, table_id: str, row_id: str) -> dict | None:
        resp = self._request("GET", f"/api/tables/{table_id}/rows/{row_id}")
        if resp["http"] == 404:
            return None
        if resp["http"] != 200 or not isinstance(resp.get("payload"), dict):
            raise SkillFailure(
                f"读取行 {table_id}/{row_id} 失败（HTTP {resp['http']}）：{error_text(resp)}",
                state="unknown" if resp["state"] == "unknown" else "failed",
            )
        row = resp["payload"].get("row")
        return row if isinstance(row, dict) else None

    def write(self, op: str, table_key: str, row_id: str, values: dict) -> dict:
        if table_key not in self.allowed:
            raise SkillFailure(f"越权写入：技能不允许写表「{TABLE_NAMES.get(table_key, table_key)}」")
        table = self.table(table_key)
        method = "POST" if op == "create" else "PATCH"
        return self._request(
            method,
            f"/api/agent/tables/{table.table_id}/rows/{row_id}",
            {"values": values},
        )

    def verify_row(self, table_key: str, row_id: str, expected: dict[str, object]) -> dict:
        """回读单行并按字段名比对；返回 ``{ok, unknown, fields, error}``。"""
        table = self.table(table_key)
        try:
            row = self.get_row(table.table_id, row_id)
        except SkillFailure as exc:
            return {"ok": False, "unknown": exc.state == "unknown", "fields": {}, "error": str(exc)}
        if row is None:
            fields = {
                name: {"expect": value, "actual": None, "ok": same_value(value, None)}
                for name, value in expected.items()
            }
            return {
                "ok": all(item["ok"] for item in fields.values()),
                "unknown": False,
                "fields": fields,
                "error": "行不存在",
            }
        values = row.get("values") or {}
        checks: dict[str, dict] = {}
        for name, want in expected.items():
            field_id = table.fid(name, required=False)
            actual = values.get(field_id) if field_id else None
            checks[name] = {"expect": want, "actual": actual, "ok": same_value(want, actual)}
        return {
            "ok": all(item["ok"] for item in checks.values()),
            "unknown": False,
            "fields": checks,
        }

    def write_verified(
        self,
        op: str,
        table_key: str,
        row_id: str,
        values: dict,
        expected: dict[str, object],
    ) -> dict:
        """写 + 回读；三态与重试矩阵按 012。返回含 state/attempts/readback 的明细。"""

        def readback() -> dict:
            return self.verify_row(table_key, row_id, expected)

        resp = self.write(op, table_key, row_id, values)
        detail = {
            "state": resp["state"],
            "http": resp["http"],
            "error": resp.get("error"),
            "attempts": 1,
            "reconciled": False,
            "readback": None,
        }
        if resp["state"] == "success":
            checked = readback()
            detail["readback"] = checked
            if checked["ok"]:
                return detail
            detail["state"] = "failed"
            detail["error"] = "写接口返回 success 但回读不一致"
            return detail
        if resp["state"] == "failed":
            # 幂等补偿（P-031）：建行撞「已存在」→ 回读一致即按 success(reconciled)。
            if op == "create" and "已存在" in (resp.get("error") or ""):
                checked = readback()
                detail["readback"] = checked
                if checked["ok"]:
                    detail["state"] = "success"
                    detail["reconciled"] = True
                    return detail
            return detail
        # unknown：先回读，回读不能定案再退避重试同一幂等键。
        for delay in (0.1, 0.2, 0.4):
            checked = readback()
            detail["readback"] = checked
            if checked["ok"]:
                detail["state"] = "success"
                detail["reconciled"] = True
                return detail
            time.sleep(delay)
            resp = self.write(op, table_key, row_id, values)
            detail["http"] = resp["http"]
            detail["attempts"] += 1
            if resp["state"] == "success":
                break
            if resp["state"] == "failed":
                if op == "create" and "已存在" in (resp.get("error") or ""):
                    continue
                detail["state"] = "failed"
                detail["error"] = resp.get("error")
                return detail
        checked = readback()
        detail["readback"] = checked
        if checked["ok"]:
            detail["state"] = "success"
            detail["reconciled"] = True
        else:
            detail["state"] = "unknown"
            detail["error"] = detail.get("error") or "unknown 且回读无法定案"
        return detail


class Table:
    """一张表的字段与行快照；字段按名称解析。"""

    def __init__(self, client: Client, key: str, table_id: str, payload: dict):
        self.client = client
        self.key = key
        self.table_id = table_id
        self._load(payload)

    def _load(self, payload: dict) -> None:
        self.fields: dict[str, dict] = {
            field.get("name"): field for field in payload.get("fields", []) if isinstance(field, dict)
        }
        self.rows: dict[str, dict] = {
            row.get("id"): (row.get("values") or {})
            for row in payload.get("rows", [])
            if isinstance(row, dict)
        }

    def refresh(self) -> "Table":
        return self.client.table(self.key, refresh=True)

    def fid(self, name: str, *, required: bool = True) -> str | None:
        field = self.fields.get(name)
        if field is None:
            if required:
                raise SkillFailure(
                    f"表「{TABLE_NAMES[self.key]}」缺少字段「{name}」；项目不是 board@4 契约"
                )
            return None
        return field.get("id")

    def require(self, names: list[str] | tuple[str, ...]) -> None:
        missing = [name for name in names if name not in self.fields]
        if missing:
            raise SkillFailure(
                f"表「{TABLE_NAMES[self.key]}」缺少字段：{'、'.join(missing)}；项目不是 board@4 契约"
            )

    def value(self, row_id: str, name: str, default: object = None) -> object:
        field_id = self.fid(name, required=False)
        if field_id is None:
            return default
        return (self.rows.get(row_id) or {}).get(field_id, default)

    def row_exists(self, row_id: str) -> bool:
        return row_id in self.rows

    def relation(self, row_id: str, name: str) -> list[str]:
        value = self.value(row_id, name)
        if not value:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str)]
        return []


class Report:
    """统一 JSON 报告；退出码 0 当且仅当 result=success。"""

    def __init__(self, skill: str, args: argparse.Namespace):
        self.data: dict[str, object] = {
            "skill": skill,
            "project": getattr(args, "project", None),
            "version": getattr(args, "version", None),
            "mode": "dry-run" if getattr(args, "dry_run", False) else "apply",
            "result": "failed",
            "checks": [],
            "writes": [],
            "readback": {},
            "counts": {},
            "orphans": [],
            "errors": [],
        }
        if getattr(args, "apply", False):
            self.data["apply"] = True
        if getattr(args, "apply", False) and getattr(args, "dry_run", False):
            # 任务契约：--dry-run 优先于 --apply，二者同给时按只读执行。
            self.data["apply_ignored_by"] = "dry-run"

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.data["checks"].append({"name": name, "ok": bool(ok), "detail": detail})

    def write(
        self,
        target: str,
        field: str,
        value: object,
        state: str,
        http: int | None = None,
        error: str | None = None,
    ) -> None:
        item = {"target": target, "field": field, "value": value, "state": state}
        if http is not None:
            item["http"] = http
        if error:
            item["error"] = error
        self.data["writes"].append(item)

    def readback(self, target: str, detail: dict) -> None:
        self.data["readback"][target] = detail

    def count(self, **counts: int) -> None:
        self.data["counts"].update(counts)

    def note(self, key: str, value: object) -> None:
        self.data[key] = value

    def finish(self, result: str, error: str | None = None) -> None:
        self.data["result"] = result
        if error:
            self.data["errors"].append(error)

    def emit(self) -> int:
        print(json.dumps(self.data, ensure_ascii=False, indent=1, sort_keys=False))
        if self.data["result"] == "success":
            return 0
        if self.data["result"] == "unknown":
            return 2
        return 1


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--version", required=True, help="目标版本号（版本表行 id，如 v0.7.0）")
    parser.add_argument("--base", default=os.environ.get("TF_BASE"), help="看板地址，默认 TF_BASE")
    parser.add_argument("--project", default=os.environ.get("TF_PROJECT", "tableflow"))
    parser.add_argument("--agent", default=os.environ.get("TF_AGENT", "agent-tf-role"))
    parser.add_argument("--repo-root", default=os.environ.get("TF_REPO_ROOT"))
    parser.add_argument(
        "--apply",
        action="store_true",
        help="显式确认执行写入（默认即写入；与 --dry-run 同时给出时按只读）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只读：检查并输出计划，不写")
    parser.add_argument("--no-stage", action="store_true", help="做本节点的工作但不推进节点")
    return parser


def make_client(args: argparse.Namespace, allowed: list[str] | tuple[str, ...]) -> Client:
    return Client(
        base=args.base,
        project=args.project,
        agent=args.agent,
        allowed=set(allowed),
    )


def resolve_repo_root(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def require_version(
    ver: Table, version: str, report: Report, *, require_planned: bool = True
) -> None:
    ver.require(["版本号", "发布状态"])
    if not ver.row_exists(version):
        raise SkillFailure(f"版本「{version}」不存在；先确认版本表行 id")
    status = ver.value(version, "发布状态")
    report.check("版本存在", True, version)
    if require_planned:
        report.check("发布状态为 planned", status == "planned", f"当前 {status}")
        if status != "planned":
            raise SkillFailure(f"版本 {version} 的发布状态是 {status}，只允许推进 planned 版本")


def require_run_version(version: str) -> None:
    """执行记录行 id 是 <版本号>--<用例号>，版本号必须形如 v<主>.<次>.<修>。"""
    if not RUN_VERSION_RE.match(version or ""):
        raise SkillFailure(
            f"版本行 id「{version}」不是 v<主>.<次>.<修> 形式；"
            "无法构造执行记录 id（<版本号>--<用例号>）"
        )


def node_snapshot(ver: Table, version: str) -> dict[str, object]:
    snapshot: dict[str, object] = {}
    for name in NODE_FIELDS:
        snapshot[name] = ver.value(version, name, default="<字段缺失>")
    return snapshot


def stage_done(snapshot: dict[str, object]) -> bool:
    return all(snapshot.get(name) == "done" for name in NODE_FIELDS)


def ensure_prior_nodes(ver: Table, version: str, node: str, report: Report) -> None:
    if node not in NODE_FIELDS:
        raise SkillFailure(f"内部错误：未知节点 {node!r}")
    index = NODE_FIELDS.index(node)
    snapshot = node_snapshot(ver, version)
    blockers = [
        (name, snapshot.get(name)) for name in NODE_FIELDS[:index] if snapshot.get(name) != "done"
    ]
    detail = "、".join(f"{name}={value}" for name, value in blockers) or "全部 done"
    report.check(f"前序节点（{index} 个）", not blockers, detail)
    if blockers:
        raise SkillFailure(f"前序节点未完成，不能推进「{node}」：{detail}")


def advance_node(
    client: Client,
    ver: Table,
    version: str,
    node: str,
    report: Report,
    *,
    dry_run: bool,
    no_stage: bool,
) -> str:
    target = f"ver/{version}"
    if dry_run or no_stage:
        reason = "dry-run" if dry_run else "no-stage"
        report.write(target, node, "done", "skipped", error=f"{reason}：未写")
        report.check(f"节点「{node}」", True, f"{reason}：未推进，只输出计划")
        return "skipped"
    field_id = ver.fid(node)
    detail = client.write_verified("update", "ver", version, {field_id: "done"}, {node: "done"})
    report.write(target, node, "done", detail["state"], detail.get("http"), detail.get("error"))
    report.readback(target, detail.get("readback") or {})
    if detail["state"] != "success":
        raise SkillFailure(
            f"节点「{node}」推进失败：{detail.get('error') or '回读不一致'}",
            state=detail["state"],
        )
    fresh = ver.refresh()
    snapshot = node_snapshot(fresh, version)
    report.readback(f"ver/{version}#nodes", snapshot)
    report.check(f"节点「{node}」读回", snapshot.get(node) == "done", f"= {snapshot.get(node)}")
    return "success"


def readback_nodes(ver: Table, version: str, report: Report) -> dict[str, object]:
    snapshot = node_snapshot(ver, version)
    report.readback(f"ver/{version}#nodes", snapshot)
    report.note("stage_done", stage_done(snapshot))
    return snapshot


# ---------- 规格场景解析（用例真源） ----------


def parse_spec(path: Path) -> list[dict]:
    """解析 spec.md 的 User Story 与 Acceptance Scenario。

    返回 ``[{number, title, priority, scenarios:[{seq, given, when, then}]}]``。
    只认 ``### User Story n - ...`` 与单行 ``1. **Given** ... **When** ... **Then** ...``，
    与各规格现有写法一致；非场景段落不猜。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillFailure(f"读取规格失败：{path}（{exc}）") from exc
    stories: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        match = STORY_RE.match(line)
        if match:
            current = {
                "number": int(match.group(1)),
                "title": match.group(2).strip(),
                "priority": (match.group(3) or "P1").strip(),
                "scenarios": [],
            }
            stories.append(current)
            continue
        if line.startswith("### "):
            current = None
            continue
        scene = SCENARIO_RE.match(line)
        if scene and current is not None:
            current["scenarios"].append(
                {
                    "seq": int(scene.group(1)),
                    "given": scene.group(2).strip(),
                    "when": scene.group(3).strip(),
                    "then": scene.group(4).strip(),
                }
            )
    return stories


def scenario_count(stories: list[dict]) -> int:
    return sum(len(story["scenarios"]) for story in stories)


def spec_dir_of(indep: Table, spec_id: str) -> str:
    directory = indep.value(spec_id, "规格目录")
    if not isinstance(directory, str) or not directory.strip():
        raise SkillFailure(f"规格「{spec_id}」的「规格目录」为空，无法定位 spec.md")
    return directory.strip()


def spec_file(repo_root: Path, indep: Table, spec_id: str) -> Path:
    directory = spec_dir_of(indep, spec_id)
    path = repo_root / directory / "spec.md"
    if not path.exists():
        raise SkillFailure(f"规格「{spec_id}」的 spec.md 不存在：{path}")
    return path


def tasks_file(repo_root: Path, indep: Table, spec_id: str) -> Path | None:
    directory = spec_dir_of(indep, spec_id)
    path = repo_root / directory / "tasks.md"
    return path if path.exists() else None


def parse_tasks(path: Path) -> dict:
    """返回未勾选/已勾选任务；tasks.md 不存在返回 exists=False。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillFailure(f"读取任务清单失败：{path}（{exc}）") from exc
    unchecked: list[str] = []
    checked = 0
    for line in text.splitlines():
        if re.match(r"^\s*- \[ \]", line):
            unchecked.append(re.sub(r"^\s*- \[ \]\s*", "", line).strip())
        elif re.match(r"^\s*- \[[xX]\]", line):
            checked += 1
    return {"exists": True, "unchecked": unchecked, "checked": checked}


def case_id_for(spec_id: str, story_number: int, seq: int) -> str:
    prefix = spec_id.split("-", 1)[0]
    if not re.match(r"^[A-Za-z0-9]{3}$", prefix):
        raise SkillFailure(
            f"规格「{spec_id}」的编号不是 <三位数字>-AR 形式，无法派生用例行 id"
        )
    return f"{prefix}-US{story_number}-AS{seq}"


def derive_cases(spec_id: str, path: Path) -> list[dict]:
    stories = parse_spec(path)
    cases: list[dict] = []
    for story in stories:
        priority = story["priority"] if story["priority"] in ("P0", "P1", "P2") else "P1"
        for scene in story["scenarios"]:
            case_id = case_id_for(spec_id, story["number"], scene["seq"])
            cases.append(
                {
                    "id": case_id,
                    "name": scene["then"][:80],
                    "precondition": scene["given"],
                    "steps": scene["when"],
                    "expect": scene["then"],
                    "priority": priority,
                }
            )
    if not cases:
        raise SkillFailure(f"规格 {spec_id} 没有可派生的 Acceptance Scenario：{path}")
    return cases


# ---------- 入口 ----------


def entry(skill: str, parser: argparse.ArgumentParser, main) -> int:
    args = parser.parse_args()
    report = Report(skill, args)
    try:
        main(args, report)
    except SkillFailure as exc:
        report.finish(exc.state, str(exc))
    except KeyboardInterrupt:
        report.finish("unknown", "被中断；写请求可能已发出，请回读核对")
    except Exception as exc:  # noqa: BLE001 - 技能不打印 traceback，避免带出环境细节
        report.finish("unknown", f"未预期错误：{type(exc).__name__}: {_redact(exc)}")
    return report.emit()
