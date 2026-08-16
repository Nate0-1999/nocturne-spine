# M3B golden-behavior statute

These tests are the zero-regression boundary for the M3 seam refactor.

- Fixed inputs must keep producing the exact checked-in outputs.
- Refactor waves must finish with this directory green and unmodified.
- Do not update a golden to make a refactor pass. A changed golden requires a
  separately authorized behavior change and new owner-visible evidence.
- The ordinary test suite remains independently authoritative; this directory
  pins the cross-seam behavior that a rearrangement could accidentally change.

Run with:

```text
uv run --locked pytest -q tests/golden
```
