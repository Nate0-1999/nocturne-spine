"""Generate the committed OpenAPI artifact from the app factory."""

import json
from pathlib import Path

from spine.config import Settings
from spine.main import create_app


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    settings = Settings(
        database_url="postgresql+asyncpg://spine:spine@localhost:5432/spine",
        token="openapi-generation-only",
    )
    rendered = json.dumps(create_app(settings).openapi(), indent=2, sort_keys=True) + "\n"
    (root / "openapi.json").write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
