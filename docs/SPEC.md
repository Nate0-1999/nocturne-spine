# Harness + Memory System — Specification

**Version 1.13** (2026-07-20) — Invariant 14 "least attention" codified as core law (D.2 entry 038). Prior v1.12 (2026-07-20): loop & interfacing: C.7 envelope v1.12 (cancel/queue/snapshot/usage + reserved M3 types) and ADR-014 prime loop with three-level send gesture (D.2 entry 037). Prior v1.11 (2026-07-19): deconflict pass: OQ-14 resolved (repo names fixed, "rename allowed" removed), vision/Invariant-1 aligned to the vernacular (D.2 entry 036). Prior v1.10 (2026-07-19): Vernacular fixed (1.0): Memory Palace / spine / Harness / Garden / relay defined once (D.2 entry 035). Prior v1.9 (2026-07-19): ADR-013 framework seam: own the interface, adapt pydantic-ai's implementations (D.2 entry 034). Prior v1.8 (2026-07-19): config: dev/test chat default minimax-m3 via OpenRouter; D1 cloud footprint recorded; /v1/search assigned to S6 (D.2 entry 033). Prior v1.7 (2026-07-19): ADR-012 work protocol: spec → loop → judge as the default grammar of all project work (D.2 entry 032). Prior v1.6 (2026-07-19): memory location law (origin_path, f_loc, movement/refresh) + flashcard-deck interface (D.2 entries 030–031). Prior v1.5 (2026-07-17): C.2/C.4 contract gaps closed at the human gate (Garden flags F001–F005) and COMPLETION authority added to 1.4 (D.2 entries 028–029). Prior v1.4 (2026-07-07): execution protocol complete (judges + Agent Zero) — reorganized from the v0.x iteration transcript;
content-preserving. Audience: implementing agents (via /goal) and the human owner.
Everything here is binding unless marked OPEN or given a non-accepted status.
ADR numbers are immutable; superseding requires a new ADR. The chronological
history of every decision is Appendix D.2.

**Reading guide:** Section 1 is the whole system in one page; Section 2 is
the Problem Tree — the why-lineage from root pain to atomic build element,
and the Blight Protocol for local defects. Part A holds the architecture
decisions (grouped by pillar, not by the order we argued them). Part B is
roadmap + scope law. Part C is the literal build spec for M1. Implementing
agents: read 1 → 2 → B → C, consult A when deeper rationale is needed; cite
tree node IDs in DECISIONS.md. Loops begin with Agent Zero (C.10) and end
with a judge (B.6, C.9).

---

## 0. Vision & Non-Negotiables

Two loosely coupled modules, designed together, usable apart:

1. **Harness** — a modern agent harness (queuing, interjection, loops, skills,
   compaction, subagents, MCP) differentiated by visualization:
   - Live per-agent **context window visualization** (existing prototype: Code
     Puppy context-visualizer-popout — category breakdown, compaction
     threshold line, compaction table).
   - Live **agent location visualization**: agents move through the filesystem
     of the machine(s) they inhabit; the UI shows where every agent is, across
     machines.
2. **Memory system (the Memory Palace)** — the persistent "heart" of the agent:
   - Cloud-resident (GCP), identical behavior across machines and subagent
     instances.
   - Intercepts every prompt submission and injects scored memories into
     context.
   - Injection output is user-modifiable in real time; modifications are
     training signals that tune the injection scorer over time.

Both are model/token agnostic.

---

## 1. The System on One Page

### 1.0 Vernacular (the words of this project, used consistently hereafter)

- **The Memory Palace** — the memory product: the database, the algorithms
  that curate it (scoring, dedup bands, the learning loop), and — from M3 —
  the curator (maintenance) agent. In M1 it is the spine deployable's
  memory module (ADR-008) and remains extractable.
- **The spine** — the always-on cloud backbone: the single deployable that
  houses the Palace plus the connective modules (auth/API plumbing,
  presence, relay/control) that local daemons and browsers connect
  through. "The heart" is a description of this always-on center, not a
  second name.
- **The Harness** (capitalized) — our local product: the per-machine
  daemon, the agent runtime, and the web command center. Lowercase
  pydantic-ai-harness is the upstream library behind the ADR-013 seam.
- **The Garden** — where this system is grown: the governance repo
  (PLAN/BOARD/FLAGS/AMENDMENTS/reports) and its culture — gardeners =
  builder agents, groundskeeper = Agent Zero, blight = defects.
- **The relay** — the Garden's execution methodology: runners, packets,
  baton handoffs, judges; ADR-012 promotes it into the product's own work
  protocol. Distinct from the spine's relay/control MODULE, which forwards
  messages between browser and daemons (M3).
- **Deck, gallery, Ant Farm, fleet color** — interface vocabulary
  (ADR-008/009): the flashcard deck is the primary interaction, the
  gallery the multiplexer view, the Ant Farm the agent visualizer; each
  top-level agent wears one fleet color everywhere.
- **Repo mapping:** local `spine/` (remote `memory-palace` — named for its
  principal resident), `harness/` (remote `harness`), `garden/` (remote
  `garden`). Local directory names are load-bearing law; remote names are
  labels.

### 1.1 Topology

```
                    ┌─────────────────────────────────────┐
                    │        SPINE (Cloud Run, GCP)       │
                    │  ┌────────┐ ┌──────────┐ ┌───────┐  │
                    │  │ memory │ │ presence │ │ relay │  │   one deployable,
                    │  │  (P1)  │ │   (P2)   │ │ (P2)  │  │   three modules
                    │  └────┬───┘ └────┬─────┘ └───┬───┘  │
                    │       └──── Cloud SQL Postgres ─────│── pgvector, logs,
                    └───────────▲───────────▲─────────────┘   DBOS checkpoints
                      HTTPS/SSE │           │ outbound WS
                    ┌───────────┴───┐   ┌───┴────────────────────────┐
                    │  BROWSER SPA  │   │  MACHINE (owned or rented) │
                    │ command center│   │  daemon ──spawns── agents  │
                    │ chat·gate·viz │   │  (pydantic-ai loops at the │
                    └───────────────┘   │   workspace, SQLite cache) │
                                        └────────────────────────────┘
   M1 shortcut: browser ↔ localhost daemon directly, same envelope.
```

### 1.2 Life of a prompt

1. User types in the command center; candidates pre-fetch on debounce.
2. Send → daemon calls spine `inject/prepare`; nothing reaches the model yet.
3. First prompt of a thread: **gate** renders scored memories (full bodies) +
   near-misses. User removes (typed reasons) / adds back. Hard pause.
4. Commit → spine logs outcomes, returns the rendered `<memory_system>` block.
5. Harness prepends it system-adjacent; the agent loop runs at its workspace;
   the panel stays live for ad-hoc removal; agent may save/edit/search
   memories via tools (write-time dedup curates).
6. Every event lands in the append-only log — the future learner's fuel.

### 1.3 The Invariants

Everything else in this document elaborates these fourteen laws:

1. **The heart is singular and cloud; bodies run where the work is.** Memory
   (the Palace, carried by the spine) is the one always-on component; agent
   loops are workspace-anchored.
2. **Every module boundary is a wire** (HTTP, WS envelope, spawned process).
   Languages earn their place per component, after interfaces stabilize.
3. **Memories are atomic**: one fact, ≤128 tokens; a human can always read
   the whole thing at a glance.
4. **Nothing is deleted; everything is lineage.** Revisions append; deletes
   tombstone; history is sacred.
5. **No silent overwrites.** Every write is compare-and-set; a conflict is a
   first-class reviewable event at any timescale — a millisecond race or a
   three-week voyage are the same mechanism.
6. **Every injection is explainable.** Full per-feature breakdown travels
   with every score. No black-box ranking, ever.
7. **The log is primary; learned state is derived.** Rich enough to replay;
   weights are recomputed from it, never synced.
8. **The user's hand is a signal.** Gate/panel modifications carry typed
   reasons and train the system.
9. **Memory failure never bricks the harness.**
10. **Every visual channel encodes a real variable.** No decoration without
    data.
11. **Git owns workspace reconciliation; the spine owns memory.** We build no
    file-sync system and store no memory in Git.
12. **The scope ledger overrides enthusiasm.** FORBIDDEN means stop and flag.
13. **Model/token/provider agnostic throughout**; embedding spaces are tagged
    and re-derivable.
14. **Least attention.** Human attention is the system's scarcest resource;
    the architecture — never habit, never fatigue — decides when it is
    spent. Safety comes from walls (sandboxes, boundaries), not questions:
    per-action approvals inside the walls are forbidden theater. Attention
    is pulled only at genuine boundary crossings and judge-released
    returns — once, at the moment of highest leverage. Everything is
    always watchable; almost nothing may demand.


### 1.4 Normativity: how this spec governs

Three classes of content, deliberately different in force:

- **CONTRACTS (normative, follow literally):** the Invariants (1.3), the DDL
  (C.2), API request/response bodies (C.4), the WS envelope (C.7), the
  feature ledger and anti-scope rules (B.4, B.5), and acceptance criteria
  (C.8). These are what modules, milestones, and collaborators agree on;
  deviation requires human sign-off — the sole exception is a qualifying
  COMPLETION, below.
- **COMPLETIONS (self-service contract repair, declared):** where a CONTRACT
  is SILENT or SELF-INCONSISTENT on a detail a packet needs — a missing
  field, an undefined response shape, a promise the DDL forgot — the agent
  does not halt. It enacts the minimal completion that honors the contract's
  stated intent and declares it as an exact spec diff in
  `garden/AMENDMENTS.md` (mechanics: Garden PLAN §2). Enacted amendments are
  law, equal to this spec, for every later agent and the judge; the human
  audits them between sessions and may veto (veto → a FIXER reverts). A
  completion QUALIFIES only if it touches no Invariant, no FORBIDDEN ledger
  row, no auth or data-loss semantics; reverses no ADR; changes nothing an
  already-DONE packet built; and contradicts no explicit spec sentence — it
  fills silence, or repairs an internal contradiction in the direction the
  spec itself points. A genuine design fork — two readings yielding
  materially different products — does not qualify: FLAG it.
- **GUIDANCE (motivated, follow the reasoning):** everything else. Decisions
  travel with their motivation and rejected alternatives so implementing
  agents understand *why*. Where an agent sees a way to serve the stated
  motivation better, it may take it — provided no CONTRACT is touched — and
  MUST record the deviation and its reasoning in the repo's `DECISIONS.md`
  (append-only journal, reviewed by the human). Silence outside a CONTRACT
  is resolved the same way: act in the spirit of the Invariants and the
  Problem Tree (§2), record the choice with its node ID. Silence inside a
  CONTRACT is a COMPLETION, above.

The intent is cultivation, not transcription: this document should produce
collaborators who grow the project in its spirit, not contractors who
implement its letter and no more.

**ADR style law (for all future decisions):** decision, motivation, rejected
alternatives. Specify mechanism only where mechanism IS the contract.

---

## 2. The Problem Tree (why-lineage)

