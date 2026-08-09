from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path


def _checker():
    path = Path(__file__).parents[1] / "scripts" / "check_test_motivations.py"
    spec = importlib.util.spec_from_file_location("check_test_motivations", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_syntax_digest_turns_a_modified_grandfathered_test_into_a_failure(tmp_path: Path) -> None:
    """A-040 makes the baseline a syntax ratchet.

    Editing an old test must not preserve its exemption.
    """
    module = _checker()
    tests = tmp_path / "tests"
    tests.mkdir()
    target = tests / "test_old.py"
    target.write_text("def test_old():\n    assert True\n")
    original = module.scan(tmp_path)[0]
    target.write_text("def test_old():\n    assert 1 == 1\n")
    modified = module.scan(tmp_path)[0]
    assert original.identity == modified.identity
    assert original.digest != modified.digest


def test_report_separates_normative_coverage_from_contextual_mentions(tmp_path: Path) -> None:
    """SPEC B.6 rule 12 requires heading coverage to exclude contextual references."""
    module = _checker()
    tests = tmp_path / "tests"
    docs = tmp_path / "docs"
    tests.mkdir()
    docs.mkdir()
    (tests / "test_law.py").write_text(
        'def test_context():\n    """SPEC C.1 explains context."""\n    assert True\n\n'
        'def test_law():\n    """SPEC C.2 prevents drift."""\n    assert True\n'
    )
    spec_path = docs / "SPEC.md"
    spec_path.write_text("## C.1 Context\n## C.2 DDL\n## C.4 API\n")
    classifications = {
        "C.1": module.HeadingClassification(module.REFERENCE_ONLY, "context only"),
        "C.2": module.HeadingClassification(module.CONTRACT, "DDL contract"),
        "C.4": module.HeadingClassification(module.CONTRACT, "API contract"),
    }
    report = tmp_path / "verification" / "law-coverage.md"
    module.write_report(
        report,
        module.scan(tmp_path),
        {},
        spec_path,
        classifications=classifications,
    )
    rendered = report.read_text()
    assert "- Catalog headings: 3" in rendered
    assert "- Catalog headings referenced: 2" in rendered
    assert "- Normative-bearing headings: 2" in rendered
    assert "- Normative-bearing heading coverage: 1 / 2" in rendered
    assert "- Zero-defender normative-bearing headings: 1" in rendered
    assert "- Unique test-to-statute mention links: 2" in rendered
    assert "Coverage is heading-level only; this report does not claim clause coverage." in rendered
    assert "### C.2 — CONTRACT — 1 defender(s)" in rendered
    assert "### C.4 — CONTRACT — ZERO DEFENDERS" in rendered
    assert "### C.1 — REFERENCE_ONLY — 1 reference(s)" in rendered

    stale_registry = dict(classifications)
    stale_registry["D.4"] = module.HeadingClassification(
        module.REFERENCE_ONLY, "not in the synthetic SPEC"
    )
    try:
        module.write_report(
            report,
            module.scan(tmp_path),
            {},
            spec_path,
            classifications=stale_registry,
        )
    except ValueError as exc:
        assert "stale registry headings: D.4" in str(exc)
    else:
        raise AssertionError("direct report generation must reject stale registry entries")


def test_normal_check_fails_closed_on_an_unknown_spec_heading(tmp_path: Path, capsys) -> None:
    """SPEC B.6 rule 12 requires new catalog headings to receive reviewed force."""
    module = _checker()
    docs = tmp_path / "docs"
    docs.mkdir()
    committed_spec = Path(__file__).parents[1] / "docs" / "SPEC.md"
    (docs / "SPEC.md").write_text(committed_spec.read_text() + "\n## C.99 Unreviewed\n")

    assert module.main(["--root", str(tmp_path)]) == 1
    error = capsys.readouterr().err
    assert "heading classification registry drift" in error
    assert "unknown headings: C.99" in error

    stale_spec = committed_spec.read_text().replace(
        "## D.4 Parked ideas", "## Appendix D.4 Parked ideas", 1
    )
    (docs / "SPEC.md").write_text(stale_spec)
    assert module.main(["--root", str(tmp_path)]) == 1
    error = capsys.readouterr().err
    assert "stale registry headings: D.4" in error


def test_committed_heading_registry_is_exhaustive_and_preserves_boundaries() -> None:
    """SPEC B.6 rule 12 requires the normative denominator to be reviewed and complete."""
    module = _checker()
    root = Path(__file__).parents[1]
    catalog = module._catalog(root / "docs" / "SPEC.md")
    registry = module._validated_classifications(catalog)

    assert len(catalog) == 53
    assert set(catalog) == set(registry)
    assert Counter(item.classification for item in registry.values()) == {
        module.CONTRACT: 15,
        module.RULE: 16,
        module.MIXED_GUARDRAIL: 9,
        module.REFERENCE_ONLY: 13,
    }
    assert registry["D.2"].classification == module.REFERENCE_ONLY
    assert registry["D.4"].classification == module.REFERENCE_ONLY
    assert registry["ADR-006"].classification == module.REFERENCE_ONLY
    assert registry["ADR-011"].classification == module.MIXED_GUARDRAIL
    assert registry["ADR-020"].classification == module.MIXED_GUARDRAIL
    assert registry["C.2"].classification == module.CONTRACT

    invalid_registry = dict(registry)
    invalid_registry["C.2"] = module.HeadingClassification("NARRATIVE", "bad value")
    try:
        module._validated_classifications(catalog, invalid_registry)
    except ValueError as exc:
        assert "invalid classifications: C.2=NARRATIVE" in str(exc)
    else:
        raise AssertionError("an unknown classification value must fail closed")


def test_report_generation_is_byte_deterministic(tmp_path: Path) -> None:
    """SPEC B.6 rule 12 requires the inverse index to be reproducible from one ground."""
    module = _checker()
    root = Path(__file__).parents[1]
    cases = module.scan(root)
    baseline = module._load_baseline(root / "tests" / "test_motivation_baseline.json")
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"

    module.write_report(first, cases, baseline, root / "docs" / "SPEC.md")
    module.write_report(second, cases, baseline, root / "docs" / "SPEC.md")

    assert first.read_bytes() == second.read_bytes()
