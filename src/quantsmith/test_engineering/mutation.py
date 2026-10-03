"""Mutation testing for Python (spec 0097).

Apply small, single-point AST mutations to one source file and re-run the tests against each mutant.
A mutant that **survives** (tests still pass) points at a behaviour the tests do not pin down. Mutants on
lines the tests never execute are reported separately as **uncovered**, because a surviving mutant there
is a coverage gap, not a weak assertion.

Operators: arithmetic (``+ - * / // % **``), comparison (``< <= > >= == !=``), boolean (``and``/``or``),
``not`` removal, ``if``/``while`` condition negation, numeric constants, ``True``/``False`` flips,
``return <expr>`` to ``return None``, and augmented assignment. The project is copied to a temporary
directory per run so the working tree is never modified. Mutation scores are only as meaningful as the
test suite's determinism, so run the flakiness check first.
"""

from __future__ import annotations

import ast
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .coverage_adapter import coverage_available, run_pytest_with_coverage
from .runners import run_pytest

ARITH = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult, ast.FloorDiv: ast.Mult, ast.Mod: ast.Mult, ast.Pow: ast.Mult}
COMPARE = {ast.Lt: ast.GtE, ast.LtE: ast.Gt, ast.Gt: ast.LtE, ast.GtE: ast.Lt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", "build", "dist", ".tox", "htmlcov"}


@dataclass(frozen=True)
class Mutant:
    index: int
    operator: str
    line: int
    description: str


@dataclass
class MutantResult:
    mutant: Mutant
    status: str                      # killed | survived | uncovered | timeout | error
    detail: str = ""


class _Mutator(ast.NodeTransformer):
    """Count mutation sites; mutate site number ``target`` (or none, when ``target`` is None)."""

    def __init__(self, target: Optional[int], skip_lines: Set[int] = frozenset()):
        self.target, self.count, self.sites, self.skip_lines = target, 0, [], skip_lines

    def _site(self, node: ast.AST, operator: str, description: str) -> bool:
        if getattr(node, "lineno", 0) in self.skip_lines:
            return False
        idx = self.count
        self.count += 1
        self.sites.append(Mutant(idx, operator, getattr(node, "lineno", 0), description))
        return idx == self.target

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        new = ARITH.get(type(node.op))
        if new and self._site(node, "AOR", f"{type(node.op).__name__} -> {new.__name__}"):
            node.op = new()
        return node

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        new = ARITH.get(type(node.op))
        if new and self._site(node, "AUG", f"{type(node.op).__name__}= -> {new.__name__}="):
            node.op = new()
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        for i, op in enumerate(node.ops):
            new = COMPARE.get(type(op))
            if new and self._site(node, "ROR", f"{type(op).__name__} -> {new.__name__}"):
                node.ops[i] = new()
                break
        return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        new = ast.Or if isinstance(node.op, ast.And) else ast.And
        if self._site(node, "LCR", f"{type(node.op).__name__} -> {new.__name__}"):
            node.op = new()
        return node

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Not) and self._site(node, "NOT", "remove `not`"):
            return node.operand
        return node

    def _negate_test(self, node, kind):
        self.generic_visit(node)
        if self._site(node, "COND", f"negate {kind} condition"):
            node.test = ast.copy_location(ast.UnaryOp(op=ast.Not(), operand=node.test), node.test)
        return node

    def visit_If(self, node):
        return self._negate_test(node, "if")

    def visit_While(self, node):
        return self._negate_test(node, "while")

    def visit_Constant(self, node):
        v = node.value
        if isinstance(v, bool):
            if self._site(node, "BOOL", f"{v} -> {not v}"):
                return ast.copy_location(ast.Constant(value=not v), node)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            if self._site(node, "CONST", f"{v!r} -> {v + 1!r}"):
                return ast.copy_location(ast.Constant(value=v + 1), node)
        return node

    def visit_Return(self, node):
        self.generic_visit(node)
        if node.value is not None and not (isinstance(node.value, ast.Constant) and node.value.value is None):
            if self._site(node, "RET", "return value -> None"):
                node.value = ast.copy_location(ast.Constant(value=None), node.value)
        return node