Every element of this system exists because of a problem; every problem is
nested inside a larger one. This tree is the chain of custody from root pain
to atomic build element. An agent parachuted into any leaf reads UPWARD to
understand why its component exists, and treats defects at the deepest node
that contains them (2.1). Node IDs are citable everywhere (DECISIONS.md,
commits, reviews).

**P0.** An agent's knowledge of its human dies with the context window;
agents scattered across machines each start ignorant; and when retrieval is
wrong, the human has no lever to correct it.
→ **S0.** One persistent, corrigible memory shared by every agent everywhere
("the heart"), plus a harness that makes agents' work visible and steerable
("the glass"). [the two pillars, §0]

- **P1. Memory must outlive every process and machine.**
  → S1: cloud spine, Postgres as single source of truth. [ADR-003 · C.2]
  - **P1.1** Many machines must see one memory identically.
    → S1.1: HTTP service + thin MemoryCapability; the API is the coupling.
    [ADR-002 · C.4]
  - **P1.2** Model calls need the right memories without human effort per call.
    → S1.2: scored injection at prompt time. [ADR-005 · C.3]
    - **P1.2.1** Relevance guesses will sometimes be wrong.
      → gate: human sees the injection before it binds; hard pause on the
      thread's first prompt. [C.6]
      - **P1.2.1a** Corrections must not be wasted. → typed removal reasons +
        append-only injection_event log with full feature vectors. [C.2, C.4]
      - **P1.2.1b** "Remove" is ambiguous (irrelevant? false? hated?).
        → three reasons: not_relevant / wrong / never — each with a distinct
        consequence (train / edit / quarantine). [ADR-005 table]
      - **P1.2.1c** Humans can only correct what they can read at a glance.
        → atomic units ≤128 tokens; gate shows full bodies. [decision 015]
      - **P1.2.1d** Some corrections happen mid-thought, not at the gate.
        → live panel + /v1/feedback. [C.6]
    - **P1.2.2** Scoring must improve from sparse, single-user signals.
      → transparent linear model; global weights first, hierarchy when data
      demands; near-misses shown so add-backs create positive signal;
      log-everything-first (M1), learn-second (M2). [ADR-005, decision 010]
    - **P1.2.3** A score no one can explain cannot be trusted or fixed.
      → per-feature breakdown travels with every MemoryCard. [Invariant 6]
    - **P1.2.4** Injection must not starve the real conversation.
      → token budget min(3000, 5%); greedy by score. [C.3, C.5]
  - **P1.3** Many hands (agents, humans, jobs) will edit the same memory.
    → CAS writes, append-only revisions, tombstones; conflict is a
    first-class event. [ADR-004 · C.2]
    - **P1.3.1** Divergence windows can be arbitrarily long (the sailing
      example) and multi-party. → ULID revisions + parent lineage, event_uids,
      union-merged logs, learned state re-derived not synced. [ADR-011;
      HORIZON — footprint only]
  - **P1.4** Accumulated memory rots (duplicates, stale facts, noise).
    → write-time dedup bands now [C.4]; maintenance agent, promotion,
    staleness later [ADR-004, M3]; quarantine for the persistently unwanted
    [C.3].
- **P2. A human cannot trust or steer what they cannot see.**
  → S2: the visibility layer. [ADR-009]
  - **P2.1** Where are my agents? → presence events → Ant Farm. [ADR-006, M3]
  - **P2.2** What is filling each context window? → Context Bars. [M2]
  - **P2.3** What does the memory know, and why was THIS injected?
    → Memory Graph + hyperparameter console; every visual channel encodes a
    real variable. [M2, Invariant 10]
- **P3. Agents must work where the files are, yet be commanded from anywhere**
  (including a phone).
  → S3: workspace-anchored loops; daemons dial out; relay-through-spine;
  browser command center; machines as an ownership-agnostic abstraction.
  [ADR-008, ADR-010]
- **P4. One human, with agents as the workforce, must be able to build and
  evolve all of the above without it collapsing.**
  → S4: Python-first polyglot-by-boundary [ADR-001]; two repos, contracts at
  the seams [B.2, C.1]; scope ledger with FORBIDDEN [B.4]; normativity model
  and DECISIONS.md [1.4]; this tree [§2].

### 2.1 The Blight Protocol (local defect, local remedy)

When an implementing agent discovers a defect, mismatch, or bad smell:

1. **Locate:** identify the DEEPEST problem node that fully contains the
   defect. (A gate rendering bug lives at P1.2.1c; it does not license
   touching the scorer at P1.2.2.)
2. **Treat locally:** fix within that node's solution space, honoring all
   CONTRACTS (1.4). This is pesticide.
3. **Escalate landscaping:** if the honest fix would alter an ANCESTOR node's
   solution or any contract, stop — that is not a local remedy. Flag the
   human with: the node, the defect, the proposed change, and which ancestors
   it disturbs.
4. **Record:** every fix and every escalation cites its node ID in
   DECISIONS.md.

**Corollary (feature attachment):** new functionality must attach to an
existing problem node or begin by proposing a new node (problem first, then
solution). Features that cannot name their problem do not get built.

---
---

# PART A — ARCHITECTURE DECISIONS

## A.1 Foundations (cross-cutting)

### ADR-001 — Framework substrate & language policy

**Status: ACCEPTED (2026-07-07)** — polyglot policy amended in same day, folded in.

**Decision:** Build on **Pydantic AI v2** (stable 2026-06). Use **Code Puppy as
a reference/donor codebase**, not a hard fork: port the context visualizer and
proven pieces; implement the harness as a clean composition of v2
*capabilities* (plus pydantic-ai-harness library capabilities where they fit).
Durable execution: pydantic-ai's native durable-execution API with the **DBOS
backend**, pointed at the same Cloud SQL Postgres (one database for memory,
presence, training log, and execution checkpoints). Adopted in M3 alongside
loops/subagents — the features that give durability something to protect;
M1/M2 sessions are plain DB rows.

**Polyglot-by-boundary policy:** Rust was weighed seriously (user-raised;
industry precedent: agent CLIs rewritten in Rust for distribution/footprint).
Ruling: components may adopt any language once their interface is stable AND a
concrete pain justifies it; **speculative Rust is forbidden**. Per component:
- **Agent runtime:** Python, locked (pydantic-ai; I/O-bound; agent-written code).
- **Spine + scorer:** Python, defended — bottleneck is idea-iteration, not CPU
  (scorer = trivial math; vector search runs compiled inside Postgres).
- **Web app:** TypeScript; WASM escape hatch for graph layout at extreme scale.
- **Daemon:** Python in M1 (single machine, minimal role). **Rust rewrite
  pre-approved** as its own repo (`daemon-rs`), trigger-gated: 2+ machines to
  install on, Ant Farm fs-watch load, or runtime-install friction. Rationale:
  long-lived per-machine process, static-binary distribution, `notify` fs
  events — the one component matching the profile that historically forces
  Rust migrations.
- **Hot spots anywhere:** PyO3 module — a file-level change, not architectural.
  The WS envelope (C.7) and daemon↔agent process contract are frozen
  language-neutral for exactly this reason.

**Alternatives considered:**
- **pi-mono (TypeScript)** — best-designed pure harness internals (AgentHarness
  hooks incl. `before_agent_start` message injection; session trees; TUI + web
  UI libs). Rejected primarily on language: the memory system needs Python's
  ML ecosystem. Single-maintainer governance also a factor. We may still crib
  UI patterns and the hook taxonomy.
- **OpenCode** — good client/server split and TUI; least leverage for deep
  memory-pipeline and visualization surgery.
- **Fork Letta** — drags in an entire competing agent runtime. We adopt the
  *memory block abstraction* (label, description, value, size limit,
  shareable, always-in-context) but none of the code. Letta's documented
  last-write-wins on concurrent block writes is explicitly rejected (ADR-004).
- **Hard fork of Code Puppy** — tempting continuity, but couples us to
  upstream churn; v2 capabilities make a clean rebuild cheaper than untangling
  a fork.

**Consequences:** memory ships as a standalone service + thin
`MemoryCapability` (the loose-coupling boundary, ADR-002); model/provider
agnosticism inherited from pydantic-ai model strings; pydantic-ai's AG-UI
event vocabulary used for agent↔daemon streaming inside the daemon (no
framework provides multi-machine control planes — that custom layer is the
point of the project).

### ADR-010 — Agent placement: workspace-anchored fleet

**Status: ACCEPTED (2026-07-07)**

**Law:** the agent loop runs adjacent to its workspace (filesystem), always.
Rationale: tool calls (fs I/O, builds, tests) outnumber memory calls by orders
of magnitude per thread; differentiator #1 (agents moving through a machine's
file structure) requires workspace locality; future local models put the model
on user hardware, which a cloud-anchored loop would invert absurdly.

**Movement law (ACCEPTED 2026-07-19; CONTRACT from the milestone agents
hold fs tools — M3; D.2 030):** agents and their sub-agents are both
permitted and *instructed* to move through the repository as they work. To
work on a file, an agent MUST first move to that file's directory —
location is a statement of attention, not an implementation detail. Every
directory change triggers a memory refresh: the injection layer re-prepares
against the new location and the procedurally injected set is re-rendered.
(Movement-triggered refresh is a distinct trigger from OQ-15's per-prompt
re-scoring question; refresh events log full location context like any
injection.)

**Fleet model:** "machine" is an abstraction over ownership. A daemon on a
personal desktop and a daemon on a provisioned cloud VM register identically
with the spine, appear identically in the command center/Ant Farm, and share
the same memory heart. **Managed/cloud agents = machines you rent.** No
special cases in relay, identity, memory, or presence.

**Explicitly rejected:**
- Fully cloud-managed harness (Letta-style server-side agents) as the sole
  pattern — kills workspace locality, the local-model future, and
  differentiator #1.
- Colocating harness VMs with the spine *for latency* — optimizes the rarest,
  smallest communication (one injection/thread, ~KB) while model calls
  dominate wall-clock by 100–1000x. Cloud machines are justified by always-on,
  parallelism, blast-radius safety, and mobile-initiated work — never by
  memory latency.

**Division of continuity:** the spine (memory + identity + logs) is the
singular always-on cloud component — "the heart." Agent loops are ephemeral
bodies at the work site. DBOS checkpoints make loops resumable in place;
cross-machine thread migration is NOT promised (workspace state is not in
Postgres). Machine provisioner: M4 (Part B).

## A.2 Pillar 1 — Memory

### ADR-002 — Service boundary (memory ↔ any harness)

**Status: PROPOSED**

**Decision:** The memory system is an HTTP(+SSE) service with a versioned API
(full M1 surface with exact bodies: C.4). The harness knows only this
interface; the harness-side integration is a thin `MemoryCapability` that
calls `inject/prepare` on prompt submit, renders the gate/ad-hoc UI, calls
`inject/commit`, and prepends the returned block. **The coupling is
deliberately symmetric** (founding requirement): any other harness gains our
memory by implementing the same small client; conversely, our harness gains
any other memory system via an adapter exposing this API — `spine_client` is
the harness's ONLY knowledge of memory, so the backend is swappable by
construction.

- Every `MemoryCard` carries the full feature vector and per-feature
  contributions → any UI can always answer "why was this injected?"
  (Invariant 6).
