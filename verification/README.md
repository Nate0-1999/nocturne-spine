# Verification

Bootstrap evidence lives in `bootstrap/`. Milestone verdict artifacts belong
under `verification/<milestone>/` and are produced by an independent judge.

## SPEC B.6 (verbatim)

```text
## B.6 Verification doctrine (judge law)

A milestone is DONE when a judge agent, acting as the user, experiences every
acceptance criterion — never merely when code exists or unit tests pass.

1. **Three evidence classes, all mandatory, per criterion:**
   - **Experiential:** drive the real UI as a user (browser automation or
     manual): real clicks, real prompts, screenshots at every meaningful
     state. If it can't be screenshotted being used, it isn't done.
   - **Traced:** follow the SAME action through the internals — log lines,
     DB rows, API payloads — and prove they agree with the surface (e.g. the
     injection_id visible in the gate maps to injection_event rows whose
     features/outcomes match what the screenshot shows).
   - **Adversarial:** deliberately trigger the failure paths named by the
     criterion (kill dependencies, force 409s, go offline) and verify the
     specified degradation, not a crash.
2. **Separation of powers:** the judge is a distinct agent from the builders
   of the loop it judges (no self-certification). Judges do not fix — a FAIL
   returns to the builders with the verdict; the Blight Protocol governs the
   fix.
3. **Verdict artifacts:** screenshots, log excerpts, and SQL outputs are
   committed under `verification/<milestone>/` ; the verdict file lists each
   criterion → PASS/FAIL → evidence paths → tree node. Any FAIL = milestone
   not done.
4. **Scope audit is judgeable:** the judge greps for FORBIDDEN-feature code
   (B.4) and verifies every DECISIONS.md entry cites a tree node. Scope
   violations are automatic FAILs regardless of functionality.
5. **Responsive law is judged:** experiential passes are repeated at a phone
   viewport (390×844) for all user-facing criteria.
6. Each milestone's concrete checklist is authored at milestone planning
   time from this doctrine (M1's is C.9).
```
