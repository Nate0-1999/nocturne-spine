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

## 015 — One regional, least-privilege D1 deployment path

**Problem Tree:** P4

**Decision.** Keep every D1 resource in `n8-memory-palace` and `us-central1`.
Store the database URL, static Spine token, and OpenRouter key in region-pinned
Secret Manager replicas, and attach Cloud Run only to the dedicated
`spine-runtime` identity. Give that identity one project role
(`roles/cloudsql.client`) and one resource-scoped accessor grant on each of the
three secrets. Build the pushed commit directly on the operator's local Buildx
amd64 worker, enforce immutable Artifact Registry tags, and avoid Cloud Build,
GCS staging, and build identities. Run Alembic separately through the Cloud SQL
Auth Proxy, using a short-lived token from the already-active gcloud deployer
when local Application Default Credentials are absent; never migrate at
container startup. Keep Cloud Run transport public while retaining Spine's
static bearer as application authentication.

**Motivation.** D1 needs one reproducible production path without turning the
default compute identity, a build service, or project-wide secret access into
ambient authority. Region-pinned secret replicas and immutable commit tags make
the deployed topology and artifact auditable, while an operator migration keeps
schema changes out of autoscaling and restart behavior.

**Rejected alternatives.** The default compute service account already carries
broad inherited authority and is not a runtime boundary. Cloud Build would add
an identity and GCS/logging behavior outside D1's mutation fence. Project-wide
Secret Accessor is broader than three resource grants. Installing ADC or
starting an interactive login merely to run the proxy would create credential
state when the active deployer's short-lived token is sufficient. Container
boot migrations would race across revisions and mix deployment with schema
ownership.

## 016 — Cloud-safe health alias under the existing bearer boundary

**Problem Tree:** P4

**Decision.** Retain the specified `/healthz` endpoint and add `/health` as an
alias of the same handler for Cloud Run verification. Protect both paths with
the existing application-wide static bearer and keep the alias out of the
committed OpenAPI surface. Use `/health` for remote D1 probes while local and
Compose acceptance continue to exercise `/healthz`.

**Motivation.** Cloud Run documents some URL paths ending in `z` as reserved
and recommends avoiding every such path. Live probes confirmed that its front
end intercepted `/healthz` with an unlogged Google HTML 404 while ordinary
paths reached the ready Spine revision. A non-`z` alias resolves that platform
collision without changing the specified endpoint or authentication boundary.

**Rejected alternatives.** Removing or renaming `/healthz` would break the C.8
acceptance contract. Making either health endpoint unauthenticated would widen
the frozen application boundary. A second service, custom domain, or proxy
would add infrastructure to solve a one-path incompatibility.

## 017 — D2 preflight: case-insensitive deployer email match [P4]

**Decision.** `deployment_checks.py` compared IAM member strings to the trusted
deployer with exact string equality. Google account emails are case-insensitive,
but an IAM policy preserves the capitalization used at grant time, so a deployer
authenticated as `user:name@x` can appear in the billing-account policy as
`user:Name@x` and be wrongly flagged as an untrusted extra billing administrator
(observed live: `NDOswalt1@gmail.com` vs `ndoswalt1@gmail.com`). Added
`_members_match`, which casefolds only the email portion (the member type prefix
stays exact), and use it at both trusted-deployer comparisons.

**Motivation.** The check's intent is "only the active human deployer may directly
hold budget/billing IAM." Case-insensitive email matching realizes that intent
exactly; it admits no additional real principal because case-variant emails are
the same Google account. This is a correctness fix to a live false-positive, made
at a human gate with the owner's explicit choice (over mutating billing-account
IAM), not a loosening of the security boundary.

**Rejected alternatives.** Removing and re-granting the owner's `billing.admin`
in canonical lowercase would leave the check untouched but mutate billing-account
IAM with a brief self-lockout window, and would not fix the general case for any
future differently-cased deployer. Lowercasing the whole member string risks
collapsing case-significant identifiers elsewhere; scoping the fold to the email
portion is precise. All 76 D2 tests pass; the fix rejects strangers and
type-swaps (verified).

## 018 — D2 preflight: deployable against a default-posture project [P4]

