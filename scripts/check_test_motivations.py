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

CONTRACT = "CONTRACT"
RULE = "RULE"
MIXED_GUARDRAIL = "MIXED_GUARDRAIL"
REFERENCE_ONLY = "REFERENCE_ONLY"
NORMATIVE_CLASSIFICATIONS = frozenset({CONTRACT, RULE, MIXED_GUARDRAIL})


@dataclass(frozen=True)
class HeadingClassification:
    classification: str
    basis: str

    @property
    def normative_bearing(self) -> bool:
        return self.classification in NORMATIVE_CLASSIFICATIONS


# This is intentionally reviewed, explicit policy rather than a prose-keyword
# inference. SPEC headings commonly mix motivation, rejected alternatives,
# future design, and operative rules; a MUST/NEVER grep would misclassify them.
HEADING_CLASSIFICATIONS: dict[str, HeadingClassification] = {
    "0": HeadingClassification(
        REFERENCE_ONLY, "SPEC 21-41 is vision not named by the 1.4 contract list."
    ),
    "1": HeadingClassification(REFERENCE_ONLY, "SPEC 45 is a container heading."),
    "1.0": HeadingClassification(
        MIXED_GUARDRAIL, "SPEC 47-89 is vocabulary plus one load-bearing naming law."
    ),
    "1.1": HeadingClassification(REFERENCE_ONLY, "SPEC 91-110 is descriptive topology."),
    "1.2": HeadingClassification(REFERENCE_ONLY, "SPEC 112-123 is a narrative prompt lifecycle."),
    "1.3": HeadingClassification(
        CONTRACT, "SPEC 1.4 lines 167-170 explicitly names the Invariants as a contract."
    ),
    "1.4": HeadingClassification(
        RULE, "SPEC 163-202 governs force classes, completions, and decision journaling."
    ),
    "2": HeadingClassification(
        REFERENCE_ONLY, "SPEC 206-298 is why-lineage; its must language states problems."
    ),
    "2.1": HeadingClassification(
        RULE, "SPEC 299-315 is the numbered Blight Protocol and record duty."
    ),
    "ADR-001": HeadingClassification(
        MIXED_GUARDRAIL, "SPEC 328-355 mixes architecture guidance with frozen boundaries."
    ),
    "ADR-010": HeadingClassification(
        RULE, "SPEC 383-394 explicitly declares placement and movement law."
    ),
    "ADR-002": HeadingClassification(
        REFERENCE_ONLY, "SPEC 428-458 delegates its exact normative bodies to C.4."
    ),
    "ADR-003": HeadingClassification(
        REFERENCE_ONLY, "SPEC 462-508 points each lifecycle stage to its owning law."
    ),
    "ADR-004": HeadingClassification(
        RULE, "SPEC 512-549 explicitly identifies the shipped unit and concurrency law."
    ),
    "ADR-005": HeadingClassification(
        MIXED_GUARDRAIL, "SPEC 553-694 mixes partial/open design with binding scorer rules."
    ),
    "ADR-011": HeadingClassification(
        MIXED_GUARDRAIL, "SPEC 696-733 is HORIZON design plus a current no-build guardrail."
    ),
    "ADR-007": HeadingClassification(
        REFERENCE_ONLY, "SPEC 739-756 is explicitly an index to owning law."
    ),
    "ADR-008": HeadingClassification(
        MIXED_GUARDRAIL, "SPEC 760-817 mixes accepted M1 constraints with later proposals."
    ),
    "ADR-012": HeadingClassification(
        CONTRACT, "SPEC 822-823 explicitly declares the work protocol a contract."
    ),
    "ADR-013": HeadingClassification(
        CONTRACT, "SPEC 889-890 explicitly declares the harness seam a contract."
    ),
    "ADR-014": HeadingClassification(
        CONTRACT, "SPEC 933-935 explicitly declares the milestone-scoped loop contract."
    ),
    "ADR-015": HeadingClassification(
        CONTRACT, "SPEC 970 explicitly declares the permission model a contract."
    ),
    "ADR-016": HeadingClassification(
        CONTRACT, "SPEC 1010 explicitly declares the session and journal contract."
    ),
    "ADR-017": HeadingClassification(
        CONTRACT, "SPEC 1068 explicitly declares the M3+ Symphony contract."
    ),
    "ADR-018": HeadingClassification(
        CONTRACT, "SPEC 1114-1117 declares the viz contract and separates guidance."
    ),
    "ADR-019": HeadingClassification(
        CONTRACT, "SPEC 1206 explicitly declares the packaging contract."
    ),
    "ADR-020": HeadingClassification(
        MIXED_GUARDRAIL, "SPEC 1318-1319 is HORIZON design plus a no-build guardrail."
    ),
    "ADR-021": HeadingClassification(
        RULE, "SPEC 1369-1531 is the accepted, operative Memory Write Law."
    ),
    "ADR-022": HeadingClassification(
        MIXED_GUARDRAIL, "SPEC 1535-1669 mixes accepted doctrine, rules, and proposed ops."
    ),
    "ADR-023": HeadingClassification(
        RULE, "SPEC 1674-1818 identifies owner law and action contracts."
    ),
    "ADR-024": HeadingClassification(
        MIXED_GUARDRAIL, "SPEC 1823-1919 mixes ledger rules with deferred and horizon design."
    ),
    "ADR-006": HeadingClassification(REFERENCE_ONLY, "SPEC 1923 marks the ADR PROPOSED."),
    "ADR-009": HeadingClassification(
        MIXED_GUARDRAIL, "SPEC 1936-2063 mixes accepted direction, rules, and proposed detail."
    ),
    "B.1": HeadingClassification(
        RULE, "SPEC 2057-2076 makes commitment tiers part of roadmap and scope law."
    ),
    "B.2": HeadingClassification(
        RULE, "SPEC 2057-2062 and 2078-2093 govern pillar and repository ownership."
    ),
    "B.3": HeadingClassification(RULE, "SPEC 2057-2062 and 2095-2137 govern what is built when."),
    "B.4": HeadingClassification(
        CONTRACT, "SPEC 1.4 lines 167-170 explicitly names the feature ledger a contract."
    ),
    "B.5": HeadingClassification(
        CONTRACT, "SPEC 1.4 lines 167-170 explicitly names anti-scope rules contracts."
    ),
    "B.6": HeadingClassification(
        RULE, "SPEC 2191 onward explicitly declares and numbers judge law."
    ),
    "C.1": HeadingClassification(
        RULE, "SPEC 2301-2305 makes Part C literal; 2307-2344 fixes repo boundaries."
    ),
    "C.2": HeadingClassification(
        CONTRACT, "SPEC 1.4 lines 167-170 explicitly names the DDL a contract."
    ),
    "C.3": HeadingClassification(RULE, "SPEC 2301-2305 and 2448-2496 make scorer rules literal."),
    "C.4": HeadingClassification(
        CONTRACT, "SPEC 1.4 lines 167-170 explicitly names API bodies contracts."
    ),
    "C.5": HeadingClassification(
        RULE, "SPEC 2301-2305 and 2680-2698 make defaults literal and single-source."
    ),
    "C.6": HeadingClassification(
        RULE, "SPEC 2301-2305 and 2700-2787 make the exact capability flow literal."
    ),
    "C.7": HeadingClassification(
        CONTRACT, "SPEC 1.4 lines 167-170 explicitly names the WS envelope a contract."
    ),
    "C.8": HeadingClassification(
        CONTRACT, "SPEC 1.4 lines 167-170 explicitly names acceptance criteria contracts."
    ),
    "C.9": HeadingClassification(
        RULE, "SPEC 2951-3008 is the concrete protocol expanding B.6 judge law."
    ),
    "C.10": HeadingClassification(
        RULE, "SPEC 3010-3066 is an accepted verbatim charge with tasks and exit criteria."
    ),
    "D.1": HeadingClassification(REFERENCE_ONLY, "SPEC 3074 marks these questions OPEN."),
    "D.2": HeadingClassification(
        REFERENCE_ONLY,
        "SPEC 3089-3198 mixes accepted and proposed history under one unscoped token.",
    ),
    "D.3": HeadingClassification(
        REFERENCE_ONLY, "SPEC 3199-3210 is a routing index to owning sections."
    ),
    "D.4": HeadingClassification(
        REFERENCE_ONLY, "A-040 lines 1546-1549 says no normative test law lives in D.4."
    ),
}


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


