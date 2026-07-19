"""Shared identifier minting helpers."""

from __future__ import annotations

import secrets
import time

_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def mint_ulid() -> str:
    """Mint a canonical 26-character ULID from 48 time and 80 random bits."""

    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    value = (timestamp_ms << 80) | secrets.randbits(80)
    encoded = ["0"] * 26
    for index in range(25, -1, -1):
        encoded[index] = _ULID_ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(encoded)


__all__ = ["mint_ulid"]