**Decision.** The D2 deploy preflight refused to arm against a standard GCP
project: its project-IAM audit hard-rejected Google's own default identities
(the Container Registry service agent and the default Compute Engine SA with
`roles/editor`) that hold `pubsub.topics.publish` in essentially every project.
Two corrections: (1) `_is_project_service_agent` now recognizes the default
Compute Engine and App Engine (`@appspot`) accounts, a curated set of Google
service-agent domains including `containerregistry`, and Google's reserved
`gcp-sa-*` per-service agents — while
still refusing a service account minted in any other project's SA domain;
(2) Google-managed project service agents are trusted for every dangerous
permission except direct billing ASSOCIATION (project-level detach), which only
the runtime binding may hold. Project-level billing CONTROL permissions are inert
because the breaker budget is BILLING_ACCOUNT-scoped and unmodifiable by any
project principal.

**Motivation.** A security gate the legitimate operator cannot pass against a
default project is a defect in the gate, not a finding about the project (Garden
report 018; owner's decision to simplify rather than harden project IAM). The
corrections preserve every resource-level guarantee — topic publish restricted to
Google's budget alerter, private/no-retry function, exact detach-role binding,
BILLING_ACCOUNT-scoped budget, and the strict billing-account IAM audit — while
making the project-IAM audit reject only genuine anomalies (users, groups, and
user-created service accounts with breaker-relevant permissions).

**Rejected alternatives.** Demoting the whole project-IAM audit to a bare warning
would drop the guard against a genuinely anomalous non-Google grant. Hardening the
project's own IAM (removing Editor from the default Compute SA) is a valid, larger
best-practice change the owner declined for now. All 76 D2 and 160 spine tests
pass; a live audit of the deployed project's IAM is clean; the destructive
`--apply` stays human-only.

## 019 — Near-miss Never reuses the removal transition

**Problem Tree:** P1.2.1b

**Decision.** Implement Garden A-022 by accepting an existing commit
`removed` entry for a row shown as `near_miss` only when its reason is
`never`. Plan that choice as `removed:never` and send it through the same
event outcome, scorer-version rule, CAS head update, bias step, kill counter,
quarantine threshold, revision reason, idempotency, and final-block exclusion
already used for an injected or pinned Never. Keep `wrong` and
`not_relevant` invalid for near misses, and keep a near-miss ID disjoint from
`added_back`. The C.4 body and database schema do not change.

**Motivation.** Two Never signals can lower a memory below the injection
threshold, making the third kill required for quarantine reachable only in
the near-miss lane. A-022 makes that lane's veto executable while preserving
one literal negative outcome and one replayable mutation path.

**Rejected alternatives.** A second request field or outcome name would split
identical human intent across two contracts and two replay semantics.
Allowing every removal reason on near misses would invent edit and relevance
behavior the amendment does not authorize. Lowering the threshold, pinning
the unit, or mutating it through a direct quarantine endpoint would manipulate
selection merely to expose an already-recorded gate action.

## 020 — One append-only receipt ledger with in-process embedding writes [P4]

**Decision.** Implement ADR-024 and A-027 as one Spine-owned `spend_event`
table at Alembic head 0003. The database permits every product family named by
ADR-024, while the M2A HTTP contract admits only `llm.request` and
`llm.embedding`; later packets can add producers without another ledger. A
database trigger rejects UPDATE and DELETE. POST `/v1/spend/events` inserts a
nonempty batch with `ON CONFLICT DO NOTHING`, reads every resulting row inside
the same transaction, and treats normalized equality as idempotence and any
field difference as an atomic 409. No update-shaped reconciliation seam exists.

The five canonical materialized views keep their named grain and expose cost,
quantity, receipt count, and unpriced-line count; `v_spend_rate` retains
purpose/model/provider dimensions so M2C can derive all three lanes without a
second view family. A production-only task refreshes the views in their frozen
name order immediately and every configured minute. Refresh failure is logged
and cannot make a derived lens authoritative or block ledger writes.

The production OpenAI-compatible embedding adapter receives the in-process
SpendService, retains the provider billing envelope, and appends one nonzero
`llm.embedding` input receipt before returning vectors. It uses a provider
response id, then `x-request-id`, then the receipt ULID as `ref`; absent usage
or cost stays absent rather than estimated. Call sites pass only lineage they
actually know. Existing injected deterministic providers remain ordinary
vector seams and do not fabricate spend.

**Motivation.** Spine already owns the database, auth boundary, and embedding
HTTP call, so a second ledger service or a loopback HTTP call would add failure
and configuration without authority. Keeping future product types in the DDL
honors ADR-024 without building wave-2 ingestion; restricting the current wire
prevents M2A from quietly becoming that ingestion packet. The unpriced count
keeps NULL dollars visible instead of letting a dashboard mistake missing bills
for free work.

**Rejected alternatives.** Mutable cost rows violate perpetuity and make late
bills overwrite history. Refresh-on-every-write couples authoritative latency
to analytics. Concurrent refresh needs extra unique-index/null policy not
required at this scale. A queue makes the explicitly synchronous broker seam
best-effort. Teaching every fake embedding provider to mint receipts would turn
test vectors into fictional purchases.

## 021 — Retire the closed-M1 regex fence [P4]

**Decision.** Remove the repository pre-commit hook and CI step from Decision
002 now that Garden report 035 has closed M1. The hook encoded M1's forbidden
feature ledger; it is not a general product-correctness check, and several of
those feature families are now expressly scheduled M2 work. Packet scope stays
governed by the current Garden board and focused packet law. Lint, tests,
packaging checks, and contract evidence remain CI gates.

**Motivation.** The closed-milestone regex rejected the enacted M2A spend
contract. Leaving a stale guard in place makes lawful work indistinguishable
from scope drift and invites bypassing a check whose premise no longer holds.

**Rejected alternatives.** `--no-verify` would conceal the mismatch and still
leave CI red. A milestone switch whose M2 branch does nothing is ceremonial
machinery. Rewriting the regex for every packet duplicates Garden authority in
two product repositories and cannot express packet dependencies reliably.

## 022 — Hybrid retrieval owns its bounded union [P1.1, P1.2]

**Decision.** Implement M2E candidate retrieval as the deduplicated union of
the configured vector pool and 50 full-text results. Maintain a `TSVECTOR`
document over `memory_unit.label`, `body`, and `keywords` with the PostgreSQL
`simple` dictionary and a GIN index. The lexical query ORs the same normalized,
non-stopword prompt terms used by scorer v0, then orders its boundary by
`ts_rank_cd` descending and memory UUID ascending. Retrieval applies the common
principal, active-status, project/global, and non-pin filters to both regular
legs; pins remain a separate unbounded lane. It merges overlap by UUID and
records canonical source membership in the private event metadata
`_retrieval.sources` as `pinned`, `vector`, and/or `fts`. The public six-feature
card remains unchanged.

For `inject/prepare`, materialize eligible memory IDs and exact cosine
distances before applying the cosine/UUID top-50 order. This deliberately does
not use the approximate HNSW cutoff: its default breadth is only 40, filters
are applied after ANN scanning, and an inner ANN limit cannot preserve C.3's
UUID tie boundary. This packet leaves the C.2 HNSW schema in place but does not
use it for the gate's exact boundary. Owner-scale gate correctness wins here; a
future scale change must preserve the same membership law rather than silently
trading away recall.

This supersedes Decision 007 only where its pure scorer reapplied the vector
pool boundary. Retrieval now owns both finite pool boundaries, and the pure
scorer ranks every candidate in the already-bounded union. Its feature formula,
score quantization, threshold, complete ordering, pin law, and token budget do
not change.

**Motivation.** Exact identifiers and proper nouns can have weak embeddings but
must still reach the gate. A fixed lexical pool of 50 matches the established
vector width, bounds work deterministically, and keeps the packet to one indexed
recall leg. `simple` preserves exact tokens rather than stemming away their
identity. Persisting source membership proves how a candidate reached scoring
without contaminating the frozen public feature contract.

**Rejected alternatives.** `plainto_tsquery` gives ordinary multiword prompts
AND semantics and can exclude the one decisive exact term. SQL `UNION` rows
carrying different source labels do not deduplicate overlap. Reapplying cosine
top-50 inside the scorer discards the FTS-only candidate M2E exists to recover.
Source ranks, weighted fields, language-specific dictionaries, and a new runtime
configuration surface add policy not required by this packet.

## 023 — Vitals is one honest canonical snapshot [P2.4, P4.1]

**Decision.** Adopt Garden A-028 and its collision repair A-029 as the M2C read
contract. Serve one
bearer-protected, repeatable-read snapshot over the ordinary materialized
`v_spend_rate` cadence and current `memory_unit` heads. Group the same trailing
hour of canonical rows into deterministic total, purpose, and model lanes with
Python `Decimal`; preserve exact decimal strings, null cost, unpriced-line
counts, and cross-lane conservation. Measure only created rate and current
active and pinned counts. Return every other named lifecycle, Palace, and queue
gauge with A-028's typed `not_recorded` or `placeholder` status.

Reserve `unreported` for the null-model lane and apply A-029's single-prefix
escape to colliding non-null model keys. This read-only identity escape never
changes the canonical model stored on a receipt.

Do not refresh the materialized view per request, infer transition history from
revision reasons or mutable timestamps, or add a lifecycle writer. The endpoint
is a read projection only; it changes no authoritative memory or spend row.

**Motivation.** The spend view is already the canonical dollar boundary, while
the current schema simply does not record most named lifecycle transitions.
One database snapshot keeps lanes and counters mutually coherent. Typed absence
is honest and reversible when future packets add canonical observations;
invented zeros or reconstructed events would be durable misinformation.

**Rejected alternatives.** Browser-side currency aggregation would duplicate
authority and invite floating-point drift. Refreshing on demand would couple a
dashboard read to analytical write work. Treating missing gauges as zero or
mining `updated_at` and free-form reasons would violate Invariant 10. A new
event log is outside M2C and would pre-build later lifecycle packets.

## 024 — Autonomous prepare is a new snapshot, not a second gate [P1.2, P1.4]

**Decision.** Adopt Garden A-030 as the M2G injection contract. Preserve gate
mode's one-shot prepare and human event rows. For each autonomous prepare, lock
the already-stamped thread, take a fresh database-clock snapshot, retrieve the
ordinary bounded union plus every current or confirmed head, apply explicit
thread exclusions, and write passive rows for selected, entered, exited, and
near-miss membership. Render the returned block only from that batch.

Pins and confirmed units are forced binary members. Pins keep their established
UUID order; only confirmed non-pins form the locked regular lane. Forced token
cost reduces ordinary budget but may overflow it, while threshold and top-k
continue to govern only ordinary candidates. A memory that is both pinned and
confirmed is one forced member, not an invalid duplicate class.

Permit a human panel removal to replace passive `kept` or `auto_entered`, then
permit `mid_thread_added` and a later removal on that same membership. These
feedback writes remain exactly once; only removal increments the corpus removal
counter.

**Motivation.** The first gate establishes human authority, but later prompts
need current relevance and live corpus state without repeatedly interrupting
the owner. Keeping locks binary prevents the scorer from silently weakening a
human decision. Actor-classed batches preserve the distinction between passive
system selection and human teaching signal.

**Rejected alternatives.** Reusing the first snapshot makes live corpus edits
invisible. Treating a lock as a score boost permits demotion. Reopening the gate
on every turn violates the product experience. Updating one durable event in
place would erase replay provenance; storing daemon-only entry/exit state would
make learning and trace evidence unverifiable.

## 025 — Whole-log convex proposals over the existing event authority [P1.2]

**Decision.** Adopt Garden A-031 as the M2F executable boundary. Build one pure,
deterministic learner over detached event examples and one Spine service that
loads a repeatable-read log snapshot, serializes retrains with a PostgreSQL
advisory transaction lock, and inserts only an inactive proposal when the
binary holdout scoreboard says it wins. Fit squared pairwise hinge loss by
deterministic projected gradient over the six-weight simplex, with L2-shrunk
per-memory offsets. Store those offsets and the full reproducibility manifest
inside the proposal's existing params JSON; active config loading treats old
versions as an empty offset map.

Use whole injection batches for the chronological split so one gate never
leaks across training and holdout. The incumbent baseline is the disposition's
recorded shown class—the decision that actually served—while the challenger is
graded from its recomputed score and unchanged tau. Preserve every other manual
parameter verbatim. Run the identical service from authenticated POST
`/retrain` and an opt-in periodic task; neither path activates a proposal.

**Motivation.** The event log already owns features, outcomes, actor class,
source version, and frozen bodies. A full refit makes that log—not mutable
process state—the learner authority, while an inactive, content-addressed row
keeps owner activation and exact replay visible. Six constrained weights do not
justify a heavyweight solver dependency in the owner service; the deterministic
convex routine is small enough to audit and test from hand-built fixtures.

**Rejected alternatives.** Online SGD contradicts the resolved batch method and
makes order an accidental authority. SciPy/CVXPY would add a large runtime
dependency for a six-weight convex problem. A new training table duplicates the
event log. Mutating `memory_unit.bias` during retrain would activate a challenger
before the owner acts and overwrite the online never-kill safety response.

## 026 — One graph snapshot and append-only scorer activation authority [P1.2, P2.5]

**Decision.** Adopt Garden A-035. Serve Memory Graph snapshots from the
non-candidate corpus under repeatable read, with exact similarity, lineage, edit
trail, revision, and CURRENT-membership evidence. Serve the Injection Console
from scorer versions, immutable injection events, and a new append-only
`scorer_activation` journal. Every contribution is serialized as an exact
decimal string; bias is the explicit residual so the seven values conserve the
recorded score.

Human controls create a new active version under one advisory transaction lock
and record the prior version, changed law-bound descriptors, actor, machine,
reason, and event UID. Learner rows remain proposals until the separate
proposal-activation operation validates their provenance. Thread Vitals reads
authoritative `spend_event` receipts directly; the existing global materialized
view remains the global path.

**Motivation.** The graph and console are instruments over existing truth, not
new authorities. A version plus activation journal makes owner control
replayable without rewriting learner history or pretending JSON configuration
diffs are an audit log.

**Rejected alternatives.** Browser-side graph inference or score arithmetic
would duplicate authority. Updating an active scorer row in place would erase
history. Reusing global spend lanes for CURRENT would misstate thread scope.
What-if and audition remain M2P rather than being smuggled into M2K controls.

## 027 — Syntax-ratcheted test motivation and inverse law index [P4]

**Decision.** Adopt Garden A-040. Ship a repository-local, standard-library
checker that reads every Python test docstring, accepts only the enacted
citation grammar, and grandfathers only an exact normalized source digest. Run
it from both the local pre-commit configuration and CI. Generate the
law-coverage artifact from the same scan rather than maintaining a second
hand-written index.

**Motivation.** A filename exemption would let an old test change forever
without explaining its purpose. A source digest makes the temporary baseline a
real ratchet, while one scanner keeps enforcement and coverage from disagreeing.

**Rejected alternatives.** Enforcing prose quality with keyword heuristics
would manufacture confidence the machine cannot justify. Sharing the script
through a sibling checkout would break installed and standalone repository
operation. Auto-inserting generic docstrings would disguise the human sweep as
completion.

## 028 — Serialize the packaged migration boundary [P1.3]

**Decision.** Adopt Garden A-041. Acquire one stable PostgreSQL session
advisory lock on Alembic's own connection around every online migration run.
Exercise each packaged historical revision through the current head against
real Postgres.

**Motivation.** Both local startup and owner-cloud deployment already converge
on the packaged Alembic entrypoint. Locking that deepest shared boundary keeps
two callers from interleaving schema history without creating a second
migration coordinator.

**Rejected alternatives.** A process-local lock cannot coordinate CLI and
deployment processes. Locking on a separate database connection would not bind
the lock lifetime to the migration transaction. Testing only empty-to-head
would miss upgrade failures in intermediate owner histories.

## 029 — Measure database size where the database lives [P1.3, P2.4]

**Decision.** Adopt Garden A-044. Extend both Vitals scopes with one resource
object measured inside the existing repeatable-read transaction. Spine fills
only `database_bytes` from PostgreSQL and marks the object partial; Harness owns
all process and filesystem enrichment.

**Motivation.** Logical database size is the one resource fact Spine can report
truthfully for both local PostgreSQL and the owner's Cloud SQL Palace. Keeping
the query in the canonical snapshot avoids a second credentialed endpoint and
lets CURRENT and GLOBAL agree about the same physical database.

**Rejected alternatives.** Docker-volume inspection does not work for Cloud SQL.
Letting Harness connect directly to PostgreSQL would break the HTTP boundary.
Having Spine guess daemon or owner-filesystem values would turn unavailable
observations into false measurements.

## 030 — Bind informed force to one replay authority [P1.2.3, P2.5]

**Decision.** Adopt Garden A-047 and A-048. Spine owns instant frozen-gate
replay, M2F-compatible held-out scoring, bounded accuracy slices, and learner
proposal auditions. A human scorer replacement must present a SHA-256 receipt
over its exact base version, eleven values, evidence boundary, denominator, and
scores; Spine recomputes that receipt inside the same advisory-locked activation
transaction and journals it with the immutable version change.

Prepare events now retain the exact model-context limit in private replay
metadata. Legacy gates without sufficient inputs return `not_replayable`.
Integer controls enumerate their real bounded domains, so `top_k` produces
eight distinct slice points rather than a duplicated ninth point.

**Motivation.** The displayed consequence and the activated values must be the
same fact. Reusing frozen injection inputs and the existing M2F referee avoids
a persuasive browser approximation, while a recomputed content receipt closes
the time-of-check/time-of-use gap without another persistence table.

**Rejected alternatives.** A confirmation dialog proves only that a click
happened. Trusting a browser-computed score would split authority. Persisting
audition state would let a presentation overlay leak into commit or feedback.

## 031 — Report the packaged schema head in authenticated health [P1.3, P4]

**Decision.** Add the installed wheel's single Alembic head to the authenticated
health response and derive it from the packaged migration graph. The health
endpoint does not query PostgreSQL.

**Motivation.** A remote `nocturne up` needs a cheap version handshake before it
starts a UI that may call newer endpoints. The packaged head is the app's schema
expectation and remains available during scale-to-zero wake-up without turning
liveness into a database diagnostic.

**Rejected alternatives.** The package version remained `0.1.0` across the M2
schema wave and cannot detect skew. Querying `alembic_version` on every health
request couples liveness to database access and breaks the contract-only app.
Hard-coding `0009` would drift from the migration graph.

## 032 — Materialize identical deploy input from wheel or canonical checkout [P4]

**Decision.** Keep the wheel's embedded allowlist as the public deployment
source. When Spine is imported from its canonical editable checkout and those
embedded files do not exist, materialize the same allowlist from the repository
root, canonical package tree, and billing-breaker directory.

**Motivation.** The owner's fixed-cloud command currently runs from this
workspace. Editable installs intentionally do not synthesize Hatch's wheel-only
`_deploy` directory, so requiring it made `nocturne up → y` fail before any
cloud mutation even though every exact source file was present.

**Rejected alternatives.** Building and reinstalling a wheel behind the prompt
would mutate the running environment and obscure which code is deploying.
Copying the entire repository would widen the image context beyond the existing
allowlist. Removing embedded wheel resources would break standalone installs.

## 033 — Preserve presentation while recording the budget boundary [P1.2]

**Decision.** Record every above-threshold candidate rejected solely by the
remaining token budget as a dedicated injection event with
`shown_as=budget_cut`, outcome `budget_cut`, its complete feature vector, rank,
score, and scorer version. A candidate that is also displayed retains its
separate `shown_as=near_miss` event, so gate commit sees exactly the same batch
member it did before. Migration 0010 extends only the `shown_as` check.

**Motivation.** D.2 101 needs the counterfactual boundary for the existing
Chrysopoeia replay, but `shown_as` answers what the owner saw while `outcome`
answers why selection stopped. Keeping those facts separate prevents learning
instrumentation from changing the gate or scorer behavior it is meant to
observe.

**Rejected alternatives.** Reclassifying a visible near miss as `budget_cut`
would break its add-back and veto controls. Overloading the mutable disposition
on that same event would erase one of the two facts. Logging only the displayed slice
would censor the band at `near_miss_k`. Adding a second tuning system or changing
the selection budget belongs to later memory-share work, not this packet.
