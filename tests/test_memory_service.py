"""Pure boundary checks for S2 memory-domain decisions."""

import pytest

from spine.memory.service import _classify_dedup_score


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (None, "distinct"),
        (0.799999, "distinct"),
        (0.80, "similar"),
        (0.919999, "similar"),
        (0.92, "duplicate"),
        (1.0, "duplicate"),
    ],
)
def test_dedup_boundaries_are_inclusive_exactly_where_enacted(
    score: float | None,
    expected: str,
) -> None:
    """SPEC C.4 is defended by verifying that dedup boundaries are inclusive exactly where
    enacted; this prevents drift in the memory deduplication contract.
    """
    assert _classify_dedup_score(score, dedup_sim=0.80, dedup_dup=0.92) == expected
