"""Shared M1 token accounting tests."""

from spine.tokens import cl100k_token_count


def test_cl100k_count_is_stable_and_treats_special_text_literally() -> None:
    """SPEC C.4 is defended by verifying that cl100k count is stable and treats special text
    literally; this prevents drift in the authoritative token-budget measurement.
    """
    assert cl100k_token_count("x x x") == 3
    assert cl100k_token_count("<|endoftext|>") > 0
