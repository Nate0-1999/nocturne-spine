"""Generate the committed OpenAPI artifact from the app factory."""

import argparse
import json
from pathlib import Path

from spine.api_contract import (
    API_CONTRACT_VERSION,
    openapi_contract_fingerprint,
    require_known_contract_fingerprint,
)
from spine.config import Settings
from spine.main import create_app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--record-api-contract",
        action="store_true",
        help="append the fingerprint for a deliberately bumped API_CONTRACT_VERSION",
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    fingerprints_path = root / "api_contract_fingerprints.json"
    settings = Settings(
        database_url="postgresql+asyncpg://spine:spine@localhost:5432/spine",
        token="openapi-generation-only",
    )
    openapi = create_app(settings).openapi()
    fingerprint = openapi_contract_fingerprint(openapi)
    fingerprints = (
        json.loads(fingerprints_path.read_text(encoding="utf-8"))
        if fingerprints_path.exists()
        else {}
    )
    recorded = fingerprints.get(API_CONTRACT_VERSION)
    if recorded is None:
        if not args.record_api_contract:
            raise SystemExit(
                f"api_contract_version {API_CONTRACT_VERSION!r} has no recorded fingerprint; "
                "after a deliberate version bump, rerun with --record-api-contract"
            )
        fingerprints[API_CONTRACT_VERSION] = fingerprint
        fingerprints_path.write_text(
            json.dumps(fingerprints, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        require_known_contract_fingerprint(openapi, fingerprints)
    rendered = json.dumps(openapi, indent=2, sort_keys=True) + "\n"
    (root / "openapi.json").write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
