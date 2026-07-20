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

## 009 — Additive, inert origin metadata on the existing CAS surface

**Problem Tree:** P1.3

**Decision.** Add `memory_unit.origin_path` through migration `0002` as plain
nullable `TEXT`, leaving the historical `0001` migration and append-only
`memory_revision` shape unchanged. Carry the supplied string literally through
create, the existing PATCH CAS allowlist, current-head snapshots, and the shared
`MemoryUnit` wire shape. Keep Garden A-004's PATCH semantics: JSON null is an
omission, so a non-null path can replace stored metadata while null alone is a
422 no-op. Leave scorer v0, its six features and weights, candidate inputs,
cards, and frozen event payloads unchanged.

**Motivation.** S5 is a schema-and-contract propagation packet. Reusing the sole
head mutation path preserves revision/conflict behavior, while an additive
migration upgrades deployed databases without rewriting their baseline. Exact
six-feature and OpenAPI fences make the metadata's M1 inertness observable.

**Rejected alternatives.** Editing `0001` would strand existing databases.
Adding path normalization, traversal checks, indexes, a default, or filesystem
existence validation would invent law absent from C.2/C.4. Treating PATCH null
as a clear operation would contradict A-004. Adding `f_loc`, `w_loc`, or
`origin_path` to scorer/event/card inputs would pull M3 behavior into M1 and
disturb S3's frozen prepare contract.

## 010 — Serialized event state machines over the existing log and CAS writer

**Problem Tree:** P1.2.1a, P1.2.1b, P1.2.1d

**Decision.** Enact Garden A-009 and A-010 in one decision service with a
transaction-scoped PostgreSQL advisory lock per injection, locked event rows,
and affected memory heads locked in UUID order. Validate the complete request
before effects, conditionally write event outcomes from their expected state,
and route every counter, bias, and status change through the existing C.2 CAS
writer in the same outer transaction. Sample the add-back database clock only
after head locks are held so concurrent injection IDs cannot make
`last_injected_at` regress. Load never behavior from each event's recorded
scorer version. Reuse the shared current-head MemoryUnit converter for
`wrong_removed`; cited feedback remains event-only.

**Motivation.** The event row is the durable gate membership already frozen by
S3, while the advisory lock makes a batch-level retry and feedback transition
serialize without adding schema. Ordered head locks preserve independent-event
statistics without deadlocks or lost updates, and the conditional writes make
same requests idempotent while rejecting different terminal choices.

**Rejected alternatives.** A new injection-batch table would rewrite completed
S3 and exists only to distinguish an eventless prepare from an unknown empty
UUID. Direct JSON updates would split head/history and violate C.2. Process-local
locks would fail across workers. Treating cited as a head statistic would turn
on C.3's explicitly inert M1 citation feature.

## 011 — One canonical renderer over frozen event cards

**Problem Tree:** P1.2.1c

**Decision.** Enact Garden A-011 as a pure renderer that sorts final event
members by rank and memory UUID, reads only `features._memory` plus the event's
`memory_kind`, applies the exact attribute/body escaping rules, and joins the
fixed structural lines with LF. Malformed or absent frozen card data fails the
transaction instead of falling back to a current memory head. The zero-member
case uses the same renderer and therefore has one canonical four-line result.

**Motivation.** Rendering from the logged card makes commit output replayable
after later edits and keeps byte-level formatting independently testable. A
fail-closed boundary exposes corrupt historical data rather than silently
changing what the gate showed.

**Rejected alternatives.** Joining current heads would violate snapshot replay
and make edits between prepare and commit leak into the prompt. A general XML
serializer would add declaration, whitespace, or escaping choices beyond the
fixed C.6 wire contract. Maintaining a second empty-block constant in the
service would invite drift.

## 012 — Current-head vector search without scorer coupling

**Problem Tree:** P1.1

**Decision.** Enact Garden A-012 inside the existing memory service: validate
the bounded result count before provider work, embed the query through the same
validated C.1 boundary as memory CRUD, and issue one read-only pgvector query
over current ACTIVE heads. Order by cosine distance ASC then memory UUID ASC;
the pgvector cosine-distance operator remains the primary ordering expression.
Expose `1 - distance` unchanged through the shared similarity-card converter.
Apply the global-or-exact project predicate only for a non-null context. Remove
the last 501 route and its now-unused scaffold helper.

**Motivation.** Search is the agent tool's direct semantic lookup, not a second
gate scorer. Keeping it on the current-head memory service reuses provider and
wire validation while one MVCC SELECT gives the complete read boundary without
locks, revisions, events, or statistics.