- The injected block is **pinned across compaction** (re-injected, not
  summarized away).
- **Block placement (RESOLVED, was OQ-1):** system-prompt-adjacent as one
  stable structured block (Letta-style). Rationale: pinned across compaction;
  changes are rare mid-thread (the gate happens before the first API call, so
  turn-1 prompt cache is unaffected); system placement signals "ground truth"
  better than user-turn placement. Ad-hoc mid-thread edits bust prompt cache —
  acceptable: rare and user-initiated.

**Rejected:** in-process library as primary interface (kills multi-machine
uniformity); MCP-only interface (fine as an *additional* adapter later, but
the gate UX needs richer semantics than tool calls).

### ADR-003 — Storage, cloud & offline

**Status: ACCEPTED (2026-07-07)**

**Decision:** GCP: **Cloud Run** (spine) + **Cloud SQL Postgres with
pgvector**. One database provides ACID transactions, vector similarity,
keyword/full-text (tsvector), relational metadata, the injection/feedback
log, and DBOS checkpoints.

- Local **SQLite read-through cache** per machine; cloud is the single source
  of truth; writes always go to cloud when online. Cache mirrors the cloud
  schema exactly (ADR-011 requirement — replica promotion is config, not
  software). Freshness: pull-on-connect + SSE invalidation; cache stores full
  units incl. embeddings and current scorer weights.
- **Degraded offline mode (RESOLVED, was OQ-2):** when the spine is
  unreachable the harness runs with **read-only memory** from the cache:
  - Semantic scoring disabled (prompt embedding needs the API); scorer
    renormalizes over keyword/temporal/project/session/frequency/history;
    gate shows an OFFLINE badge.
  - Memory writes fail loudly; the agent's create tool appends to a local
    `memory_drafts` queue surfaced for gate review on reconnect. Drafts are
    candidates, not memories — no silent sync conflicts by construction.
  - No weight updates offline; queued events upload on reconnect as log-only
    (audit, not training — feature vectors were degraded).
- Embeddings: provider-pluggable; model name + dim stored per vector;
  re-embedding on model change is a maintenance job (dim fixed 1536 in v1).
- Auth: single static bearer token until horizon; keyed by `principal_id`
  so multi-user is never a schema migration (feature itself: horizon).

**Rejected:** SQLite-only ("entirely local for now" from the original proposal
sheet) — contradicts the cloud/multi-machine requirement, and retrofitting
sync is far costlier than starting cloud-first. Firestore (no clean
vector+relational combo). Spanner (overkill). Separate vector DB (operational
overhead, two-phase consistency problems).

### ADR-004 — Memory unit model & concurrency

**Status: PROPOSED** (unit shape refined ACCEPTED in review: atomic ≤128
tokens, no summary field — decision 015)

**Unit model (authoritative DDL: C.2):** a memory unit is an ATOMIC fact —
label (short handle), description, body (≤128 tokens), kind (fact |
preference | procedure | project_note | persona | pinned), agent-chosen
keywords, embedding (+model tag), optional project/thread/path stamps, pin flag,
status (active | quarantined | tombstoned), stats (injections, removals,
citations, never_kills, last_injected_at), per-memory bias b_m.

**Concurrency & history:**
- All writes compare-and-set on `revision`; conflict → HTTP 409 with current
  unit, retry is deliberate (agent sees fresh state), never silent overwrite —
  explicit rejection of Letta's last-write-wins.
- Revisions are append-only, identified by client-mintable ULIDs with
  `parent_uid` lineage (DAG-capable, ADR-011); the integer `revision` is
  solely the cloud head's CAS counter. Deletes are tombstones; nothing is
  hard-deleted (the "update history" memory index is this revision table).
- **Thread snapshot pinning:** first `inject/prepare` stamps the thread's
  `snapshot_ts`; automatic scoring within the thread reads as-of that
  snapshot so memory doesn't mutate under a running agent. **Ad-hoc
  mid-thread injections read LIVE memory (RESOLVED, was OQ-3)** — the user is
  explicitly reaching outside the snapshot.

**Promotion (resolves the original proposal-sheet contradiction):**
frequency-threshold promotion does NOT write to agents.md/user.md. It flips
`pin=true` (always injected, exempt from scoring, still user-removable in the
gate → unpins). The "does not manipulate sessions/skills/agents.md" invariant
holds. Automatic promotion logic: M3; manual pinning: free from M1.

**Maintenance (M3; cron + /maintain_memory + 80%-budget trigger):** semantic
clustering over embeddings → dedup merge proposals (merge = new unit with
`merged_from` lineage, sources tombstoned), staleness review,
promotion/demotion pass. Runs as its own agent under the same CAS rules.
OPEN (OQ-4): auto-merge above high similarity vs user-approved queue —
leaning: auto only above high threshold, queue the rest.

### ADR-005 — Injection scoring, gate & the learning loop

**Status: PARTIALLY ACCEPTED** — removal semantics, gate behavior, learning
scope ACCEPTED; scorer constants remain tunable config. This is the
differentiator; the spec is deliberately detailed. (Exact v0 formulas and
constants: C.3, C.5.)

**Scorer:** transparent linear model per candidate m for prompt q:
`score(m,q) = w_sem·f_sem + w_kw·f_kw + w_time·f_time + w_proj·f_proj
+ w_freq·f_freq + w_hist·f_hist + b_m` — features ∈ [0,1]: semantic cosine,
keyword overlap, recency decay, project match, citation frequency,
human-edit recency, plus per-memory bias. (f_sess excised 2026-07-07: a
feature "kept for parity" that was near-always zero on first prompts —
thread_origin remains on units as metadata.) Top-k
above threshold τ within token budget; **near-misses** (next 3) are shown in
the gate so add-backs generate positive signal.

**Signals → updates** (all logged via injection_event; applied online from M2):

| action | label | update |
|---|---|---|
| removed: "not relevant here" (one-tap DEFAULT — ACCEPTED) | strong neg | SGD step on w against f(m,q); b_m small − |
| removed: "wrong/stale" | content | NO weight update; opens edit/expire flow on m |
| removed: "never show this" | kill | b_m large −, quarantine at 3 kills; small global step |
| added back a near-miss | strong pos | SGD + on w; b_m small + |
| kept (survived gate) | weak pos | tiny + step (heavily discounted — passive) |
| agent cited memory in work | strong pos | + step; increments f_freq numerator |
| ad-hoc mid-thread removal | strong neg | as "not relevant", flagged mid_thread |

Weights versioned (`scorer_version` on every event) → auditability, rollback,
offline replay. Citation detection v1: n-gram heuristic; OPEN (OQ-5):
LLM-judge later (cost).

**Learning scope (ACCEPTED, phased):** M1 = no learning, log the full context
tuple (project_key, agent_kind, memory_kind, scorer_version) so any scope is a
modeling change, not a migration; offline replay is a first-class evaluation
tool. M2 = **global weights** (fastest learner on sparse single-user signal;
b_m absorbs memory-specific corrections; f_proj expresses project affinity).
M3 = **hierarchical per-project offsets**, zero-initialized, partial-pooling:
`score = (w_global + w_offset[project])·f + b_m`; adopt when the log shows a
context whose removals fight the global trend. Rejected: fully per-context
scorers (signal starvation for a single user).

