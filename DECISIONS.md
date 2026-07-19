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

## 003 — Typed v1.5 stub contract without premature behavior

**Problem Tree:** P1.1

**Decision.** Hand-mirror the v1.5 C.4 success and alternate response bodies
as strict Pydantic models and expose them in the committed OpenAPI document,
while each P0 route continues to return its explicit named RFC 7807 `501`.
Keep the shared `MemoryCard` and `MemoryUnit` shapes in one contract module so
the injection and memory routers cannot drift within this repository.

**Motivation.** The human-gate amendment makes the cross-repository wire
contract exact enough to freeze now. Publishing the success and conflict
schemas gives Harness a complete artifact to mirror without stealing S1–S4's
business behavior from their packets.

**Rejected alternatives.** Leaving successful responses absent from OpenAPI
would preserve the v1.4 ambiguity after the constitution resolved it. Returning
dummy success values would make P0 appear to implement memory behavior and
would cross the packet boundary.

## 004 — One CAS writer and a detached conflict boundary

**Problem Tree:** P1.3

**Decision.** Enact Garden A-001 through one allowlisted C.2 write path:
`cas_update_memory_unit` performs a conditional head update, derives the prior
cloud-head revision as its parent, and appends the resulting revision inside
an internal savepoint within the caller-owned transaction, so even a caught
lineage error cannot commit a head/history split. `tombstone_memory_unit` is
only a status-specific wrapper over that path. The caller supplies the
client-mintable `rev_uid`, whose canonical ULID syntax is validated; the helper
neither generates IDs nor commits. Callers write a given memory at most once
per outer transaction, keeping a conflict snapshot tied to a committed prior
head. A stale write raises a typed `MemoryCasConflictError` carrying a detached
current-head snapshot and explicit 409 semantics; S2 remains responsible for
translating it at the HTTP boundary.

**Motivation.** A single conditional `UPDATE ... RETURNING` holds the memory
row through the revision insert, so a loser cannot overwrite a winner and any
history failure rolls the head change back. Deriving `parent_uid` from the
expected cloud-head revision prevents ordinary online writes from attaching to
an arbitrary memory lineage. A detached snapshot remains readable after the
caller's rollback and is exactly what the later 409 response needs.

**Rejected alternatives.** Committing inside the helper would make the head
and surrounding service work impossible to compose atomically. A read-then-
write CAS is race-prone. Accepting arbitrary update dictionaries would expose
identity, ownership, counters, and timestamps to accidental mutation. Wiring
PATCH now would steal S2. A server-side ULID generator or new ULID dependency
would duplicate the client-mintable boundary for no S1 benefit.

## 005 — One injected embedding boundary, with a real production adapter

**Problem Tree:** P1.1

**Decision.** Implement C.1's embedding seam as an async provider protocol with
an OpenAI HTTP adapter and explicit model/dimension metadata. The production app
uses `text-embedding-3-small` at the authoritative 1536 dimensions, obtains its
key from `SPINE_OPENAI_API_KEY`, and returns a service-availability problem when
the provider cannot run; deterministic vectors exist only as injected tests.
The adapter validates response cardinality, index order, finite non-zero-norm
numeric values, and exact vector width before any database write. App
construction accepts the provider and SQLAlchemy session factory explicitly so
tests exercise the real HTTP/service/database stack without global monkeypatches.

**Motivation.** Provider validation keeps malformed or cross-model vectors out
of the fixed `vector(1536)` column. Injection satisfies the provider-pluggable
contract while retaining a real runtime path and deterministic verification.

**Rejected alternatives.** A deterministic fake as the runtime fallback would
make successful-looking writes semantically false. Adding the OpenAI SDK would
duplicate the already-required `httpx` boundary for one stable endpoint. Making
the fixed storage dimension environment-variable-dependent would let config and
the authoritative DDL disagree.

## 006 — Serializable create dedup and one memory service transaction boundary

**Problem Tree:** P1.4, P1.1

