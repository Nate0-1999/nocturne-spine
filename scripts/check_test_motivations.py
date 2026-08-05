#!/usr/bin/env python3
"""Enforce and index test motivations under Garden A-040 / SPEC B.6."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import textwrap
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

CITATION_RE = re.compile(
    r"\b(?:SPEC\s+(?:\d+(?:\.\d+)*|[BCD]\.\d+)|ADR-\d{3}|A-\d{3}|"
    r"Invariant\s+\d+|P\d+(?:\.\d+)*(?:[a-z])?|F\d{3})\b"
)
JS_TEST_RE = re.compile(r"^\s*(?:test|it)\s*\(")
SPEC_HEADING_RE = re.compile(r"^#{1,6}\s+(?P<token>(?:\d+(?:\.\d+)*|[BCD]\.\d+|ADR-\d{3}))\b")


@dataclass(frozen=True)
class TestCase:
    identity: str
    digest: str
    motivation: str | None
    citations: tuple[str, ...]

    @property
    def compliant(self) -> bool:
        return bool(self.motivation and self.citations)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _python_digest(source: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    lines = source.splitlines()
    starts = [node.lineno, *(decorator.lineno for decorator in node.decorator_list)]
    segment = "\n".join(lines[min(starts) - 1 : node.end_lineno])
    normalized = "\n".join(line.rstrip() for line in textwrap.dedent(segment).strip().splitlines())
    return _digest(normalized)


def _python_cases(path: Path, root: Path) -> list[TestCase]:
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    relative = path.relative_to(root).as_posix()
    cases: list[TestCase] = []

    def visit(body: list[ast.stmt], parents: tuple[str, ...] = ()) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    motivation = ast.get_docstring(node, clean=True)
                    identity = f"{relative}::{'::'.join((*parents, node.name))}"
                    cases.append(
                        TestCase(
                            identity,
                            _python_digest(source, node),
                            motivation,
                            tuple(dict.fromkeys(CITATION_RE.findall(motivation or ""))),
                        )
                    )
                visit(node.body, (*parents, node.name))
            elif isinstance(node, ast.ClassDef):
                visit(node.body, (*parents, node.name))

    visit(tree.body)
    return cases


def _js_cases(path: Path, root: Path) -> list[TestCase]:
    lines = path.read_text().splitlines()
    relative = path.relative_to(root).as_posix()
    cases: list[TestCase] = []
    for index, line in enumerate(lines):
        if not JS_TEST_RE.match(line):
            continue
        cursor = index - 1
        while cursor >= 0 and not lines[cursor].strip():
            cursor -= 1
        motivation: str | None = None
        if cursor >= 0 and lines[cursor].strip().endswith("*/"):
            end = cursor
            while cursor >= 0 and "/**" not in lines[cursor]:
                cursor -= 1
            if cursor >= 0:
                motivation = "\n".join(lines[cursor : end + 1]).strip()
        identity = f"{relative}::line-{index + 1}"
        cases.append(
            TestCase(
                identity,
                _digest(line.strip()),
                motivation,
                tuple(dict.fromkeys(CITATION_RE.findall(motivation or ""))),
            )
        )
    return cases


def scan(root: Path) -> list[TestCase]:
    cases: list[TestCase] = []
    tests = root / "tests"
    if tests.exists():
        for path in sorted(tests.rglob("test_*.py")):
            cases.extend(_python_cases(path, root))
    web_tests = root / "web" / "tests"
    if web_tests.exists():
        for path in sorted(web_tests.rglob("*.mjs")):
            cases.extend(_js_cases(path, root))
        for path in sorted(web_tests.rglob("*.js")):
            cases.extend(_js_cases(path, root))
    return cases


def _load_baseline(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if data.get("version") != 1 or not isinstance(data.get("tests"), dict):
        raise ValueError(f"unsupported baseline format: {path}")
    return {str(key): str(value) for key, value in data["tests"].items()}


def _write_baseline(path: Path, cases: list[TestCase]) -> None:
    tests = {case.identity: case.digest for case in cases if not case.compliant}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "tests": tests}, indent=2, sort_keys=True) + "\n")


def _catalog(spec_path: Path) -> list[str]:
    if not spec_path.exists():
        return []
    return list(
        dict.fromkeys(
            match.group("token")
            for line in spec_path.read_text().splitlines()
            if (match := SPEC_HEADING_RE.match(line))
        )
    )


def write_report(
    path: Path,
    cases: list[TestCase],
    baseline: dict[str, str],
    spec_path: Path,
) -> None:
    defenders: dict[str, list[str]] = defaultdict(list)
    for case in cases:
        if case.compliant:
            for citation in case.citations:
                statute = citation.removeprefix("SPEC ")
                defenders[statute].append(case.identity)
    catalog = _catalog(spec_path)
    current = {case.identity for case in cases}
    stale = sorted(set(baseline) - current)
    debt = [
        case for case in cases if not case.compliant and baseline.get(case.identity) == case.digest
    ]
    lines = [
        "# Law coverage",
        "",
        "Generated deterministically by `scripts/check_test_motivations.py`.",
        "",
        f"- Tests discovered: {len(cases)}",
        f"- Motivated tests: {sum(case.compliant for case in cases)}",
        f"- Grandfathered baseline debt: {len(debt)}",
        f"- Stale baseline entries: {len(stale)}",
        "",
        "## SPEC and ADR defenders",
        "",
    ]
    for statute in catalog:
        tests = sorted(defenders.get(statute, []))
        heading = (
            f"### {statute} — {len(tests)} defender(s)"
            if tests
            else f"### {statute} — ZERO DEFENDERS"
        )
        lines.append(heading)
        lines.append("")
        lines.extend(f"- `{identity}`" for identity in tests)
        if not tests:
            lines.append("- _None._")
        lines.append("")
    other = sorted(key for key in defenders if key not in set(catalog))
    lines.extend(["## Other referenced statutes", ""])
    if other:
        for statute in other:
            lines.append(f"### {statute}")
            lines.append("")
            lines.extend(f"- `{identity}`" for identity in sorted(defenders[statute]))
            lines.append("")
    else:
        lines.extend(["_None._", ""])
    lines.extend(["## Baseline debt", ""])
    lines.extend(f"- `{case.identity}`" for case in debt)
    if not debt:
        lines.append("_None._")
    lines.extend(["", "## Stale baseline entries", ""])
    lines.extend(f"- `{identity}`" for identity in stale)
    if not stale:
        lines.append("_None._")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    baseline_path = args.baseline or root / "tests" / "test_motivation_baseline.json"
    cases = scan(root)
    if args.write_baseline:
        _write_baseline(baseline_path, cases)
    baseline = _load_baseline(baseline_path)
    if args.report:
        report_path = args.report if args.report.is_absolute() else root / args.report
        write_report(report_path, cases, baseline, root / "docs" / "SPEC.md")
    failures = [
        case for case in cases if not case.compliant and baseline.get(case.identity) != case.digest
    ]
    if failures:
        print("test motivation check failed:", file=sys.stderr)
        for case in failures:
            print(f"  {case.identity}: add a motivation docstring with a citation", file=sys.stderr)
        return 1
    debt = sum(not case.compliant for case in cases)
    print(f"test motivation check passed: {len(cases)} tests, {debt} grandfathered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
