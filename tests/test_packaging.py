"""Artifact metadata and allowlisted deploy-resource proofs."""

from __future__ import annotations

import shutil
from importlib.metadata import version
from pathlib import Path

import pytest

from spine import __version__, deploy_resources

ROOT = Path(__file__).resolve().parents[1]
D2_FILES = {
    "README.md",
    "billing_breaker.py",
    "deploy.sh",
    "deployment_checks.py",
    "main.py",
    "requirements.txt",
}


@pytest.fixture
def packaged_spine_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    package_root = tmp_path / "installed" / "spine"
    shutil.copytree(ROOT / "src" / "spine", package_root)

    deploy_root = package_root / "_deploy"
    d2_root = deploy_root / "billing-breaker"
    d2_root.mkdir(parents=True)
    shutil.copy2(ROOT / "pyproject.toml", deploy_root / "pyproject.toml")
    shutil.copy2(ROOT / "Dockerfile", deploy_root / "Dockerfile")
    for filename in D2_FILES:
        shutil.copy2(ROOT / "infra" / "billing-breaker" / filename, d2_root / filename)

    monkeypatch.setattr(deploy_resources, "files", lambda package: package_root)
    return package_root


def test_distribution_metadata_uses_the_package_version() -> None:
    assert version("nocturne-spine") == __version__ == "0.1.0"


def test_container_base_is_an_exact_multiarch_python_release() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith(
        "FROM python:3.12.13-slim@sha256:"
        "57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS base\n"
    )
    assert "FROM python:3.12-slim" not in dockerfile


def test_materialize_app_source_is_an_allowlisted_rebuildable_context(
    tmp_path: Path,
    packaged_spine_resources: Path,
) -> None:
    destination = deploy_resources.materialize_app_source(tmp_path / "app-source")

    assert {path.name for path in destination.iterdir()} == {
        "Dockerfile",
        "infra",
        "pyproject.toml",
        "src",
    }
    assert not (destination / "src" / "spine" / "_deploy").exists()
    assert (destination / "src" / "spine" / "main.py").read_bytes() == (
        ROOT / "src" / "spine" / "main.py"
    ).read_bytes()
    assert {path.name for path in (destination / "infra" / "billing-breaker").iterdir()} == D2_FILES


def test_materialize_billing_breaker_preserves_human_deploy_path(
    tmp_path: Path,
    packaged_spine_resources: Path,
) -> None:
    destination = deploy_resources.materialize_billing_breaker_source(tmp_path / "d2-source")

    assert {path.name for path in destination.iterdir()} == D2_FILES
    assert (destination / "deploy.sh").stat().st_mode & 0o111 == 0o111


def test_materializers_refuse_nonempty_destinations(
    tmp_path: Path,
    packaged_spine_resources: Path,
) -> None:
    destination = tmp_path / "occupied"
    destination.mkdir()
    (destination / "keep.txt").write_text("owned by caller", encoding="utf-8")

    with pytest.raises(FileExistsError, match="not empty"):
        deploy_resources.materialize_app_source(destination)