**Decision.** Enact Garden A-002 through A-006 in one memory service. Creation
does the required active-label preflight before embedding, then takes a
transaction-scoped PostgreSQL advisory lock derived from the principal and
rechecks label/dedup before atomically inserting the head and its root revision.
This serializes competing creates for one principal without blocking unrelated
principals. The server mints canonical ULIDs because C.4 exposes no revision ID
field; PATCH still routes through S1's sole CAS writer. Partial-index races are
translated by constraint name into the exact label-conflict body, while provider
and generic failures remain RFC7807 problems. Use the maintained `tiktoken`
implementation of A-006's `cl100k_base` rule instead of a word-count
approximation; load it only when a mutation needs body validation so health and
read-only routes do not depend on tokenizer setup.

**Motivation.** Without a principal-scoped transaction lock, concurrent requests
with different labels but duplicate bodies can both pass the cosine check and
create the hard duplicate that C.4 forbids. Keeping each head/history mutation
in one caller-owned transaction preserves C.2 lineage and rollback semantics.

**Rejected alternatives.** A process-local lock would fail across workers. A
table lock would serialize unrelated principals. Relying only on the active-label
unique index protects labels but not semantic duplicates. Retrying an integrity
error without rolling back its savepoint would leave the transaction unusable.

## 007 — Pure scorer core with a versioned database boundary

**Problem Tree:** P1.2

**Decision.** Enact Garden A-007 as a pure scorer that accepts detached
candidates, an immutable typed `scorer_config`, and an explicit snapshot clock,
then returns scored/ranked selections without database or HTTP access. Load
exactly one active `scorer_config` row for each prepare and persist that row's
version on every event. Keep vector-pool ordering in PostgreSQL for production,
while reapplying the same cosine/UUID boundary in the pure function so its golden
fixtures independently exercise the complete algorithm. Use `cl100k_base` for
the body budget through the same lazy tokenizer family as memory validation.
Order the vector pool by raw cosine and clamp only the semantic feature; quantize
the aggregate score once to C.2's PostgreSQL `REAL` width before threshold,
ordering, response, and persistence so no hidden precision changes a decision.

**Motivation.** A side-effect-free function makes all six feature calculations,
pin bypass, score ordering, inclusive threshold, greedy skipping, budget, and
near-miss behavior reproducible from hand calculations. Treating the active
versioned row as one indivisible input keeps event replay tied to the weights and
parameters that actually produced the score.

**Rejected alternatives.** Computing features inside SQL would make golden
tests mirror query machinery instead of the contract math. Reading weights from
the database but selection parameters from environment settings would permit one
reported scorer version to describe two different algorithms. A process-global
mutable scorer would weaken replay and make concurrent config activation opaque.

## 008 — One-shot frozen prepare with replayable card events

**Problem Tree:** P1.2, P1.3

**Decision.** Enact Garden A-008 by embedding before the database phase, then
perform thread stamping, repeatable-read candidate selection, event insertion,
and injected-only statistic writes in one transaction. Reject a second M1
prepare for the thread instead of pretending C.2's partial revision rows can
reconstruct historical vectors. Preserve each returned card's label/body/pin/
updated-at snapshot under the event feature payload's enacted `_memory` key so
S4 can render and J6 can replay the original gate after later edits. Route every
injection counter through S1's CAS helper in UUID order, with bounded whole-
transaction retry on PostgreSQL serialization conflicts. Share provider-vector
validation and canonical ULID minting with S2 rather than growing parallel
helpers.

**Motivation.** The one successful transaction gives `snapshot_ts` observable
meaning under concurrent writes, and card snapshots close the prepare-to-commit
gap without adding a sixth persistence table. Atomic CAS events/counters leave
neither a logged injection without its statistic nor a statistic without its
decision context.

**Rejected alternatives.** Joining a historical body to the current embedding
would silently violate snapshot pinning. Long-lived transactions or an in-memory
thread cache would fail across workers and restarts. A per-thread copy of every
eligible vector is unnecessary in M1's explicit one-injection-per-thread flow.
Direct JSON counter updates would avoid revision churn but violate Invariant 5
and C.2's standing all-writes CAS rule.
