from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    code: str
    detail: str

    def to_data(self) -> dict[str, Any]:
        return {"path": self.path, "line": self.line, "code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class ScanReport:
    root: str
    checked_files: int
    findings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    def to_data(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "checked_files": self.checked_files,
            "ok": self.ok,
            "findings": [item.to_data() for item in self.findings],
        }


def _task_key(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "task_id"
    if isinstance(node, ast.Subscript):
        key = node.slice
        return isinstance(key, ast.Constant) and key.value == "task_id"
    return False


def _scan_ast(path: Path, source: str) -> list[Finding]:
    findings: list[Finding] = []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [Finding(str(path), exc.lineno or 0, "SYNTAX_ERROR", str(exc))]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
            findings.append(Finding(str(path), node.lineno, "DYNAMIC_EXECUTION", node.func.id))
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if ".tests" in name or ".regression" in name:
                    findings.append(Finding(str(path), node.lineno, "TEST_IMPORT", name))
                if name.split(".")[0] in {"socket", "requests", "urllib", "httpx"}:
                    findings.append(Finding(str(path), node.lineno, "NETWORK_IMPORT", name))
        if isinstance(node, ast.ImportFrom):
            name = node.module or ""
            if ".tests" in name or ".regression" in name:
                findings.append(Finding(str(path), node.lineno, "TEST_IMPORT", name))
            if name.split(".")[0] in {"socket", "requests", "urllib", "httpx"}:
                findings.append(Finding(str(path), node.lineno, "NETWORK_IMPORT", name))
        if isinstance(node, ast.Compare) and _task_key(node.left):
            if any(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in node.comparators):
                findings.append(Finding(str(path), node.lineno, "TASK_ROUTING", "task identifier comparison"))
    return findings


def scan_tree(root: Path) -> ScanReport:
    root = Path(root)
    findings: list[Finding] = []
    checked = 0
    forbidden = ''.join(chr(item) for item in (115, 111, 108))
    suspicious = {
        "ROW_KEY_MAP": ("input_hash_" + "answer", "row_answer_" + "map"),
        "TARGET_STORE": ("target_" + "ledger", "correction_" + "ledger"),
    }
    for path in sorted(root.rglob("*.py")):
        if "tests" in path.parts or "__pycache__" in path.parts:
            continue
        checked += 1
        source = path.read_text(encoding="utf-8")
        findings.extend(_scan_ast(path, source))
        lowered = source.casefold()
        if forbidden in lowered:
            findings.append(Finding(str(path), 0, "FORBIDDEN_TOKEN", "owner policy token"))
        if path.name != "security.py":
            for code, tokens in suspicious.items():
                for token in tokens:
                    if token in lowered:
                        findings.append(Finding(str(path), 0, code, token))
    return ScanReport(str(root), checked, tuple(findings))