def _docstring_lines(tree: ast.AST) -> Set[int]:
    lines: Set[int] = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and n.body:
            first = n.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                lines.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return lines


def enumerate_mutants(source: str) -> List[Mutant]:
    tree = ast.parse(source)
    m = _Mutator(None, _docstring_lines(tree))
    m.visit(tree)
    return m.sites


def apply_mutant(source: str, index: int) -> str:
    tree = ast.parse(source)
    _Mutator(index, _docstring_lines(tree)).visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def _copy_project(root: Path, dest: Path) -> None:
    def ignore(_d, names):
        return [n for n in names if n in IGNORE_DIRS or n.endswith(".pyc")]
    shutil.copytree(root, dest, ignore=ignore, symlinks=True, dirs_exist_ok=True)


def run_mutation(root: str | Path, target: str, test_args: Sequence[str] = (), python: Optional[str] = None, max_mutants: int = 60,
                 timeout_s: float = 120.0, use_coverage: bool = True, line_range: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
    """Mutate ``target`` (path relative to ``root``) and run the tests on each mutant."""
    root = Path(root).resolve()
    target_path = (root / target).resolve()
    if not target_path.is_file() or root not in target_path.parents:
        raise ValueError(f"target {target!r} is not a file inside {root}")
    source = target_path.read_text(encoding="utf-8")
    base = run_pytest(root, test_args, timeout_s, python)
    if base.verdict != "passed":
        return {"target": target, "baseline": base.verdict, "score": None, "mutants": [], "note": "baseline tests do not pass; fix them before mutating"}
    covered: Optional[Set[int]] = None
    if use_coverage and coverage_available():
        cov = run_pytest_with_coverage(root, [str(target_path.parent)], test_args, timeout_s, python)
        files = cov.get("files", {})
        info = next((v for k, v in files.items() if Path(k).resolve() == target_path or k.endswith(target)), None)
        if info is not None:
            covered = set(info["executed"])
    sites = enumerate_mutants(source)
    if line_range:
        sites = [s for s in sites if line_range[0] <= s.line <= line_range[1]]
    truncated = len(sites) > max_mutants
    if truncated:
        step = len(sites) / max_mutants
        sites = [sites[int(i * step)] for i in range(max_mutants)]
    results: List[MutantResult] = []
    for s in sites:
        if covered is not None and s.line not in covered:
            results.append(MutantResult(s, "uncovered", "no test executes this line"))
            continue
        with tempfile.TemporaryDirectory(prefix="qte-mut-") as tmp:
            work = Path(tmp) / "proj"
            _copy_project(root, work)
            (work / target).write_text(apply_mutant(source, s.index), encoding="utf-8")
            r = run_pytest(work, [*test_args, "-x", "-q"], timeout_s, python)
        if r.verdict == "timeout":
            results.append(MutantResult(s, "timeout", "tests hung; counted as killed"))
        elif r.verdict in ("failed", "error"):
            results.append(MutantResult(s, "killed", r.verdict))
        else:
            results.append(MutantResult(s, "survived", "tests still pass"))
    killed = sum(r.status in ("killed", "timeout") for r in results)
    survived = [r for r in results if r.status == "survived"]
    uncovered = [r for r in results if r.status == "uncovered"]
    denom = killed + len(survived)
    return {
        "target": target, "baseline": "passed", "mutants_total": len(results), "killed": killed, "survived": len(survived),
        "uncovered": len(uncovered), "score": (killed / denom) if denom else None, "truncated_to": max_mutants if truncated else None,
        "coverage_used": covered is not None,
        "survivors": [{"line": r.mutant.line, "operator": r.mutant.operator, "change": r.mutant.description} for r in survived],
        "uncovered_mutants": [{"line": r.mutant.line, "operator": r.mutant.operator, "change": r.mutant.description} for r in uncovered],
        "note": "score = killed / (killed + survived); uncovered mutants are excluded and listed as coverage gaps. "
                "Some survivors are equivalent mutants (no observable change) and need human judgement.",
    }
