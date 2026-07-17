# Decision Journal

This journal is append-only. Every entry cites the deepest applicable Problem
Tree node from `docs/SPEC.md` §2.

## 000 — Relay law

**Problem Tree:** P4

Read docs/SPEC.md 1 -> 2 -> B -> C before touching dirt. Every entry in this
journal cites a Problem Tree node. Local defects follow the Blight Protocol
(SPEC 2.1). Features that cannot name their problem do not get built.

## 001 — Bootstrap tooling and operational boundaries

**Problem Tree:** P4

**Decision.** Package the Python 3.12 `src/` layout with Hatchling and a uv
lockfile; use Ruff for linting and pytest with testcontainers for verification. The local
container boundary is `spine:8000` to `pgvector/pgvector:pg16:5432`; Compose
runs Alembic before Uvicorn so a cold start establishes the authoritative C.2
schema. Tests use a disposable pgvector Postgres and the same Alembic path.
Generate and commit `openapi.json` from the app factory.

**Motivation.** These are small, conventional, replaceable choices that make
the two promised checks—lint and tests—reproducible while keeping persistence
behind its wire and preserving a fresh-clone path.

**Rejected alternatives.** A host-installed Postgres would make tests depend
on hidden machine state. A synchronous database driver would create a second
runtime path beside the C.1 async stack. Adding an ORM, repository helpers, or
future feature scaffolds now would cross P0's zero-business-logic boundary.

**Literal-contract note.** C.2 describes an active-label partial unique index
in a column comment but does not include that index in its authoritative DDL;
P0 does not add one. C.4 mentions retrying memory creation with `force=true`
but does not place `force` in the exact request body or route signature; P0
does not invent it. C.4 calls the memory list paged without defining paging
parameters or a response body, and its create/patch bodies do not supply the
`origin_machine_id` required for a C.2 revision row. P0 escalates these and
the related response-shape seams as Garden FLAGS F001–F005, without silently
changing a contract.

## 002 — Tracked M1 scope fence

**Problem Tree:** P4

**Decision.** Keep a repository-owned pre-commit hook that scans staged files
for the forbidden M1 feature families named by Garden Plan §7, and run the
same check over all tracked files in CI. Exclude the hook itself, frozen law,
decision/report Markdown, lockfiles, and verification artifacts from the
pattern scan; those files necessarily name forbidden concepts while defining
or evidencing the boundary.

**Motivation.** A local-only hook configuration disappears on clone. Tracking
the small POSIX script and repeating it in CI makes the scope boundary visible
and reproducible without adding a hook framework.

**Rejected alternatives.** A dependency-heavy pre-commit framework adds no
useful P0 capability. Scanning `docs/SPEC.md` or the hook's own pattern list
would make every run fail on the words that define the prohibition.
