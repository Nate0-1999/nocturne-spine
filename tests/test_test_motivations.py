from __future__ import annotations

import importlib.util
import sys
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


def test_report_indexes_citations_and_marks_uncovered_law(tmp_path: Path) -> None:
    """SPEC B.6 requires the inverse index to expose defenders and zero-defender sections."""
    module = _checker()
    tests = tmp_path / "tests"
    docs = tmp_path / "docs"
    tests.mkdir()
    docs.mkdir()
    (tests / "test_law.py").write_text(
        'def test_law():\n    """SPEC C.1 prevents silent drift."""\n    assert True\n'
    )
    spec_path = docs / "SPEC.md"
    spec_path.write_text("## C.1 First law\n## C.2 Second law\n")
    report = tmp_path / "verification" / "law-coverage.md"
    module.write_report(report, module.scan(tmp_path), {}, spec_path)
    rendered = report.read_text()
    assert "### C.1 — 1 defender(s)" in rendered
    assert "### C.2 — ZERO DEFENDERS" in rendered
