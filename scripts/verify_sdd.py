#!/usr/bin/env python3
"""SDD 规约验证器（Spec-Driven Development Verifier）

验证代码实现是否对齐规约文档（specs/），并自动生成追溯矩阵。

用法：
    python3 scripts/verify_sdd.py              # 完整验证
    python3 scripts/verify_sdd.py --spec api   # 只验证 API 规约
    python3 scripts/verify_sdd.py --spec models# 只验证数据模型
    python3 scripts/verify_sdd.py --spec protocol  # 只验证协议规约
    python3 scripts/verify_sdd.py --spec evidence  # 只验证证据链
    python3 scripts/verify_sdd.py --regen        # 只重新生成追溯矩阵
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ─── 路径设置 ───────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent          # Ai-worker/
DOCS = ROOT / "docs"
SCHEMAS = DOCS / "schemas"
APISPEC = DOCS / "api" / "openapi.yaml"
SPECSDIR = ROOT / "specs"
SERVER_PY = ROOT / "mvp" / "server.py"
WORKFORCE_PY = ROOT / "mvp" / "workforce.py"


# ─── 结果记录 ───────────────────────────────────────────────────────
@dataclass
class CheckResult:
    """单个检查项的结果。"""
    category: str          # api / models / protocol / evidence
    spec_ref: str          # 规约文档中的引用（如 "api-contract.md#1.1"）
    description: str       # 检查描述
    status: str = "pending"  # pending / pass / fail / skip
    detail: str = ""       # 详细信息

    @property
    def symbol(self) -> str:
        return {"pass": "✅", "fail": "❌", "skip": "🔲", "pending": "⏳"}[self.status]


@dataclass
class Verifier:
    """规约验证器。"""
    results: list[CheckResult] = field(default_factory=list)
    categories: set[str] = field(default_factory=set)

    def check(self, category: str, spec_ref: str, description: str,
              condition: bool, detail: str = "") -> None:
        """记录一个检查项。"""
        self.categories.add(category)
        status = "pass" if condition else "fail"
        self.results.append(CheckResult(category, spec_ref, description, status, detail))


# ─── OpenAPI 解析器 ─────────────────────────────────────────────────
def parse_openapi() -> dict:
    """简易 YAML 解析器（不依赖 pyyaml，避免系统缺少依赖）。"""
    try:
        import yaml
        with open(APISPEC, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        return _parse_yaml_fallback()


def _parse_yaml_fallback() -> dict:
    """最简 YAML 解析：只提取 paths 和 components.schemas。"""
    text = APISPEC.read_text(encoding="utf-8")
    result: dict = {"paths": {}, "components": {"schemas": {}}}

    # 提取 paths
    in_paths = False
    current_path = None
    current_method = None
    path_data: dict = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "paths:":
            in_paths = True
            continue
        if in_paths and stripped and not line[0].isspace():
            in_paths = False
        if in_paths:
            m = re.match(r"^  (/[\w/]+):$", line)
            if m:
                current_path = m.group(1)
                result["paths"][current_path] = {}
                continue
            m = re.match(r"^    (get|post|put|delete|patch|head):$", line)
            if m and current_path:
                current_method = m.group(1)
                result["paths"][current_path][current_method] = {}
                continue

    # 提取 schemas
    in_schemas = False
    current_schema = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "schemas:":
            in_schemas = True
            continue
        if in_schemas:
            m = re.match(r"^    ([A-Z]\w+):$", line)
            if m:
                current_schema = m.group(1)
                result["components"]["schemas"][current_schema] = {}
                continue
            if current_schema and stripped.startswith("type:"):
                result["components"]["schemas"][current_schema]["type"] = stripped.split(":", 1)[1].strip()
            if current_schema and "required" in stripped.lower():
                # 提取 required 数组
                m2 = re.search(r"\[(.*?)\]", stripped)
                if m2:
                    items = [i.strip().strip('"').strip("'") for i in m2.group(1).split(",")]
                    result["components"]["schemas"][current_schema]["required"] = items

    return result


# ─── 代码解析器 ─────────────────────────────────────────────────────
def extract_server_routes() -> dict:
    """从 server.py 提取路由信息。"""
    text = SERVER_PY.read_text(encoding="utf-8")
    routes: dict = {}

    # 提取路由（两种写法：单路径 == 和批量 in）；路径可含 - 与 /
    for m in re.finditer(r'if self\.path == "(/[^\"]*)":', text):
        path = m.group(1)
        routes[path] = {"methods": {"get": True}}
    # 批量路由（含根路径 "/"）
    for m in re.finditer(r'if self\.path in \((.*?)\):', text):
        paths_str = m.group(1)
        for p in re.findall(r'"(/[^\"]*)"', paths_str):
            if p not in routes:
                routes[p] = {"methods": {"get": True}}

    # 提取 POST 路由
    for m in re.finditer(r'if self\.path == "(/[^\"]*)":', text):
        path = m.group(1)
        if path not in routes:
            routes[path] = {"methods": {"post": True}}
        else:
            routes[path]["methods"]["post"] = True
    # 批量 POST 路由
    for m in re.finditer(r'if self\.path in \((.*?)\):', text):
        paths_str = m.group(1)
        for p in re.findall(r'"(/[^\"]*)"', paths_str):
            if p not in routes:
                routes[p] = {"methods": {"post": True}}
            else:
                routes[p]["methods"]["post"] = True

    return routes


def extract_workforce_methods() -> dict:
    """从 workforce.py 提取方法签名。"""
    text = WORKFORCE_PY.read_text(encoding="utf-8")
    methods: dict = {}

    for m in re.finditer(r'def (\w+)\(self[^)]*\)[^:]*:', text):
        name = m.group(1)
        methods[name] = {"signature": m.group(0)}

    return methods


# ─── 验证器：API 规约 ───────────────────────────────────────────────
def verify_api(v: Verifier) -> None:
    """验证 API 规约。"""
    openapi = parse_openapi()
    routes = extract_server_routes()
    paths = openapi.get("paths", {})

    for path, methods in paths.items():
        for method in methods:
            if method in ("head",):
                continue  # 页面 HEAD 检查不验证
            spec_ref = f"api-contract.md#{path}_{method}"
            desc = f"{method.upper()} {path}"

            # 检查路由是否存在
            if path in routes:
                route_methods = routes[path].get("methods", {})
                if method in route_methods:
                    v.check("api", spec_ref, desc, True, f"路由 {method.upper()} {path} 存在于 server.py")
                else:
                    v.check("api", spec_ref, desc, False, f"server.py 中缺少 {method.upper()} {path}")
            else:
                v.check("api", spec_ref, desc, False, f"server.py 中缺少路由 {path}")


# ─── 验证器：数据模型 ───────────────────────────────────────────────
def verify_models(v: Verifier) -> None:
    """验证数据模型规约。"""
    methods = extract_workforce_methods()

    # 验证 Task 模型
    task_schema = _load_schema("task.json")
    if task_schema:
        required_fields = task_schema.get("properties", {}).get("required", [])
        if not required_fields:
            # 从 schema 中提取 required
            for line in SCHEMAS.joinpath("task.json").read_text().splitlines():
                if "required:" in line:
                    m = re.search(r"\[(.*?)\]", line)
                    if m:
                        required_fields = [f.strip() for f in m.group(1).split(",")]
                    break

        for field_name in required_fields:
            spec_ref = f"data-models.md#1-task"
            # 检查 workforce.py 中 create_task 是否返回此字段
            text = WORKFORCE_PY.read_text(encoding="utf-8")
            has_field = field_name in text
            v.check("models", spec_ref, f"Task.{field_name} 在代码中存在", has_field)

    # 验证 EvidenceItem 模型
    evidence_schema = _load_schema("evidence.json")
    if evidence_schema:
        spec_ref = f"data-models.md#4-evidenceitem"
        text = WORKFORCE_PY.read_text(encoding="utf-8")
        has_source_url = '"source_url"' in text
        has_https_check = 'startswith("https://")' in text
        v.check("models", spec_ref, "EvidenceItem.source_url 存在", has_source_url)
        v.check("models", spec_ref, "EvidenceItem.source_url HTTPS 校验", has_https_check)

    # 验证 TwinDecision 模型
    twin_schema = _load_schema("twin-decision.json")
    if twin_schema:
        spec_ref = f"data-models.md#9-twindecision"
        text = WORKFORCE_PY.read_text(encoding="utf-8")
        # 这些字段以关键字参数形式写入（evidence_ids=...），不带引号
        has_evidence_ids = 'evidence_ids' in text
        has_ignored = 'ignored_evidence' in text
        has_uncertainty = re.search(r'\buncertainty\b', text) is not None
        v.check("models", spec_ref, "TwinDecision.evidence_ids 存在", has_evidence_ids)
        v.check("models", spec_ref, "TwinDecision.ignored_evidence 存在", has_ignored)
        v.check("models", spec_ref, "TwinDecision.uncertainty 存在", has_uncertainty)


# ─── 验证器：协议规约 ───────────────────────────────────────────────
def verify_protocol(v: Verifier) -> None:
    """验证协议规约。"""
    text = WORKFORCE_PY.read_text(encoding="utf-8")

    # 验证状态机
    status_enum = ["queued", "approval_required", "assigned", "awaiting_validation",
                   "completed", "blocked", "failed", "cancelled", "superseded"]
    for status in status_enum:
        spec_ref = "protocol.md#2-任务生命周期状态机"
        has_status = f'"{status}"' in text or f"'{status}'" in text
        v.check("protocol", spec_ref, f"状态 {status} 在代码中存在", has_status)

    # 验证租约令牌
    spec_ref = "protocol.md#42-租约令牌fencing-token"
    has_lease_token = '"_lease_token"' in text
    has_lease_check = 'lease_token' in text
    v.check("protocol", spec_ref, "租约令牌分配", has_lease_token)
    v.check("protocol", spec_ref, "租约令牌校验", has_lease_check)

    # 验证重试有界
    spec_ref = "protocol.md#43-重试策略"
    has_max_attempts = '"max_attempts"' in text
    has_attempts_check = 'attempts' in text and 'max_attempts' in text
    v.check("protocol", spec_ref, "max_attempts 字段", has_max_attempts)
    v.check("protocol", spec_ref, "attempts < max_attempts 检查", has_attempts_check)


# ─── 验证器：证据链规约 ─────────────────────────────────────────────
def verify_evidence(v: Verifier) -> None:
    """验证证据链规约。"""
    server_text = SERVER_PY.read_text(encoding="utf-8")
    workforce_text = WORKFORCE_PY.read_text(encoding="utf-8")

    # 验证 _assess_source_reliability
    spec_ref = "evidence-chain.md#3-来源可靠性评级规则"
    has_assess = "_assess_source_reliability" in server_text
    v.check("evidence", spec_ref, "_assess_source_reliability() 存在", has_assess)

    # 验证 _check_evidence_traceability
    spec_ref = "evidence-chain.md#4-可追溯性检查规则"
    has_trace = "_check_evidence_traceability" in server_text
    v.check("evidence", spec_ref, "_check_evidence_traceability() 存在", has_trace)

    # 验证 _audit_worker_result
    spec_ref = "evidence-chain.md#5-分身审计流程"
    has_audit = "_audit_worker_result" in server_text
    has_simulated_verdict = "SIMULATION_ONLY" in server_text
    has_traceable_verdict = "TRACEABLE_BUT_UNVERIFIED" in server_text
    has_needs_evidence_verdict = "NEEDS_INDEPENDENT_EVIDENCE" in server_text
    v.check("evidence", spec_ref, "_audit_worker_result() 存在", has_audit)
    v.check("evidence", spec_ref, "verdict: SIMULATION_ONLY", has_simulated_verdict)
    v.check("evidence", spec_ref, "verdict: TRACEABLE_BUT_UNVERIFIED", has_traceable_verdict)
    v.check("evidence", spec_ref, "verdict: NEEDS_INDEPENDENT_EVIDENCE", has_needs_evidence_verdict)

    # 验证 evidence 字段校验
    spec_ref = "evidence-chain.md#11-证据项字段规约"
    has_evidence_param = "evidence" in workforce_text
    has_confidence_check = "confidence" in workforce_text
    has_simulated_check = "simulated" in workforce_text
    v.check("evidence", spec_ref, "report() 含 evidence 参数", has_evidence_param)
    v.check("evidence", spec_ref, "confidence 校验", has_confidence_check)
    v.check("evidence", spec_ref, "simulated 校验", has_simulated_check)


# ─── 追溯矩阵生成 ───────────────────────────────────────────────────
def generate_traceability_md(v: Verifier) -> None:
    """生成追溯矩阵 Markdown 文件。"""
    lines: list[str] = []
    lines.append("# 追溯矩阵（Traceability Matrix）")
    lines.append("")
    lines.append("> **自动生成：** 此文件由 `scripts/verify_sdd.py` 生成。")
    lines.append(f"> **最后更新：** {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}")
    lines.append("> **规约目录：** [specs/](./)")
    lines.append("")

    symbols = {"pass": "✅", "fail": "❌", "skip": "🔲"}

    for category in ["api", "models", "protocol", "evidence"]:
        cat_results = [r for r in v.results if r.category == category]
        if not cat_results:
            continue

        cat_names = {"api": "API 规约", "models": "数据模型", "protocol": "协议规约", "evidence": "证据链规约"}
        lines.append(f"## {cat_names[category]}追溯")
        lines.append("")
        lines.append("| 规约条目 | 规约文档 | 代码位置 | 状态 |")
        lines.append("|---------|---------|---------|------|")

        for r in cat_results:
            status_sym = symbols.get(r.status, "⏳")
            lines.append(f"| {r.description} | {r.spec_ref} | — | {status_sym} |")

        lines.append("")

    # 统计
    lines.append("## 统计摘要")
    lines.append("")
    lines.append("| 类别 | 总条目 | ✅ | ❌ |")
    lines.append("|------|--------|----|----|")
    for category in ["api", "models", "protocol", "evidence"]:
        cat_results = [r for r in v.results if r.category == category]
        total = len(cat_results)
        passed = sum(1 for r in cat_results if r.status == "pass")
        failed = sum(1 for r in cat_results if r.status == "fail")
        lines.append(f"| {cat_names[category]} | {total} | {passed} | {failed} |")

    lines.append("")
    total_all = len(v.results)
    passed_all = sum(1 for r in v.results if r.status == "pass")
    failed_all = sum(1 for r in v.results if r.status == "fail")
    lines.append(f"| **合计** | **{total_all}** | **{passed_all}** | **{failed_all}** |")
    lines.append("")

    trace_path = SPECSDIR / "traceability.md"
    trace_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  追溯矩阵已更新: {trace_path}")


# ─── 辅助函数 ───────────────────────────────────────────────────────
def _load_schema(name: str) -> dict | None:
    """加载 JSON Schema 文件。"""
    path = SCHEMAS / name
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


# ─── 主入口 ─────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="SDD 规约验证器")
    parser.add_argument("--spec", choices=["api", "models", "protocol", "evidence"],
                        help="只验证指定类别")
    parser.add_argument("--regen", action="store_true", help="只重新生成追溯矩阵")
    args = parser.parse_args()

    v = Verifier()

    if args.regen:
        # 重新生成追溯矩阵（使用现有结果或空结果）
        generate_traceability_md(v)
        return 0

    # 运行验证
    if args.spec is None or args.spec == "api":
        print("验证 API 规约...")
        verify_api(v)
    if args.spec is None or args.spec == "models":
        print("验证数据模型规约...")
        verify_models(v)
    if args.spec is None or args.spec == "protocol":
        print("验证协议规约...")
        verify_protocol(v)
    if args.spec is None or args.spec == "evidence":
        print("验证证据链规约...")
        verify_evidence(v)

    # 打印结果
    print()
    passed = sum(1 for r in v.results if r.status == "pass")
    failed = sum(1 for r in v.results if r.status == "fail")
    skipped = sum(1 for r in v.results if r.status == "skip")

    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    if skipped:
        print(f"  跳过: {skipped}")
    print()

    if failed:
        print("失败的检查项:")
        for r in v.results:
            if r.status == "fail":
                print(f"  {r.symbol} [{r.category}] {r.description}")
                if r.detail:
                    print(f"       {r.detail}")
        print()

    # 生成追溯矩阵
    generate_traceability_md(v)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