def _validated_classifications(
    catalog: list[str],
    classifications: dict[str, HeadingClassification] | None = None,
) -> dict[str, HeadingClassification]:
    registry = classifications or HEADING_CLASSIFICATIONS
    catalog_tokens = set(catalog)
    unknown = sorted(catalog_tokens - set(registry))
    stale = sorted(set(registry) - catalog_tokens)
    valid_classifications = {
        CONTRACT,
        RULE,
        MIXED_GUARDRAIL,
        REFERENCE_ONLY,
    }
    invalid = sorted(
        f"{token}={entry.classification}"
        for token, entry in registry.items()
        if entry.classification not in valid_classifications
    )
    if unknown or stale or invalid:
        details = []
        if unknown:
            details.append(f"unknown headings: {', '.join(unknown)}")
        if stale:
            details.append(f"stale registry headings: {', '.join(stale)}")
        if invalid:
            details.append(f"invalid classifications: {', '.join(invalid)}")
        raise ValueError("heading classification registry drift; " + "; ".join(details))
    return registry


def write_report(
    path: Path,
    cases: list[TestCase],
    baseline: dict[str, str],
    spec_path: Path,
    classifications: dict[str, HeadingClassification] | None = None,
) -> None:
    defenders: dict[str, list[str]] = defaultdict(list)
    for case in cases:
        if case.compliant:
            for citation in case.citations:
                statute = citation.removeprefix("SPEC ")
                defenders[statute].append(case.identity)
    catalog = _catalog(spec_path)
    registry = _validated_classifications(catalog, classifications)
    mention_links = {
        (case.identity, citation.removeprefix("SPEC "))
        for case in cases
        if case.compliant
        for citation in case.citations
    }
    referenced_catalog = {statute for statute in catalog if defenders.get(statute)}
    normative_catalog = [statute for statute in catalog if registry[statute].normative_bearing]
    covered_normative = [statute for statute in normative_catalog if defenders.get(statute)]
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
        f"- Catalog headings: {len(catalog)}",
        f"- Catalog headings referenced: {len(referenced_catalog)}",
        f"- Normative-bearing headings: {len(normative_catalog)}",
        (
            f"- Normative-bearing heading coverage: {len(covered_normative)} / "
            f"{len(normative_catalog)}"
        ),
        (
            "- Zero-defender normative-bearing headings: "
            f"{len(normative_catalog) - len(covered_normative)}"
        ),
        f"- Unique test-to-statute mention links: {len(mention_links)}",
        "",
        "Coverage is heading-level only; this report does not claim clause coverage.",
        "",
        "## Normative-bearing heading coverage",
        "",
    ]
    for statute in normative_catalog:
        tests = sorted(defenders.get(statute, []))
        classification = registry[statute]
        heading = (
            f"### {statute} — {classification.classification} — {len(tests)} defender(s)"
            if tests
            else f"### {statute} — {classification.classification} — ZERO DEFENDERS"
        )
        lines.append(heading)
        lines.append("")
        lines.append(f"- Classification basis: {classification.basis}")
        lines.extend(f"- `{identity}`" for identity in tests)
        if not tests:
            lines.append("- _None._")
        lines.append("")
    reference_catalog = [statute for statute in catalog if not registry[statute].normative_bearing]
    lines.extend(["## Contextual and reference-only catalog mentions", ""])
    for statute in reference_catalog:
        tests = sorted(defenders.get(statute, []))
        classification = registry[statute]
        heading = (
            f"### {statute} — {classification.classification} — {len(tests)} reference(s)"
            if tests
            else f"### {statute} — {classification.classification} — ZERO REFERENCES"
        )
        lines.append(heading)
        lines.append("")
        lines.append(f"- Classification basis: {classification.basis}")
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
    spec_path = root / "docs" / "SPEC.md"
    try:
        _validated_classifications(_catalog(spec_path))
    except ValueError as exc:
        print(f"test motivation check failed: {exc}", file=sys.stderr)
        return 1
    cases = scan(root)
    if args.write_baseline:
        _write_baseline(baseline_path, cases)
    baseline = _load_baseline(baseline_path)
    if args.report:
        report_path = args.report if args.report.is_absolute() else root / args.report
        write_report(report_path, cases, baseline, spec_path)
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
