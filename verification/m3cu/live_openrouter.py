"""One redacted real-provider proof for the M3CU judgment-only seam."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from spine.curation.contracts import HealthFinding, PalaceHealthReport
from spine.curation.provider import OpenRouterCuratorProvider
from spine.ids import mint_ulid


class RecordingSpend:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def append(self, events: list[Any]) -> None:
        self.events.extend(events)


async def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is required")
    first = UUID("00000000-0000-0000-0000-000000000101")
    second = UUID("00000000-0000-0000-0000-000000000102")
    finding = HealthFinding(
        ordinal=0,
        kind="duplicate",
        memory_ids=[first, second],
        evidence={
            "cosine": "0.900000000",
            "memories": [
                {
                    "memory_id": str(first),
                    "revision": 1,
                    "label": "Archive closing time",
                    "body": "The archive closes at nine.",
                    "kind": "fact",
                    "keywords": ["archive", "hours"],
                },
                {
                    "memory_id": str(second),
                    "revision": 1,
                    "label": "Archive hours",
                    "body": "Archive closing time is nine.",
                    "kind": "fact",
                    "keywords": ["archive", "closing"],
                },
            ],
        },
        fingerprint="0" * 64,
    )
    report = PalaceHealthReport(
        principal_id="m3cu-fixture-owner",
        as_of=datetime(2026, 8, 31, 12, tzinfo=UTC),
        corpus_revision="1" * 64,
        active_units=2,
        clusters=[[first, second]],
        findings=[finding],
        keyword_coverage_percent="100.000",
        stats_delta={"revisions": 2, "reinforcements": 0, "merges": 0, "retirements": 0},
    )
    spend = RecordingSpend()
    provider = OpenRouterCuratorProvider(
        api_key=key,
        model=os.environ.get("CHAT_MODEL", "openrouter:minimax/minimax-m3"),
        spend_service=spend,  # type: ignore[arg-type]
    )
    try:
        verdict = await provider.verdict(
            finding,
            report,
            run_uid=mint_ulid(),
            machine_id="m3cu-live-proof",
        )
    finally:
        await provider.aclose()
    receipt = spend.events[0]
    print(
        json.dumps(
            {
                "action": verdict.action,
                "rationale_chars": len(verdict.rationale),
                "provider": receipt.provider,
                "purpose": receipt.purpose,
                "model": receipt.model,
                "basis": receipt.basis,
                "request_ref_present": bool(receipt.ref),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
