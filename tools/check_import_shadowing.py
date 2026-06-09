#!/usr/bin/env python3
"""
检测「导入名被路由/本地函数遮蔽」导致的协程误用问题。

典型故障：async 路由函数与导入的工具函数同名，运行时调用返回 coroutine 而非实际值。
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = [ROOT / "app"]


@dataclass
class Issue:
    path: Path
    line: int
    kind: str
    name: str
    detail: str


class ModuleAnalyzer(ast.NodeVisitor):
    def __init__(self, path: Path, source: str):
        self.path = path
        self.source = source
        self.imports: dict[str, int] = {}
        self.functions: dict[str, ast.AST] = {}
        self.issues: list[Issue] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.asname or alias.name
            self.imports[name] = node.lineno
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                continue
            name = alias.asname or alias.name
            self.imports[name] = node.lineno
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._register_function(node)
        self._check_async_calls(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._register_function(node)
        self._check_async_calls(node)
        self.generic_visit(node)

    def _register_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if node.name in self.imports:
            imported_at = self.imports[node.name]
            is_async = isinstance(node, ast.AsyncFunctionDef)
            self.issues.append(
                Issue(
                    path=self.path,
                    line=node.lineno,
                    kind="import_shadow",
                    name=node.name,
                    detail=(
                        f"本地定义遮蔽了第 {imported_at} 行的导入；"
                        f"{'async 路由' if is_async else '函数'}会覆盖工具函数引用"
                    ),
                )
            )
        self.functions[node.name] = node

    def _check_async_calls(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if not isinstance(node, ast.AsyncFunctionDef):
            return

        async_funcs = {
            name: fn
            for name, fn in self.functions.items()
            if isinstance(fn, ast.AsyncFunctionDef)
        }
        self._attach_parents(node)

        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if not isinstance(func, ast.Name):
                continue
            callee = func.id
            if callee not in async_funcs:
                continue
            parent = getattr(child, "_parent", None)
            if isinstance(parent, ast.Await):
                continue
            self.issues.append(
                Issue(
                    path=self.path,
                    line=child.lineno,
                    kind="missing_await",
                    name=callee,
                    detail="async 函数被直接调用但未 await，可能返回 coroutine",
                )
            )

    @staticmethod
    def _attach_parents(node: ast.AST) -> None:
        for child in ast.walk(node):
            for sub in ast.iter_child_nodes(child):
                sub._parent = child  # type: ignore[attr-defined]


def analyze_file(path: Path) -> list[Issue]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    analyzer = ModuleAnalyzer(path, source)
    analyzer.visit(tree)
    return analyzer.issues


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        files.extend(sorted(base.rglob("*.py")))
    return files


def main() -> int:
    all_issues: list[Issue] = []
    for path in iter_python_files():
        try:
            all_issues.extend(analyze_file(path))
        except SyntaxError as exc:
            print(f"SYNTAX ERROR {path}: {exc}", file=sys.stderr)
            return 2

    if not all_issues:
        print("OK: 未发现导入遮蔽或 async 未 await 问题")
        return 0

    print(f"发现 {len(all_issues)} 个问题:\n")
    for issue in all_issues:
        rel = issue.path.relative_to(ROOT)
        print(f"  [{issue.kind}] {rel}:{issue.line}  {issue.name}")
        print(f"           {issue.detail}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