**Location relevance (ACCEPTED 2026-07-19; D.2 030):** every memory carries
`origin_path` — the workspace-relative directory context where it was
learned (NULL when there is none; M1 writes it as inert metadata only, like
thread_origin). From the milestone where agents hold filesystem tools (M3),
scorer versions add f_loc:
- d = hop distance between the agent's current working directory and
  origin_path in the workspace directory tree (each step up or down one
  level = 1 hop; same directory d=0); a memory from a different
  workspace/repo takes f_loc = 0 (cross-repo affinity stays f_proj's job).
- f_loc = 2^(−d / h_loc), h_loc default 2 hops (config).
- **Null rule (CONTRACT):** when either side lacks a location (origin_path
  NULL, or the agent has no working directory), the location term is
  OMITTED and the score renormalizes over the remaining weights —
  score = (Σ_{i≠loc} w_i·f_i) / (1 − w_loc) + b_m — so a location-less
  memory is NEVER penalized relative to a location-aware one. Scorer v0
  (no w_loc) is unaffected.

**Gate UX (ACCEPTED in review):** first prompt of thread = hard pause, no
timeout (config: auto-continue T or non-blocking per agent/project);
candidates pre-fetched on typing debounce so the gate renders instantly. Rows
show label + FULL body (atomic units make summaries unnecessary) + score;
one-tap ✕ = not_relevant; modifier menu: wrong / never; near-misses grayed,
tap to add. After the first prompt: no pause; the panel stays live, removals
apply from the next model call. Gate rows show per-feature contribution bars
(context-visualizer visual language) — Invariant 6. One gate per thread in
M1; per-prompt re-scoring is OPEN (OQ-15, M2 decision).

### ADR-011 — Divergence & reconciliation ("the sailing example") — HORIZON

**Status: ACCEPTED (2026-07-07)** as end-state design + M1 schema footprint.
Building the machinery is FORBIDDEN before M5 (Part B).

**Scenario it must survive:** weeks offline on rented hardware with a local
model and a writable local memory replica; meanwhile multiple principals keep
using the same agent memory in the cloud; at reconnect, workspace and memory
reconcile.

**Jurisdictions:**
- **Workspace = Git's job.** Boat work is a long-lived branch; reconciliation
  is push + merge. We never build a file-sync system; agents commit as they
  work; non-repo files wanting merge semantics move into a repo.
- **Memory = per-unit three-way merge**, enabled by atomic units:
  new-on-either-side → union (+ sync-time dedup pass reusing write-time
  similarity machinery); edited-one-side → fast-forward; edited-both →
  conflict into the same review queue as maintenance merges (OQ-4);
  edit-vs-tombstone → review queue.
- **Logs = union.** Append-only; conflicts impossible.
- **Learned state = derived, never synced.** After log union, weights are
  RE-DERIVED by replaying merged history (the M2 replay tool doubles as the
  sync mechanism for learned state). Events scored in a non-canonical
  embedding space are flagged via embed_model and excluded/down-weighted.
- **Unifying model:** online CAS and offline sync are one mechanism at
  different timescales — one conflict taxonomy, one review UI (Invariant 5).

**Foundation footprint applied in M1 (the ONLY committed part):** revision
ULIDs + parent_uid lineage; client-minted `event_uid` on every event
(idempotent union-safe upload); client-mintable IDs on all creates; cache
schema mirroring; `/v1/sync/*` namespace reserved (M1 drafts flow is its
degenerate ancestor). Local model support needs nothing (model-agnostic +
embed_model tagging, verified).

**Explicitly rejected:** storing memory in Git (multi-writer DB semantics
don't fit); CRDTs for memory bodies (atomic units + review queue beat
automatic text merging for facts a human must trust); syncing learned weights.

## A.3 Pillar 2 — Harness & Interface

### ADR-007 — Harness feature parity

**Status: DRAFT** — parity with modern harnesses; each item a capability:
queuing (prompt queue + steering/interjection mid-run), loops (/goal-style
autonomous iteration with stop conditions), skills (SKILL.md discovery,
project > user precedence), subagents (spawn/track/report; each registers
presence + context accounting), compaction (summarization strategy +
threshold), sessions (durable, resumable, branching), MCP, human-in-the-loop
tool approval, per-model tokenizer abstraction for honest context accounting.
Parity lands with the M3 harness buildout (re-planned after M2); the M1
agent is deliberately chat + memory tools only. Durable execution (DBOS)
arrives with loops/subagents in M3 — M1 sessions are plain DB rows.
Plan-mode compaction variant: parked (D.4).

### ADR-008 — Interface layer & control plane

**Status: ACCEPTED (2026-07-07)** — direction confirmed ("browser-based, no
TUI maintenance"); stack details PROPOSED.

**Decision:** Prompt entry, memory gate, queuing/interjection, and all
visualizations live in a single **web command center**. No interactive TUI is
built or maintained.

**Primary interaction: the flashcard deck (ACCEPTED 2026-07-19; D.2 031;
built when the multi-agent era opens — M1/M2's single-thread chat pane is
unchanged):** the command center's main mode is a deck of flashcards, one
per top-level agent, each card wearing its agent's fleet color — the same
color that agent has in the Ant Farm and every other visualizer (one color
per agent, everywhere). Exactly one card is on top: that agent's latest
response, awaiting the human. Queue order is purely time-based — whichever
agent finishes next takes the next slot; responding advances the deck. The
human may also manually cycle through the deck to watch running agents
without dequeuing them. Expanding a card opens the full thread view, whose
scrollbar is a scrubber of one line per HUMAN input — click a line to jump
the transcript to that exchange (navigation indexed by what the human
remembers saying). Secondary mode — the gallery: on demand, or when the
queue is empty, live conversations tile like a terminal multiplexer, at
most 4 tiles visible at once, panning to reach the rest. Sub-agents never
surface cards and never address the human directly; they are visible only
through the visualizers (Ant Farm et al.), and their work reaches the
human, if at all, through their top-level agent's card.

- **Frontend:** React + TypeScript + Vite SPA; SVG/canvas visualizations (no
  heavy chart deps); WebSocket (control/streams) + SSE (memory/presence).
- **Not Electron.** Desktop feel = Chrome app mode (`chrome --app=<url>`),
  matching the existing popout pattern; Tauri can wrap the same SPA later.
  Rationale: zero desktop-runtime maintenance for a single-user tool.
- **Harness daemon (per machine):** small Python/FastAPI process that spawns
  and supervises pydantic-ai agent processes, owns local FS access, emits
  presence + context-accounting events, executes prompt/queue/interject
  commands. Thin CLI only to install/start/register and one-shot `--print`.
- **Relay-through-spine (RESOLVED, was OQ-13, PURE relay):** daemons open
  *outbound* WebSockets and register `{machine_id, capabilities}`; the
  browser talks only to the spine, which relays commands down and streams
  events up. No inbound ports/VPN; works from anywhere; single origin + auth.
  Rejected: browser→daemon direct (LAN latency win; port/auth/NAT pain,
  second auth story). M1 shortcut: browser↔localhost daemon, same envelope —
  M3 changes the path, not the messages.
- **Spine = three segregated modules, one deployable:** memory (P1), presence
  (P2), relay/control (P2). No cross-module imports beyond shared db/auth
  plumbing; presence/relay must remain extractable (split = deploy change).
- **Identity (RESOLVED, was OQ-11):** client-mintable/service-minted ULIDs:
  `principal_id` (human), `machine_id` (daemon registration, stored in
  config), `agent_id` (per spawned instance), `thread_id`. All events carry
  the full tuple.
- OPEN (OQ-12): minimal localhost fallback page for offline prompt entry —
  which milestone.

### ADR-012 — The work protocol: spec → loop → judge (default grammar of work)

**Status: ACCEPTED (2026-07-19; D.2 032).** CONTRACT from the milestone the
multi-agent harness ships (M3); M1/M2's single-thread chat is its degenerate
predecessor. This is the Garden relay methodology that built this very
system, promoted to product behavior.

**The protocol — every unit of project work, no exceptions:**
1. **Spec alignment.** Work begins as a conversation that produces a spec
   artifact the human ratifies. The spec scales with the task — one
   ratified sentence for a rename, a document for a feature — but it always
   exists: it is the judge's rubric, and work without a rubric cannot be
   judged.
2. **Agent loop.** The orchestrator dispatches the work: one agent, or N
   parallel attempts at the same spec in isolated git worktrees. The system
   sizes N from the task, capped by the `max_parallel_project_agents`
   setting (harness config; the knob ships with this milestone). Agents
   follow the movement law (ADR-010) as they work.
3. **Judge.** Judging inherits B.6 doctrine: fresh context, different model
   preferred, sees only the spec and the artifacts, never the builders'
   reasoning. Verdicts: COMPLETE → release to the human; INCOMPLETE or
   defective → dispatch a continuation/fix agent charged with the verdict
   (loop back to 2). For parallel attempts the judge picks the winner
   against the spec and may charge a graft agent with folding the losers'
   best pieces into it.
4. **Return.** Only judge-released items enter the flashcard deck
   (ADR-008). The system never pulls human attention otherwise.

**Blockers (judge-triaged):** an agent that hits a genuine blocker (missing
credential, spec ambiguity) routes its question to the judge, not the
human. If the answer is derivable from the spec, the judge sends the agent
back with it; only questions the spec truly cannot answer are released as
cards. Agents cannot "block" their way to human attention.

**Interjection rule:** the human may always watch (gallery, deck cycling).
Interjection is allowed while ONE agent holds the work; when N>1 parallel
attempts run, the run is watch-only — an interjection mid-swarm would fork
the attempts' common ground. Attention-pulls are judge-gated always;
attention-pushes are solo-run only.

**Rejected:** direct-mode escapes for "small" tasks (the human chose no
exceptions — the spec simply scales down); human-picked winners among
parallel attempts (reopens human attention mid-protocol; the judge exists
precisely so that attention is spent once, at the end).

### ADR-013 — Framework seam: own the interface, adapt the implementation

**Status: ACCEPTED (2026-07-19; D.2 034).** CONTRACT for all harness-side
feature construction from H3 onward. Motivation: pydantic-ai v2 +
pydantic-ai-harness now cover real harness territory (capabilities,
history processors, provider compaction, CodeMode, fs/shell batteries,
cost tracking) — we want their institutional implementations without ever
waiting on them, and our differentiators must never be trapped inside
their API.

**The two-module law:**
1. Every harness feature is written against OUR minimal internal
   capability protocol (typed pydantic models: instructions, tools,
   lifecycle hooks, history transforms, event-stream taps) — defined in
   the harness repo, owned by us, versioned by us.
2. Exactly ONE adapter module translates our protocol ↔ pydantic-ai's
   capability machinery, in BOTH directions. Outbound: our features ship
   as standard pydantic-ai v2 `Capability` subclasses (MemoryCapability
   first), mountable by any vanilla pydantic-ai user — honoring ADR-002's
   bidirectional coupling. Inbound: upstream batteries are adopted
   individually, version-pinned, and wrapped behind the same protocol, so
   consumers cannot tell home-grown from adopted.
3. **Import fence (greppable):** nothing outside the adapter module
   imports pydantic-ai capability machinery. Swapping an implementation —
   ours for theirs when upstream matures, theirs for ours when 0.x churn
   breaks or stalls — touches only the adapter, never consumers.
4. **Wrap on first use** — no speculative wrapping of upstream's catalog
   (the "no speculative Rust" principle applied to adapters).

**Known adoption targets (through the seam, at their milestone):**
- `defer_loading=True` per capability when toolsets widen (M3) — opt-in,
  NOT automatic; collapses unused bundles to one-line catalog entries.
- CodeMode for fs/shell-heavy work (M3): one sandboxed program replaces
  per-call round-trips (~11 calls → ~2 on a 10-item fan-out). Adoption
  MUST preserve ADR-010's movement law: refresh-on-move fires at the tool
  boundary inside code-mode execution too.
- Provider compaction capabilities + ProcessHistory as the chassis for
  D.4's plan-mode compaction (M3).
- Cost-tracking battery (pairs with the D2 billing breaker).

**Rejected:** wholesale dependence on pydantic-ai-harness (0.x, breaking
minor releases); bypassing the seam for expedience; rebuilding commodity
batteries ourselves when upstream's are adoptable through the seam.

### ADR-014 — The prime loop: turn lifecycle, interruption & budgets

**Status: ACCEPTED (2026-07-19; D.2 037).** M1 implements the subset wired
by C.7 v1.12 (cancel, queue, snapshot, usage); the full law is CONTRACT for
the M3 harness buildout. This designs what ADR-007's draft list only named.

**Turn lifecycle.** A turn: context assembly (memory injection per C.6;
M3+ adds skills/files) → model call → tool execution → repeat until the
model yields or a limit trips → verify/report. Every turn is correlated by
run_id; every state change is an envelope event — the UI renders the loop
exclusively from the event stream, no side channels.

**Interruption (work preserved).** Cancel aborts the in-flight model call
and tool batch, keeps everything already produced, marks aborted tool
calls with a terminal cancelled state (history stays well-formed), and
returns control with stop_reason:"cancelled". Cancellation is always
confirmed by run.done — never fire-and-forget.

**The three-level send gesture (M3).** While a run is live the composer
stays active; sending escalates:
1. QUEUE — deliver after the run completes, as a new turn (M1 ships this).
2. STEER — inject into the running turn at the next tool boundary,
   cancelling the remainder of the current tool batch (run.steer).
3. INTERRUPT — stop now (run.cancel), keep partial work, redirect.
A visible queue with per-message edit/delete is part of the composer.

**Failure & retry.** Provider 429/5xx: bounded exponential backoff,
retries surfaced as events, never silent. A turn that dies on a terminal
provider error ends run.done{stop_reason:"error"} with partial output
preserved and labeled partial — the loop never fabricates completeness.

**Budgets are loop inputs.** Each run accepts request and token ceilings
(defaults in C.5: run_request_limit=40, run_total_tokens_limit=500000,
harness config); consumption streams via run.usage; breach is a DISTINCT
terminal status (stop_reason:"budget_exceeded"), rendered differently from
error. Enforcement seat: pydantic-ai UsageLimits through the ADR-013 seam.

### ADR-006 — Presence

**Status: PROPOSED**

- Every harness instance emits presence events: `{agent_id, machine_id,
  session_id, event: spawn|cwd_change|read|write|idle|exit, path, ts}`.
- "Location" = CWD (badge) + heat-decayed working set (recently touched paths).
- Events flow to `/v1/presence` and fan out on SSE; Postgres keeps a
  short-retention (24h) presence table — presence is ephemeral, not memory.
- **Transport (RESOLVED, was OQ-6):** presence rides the spine ("one spine,
  two schemas") in a segregated module with its own tables; extraction to a
  separate channel later is a deploy change, not a rewrite.

### ADR-009 — Visualization suite & mobile

**Status: ACCEPTED (2026-07-07, direction) / details PROPOSED**

Three named visualizations, all fed by data the spine already logs
(Invariant 10: every visual channel encodes a real variable):

1. **Context Bars** (per agent) [M2] — port of the existing Code Puppy
   context visualizer: category breakdown, compaction threshold line,
   compaction table; extended with a "memory" category for the injected
   block's share.
2. **Ant Farm** (per machine / fleet) [M3] — directory tree with agent badges
   at CWDs, heat-decay trails on touched paths; fed by ADR-006 events.
   (Spawn/exit animations excised: encoded nothing — Invariant 10.)
3. **Memory Graph** ("tesseract") [M2] — force-directed graph of memory
   units. Encodings (authoritative): node size = stats.injections; color =
   kind; brightness = recency; halo = pin; ghosted = quarantined; border
   pulse = injected in a live thread. Edge type A: cosine similarity ≥
   cfg.graph_edge_sim (default 0.75) — the SAME similarity used by
   dedup/scorer, so the picture is honest. Edge type B: revision lineage
   (merged_from / edit trail). Click node → CAS-safe edit flow. (Lasso/bulk
   actions excised from M2; may return with M3 maintenance workflows, which
   would give bulk operations a purpose.)
4. **Hyperparameter console** [M2] — adjacent to the graph: τ, top_k, budget,
   half-lives, seven weights, displayed and editable. Every change INSERTs a
   new scorer_config version and activates it; in-place mutation forbidden
   (manual tweaks stay comparable/auditable against learned versions via
   offline replay).

**Mobile:** the SPA is responsive from day one (hard requirement on all M1 UI
work; gate and chat must be phone-usable). PWA manifest + install flow [M3].
Chrome app mode remains the desktop packaging; no native builds.

---
---

# PART B — ROADMAP & SCOPE LAW

This part governs WHAT gets built WHEN. It overrides enthusiasm. If a task
appears to require a feature marked OFF or FORBIDDEN for the current
milestone, the implementing agent STOPS and flags the human — it does not
build ahead.

## B.1 Commitment tiers

- **COMMITTED (M1, M2):** build to acceptance criteria; deviation requires
  human sign-off.
- **DIRECTIONAL (M3):** sequenced and believed; formally re-planned after M2
  ships. Do not build M3 features during M1/M2.
- **HORIZON (M4, M5):** design constraints are BINDING (do not make these
  impossible); building them is FORBIDDEN. Committed footprint is exactly the
  ADR-011 list (revision ULIDs + parent_uid, event_uids, client-mintable IDs,
  `/v1/sync/*` reservation, cache schema mirroring). Nothing else.
- **Single-user assumption** holds through COMMITTED and DIRECTIONAL work.
  principal_id is a stamped column, not a feature. Auth = one static bearer
  token until horizon. Multi-principal anything: FORBIDDEN.

## B.2 Pillars & repositories

- **P1 — Memory** (repo `spine`, module memory): the harness-agnostic
  product. Units, revisions, scoring, injection, feedback log, learning,
  maintenance, (horizon: sync). The local cache is P1.
- **P2 — Harness** (repo `harness` + spine modules presence/relay): pydantic
  runtime, capabilities, daemon, WS envelope, command center web app —
  including ALL visualizers. **Visualization is a LAYER of P2, not a pillar.**
- **Deployment note (do not confuse):** the spine repo hosts three modules —
  memory (P1), presence (P2), relay (P2). Colocation is operational
  convenience; presence/relay must remain extractable.

ADR → pillar: 001 P2+policy · 002 P1↔P2 contract · 003 P1 · 004 P1 ·
005 P1 scorer+log / P2 gate UI · 006 P2 (deployed in spine) · 007 P2 ·
008 P2 · 009 P2 · 010 policy (provisioner horizon) · 011 P1 horizon
(schema footprint only in M1).

## B.3 Milestones

**M1 — core memory loop (COMMITTED):** chat with one agent in the browser;
memories accumulate (agent tool + /remember), curated at write time
(dedup/similar bands), injected through the gate; every event logged with
full context. Single machine, browser→localhost daemon (relay-shaped
envelope), spine on Cloud Run, hand-set weights. Minimal UI: thread list,
chat pane, gate modal, memory side panel. No visualizations beyond the gate.
**The M1 agent is chat + memory tools ONLY** — no fs/shell/skills/compaction/
HITL/durable execution (its acceptance criteria test nothing but the memory
loop; stock capabilities make these cheap to add when their milestone
arrives). Full build spec: Part C.

**M2 — learning loop + extraction (COMMITTED):** online weight updates per
ADR-005 table; scorer versioning + offline replay + rollback; per-feature
contribution bars in gate; citation heuristic; end-of-thread extraction with
approval queue; Context Bars port (+memory category); Memory Graph +
hyperparameter console.

**M3 — scale-out + harness buildout + curation + presence (DIRECTIONAL):**
cloud relay (multi-machine), harness parity (fs/shell/skills/compaction/HITL,
queuing/interjection, loops, subagents) + DBOS durable execution, maintenance
agent (clustering, dedup merge queue, promotion, staleness), memory_drafts
offline flow, Ant Farm, PWA install, hierarchical scorer offsets when data
justifies, Rust daemon if triggers fire.

**M4 — fleet expansion (HORIZON):** machine provisioner (ADR-010): leased
cloud workspaces as first-class machines, GCS snapshot lifecycle, spot
instances, parallel workspace fan-out.

**M5 — blue-water mode (HORIZON):** writable replica promotion, sync engine
(union/fast-forward/conflict queue), conflict review UI, local embedding
space, re-derivation pipeline, multi-principal soak test (ADR-011).

## B.4 Feature ledger

States: ON = build; SCHEMA = columns/namespace only, zero behavior;
OFF = later milestone; FORB = forbidden — flag if seemingly needed.

| Feature | M1 | M2 | M3 | M4/M5 |
|---|---|---|---|---|
| Chat loop, sessions, model-agnostic (incl. local via model string) | ON | ON | ON | ON |
| Memory CRUD + agent tools + /remember | ON | ON | ON | ON |
| Write-time dedup (dup/similar bands) | ON | ON | ON | ON |
| First-prompt gate + panel + removal reasons | ON | ON | ON | ON |
| Injection/feedback logging (full context) | ON | ON | ON | ON |
| Scorer: hand-set weights | ON | superseded | — | — |
| "never" bias + quarantine | ON | ON | ON | ON |
| Harness parity: fs/shell tools, skills, compaction, HITL, queuing, loops | FORB | FORB | ON | ON |
| Durable execution (DBOS) | FORB | FORB | ON | ON |
| Responsive SPA (phone-usable) | ON | ON | ON | ON |
| Online weight learning (global) | FORB | ON | ON | ON |
| Offline replay evaluation | OFF | ON | ON | ON |
| Scorer versioning + rollback + hyperparam console | OFF | ON | ON | ON |
| End-of-thread extraction + approval queue | FORB | ON | ON | ON |
| Context Bars (+memory category) | OFF | ON | ON | ON |
| Memory Graph | OFF | ON | ON | ON |
| Per-prompt re-scoring (OQ-15) | FORB | decide | — | — |
| Citation heuristic | OFF | ON | ON | ON |
| Cloud relay (multi-machine) | FORB* | OFF | ON | ON |
| Subagents, queue/interjection | OFF | OFF | ON | ON |
| Maintenance agent (cluster/dedup/promote/stale) | FORB | OFF | ON | ON |
| Pin-promotion by frequency | SCHEMA | OFF | ON | ON |
| Ant Farm + presence pipeline | SCHEMA | OFF | ON | ON |
| PWA install | OFF | OFF | ON | ON |
| memory_drafts offline flow | SCHEMA | OFF | ON | ON |
| Rust daemon rewrite | FORB | FORB | trigger-gated | trigger-gated |
| Machine provisioner / rented machines | FORB | FORB | FORB | M4 |
| Writable replica + sync engine + conflict UI | FORB | FORB | FORB | M5 |
| Local embedding space | FORB | FORB | FORB | M5 |
| Multi-principal (auth, sharing) | FORB | FORB | FORB | M5 |

*the envelope is relay-SHAPED in M1 (C.7) — that is ON; the cloud relay
itself is not built.

## B.5 Anti-scope rules for implementing agents

1. FORBIDDEN features: do not build, stub, scaffold, or "prepare for" beyond
   the explicit schema footprints in B.1.
2. When in doubt which milestone you are in: you are in M1.
3. A feature's SCHEMA state grants exactly the DDL in Part C — no handlers,
   no UI, no background jobs.
4. If an acceptance criterion seems to require an OFF/FORB feature, the spec
   has a bug: stop and report; do not resolve it by building.

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

---
---

# PART C — M1 IMPLEMENTATION SPEC (core memory loop)

This part is implementation-grade. Implementing agents follow it literally;
anything not specified here follows Part A; anything covered by neither gets
flagged back to the human, not improvised.

## C.1 Repositories

**Repo 1: `spine`** (name FIXED by the 1.0 vernacular; OQ-14 resolved — do
NOT rename; the GitHub remote's `memory-palace` label is cosmetic only)
```
spine/
  pyproject.toml            # python 3.12; fastapi, sqlalchemy[asyncio] 2.x,
                            # alembic, pgvector, asyncpg, httpx, pydantic v2
  src/spine/
    main.py                 # FastAPI app factory; mounts routers
    config.py               # pydantic-settings; all defaults from C.5
    db/                     # engine, session, models, alembic migrations
    memory/                 # router /v1/memories, /v1/search
    inject/                 # router /v1/inject/*, /v1/feedback; scorer.py
    embeddings/             # provider-pluggable embed(texts) -> vec[1536]
    events/                 # injection_event writer (SSE /v1/stream arrives in M2)
    auth.py                 # M1: single static bearer token (env SPINE_TOKEN)
  tests/                    # pytest + testcontainers postgres w/ pgvector
```
**Repo 2: `harness`**
```
harness/
  pyproject.toml            # python 3.12; pydantic-ai>=2, fastapi, websockets
  src/harness/
    daemon.py               # FastAPI: serves web/ static + WS /ws
    agent.py                # pydantic-ai v2 agent assembly (capabilities)
    memory_capability.py    # MemoryCapability (C.6)
    spine_client.py         # typed httpx client for spine API (C.4)
    tools_memory.py         # save_memory / search_memory / edit_memory tools
    envelope.py             # WS message envelope (C.7)
    config.py
  web/                      # React+TS+Vite SPA (chat, gate, memory panel)
  tests/
```
- Contract between repos: spine's generated OpenAPI is committed to spine repo
  (`openapi.json`); harness CI runs contract tests of `spine_client` against a
  spun-up spine container. Models are hand-mirrored pydantic classes (accepted
  duplication; two repos was a deliberate choice).

## C.2 Postgres DDL (authoritative)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE memory_unit (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  principal_id  TEXT NOT NULL,
  label         TEXT NOT NULL,                  -- <= 64 chars, unique per principal (partial idx, status='active')
  body          TEXT NOT NULL,                  -- <= cfg.memory_max_tokens (128) when tokenized;
                                                -- ATOMIC: one fact/preference/procedure step per unit
  kind          TEXT NOT NULL CHECK (kind IN
                ('fact','preference','procedure','project_note','persona','pinned')),
  keywords      TEXT[] NOT NULL DEFAULT '{}',
  embedding     vector(1536) NOT NULL,
  embedding_model TEXT NOT NULL,
  project_key   TEXT,                           -- NULL = global
  thread_origin TEXT,
  origin_path   TEXT,                           -- workspace-relative directory context at creation;
                                                -- NULL = no location. M1: inert metadata (D.2 030)
  pin           BOOLEAN NOT NULL DEFAULT FALSE,
  status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN
                ('active','quarantined','tombstoned')),
  revision      INTEGER NOT NULL DEFAULT 1,
  stats         JSONB NOT NULL DEFAULT '{"injections":0,"removals":0,"citations":0,"never_kills":0,"last_injected_at":null}',
  bias          REAL NOT NULL DEFAULT 0.0,      -- b_m
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON memory_unit USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON memory_unit (principal_id, status, project_key);
CREATE UNIQUE INDEX memory_unit_active_label ON memory_unit (principal_id, label)
  WHERE status = 'active';                      -- labels are handles: unique among
                                                -- ACTIVE units; tombstone/quarantine
                                                -- frees the label for reuse

CREATE TABLE memory_revision (                  -- append-only "update history" index
  rev_uid     TEXT PRIMARY KEY,                 -- client-mintable ULID (ADR-011)
  parent_uid  TEXT REFERENCES memory_revision(rev_uid),  -- lineage DAG; NULL = root
  memory_id   UUID NOT NULL REFERENCES memory_unit(id),
  revision    INTEGER,                          -- cloud-head CAS counter only; NULL on divergent branches
  body        TEXT NOT NULL,
  label       TEXT NOT NULL,
  editor      TEXT NOT NULL,                    -- 'user' | 'agent:<agent_id>' | 'maintenance'
  origin_machine_id TEXT NOT NULL,
  reason      TEXT NOT NULL DEFAULT '',
  ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON memory_revision (memory_id, ts);

CREATE TABLE thread (
  id              UUID PRIMARY KEY,
  principal_id    TEXT NOT NULL,
  agent_id        TEXT NOT NULL,
  machine_id      TEXT NOT NULL,
  project_key     TEXT,
  snapshot_ts     TIMESTAMPTZ,                  -- set by first inject/prepare
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE injection_event (                  -- append-only training log
  id            BIGSERIAL PRIMARY KEY,
  event_uid     TEXT NOT NULL UNIQUE,           -- client-minted ULID; union-safe upload (ADR-011)
  injection_id  UUID NOT NULL,
  thread_id     UUID NOT NULL,
  agent_id      TEXT NOT NULL,
  machine_id    TEXT NOT NULL,
  principal_id  TEXT NOT NULL,
  project_key   TEXT,
  agent_kind    TEXT NOT NULL DEFAULT 'general',
  prompt_text   TEXT NOT NULL,                  -- full text; own infra, needed for replay
  scorer_version TEXT NOT NULL,
  memory_id     UUID NOT NULL,
  memory_kind   TEXT NOT NULL,
  features      JSONB NOT NULL,                 -- {sem,kw,time,proj,freq,hist}
  score         REAL NOT NULL,
  rank          INTEGER NOT NULL,
  shown_as      TEXT NOT NULL CHECK (shown_as IN ('injected','near_miss','pinned')),
  outcome       TEXT,                           -- NULL until commit/feedback:
                -- kept | removed:not_relevant | removed:wrong | removed:never
                -- | added_back | cited | mid_thread_removed
  ts            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON injection_event (injection_id);

CREATE TABLE scorer_config (
  version     TEXT PRIMARY KEY,                 -- 'v0'
  weights     JSONB NOT NULL,
  params      JSONB NOT NULL,                   -- tau, top_k, near_miss_k, half_lives...
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  active      BOOLEAN NOT NULL DEFAULT FALSE
);
```
Rules: UPDATEs on memory_unit require `WHERE revision = :expected` and bump
revision + write memory_revision, all in one transaction; conflict → HTTP 409
with current unit in body. Tombstone = status change, never DELETE.

## C.3 Scorer v0 (hand-set)

For prompt q and candidate m (status='active', principal match, and
(project_key IS NULL OR project_key = thread.project_key)):

- f_sem  = max(0, cosine(embed(q), m.embedding))            ∈ [0,1]
- f_kw   = |kw(q) ∩ (m.keywords ∪ tokens(m.label))| / max(1,|kw(q)|), kw = lowercased
           non-stopword tokens; cap at 1.0
- f_time = 2^(−age_days(m.updated_at)/14)
- f_proj = 1.0 if m.project_key = thread.project_key else (0.5 if m.project_key IS NULL else 0.0)
- f_freq = min(1.0, m.stats.citations / 10)   (inert in M1: citations arrive with the M2 heuristic)
- f_hist = 2^(−days_since_last_human_edit/7); 0 if never human-edited
- score  = 0.42·f_sem + 0.16·f_kw + 0.11·f_time + 0.16·f_proj
         + 0.08·f_freq + 0.07·f_hist + m.bias
- Candidates: top 50 by vector similarity → score all → injected = top k≤8 with
  score ≥ τ=0.55, subject to token budget min(3000, 5%·model_ctx) (greedy by
  score; a memory that would exceed budget is skipped, next tried).
- near_misses = next 3 below the injected set regardless of τ.
- pinned units (pin=TRUE) bypass scoring, always injected first, count against
  budget, shown_as='pinned'.
- M1 sets `bias` only via removed:never (−0.15 each, quarantine at
  never_kills≥3). No other learning in M1; everything else is logged only.

## C.4 Spine API (M1 surface, exact bodies)

Auth: `Authorization: Bearer $SPINE_TOKEN` on all routes. Errors: RFC7807 JSON.

POST /v1/inject/prepare
  req: {thread_id, agent_id, machine_id, principal_id, project_key?,
        agent_kind?, prompt, model_context_tokens}
  beh: create thread row if new (sets snapshot_ts=now()); embed prompt;
       candidates read as-of thread.snapshot_ts (latest revision ≤ snapshot_ts);
       write injection_event rows (outcome NULL); update stats.injections.
  res: {injection_id, snapshot_ts, scorer_version,
        injected: [MemoryCard], near_misses: [MemoryCard]}
  MemoryCard: {memory_id, label, body, kind, pin, score,
               features: {sem,kw,time,proj,freq,hist}, rank}
  MemoryUnit (shared shape; the C.2 row minus embedding):
    {memory_id, principal_id, label, body, kind, keywords, project_key,
     thread_origin, origin_path, pin, status, revision, stats, bias,
     embedding_model, created_at, updated_at}
  MemoryCard.score/features/rank are populated only by inject/prepare; in
  dedup and /v1/search responses score = cosine similarity, features/rank null.

POST /v1/inject/commit
  req: {injection_id,
        removed: [{memory_id, reason: "not_relevant"|"wrong"|"never"}],
        added_back: [memory_id]}
  beh: set outcomes (kept for the untouched injected set); apply
       removed:never bias/quarantine rule; reason "wrong" additionally returns
       the unit so the UI can open the edit flow.
  res: {final_block: string,        # the exact rendered block (C.6) the harness injects
        wrong_removed: [MemoryUnit]} # current unit for each removed:"wrong" so the
                                     # UI opens the edit flow with a valid
                                     # expected_revision; [] when none

POST /v1/feedback            # mid-thread, ad-hoc
  req: {injection_id, memory_id, signal: "mid_thread_removed"|"cited"}
  res: {ok: true}

POST /v1/memories
  req: {principal_id, label, body, kind, keywords?,
        project_key?, thread_origin?, origin_path?, editor, machine_id,
        force?: bool = false}
  beh: label check first: another ACTIVE unit of principal with this label →
       409 {label_conflict: {memory_id, label}} (force does not override;
       tombstoned/quarantined labels are reusable — see C.2 partial index);
       embed; dedup check vs active units of principal:
       max cosine ≥ 0.92 → 409 {duplicate_of: MemoryCard} (force does NOT
         override a hard duplicate; the caller's move is editing that unit);
       0.80–0.92 and force=false → 200 {created: null, similar: [MemoryCard...]}
         (caller decides, may retry with force=true; force skips ONLY this band);
       else insert (revision 1 + memory_revision row,
         origin_machine_id = machine_id).
  res: 201 {created: MemoryUnit}

PATCH /v1/memories/{id}
  req: {expected_revision, body?, label?, keywords?, kind?, pin?, status?,
        origin_path?, editor, reason, machine_id}
  beh: CAS per C.2 rules; the revision row gets origin_machine_id = machine_id;
       a label change colliding with another active unit → 409 {label_conflict}
       as on create.
  res: 200 MemoryUnit | 409 {conflict: MemoryUnit}   # current unit, per C.2 rules

GET  /v1/memories?project_key=&status=&q=&limit=&offset=
  beh: panel list; limit default 50 max 200, offset default 0;
       ordered by updated_at DESC, memory_id ASC (stable paging).
  res: {items: [MemoryUnit], total, limit, offset}
POST /v1/search             req: {principal_id, query, k=10, project_key?}
                            res: {results: [MemoryCard]}  (agent tool backend)

## C.5 Config defaults (single source: spine config.py / harness config.py)

tau=0.55, top_k=8, near_miss_k=3, budget_tokens=3000, budget_pct=0.05,
half_life_time_days=14, half_life_hist_days=7, dedup_dup=0.92, dedup_sim=0.80,
never_bias_step=-0.15, quarantine_kills=3, candidate_pool=50,
embed_model="text-embedding-3-small" (dim 1536, provider-pluggable),
memory_max_tokens=128, label_max=64.
run_request_limit=40, run_total_tokens_limit=500000 (harness; ADR-014).
Chat model defaults: development/testing `openrouter:minimax/minimax-m3`
(verified live 2026-07-19; ≈$0.30/M in, $1.20/M out); flagship
`anthropic:claude-sonnet-4-6` for real use; OpenRouter configured as the
any-model escape hatch; keys (Anthropic, OpenAI, OpenRouter) live in
harness/.env (untracked; .env.example is the shape); model selectable per
thread.

## C.6 MemoryCapability (harness) — exact flow

First prompt in thread:
 1. User hits send → daemon calls inject/prepare (prompt is NOT yet sent to model).
 2. WS `gate.open` → UI modal: injected rows show label + FULL body (memories
    are atomic ≤128 tokens by design; no summaries, no expand step) + score;
    one-tap ✕ = not_relevant; long-press/alt-✕ menu: wrong / never; grayed
    near-misses (tap = add back); Enter/"Continue". Hard pause, no timeout
    (per ADR-005). ACCEPTED in review 2026-07-07.
 3. On continue → inject/commit → spine returns final_block.
 4. Capability prepends final_block system-adjacent; run starts.
Subsequent prompts: no prepare/no gate in M1 (one injection per thread;
per-prompt re-scoring is an M2 decision — OQ-15). Memory panel stays live:
✕ on a memory → /v1/feedback mid_thread_removed → block re-rendered without it
from the next model call.

Rendered block format (final_block):
```
<memory_system>
The following long-term memories were retrieved for this conversation.
Treat them as your own accumulated knowledge; they may be imperfect.
<memory label="..." kind="..." updated="ISO8601">
[body]
</memory>
...
</memory_system>
```

Agent tools (tools_memory.py; docstrings are the model-facing spec):
- save_memory(label, body, kind, keywords?, project_scoped: bool)
  → handles 409/similar responses by surfacing them to the model
    ("similar memory exists: ...; update it, or call again with force=true").
- search_memory(query, k=5) → MemoryCards rendered compactly.
- edit_memory(label_or_id, new_body, reason) → CAS retry once on 409.
Agent instructions addition (verbatim, part of capability):
  "Save a memory when you learn a durable user preference, a correction to
   something you got wrong, a stable project fact, or a procedure the user
   wants repeated. Keep every memory ATOMIC: one fact per unit, at most a
   few sentences (hard cap 128 tokens); split larger content into multiple
   units. Prefer editing an existing memory over creating a near-duplicate.
   Never save secrets or credentials."
User command: `/remember <text>` → daemon calls POST /v1/memories with
kind=fact, editor='user', label auto-generated by the agent model (one short
completion), then confirms in chat.

## C.7 WS envelope (relay-shaped from day one)

All daemon↔browser messages:
```
{v:1, id: ulid, ts, machine_id, agent_id?, thread_id?, type, payload}
```
M1 types (as amended v1.12 — D.2 037):
- thread.create, prompt.submit, gate.open, gate.commit, run.delta, run.done,
  memory.panel.update, error — as before, plus the field requirements below.
- run.started (D→C): acks prompt.submit; payload {run_id}. Every subsequent
  run.* / gate.* payload carries that run_id.
- run.cancel (C→D): request clean abort. The daemon aborts model work,
  dismisses any open gate, and ALWAYS answers with
  run.done{stop_reason:"cancelled"} — cancellation is confirmed, never
  fire-and-forget.
- prompt.submit received mid-run is NOT an error: the daemon acks with
  prompt.queued (D→C) and delivers the prompt as a fresh turn when the
  current run ends (M1 queues to the turn boundary; mid-turn steering is
  reserved for M3 — ADR-014).
- thread.snapshot (D→C): authoritative full resync — message history, open
  gate, active-run state — sent on WS (re)connect for the active thread and
  on request; the UI hydrates from snapshots, never from replayed deltas.
- run.usage (D→C): incremental {requests, input_tokens, output_tokens}
  during a run.
- gate.dismiss (D→C): the daemon withdraws an open gate (e.g. its run was
  cancelled); the UI must close the modal.
Field requirements: run.done carries stop_reason ∈ end_turn | cancelled |
error | budget_exceeded. run.delta payload is a discriminated union
{kind: text | thinking | event, ...} (AG-UI events pass through under
kind:"event"). gate.open carries kind (M1: always "memory_gate") so the
gate generalizes to tool approval / elicitation / plan review in M3.
RESERVED M3 type names (relay and clients MUST forward/ignore unknown
types unchanged): run.steer, plan.update, checkpoint.created,
checkpoint.restore, presence.update. The relay in M3 forwards all types
unchanged; nothing in the UI may assume localhost.

## C.8 M1 acceptance criteria

1. Fresh clone → `docker compose up` (spine+postgres) + `harness dev` →
   browser chat works end to end with any pydantic-ai model string.
2. Telling the agent a preference results in a memory (visible in panel) and
   a 409/similar path is demonstrable by repeating it.
3. New thread on a related topic → gate shows that memory with per-feature
   scores; removing it as "not relevant" logs outcome and it is absent from
   final_block; near-miss add-back works and is logged.
4. "never" removal 3× quarantines the unit (stops appearing).
5. /remember works; edit via panel bumps revision and memory_revision row.
6. injection_event table replays: every gate interaction reconstructable
   (features, prompt_text, scorer_version, outcome) — verified by a test.
7. Kill spine mid-thread → daemon surfaces a clear error; chat without
   injection still functions (memory failures never brick the harness).

## C.9 M1 Judge Protocol (concrete checklist; expands C.8 per B.6)

Judge persona: "the owner opens the product for the first time." Every J-item
records experiential + traced + (where named) adversarial evidence under
`verification/m1/`.

- **J0 — Scope & journal audit.** Every DECISIONS.md entry in both repos
  cites a tree node. Grep for FORBIDDEN code (weight updates, extraction,
  relay client, maintenance jobs, multi-principal auth). Any hit: FAIL.
- **J1 (AC1) — Cold start.** Fresh clone both repos → `docker compose up` +
  `harness dev` → browser loads chat. Screenshot: empty state. Send "hello"
  on the default model; screenshot streamed reply. Switch the thread to an
  OpenRouter model string; one exchange. Trace: thread row exists; run.delta
  envelopes in daemon log carry the C.7 shape.
- **J2 (AC2) — Accumulation & curation.** Tell the agent a durable
  preference ("I prefer tabs over spaces"). Screenshots: agent acknowledges;
  panel shows the new memory (label + full body ≤128 tokens). Trace:
  memory_unit row (revision 1, embedding NOT NULL), memory_revision root
  (parent_uid NULL, editor 'agent:<id>'). Re-state the same preference in
  fresh words → screenshot the agent handling the similar/duplicate path.
  Trace: 409 or similar[] response in spine log.
- **J3 (AC3) — The gate, end to end.** New thread on a related topic.
  Screenshot: gate open, that memory present with per-feature scores;
  near-misses grayed. Remove one as not_relevant; add one near-miss back;
  continue. Trace: injection_event outcomes = removed:not_relevant /
  added_back / kept, features JSONB populated, scorer_version='v0'; the
  final_block in the daemon log excludes the removed unit and includes the
  added one. Cross-check: injection_id on screen == rows traced.
- **J4 (AC4) — Quarantine.** Across three fresh threads, remove the same junk
  memory with "never." Screenshots of each modifier menu. Trace:
  stats.never_kills increments to 3, bias steps −0.15 each, status flips to
  'quarantined'. Fourth thread: gate screenshot proves absence; prepare
  response traced without it.
- **J5 (AC5) — Human hands.** `/remember` a fact → screenshot confirmation +
  panel. Edit a memory body in the panel → trace: revision bumped,
  memory_revision row with editor='user', parent_uid = prior head. Force a
  CAS conflict (stale expected_revision via curl) → 409 traced, UI surfaces
  fresh state, no silent overwrite.
- **J6 (AC6) — Replay integrity.** Run the replay test suite; then manually:
  pick J3's injection_id, SELECT its events, and reconstruct the gate the
  judge saw — memories, scores, outcomes must match J3's screenshots
  one-for-one. This is the log-through-functionality trace.
- **J7 (AC7) — Adversarial: memory death.** Mid-thread, kill the spine
  container. Screenshots: clear error surfaced; chat continues functioning.
  Start a NEW thread: proceeds memoryless with visible warning (default
  stands). Trace: daemon logs graceful degradation, zero stack-trace crashes.
  Restart spine; next thread's gate works.
- **J8 — Mobile.** Repeat J3 at 390×844. Screenshots: gate readable, full
  bodies visible, one-tap remove and near-miss add work by tap, chat usable.

Verdict file: `verification/m1/VERDICT.md` — J0–J8 → PASS/FAIL → evidence
paths → tree nodes. All PASS = M1 done.

## C.10 Agent Zero — the n=0 bootstrap charge (verbatim; paste as the first /goal)

```
You are Agent Zero, the groundskeeper. You prepare the environment; you
build NO features. Your successors are gardeners; your job is dirt, water,
and fences.

READ FIRST, fully, in order: docs/SPEC.md sections 1 -> 2 -> B -> C.
You are governed by its CONTRACTS (1.4), the feature ledger (B.4), and the
Blight Protocol (2.1). The ledger's FORBIDDEN column applies to you
absolutely: scaffolding only, zero business logic.

TASKS
1. Create two git repositories per C.1: `spine` and `harness`, with exactly
   the listed skeletons. Commit the current spec into each at docs/SPEC.md
   with its version noted (frozen reference copy).
2. Prime DECISIONS.md in each repo:
   - Entry 000: "Read docs/SPEC.md 1 -> 2 -> B -> C before touching dirt.
     Every entry in this journal cites a Problem Tree node. Local defects
     follow the Blight Protocol (SPEC 2.1). Features that cannot name their
     problem do not get built."
   - Entry 001: your own bootstrap decisions (tooling choices etc.), each
     citing node P4.
3. spine: pyproject (deps per C.1); docker-compose.yml (postgres:16 +
   pgvector, spine service); alembic initialized with the FULL C.2 DDL as
   migration 0001; config.py with every C.5 default; seed row
   scorer_config('v0', C.3 weights/params, active=true); routers for every
   C.4 endpoint returning 501 with an RFC7807 body naming the endpoint;
   /healthz returning {ok, version}; auth middleware (static bearer);
   pytest + testcontainers wired with one passing test (migration applies,
   healthz 200, 501s are 501).
4. harness: pyproject (deps per C.1); daemon.py serving web/ static + WS /ws
   echoing valid C.7 envelopes (type 'error', payload 'not implemented');
   envelope.py with the C.7 schema as pydantic models + tests;
   spine_client.py typed stubs mirroring C.4 bodies; web/: Vite React TS
   scaffold rendering a placeholder shell (responsive, 390px sane);
   .env.example (SPINE_TOKEN, ANTHROPIC/OPENAI/OPENROUTER keys, model
   default per C.5).
5. Create verification/ in both repos with a README quoting B.6.
6. CI stub in each: lint + tests; harness CI includes a contract-test job
   skeleton targeting a spine container.

WHERE THE SPEC IS SILENT on scaffolding minutiae (linter, formatter, port
numbers), decide in the spirit of the Invariants, record in DECISIONS.md
citing P4. Where a decision would touch a CONTRACT: if it qualifies as a
COMPLETION (1.4), enact it via garden/AMENDMENTS.md and proceed; otherwise
stop and flag the human.

EXIT CRITERIA (self-verify, evidence in verification/bootstrap/):
- `docker compose up` boots postgres + spine; /healthz 200; migration clean.
- `harness dev` serves the shell; WS echo works; envelope tests pass.
- Both DECISIONS.md primed; spec copies committed; CI green on the stubs.

FINISH by writing BOOTSTRAP_REPORT.md at each repo root: what exists, what
is stubbed (every 501), and the exact C-section where the next agent begins
(C.2 rules -> C.4 memory endpoints first). You are done when a gardener can
start planting without asking where anything is.
```

---
---

# APPENDIX

## D.1 Open questions (all currently open items; everything else is folded
into its owning ADR above)

- **OQ-4:** Maintenance dedup merges — auto-merge above high similarity,
  queue the rest (leaning) vs fully automatic. [decide before M3]
- **OQ-5:** Citation signal — n-gram heuristic (M2 v1) vs LLM judge (cost).
  [M2]
- **OQ-12:** Localhost fallback page for offline prompt entry — which
  milestone. [M3 planning]
- **OQ-15:** Per-prompt re-scoring within a thread (gate-less, panel-only)
  vs once per thread. M1 deliberately ships once-per-thread. [M2 decision]

## D.2 Decision log (chronological, immutable)

| # | Date | Decision | Status |
|---|------|----------|--------|
| 001 | 2026-07-07 | Pydantic AI v2, Code Puppy as donor | ACCEPTED |
| 002 | 2026-07-07 | Memory = HTTP service + MemoryCapability | PROPOSED |
| 003 | 2026-07-07 | Cloud Run + Cloud SQL pgvector; degraded read-only offline | ACCEPTED |
| 004 | 2026-07-07 | CAS revisions, tombstones, thread snapshots, pin-promotion | PROPOSED |
| 005 | 2026-07-07 | Linear scorer; one-tap removal = "not relevant"; near-misses | PARTIAL |
| 006 | 2026-07-07 | Presence rides memory service (segregated module) | PROPOSED |
| — | 2026-07-07 | Memory block placement: system-adjacent | PROPOSED |
| — | 2026-07-07 | Durable execution: pydantic-ai API + DBOS on same Postgres | PROPOSED |
| 008 | 2026-07-07 | Web command center, no TUI; harness daemon; relay-through-spine | ACCEPTED |
| — | 2026-07-07 | M1 vertical slice: hand-set weights + full logging; learning in M2 | PROPOSED |
| 009 | 2026-07-07 | Pure relay topology; AG-UI events inside daemon | ACCEPTED |
| 010 | 2026-07-07 | Learning scope: context-rich logs (M1) → global (M2) → hierarchical offsets (M3) | ACCEPTED |
| 011 | 2026-07-07 | Two repos: `spine` and `harness` (web UI lives in harness) | ACCEPTED |
| 012 | 2026-07-07 | M1 re-scoped to core memory loop; visuals deferred | ACCEPTED |
| 013 | 2026-07-07 | M1 accumulation = agent tool + /remember; auto-extraction = M2 | PROPOSED |
| 014 | 2026-07-07 | M1 browser→localhost daemon with relay-shaped envelope | ACCEPTED |
| 015 | 2026-07-07 | Review R1: gate + once-per-thread confirmed; memories atomic ≤128 tok, no summary field, gate shows full bodies | ACCEPTED |
| 016 | 2026-07-07 | Viz suite: Context Bars / Ant Farm / Memory Graph + hyperparam console; every channel encodes data; scorer tweaks versioned | ACCEPTED |
| 017 | 2026-07-07 | Responsive SPA from day one; PWA in M3; mobile is the web app | ACCEPTED |
| 018 | 2026-07-07 | ADR-001 amended: polyglot-by-boundary; Rust daemon pre-approved with triggers; no speculative Rust | ACCEPTED |
| 019 | 2026-07-07 | ADR-010: workspace-anchored fleet; cloud agents = rented machines; provisioner M4; colocation-for-latency rejected | ACCEPTED |
| 020 | 2026-07-07 | ADR-011: sailing end-state; Git owns workspaces; per-unit 3-way merge; logs union; learned state re-derived; ULID revisions + event_uids in M1 schema; M5 blue-water | ACCEPTED |
| 021 | 2026-07-07 | Scope law: commitment tiers; two pillars, viz = layer of P2; feature ledger with FORBIDDEN state; single-user through M3 | ACCEPTED |
| 022 | 2026-07-07 | Spec reorganized to v1.0 (pillar-grouped ADRs, invariants, scope law, appendix); content-preserving; ADR-004 Part-I schema drift removed (Part C DDL is sole authority) | ACCEPTED |
| 023 | 2026-07-07 | Excisions: f_sess feature, description column, ant-farm animations, graph lasso, plan-mode compaction (parked), M1 SSE. Demotions: M1 agent = chat + memory tools only; harness parity + DBOS → M3 | ACCEPTED |
| 024 | 2026-07-07 | Normativity model (1.4): CONTRACTS followed literally; GUIDANCE followed by reasoning with recorded deviations in DECISIONS.md; ADR style law | ACCEPTED |
| 025 | 2026-07-07 | Problem Tree (§2): nested problem→solution lineage with citable node IDs; Blight Protocol (locate deepest node, treat locally, escalate landscaping); feature-attachment corollary | ACCEPTED |
| 026 | 2026-07-07 | Founding-prompt audit: all original objects verified represented; ADR-002 coupling made explicitly bidirectional; f_sess divergence recorded in D.4 with resurrection condition | ACCEPTED |
| 027 | 2026-07-07 | Verification doctrine (B.6): experiential + traced + adversarial evidence, judge/builder separation, verdict artifacts, judgeable scope audit; M1 checklist J0–J8 (C.9); Agent Zero verbatim charge (C.10) | ACCEPTED |
| 028 | 2026-07-17 | v1.5 human-gate amendment resolving Garden F001–F005: active-label partial unique index + label_conflict 409 (F001); force flag on create, similar-band only, never overrides ≥0.92 (F002); machine_id on create/PATCH → origin_machine_id (F003); commit returns wrong_removed: [MemoryUnit] (F004); MemoryUnit shape + limit/offset paging + PATCH 200/409 bodies (F005); create returns MemoryUnit; card score = similarity in dedup/search | ACCEPTED |
| 029 | 2026-07-17 | Normativity (1.4) gains COMPLETION class: agents self-resolve silent/self-inconsistent contract details by enacting exact-diff entries in garden/AMENDMENTS.md — law for later agents and the judge, human audit-with-veto between sessions (veto → FIXER). Hard FLAG reserved for Invariants, FORBIDDEN rows, auth/data-loss, ADR reversals, changes to DONE-packet behavior, and genuine design forks. Motivated by F001–F005 all being qualifying completions that stopped the line | ACCEPTED |
| 030 | 2026-07-19 | v1.6 location law: origin_path on memory_unit + C.4 surfaces (M1 inert metadata; S5 packet); f_loc = 2^(−hops/h_loc) directory distance with weight renormalization when location is null (no-penalty CONTRACT); movement law — agents must cd to a file's directory to work on it, every move refreshes injected memories (CONTRACT from the M3 fs milestone) | ACCEPTED |
| 031 | 2026-07-19 | Command center primary interaction = flashcard deck: one card per top-level agent in its fleet color (shared across all visualizers), completion-time FIFO, respond-to-advance, manual deck cycling; card expands to thread view with a line-per-human-input scrubber; gallery mode (≤4 multiplexer tiles) secondary; sub-agents card-less, visualizer-only | ACCEPTED |
| 032 | 2026-07-19 | v1.7 ADR-012 work protocol: ALL project work = spec alignment → agent loop (system-sized N parallel worktree attempts ≤ max_parallel_project_agents) → independent judge (COMPLETE → deck card; else continuation agent; picks swarm winner, may graft) → human. Judge triages blockers; interjection solo-run only, watching always; no size exceptions — the spec scales down instead | ACCEPTED |
| 033 | 2026-07-19 | v1.8 config: dev/test chat default openrouter:minimax/minimax-m3 (live-verified; sonnet remains flagship); D1 executed — GCP project n8-memory-palace (us-central1), Cloud SQL Postgres 16 + pgvector (db-f1-micro), Cloud Run spine, $100/mo budget with 50/90/100% alerts; /v1/search (only remaining 501) assigned to new packet S6 | ACCEPTED |
| 034 | 2026-07-19 | v1.9 ADR-013 framework seam: internal capability protocol + single bidirectional adapter to pydantic-ai v2; import fence outside the adapter; wrap-on-first-use; outbound features ship as standard Capability subclasses (MemoryCapability first at H3); adoption targets — defer_loading (opt-in), CodeMode (must preserve movement-law refresh), ProcessHistory compaction chassis, cost tracking. Never blocked on upstream; 0.x churn contained in the adapter | ACCEPTED |
| 035 | 2026-07-19 | v1.10 vernacular (1.0): Memory Palace = memory product (db + curation algorithms + M3 curator; the spine's memory module, extractable); spine = always-on backbone housing the Palace + connective modules; Harness = local product; Garden = governance; relay = methodology (vs spine's relay module); heart = description not name; local dir names load-bearing, remote names labels | ACCEPTED |
| 036 | 2026-07-19 | v1.11 deconflict pass: OQ-14 resolved — repo names fixed by 1.0, C.1's "cosmetic rename allowed" removed (do NOT rename); vision §0 and Invariant 1 aligned to Palace/spine wording. Full-term audit found no other conflicts: "heart" reads as description throughout, relay methodology/module disambiguated by 1.0. No semantic change | ACCEPTED |
| 037 | 2026-07-20 | v1.12 after 3-agent harness-field survey: C.7 gains run.started/run.cancel (confirmed)/prompt.queued/thread.snapshot/run.usage/gate.dismiss, stop_reason on run.done, typed run.delta, gate.open kind field, reserved M3 names (run.steer, plan.update, checkpoint.*, presence.update); ADR-014 prime loop — interruption preserves work, three-level send gesture (queue M1 / steer / interrupt M3), budgets as loop inputs with distinct terminal status (C.5: run_request_limit=40, run_total_tokens_limit=500k); H7 packet implements the M1 subset before H4. Permissions + sessions ADRs deferred pending human discussion | ACCEPTED |
| 038 | 2026-07-20 | v1.13 Invariant 14 LEAST ATTENTION codified as core philosophy: attention is the scarcest resource and the architecture decides when it is spent; walls not questions (per-action approvals inside the sandbox are forbidden theater); pulls only at boundary crossings + judge releases, once, at highest leverage; all watchable, almost nothing demands. Ground-rules template gains rule 9 so every relay agent boots into it | ACCEPTED |

## D.3 Resolved-question index (where each folded)

OQ-1 block placement → ADR-002 · OQ-2 offline mode → ADR-003 · OQ-3 mid-thread
live reads → ADR-004 · OQ-6 presence transport → ADR-006 · OQ-7 durable
execution → ADR-001 · OQ-8 framework → ADR-001 · OQ-9 web command center →
ADR-008 · OQ-10 M1 slice → B.3 · OQ-11 identity → ADR-008 · OQ-13 pure relay →
ADR-008 · OQ-16 providers/models → C.5 · OQ-14 repo/product names → 1.0
vernacular (v1.10)

## D.4 Parked ideas (not scope; preserved thinking)

- **Plan-mode compaction** (original proposal sheet): on compaction, save
  context → strongest available model summarizes → summarizer asks the user
  1–4 clarifying questions before the thread continues. Interesting,
  unproven; revisit when compaction (M3) has real usage. Implementation
  chassis when it comes: the ADR-013 seam over pydantic-ai ProcessHistory
  (+ harness summarization batteries).
- **Memory Graph lasso/bulk actions:** revisit with M3 maintenance workflows.
- **Gate near-miss count/e-greedy exploration:** deliberately not designed;
  the near-miss mechanism already provides mild exploration.
- **Session-affinity feature (f_sess):** present in the founding memory-index
  list; excised 2026-07-07 as a conscious divergence (near-always zero at the
  only moment scoring occurs). `thread_origin` metadata is preserved on every
  unit. Resurrection condition: M2 logs show resumed-thread patterns where
  session affinity would have changed rankings.
