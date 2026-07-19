"""Shared token accounting for enacted M1 memory limits and budgets."""

from functools import cache

import tiktoken


def cl100k_token_count(value: str) -> int:
    """Count text with the M1 tokenizer while treating special text literally."""

    return len(_cl100k_encoding().encode(value, disallowed_special=()))


@cache
def _cl100k_encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


__all__ = ["cl100k_token_count"]