**Rejected alternatives.** Reusing scorer v0 would introduce weights,
thresholds, bias, pin priority, feature calculation, and snapshot/event side
effects that C.4 does not request. Reusing the dedup query would incorrectly
drop low and negative similarities at its configured threshold. A new module,
table, or search index duplicates boundaries already owned by memory_unit and
its HNSW cosine index.

## 013 — One-way, identity-pinned billing detach

**Problem Tree:** P4

**Decision.** Implement D2 as an isolated Python 3.12 Cloud Run function with a
stdlib-only decision core and a thin Cloud Billing adapter. Pin the target to
`projects/n8-memory-palace`, require the configured billing-account ID, budget
ID, and Pub/Sub schema on every message, compare amounts as exact decimals, and
request an empty billing account at equality or overage. Treat malformed or
foreign messages as logged acknowledgements; log before and after the detach,
and surface Cloud Billing failures. Repeated requests set the same empty-account
state, so idempotency does not require a status read. Deploy through a
default-inert, first-deploy-only human script that validates the explicitly
named, billing-account-owned monthly whole-project $100 budget and requires
fresh infrastructure.
Reject ambient gcloud credential overrides and inspect the current permissions
of every directly bound project and billing-account role instead of maintaining
a drifting role denylist. Only the active human may directly update the budget
or billing-account IAM; allow other dangerous project permissions only to that
human, the armed runtime role, and exact project-number identities at a fixed
allowlist of Google-owned service-agent domains. Account ownership also keeps
project-level resource-budget writers read-only. Require the
named Project Billing Manager role to be absent before arming and exactly bound
to runtime afterward.
Separate runtime, trigger, and build identities: only runtime receives Project
Billing Manager on this project, only trigger receives service-scoped Invoker,
and the build identity loses its temporary documented roles before arming. Wire
the budget last, after exact topology validation. Require one target-project
Eventarc subscription exactly named by the healthy function-owned trigger's
output-only transport, with no direct subscription IAM or topic/subscription
message transforms, since transforms can rewrite both trusted data and
attributes. Use automatic detach-role rollback on later errors and fail-closed
policy readback.

**Motivation.** Pub/Sub is at-least-once and budget data is delayed, while the
operation deliberately kills its own project. Identity checks keep an unrelated
budget message from authorizing that outage; a fixed source target prevents
ambient configuration or payload data from redirecting it. The empty desired
state is naturally safe under duplicates. Platform retries are disabled because
a permanent failure could preserve an old destructive event through recovery;
Cloud Billing publishes a fresh status several times per day. Avoiding
`getProjectBillingInfo` keeps the runtime on the project-scoped detach permission
promised by D2 rather than adding a read or billing-account role.

**Rejected alternatives.** Discovering a budget by its display name or amount
could silently wire the wrong $100 budget. A simulation flag could leave the
supposed breaker permanently inert. A datastore latch, automatic reattach,
account-level runtime Billing Administrator, a long-lived privileged build
identity, and a separate FinOps project add state, privilege, or scope D2 does
not need. Reusing partial resources is rejected because it makes unknown keys,
policies, and queued deliveries part of the destructive boundary. The newer
two-step `gcloud run deploy --function` plus manually managed Eventarc trigger
adds drift without changing the deployed Cloud Run function; the supported
second-generation functions command owns that pairing in one operation. A live
at-limit synthetic drill is
rejected because its successful outcome is an intentional outage; fake-client
tests prove that branch while the runbook's live drill stays below threshold.
Treating topic deletion as queue deletion is also rejected: recovery captures
every subscription attached to the dedicated topic through its topic-side
index before teardown, including cross-project and orphaned Eventarc queues,
then deletes or irreversibly detaches each and proves the topic-side index empty
because Pub/Sub retains subscriptions and backlog after topic deletion.

## 014 — Broker routing at the existing provider seam

**Problem Tree:** P1.1

**Decision.** Enact SPEC v2.3 C.5 by making the runtime embedding URL an
environment-backed setting, defaulting it to OpenRouter, and passing it to the
existing OpenAI-compatible HTTP adapter. Use the broker-namespaced model by
default while retaining both URL and model overrides for direct providers.
Keep the generic bearer-key slot and fixed 1536-dimensional validation
unchanged. Local Compose forwards both routing settings; for credentials, let
an explicit generic key win, then the default broker key, then the legacy
direct-provider key. Exercise both routes by replacing only the adapter
constructor with a deterministic provider in configuration tests; production
has no fake fallback.

**Motivation.** Routing belongs at composition, not in a second adapter. One
OpenAI-compatible boundary keeps provider choice deploy-time configurable and
preserves all validation before persistence.

**Rejected alternatives.** A broker-specific SDK or adapter would duplicate
the existing wire protocol. Inferring the model name from the URL would couple
independent settings and make custom compatible endpoints ambiguous. Renaming
the established key slot would add secret migration work without changing the
bearer protocol.
