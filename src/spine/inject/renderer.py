"""Canonical C.6 renderer for frozen injection-event memory cards."""

from collections.abc import Mapping, Sequence
from typing import Any

_OPEN = "<memory_system>"
_PREAMBLE = (
    "The following long-term memories were retrieved for this conversation.",
    "Treat them as your own accumulated knowledge; they may be imperfect.",
)
_CLOSE = "</memory_system>"


class FrozenMemoryPayloadError(ValueError):
    """An event does not contain the frozen A-008 card needed for rendering."""


def render_final_block(events: Sequence[Mapping[str, Any]]) -> str:
    """Render final members in stable rank order using only frozen event data."""

    lines = [_OPEN, *_PREAMBLE]
    for event in sorted(events, key=_event_order):
        frozen = _frozen_memory(event)
        kind = event.get("memory_kind")
        if not isinstance(kind, str):
            raise FrozenMemoryPayloadError("event memory_kind must be a string")
        lines.extend(
            (
                (
                    f'<memory label="{_escape_attribute(frozen["label"])}" '
                    f'kind="{_escape_attribute(kind)}" '
                    f'updated="{_escape_attribute(frozen["updated_at"])}">'
                ),
                _escape_body(frozen["body"]),
                "</memory>",
            )
        )
    lines.append(_CLOSE)
    return "\n".join(lines)


def _event_order(event: Mapping[str, Any]) -> tuple[int, str]:
    rank = event.get("rank")
    if isinstance(rank, bool) or not isinstance(rank, int):
        raise FrozenMemoryPayloadError("event rank must be an integer")
    memory_id = event.get("memory_id")
    if memory_id is None:
        raise FrozenMemoryPayloadError("event memory_id is required")
    return rank, str(memory_id)


def _frozen_memory(event: Mapping[str, Any]) -> dict[str, str]:
    features = event.get("features")
    if not isinstance(features, Mapping):
        raise FrozenMemoryPayloadError("event features must be an object")
    frozen = features.get("_memory")
    if not isinstance(frozen, Mapping):
        raise FrozenMemoryPayloadError("event features._memory must be an object")
    values: dict[str, str] = {}
    for name in ("label", "body", "updated_at"):
        value = frozen.get(name)
        if not isinstance(value, str):
            raise FrozenMemoryPayloadError(f"event features._memory.{name} must be a string")
        values[name] = value
    return values


def _escape_attribute(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\t", "&#9;")
        .replace("\n", "&#10;")
        .replace("\r", "&#13;")
    )


def _escape_body(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


__all__ = ["FrozenMemoryPayloadError", "render_final_block"]
