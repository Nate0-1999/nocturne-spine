"""Shared identifier helper tests."""

import re

from spine.ids import mint_ulid

_CANONICAL_ULID = re.compile(r"[0-7][0-9A-HJKMNP-TV-Z]{25}\Z")


def test_mint_ulid_returns_distinct_canonical_values() -> None:
    values = {mint_ulid() for _ in range(32)}

    assert len(values) == 32
    assert all(_CANONICAL_ULID.fullmatch(value) for value in values)
