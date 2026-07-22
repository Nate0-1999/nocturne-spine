# NOCTURNE — Harness + Memory Palace Specification

**Version 2.7** (2026-07-22) — gate-day data + v0.2 proposal adoptions: hybrid candidate retrieval, keywords mandate, training-data hygiene, curator consolidation taxonomy + typed edges, promotion blend, candidate status (D.2 050). Prior v2.6: OQ-17 resolved (roots alpha = selection focus); ADR-019 seed ingestion; nocturne-* remotes + splash repo (D.2 049). Prior v2.5: B.6 rule 8 agent walkthroughs (D.2 048). Prior v2.4: NOCTURNE christened; ADR-019 onboarding; ADR-020 shared Palaces (D.2 046–047). Prior v2.3: broker-routed embeddings (D.2 044). Prior v2.2: themes (D.2 043). Prior v2.1: procedural law (D.2 042). Prior v2.0: EDITOR PASS: content-preserving consolidation of the v1.5–v1.15 organic growth. New/amended law: ADR-012 mode scale, ADR-015 walls, ADR-016 tree, ADR-017 Symphony, ADR-018 Cube+plugins+stack, ADR-007→index, ADR-008 stack resolved; enacted amendments A-001–A-017 folded into Part C (AMENDMENTS.md remains the historical record); D.1 refreshed. Full version lineage: Appendix D.2. Prior v1.4 (2026-07-07) was reorganized from the v0.x iteration transcript;
content-preserving. Audience: implementing agents (via /goal) and the human owner.
Everything here is binding unless marked OPEN or given a non-accepted status.
ADR numbers are immutable; superseding requires a new ADR. The chronological
history of every decision is Appendix D.2.

**Reading guide:** Section 1 is the whole system in one page; Section 2 is
the Problem Tree — the why-lineage from root pain to atomic build element,
and the Blight Protocol for local defects. Part A holds the architecture
decisions (grouped by pillar, not by the order we argued them). Part B is
roadmap + scope law. Part C is the literal build spec for M1. Implementing
agents: read 1 → 2 → B → C, consult A when deeper rationale is needed;
packets touching user-facing surface also read garden/NATES_VISION.md
(GUIDANCE per 1.4); cite tree node IDs in DECISIONS.md. Loops begin with Agent Zero (C.10) and end
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

- **NOCTURNE** — the product entire: the Harness and the Memory Palace as
  one instrument, named 2026-07-20 (D.2 046) — night music: the agent
  plays through the night so the composer hears the premiere in the
  morning. The install name (`pipx install nocturne`, ADR-019) and the
  front door; every component name below is unchanged beneath it.
- **The Escher view** — the Cube's formal name (ADR-018): six projections
  of one object no single face can fully show.
- **The Chrysopoeia** — the learning loop (ADR-005 signals → M2 weight
  learning): the transmutation of gate decisions into scorer gold.
- **A shared Palace** — a team's combined memory palace, built by
  selective contribution from personal Palaces (ADR-020, HORIZON).
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
- **Repo mapping:** local `spine/` (remote `nocturne-spine`), `harness/`
  (remote `nocturne-harness`), `garden/` (remote `nocturne-garden`);
  `nocturne` is the SPLASH repo — the single front door for new users
  (quickstart lands there with D3). Renamed to the nocturne-* family
  2026-07-21; GitHub redirects the old labels. Local directory names are
  load-bearing law; remote names are labels.

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
promotion does NOT write to agents.md/user.md. It flips
`pin=true` (always injected, exempt from scoring, still user-removable in the
gate → unpins). The "does not manipulate sessions/skills/agents.md" invariant
holds. Automatic promotion logic: M3; manual pinning: free from M1. The M3
promotion score blends signals — reuse success (citations/kept outcomes from
the log), stability (survives revisions/time), and manual signal (pins,
add-backs) — never raw injection frequency alone (frequency alone promotes
nonsense; v2.7).

**Maintenance (M3; cron + /maintain_memory + 80%-budget trigger):** semantic
clustering over embeddings → consolidation proposals with a four-verdict
taxonomy (v2.7): **merge** (new unit with `merged_from` lineage, sources
tombstoned), **new** (keep separate), **contradict** (two active memories
assert conflicting facts → review queue; truth calls are never automatic),
**supersede** (newer memory replaces older → typed edge + demote/tombstone
proposal); plus staleness review and the promotion/demotion pass. Curators
may maintain a TYPED EDGE OVERLAY (supersedes / contradicts / relates-to)
as rows in the same database — used for 1-hop expansion during consolidation
and audit, never as first-pass retrieval (graph is an overlay, not the
architecture). Runs as its own agent under the same CAS rules.
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
TRAINING-DATA HYGIENE (v2.7): learning and replay MUST exclude events from
verification/test principals — filter on machine_id/editor prefixes used by
packet verification (e.g. `*-verification-*`, `verification:*`) — so fixture
runs never tune the scorer; the events remain in the log (append-only law).
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

### ADR-007 — Harness feature parity (now an index)

**Status: ACCEPTED as index (2026-07-20; D.2 041)** — the 2026-07-19/20
gate sessions designed what this draft only named. Parity items and their
owning law:
- Queuing / steering / interruption → ADR-014 (three-level send gesture).
- Human-in-the-loop & tool approval → ADR-015 (walls and boundaries; the
  approval ladder is deliberately DEAD — read ADR-015 before assuming one).
- Sessions (durable, resumable, branching) + checkpoints/rewind → ADR-016.
- Loops / autonomous iteration / subagent orchestration at scale → ADR-012
  (work protocol + mode scale) and ADR-017 (Symphony search).
- Skills, MCP, compaction, cost batteries → adopted through the ADR-013
  seam (pydantic-ai capabilities; compaction chassis = ProcessHistory,
  plan-mode variant parked in D.4).
- Visualization & interfacing → ADR-008 (deck, scrubber, gallery) and
  ADR-018 (the Cube, plugins, stack).
Remaining parity items still owned here until their milestone planning:
per-model tokenizer abstraction for honest context accounting; DBOS
durable execution (arrives with loops/subagents in M3; M1 sessions are
plain DB rows).

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

- **Frontend (stack RESOLVED 2026-07-20 — D.2 041; was PROPOSED):** React +
  TypeScript + Vite SPA. DOM for rails/panels/text; ONE WebGL/WebGPU stage
  scene for the Cube (three.js + react-three-fiber, TSL dual-target
  shaders) per ADR-018; SVG for small panel charts; WebSocket
  (control/streams) + SSE (memory/presence). Chromium-class browsers only
  through M4. M1's H4 chat shell is plain React DOM — the stage arrives
  with the M2/M3 viz buildout.
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

**The mode scale (amended 2026-07-20; D.2 041).** One protocol, a movable
JUDGE SEAT, four rungs — scalar so new rungs slot in without machinery:
- **Solo** (pp): one agent, headless one-shot; the output is the verdict.
- **Duet** (mp): turn-based pair — THE HUMAN HOLDS THE JUDGE SEAT, every
  turn. Attention flows continuously by the human's choice, which is an
  Invariant-14-legal spend: the architecture's decision is that the human
  elected it. For trust-building and craft.
- **Ensemble** (mf): a few parallel agents; gallery watching; interjection
  on solo runs only. The seat is shared.
- **Symphony** (ff): full ADR-017 search; judges conduct; attention
  arrives as the premiere card.
Roles in the music: the human is the COMPOSER (writes the score — spec,
objective, budget); the CONDUCTOR is the orchestrator plus its judges;
agents are SECTIONS. The composer does not play in the pit; the composer
hears the premiere. The seat transfers per-thread, mid-thread, both
directions, in one gesture ("take it from here" / "let me drive"). Pair
mode is not an escape from the protocol — it is the human occupying one of
its offices.
*Verification:* mode state is an envelope-visible thread property; judged
by driving a seat transfer both directions and observing that attention
pulls (cards) occur only per the active rung's law.

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

### ADR-015 — Walls and boundaries: the permission model

**Status: ACCEPTED (2026-07-20; D.2 041).** CONTRACT from the milestone
agents hold fs/shell tools (M3). Codifies the human-gate discussion that
produced Invariant 14.

**Motivation (the intuition).** Per-command approval is security theater:
an agent with write+bash already holds full capability the moment one
command runs; fifty "allow" clicks change nothing except training the
human to click. The field's approval-mode ladders replace judgment with
fatigue. Meanwhile our own gate/judge design already knows the answer:
spend attention only where it is decisive.

**Decision — safety from walls, attention at the walls:**
1. DEFAULT posture, zero setup: every agent runs inside an OS-level
   sandbox scoped to its workspace/worktree (Seatbelt on macOS,
   Landlock/container on Linux) with a network allowlist. INSIDE the
   walls: full autonomy — no per-action approvals exist. (Pi's honesty
   with Codex's kernel enforcement, made the default.)
2. Attention is spent only at BOUNDARY CROSSINGS: leaving the sandbox —
   remote pushes, deploys, credentials, network beyond allowlist,
   spending money. A crossing is not an "approval"; it routes like every
   attention pull: through the judge first (ADR-012 blocker triage — a
   PermissionJudge answers what the boundary list can answer; only
   decisions genuinely reserved for the human become cards).
3. There is no permission-mode ladder. Configuration = sandbox profiles
   (what the walls permit) + the boundary list (what makes a card).
   Worktree isolation per parallel attempt means every swarm branch is
   its own walled garden.
4. Trust invariant: the repository and all tool output are UNTRUSTED
   input; only human-owned configuration escalates capability.

**Rejected:** approval-mode ladders (fatigue generation); pure
Pi-style YOLO without default walls (right honesty, wrong default —
"a clean protected environment should be the default"); LLM screening of
every in-wall action (attention theater relocated into compute).
*Verification:* drive an in-wall destructive-looking action (no prompt
appears) and a boundary crossing (card appears, judge-triaged); attempt
capability escalation from repo config (refused).

### ADR-016 — Two ledgers, one tree: sessions, checkpoints, rewind

**Status: ACCEPTED (2026-07-20; D.2 041).** CONTRACT for M2/M3 session
machinery; ONE M1 seed already landing with H4 (see below).

**Motivation.** Two user stories are one mechanism: the Duet user who went
down a bad path wants one-click return of conversation AND code to any
earlier point (Cursor's revert, SolidWorks' rollback bar); the Symphony
search needs cheap branchable states. Undo and exploration are the same
tree walked in different directions.

**Decision:**
1. TWO LEDGERS. The real git repo stays deliberate — commits happen when
   work means something; history stays clean. A SHADOW ledger (second git
   dir over the same worktree) checkpoints file state automatically at
   every HUMAN TURN. A checkpoint is a restore point, never a commit.
2. ONE TREE. Every message carries `parentId`; a session is a tree that
   usually never branches. REWIND = continue from an earlier node (the
   old continuation survives as a sibling). FORK = new child from any
   node, conversation + checkpointed files traveling together into a
   fresh worktree. Restore scope is always explicit:
   conversation | files | both.
3. The scrubber (one line per human input — ADR-008) is the tree's UI:
   every line anchors a checkpoint; click to jump, rewind, or fork.
4. Every query surface accepts `as_of` (timestamp/checkpoint ref):
   live view, scrubbing, and time-lapse are one mechanism at three
   speeds. Client state is event-sourced with keyframe snapshots so
   seeking is cheap.
5. M1 SEED (H4): browser message objects already carry ULID ids; the
   `parentId` column lands with the first persistent transcript store so
   no migration is ever needed. Tree semantics activate in M2/M3.

**Rejected:** committing every turn to the real repo (noise; the two
ledgers exist so history stays human); flat sessions with git-only undo
(kills forking, the scrubber-as-time-machine, and Symphony's substrate);
conversation-only rewind (Cursor taught that code and chat must travel
together).
*Verification:* scrub to an earlier human turn, rewind scope=both,
verify workspace + transcript match that moment; fork two siblings from
one node and verify divergent worktrees with a shared prefix.

### ADR-017 — Symphony search: the work protocol at scale

**Status: ACCEPTED (2026-07-20; D.2 041).** CONTRACT for the M3+ Symphony
rung of ADR-012. Generalizes the one-round swarm ADR-012 already defines.

**Motivation.** ADR-012's parallel attempts are one round of breadth.
Real problems (optimize this kernel) want ITERATED, COORDINATED search:
many stratagems advancing in parallel, evidence reallocating effort,
partial wins combining — Karpathy-style auto-research, but multi-agent
and budget-aware. The relay that built this system is the manual version;
Symphony is its automation.

**Decision — value-guided tree search over materialized workspaces:**
- A NODE is (conversation, workspace checkpoint, spec) — cheap to mint
  (ADR-016 shadow ledger), isolated to run (worktree).
- Four operators: EXPAND (an agent advances a leaf) · FORK (N siblings
  seeded with named STRATAGEMS — approach hypotheses enumerated at spec
  alignment by human or strategist agent) · GRAFT (git-native crossover:
  merge the best of two branches; elevates ADR-012's graft to a
  first-class move) · PRUNE (defund; branches PERSIST forever —
  auditable, revivable).
- The VALUE FUNCTION is the judge: a BENCHMARK when the spec declares its
  objective MEASURED (latency, tests, tokens/sec — full autonomy); a
  judge MODEL when JUDGED (taste; premiere cards deserve more
  skepticism). Every spec declares which.
- The BUDGET is a portfolio: allocation follows expected value PLUS
  uncertainty (bandit-style); beam width = max_parallel_project_agents.
  Evaluation competes with expansion for tokens (value-of-information:
  sometimes the right spend is to listen, not play).
- CONVERGENCE: target metric hit, budget exhausted, or judge COMPLETE →
  exactly one premiere card (Invariant 14).
- THE REMEMBERING ORCHESTRA (the moat): every branch — especially pruned
  ones — files atomic lessons to the Palace, stamped project +
  origin_path. The next search on similar ground opens with those
  lessons injected. Search compounds across projects; this is only
  possible because the Palace was built first.

**Rejected:** fixed-round tournaments (evidence should move money);
human-picked winners mid-search (ADR-012's rejection, inherited);
deleting pruned branches (their lessons and audit trail are half the
value).
*Verification:* on a MEASURED toy objective, verify budget reallocation
away from a weak stratagem, one graft producing a leaf that outscores
both parents, pruned-branch lessons appearing as Palace units, and
exactly one card at convergence.

### ADR-018 — The Cube and the plugin rack

**Status: ACCEPTED (2026-07-20; D.2 041).** CONTRACT for the M2/M3 viz
buildout; supersedes nothing — it UNIFIES ADR-009/decision-016's committed
visualizers into one object. Detail and aesthetics: garden/NATES_VISION.md
(GUIDANCE) + garden/notes/cube-visualizer.md (design notes).

**Motivation.** The viz suite was a list; the Cube is its geometry. One
underlying object — the work — projected on faces the human rotates
between, with ComfyUI's lesson (the visualization IS the app; you get
where you're going by clicking into it) and Ableton's lesson (a rack the
user rearranges, not furniture).

**Decision:**
1. FACES with true spatial logic: FARM front (the colony: whole directory
   tree as chambered burrows, files as cells, zoom, CAD-floating on black
   + faint grid) · ROOTS the depth axis (organic meandering roots growing
   horizontally from each colony; dead roots preserved and desiccated;
   thickness = tokens spent; opacity = SELECTION FOCUS — the selected
   score's roots at full presence, every other score dimmed but always
   visible, floor 0.25; EV is NOT an alpha channel — OQ-17 resolved
   2026-07-21: the owner wants focus, not valuation, in opacity) · TIPS opposite the
   Farm (roots end-on; the frontier grid of next-round starts) · plus
   DECK (left rail, time-ordered, auto-advance, conductor drafts — the
   ONLY surface that may demand) · LEDGER (capital alluvial) · PALACE
   (memory; inverted light scheme) · SCORE (context bars + timeline).
   ORBIT rotates around (90°-class azimuth moves), zoom scrolls, faces
   render FLAT when focused (the cube is navigation, not decoration).
2. ONE SELECTION shared by every face; selection is also navigation.
   The rollback bar (ADR-016) scrubs every face to any `as_of`.
3. MEMORY-TRACE SANCTITY: selecting anything traces its injections —
   injected list with one-tap pop-off, near-miss suggestions with
   one-tap add — as pure CONSUMERS of the injection_event log. No
   visualizer may write to, delay, or bias the scorer. Ever.
4. THE RACK: layouts are savable per-mode SETS. Plugins (panels, console
   widgets, card renderers, stage faces) receive exactly THREE surfaces —
   the C.7 event stream, the query surface (+as_of), the selection bus —
   and no notify API exists: Invariant 14 is structural. Panel plugins =
   sandboxed iframes (postMessage bridge); face plugins = data-driven
   scene schemas (never raw renderer access). Plugin API versioned;
   churn contained per ADR-013.
5. STACK (resolves ADR-008's PROPOSED details): React DOM for rails and
   all text; ONE WebGL/WebGPU stage scene — three.js + react-three-fiber
   inside the existing React+Vite app, TSL shaders dual-targeting
   WGSL/GLSL; instancing for populations, compute for living systems
   (curators, root growth); text never enters the canvas; refs +
   useFrame, never per-frame setState; parallel DOM/table rendering for
   accessibility. Chromium-class browsers are the ONLY support target
   through M4. Fleet palette machine-validated on final grounds
   (dataviz six checks) — revalidate on any ground change.

6. PROCEDURAL LAW (amended 2026-07-20; D.2 042). All stage geometry is
   PROCEDURAL: generated at runtime as a DETERMINISTIC function of work
   metadata, seeded by stable ids — no hand-authored scene assets, ever.
   The visuals are model-like — real 3D parts with materials and lighting
   (the CAD/SolidWorks feel), built by generators, not drawn: roots are
   GROWN from search metadata (thickness = spend, meander seeded by
   branch id, length = depth, junctions = fork/graft events, desiccation
   = prune state); colonies are GROWN from the live directory tree
   (chambers from directories, cell counts from files, tunnels from
   hierarchy); Palace architecture and curators derive from memory-unit
   populations and curator events. Same data → same geometry, which is
   what makes the ADR-016 rollback bar work on the scene: scrubbing
   re-runs generation at that `as_of`. Generators live behind the face
   schema — plugins parameterize them with data and never emit meshes.
   Mechanism: parametric/instanced mesh generation with TSL/compute for
   growth animation (clause 5's stack).
7. THEMES (amended 2026-07-20; D.2 043). The aesthetic is a swappable
   STYLE CONFIGURATION on the rack — tokens, motif set, material
   language — loadable and user-authorable like any panel. Default theme:
   NEO-NOIR (Syd Mead / tech-noir: neon against dark urban, street-level
   claustrophobic composition, holographic-display language, rain-slicked
   materials, volumetric lighting — full vocabulary in NATES_VISION §8).
   Named alternate: COBALT-SERAPH. Theme law: themes STYLE meaning and
   never re-encode it — data encodings, fleet identity, and Invariant 14
   survive every theme; each theme's fleet palette is machine-validated
   on that theme's grounds before it ships; one danger color per theme.
   Themes ride the plugin distribution path (versioned, sandbox-safe:
   a theme is tokens and materials, never code with surface access).

**Rejected:** literal always-3D rendering (readability loses to
spectacle); per-visualizer data plumbing (the three surfaces are the
whole API); plugin notify capability (would re-open the attention wall);
Safari/Firefox support before M4 (single-user product; compat tax steals
packets); hand-modeled or imported scene assets (cannot time-scrub,
cannot track live projects, and would let art drift from truth — the
organism must be GROWN from its data or it is a picture of an organism).
*Verification:* per B.6 rule 7 throughout — plus: a hostile test plugin
must be unable to notify, write, or escape its rectangle; selection made
on any face must appear on all faces and the trace drawer within one
event cycle; the palette validator must pass on the shipped grounds;
and procedural determinism is judged directly — render the same `as_of`
twice and diff the geometry (must be identical), change one metadata
input and verify exactly the corresponding visual property moves.

### ADR-019 — Onboarding: the two-secrets rule and packaging

**Status: ACCEPTED (2026-07-20; D.2 046).** CONTRACT for the packaging
wave (packet D3, opens after the M1 judge); the principle binds all
future onboarding surface immediately.

**Motivation.** The three-repo workspace is the RELAY's reality, not the
user's. A newcomer must reach a working Nocturne without cloning
anything, building web assets, or hand-assembling env files — the
onboarding tax is a product surface, and Invariant 14 applies to it:
setup attention is still attention.

**Decision:**
1. THE TWO-SECRETS RULE. A newcomer reaches a working Nocturne with at
   most two secrets: an OpenRouter key (always — the broker carries chat
   AND embeddings per v2.3) and GCP credentials (cloud mode only, via
   their existing `gcloud auth`). LOCAL MODE NEEDS ONE SECRET. Everything
   else — spine bearer token, database passwords, runtime identities,
   budget guard, billing breaker — is generated, defaulted, or derived.
2. THE FOUR COMMANDS (contract names): `nocturne init` (first-run wizard;
   asks only for the secrets), `nocturne up` (local: pull pgvector
   container, migrate, start spine + daemon, open the browser),
   `nocturne deploy` (cloud: the D1 runbook as idempotent code with
   --dry-run; includes the D2 breaker), `nocturne open`.
3. PACKAGING. Two wheels, zero clones: `nocturne` (harness repo — daemon,
   CLI, agent, spine client, WEB ASSETS PRE-BUILT AND BUNDLED as package
   data; users never run Node) and `nocturne-spine` (spine repo — app +
   alembic migrations as package data; a dependency of `nocturne` for
   local mode; `nocturne deploy` ships its packaged source). Versioning
   is LOCKSTEP: one product version stamps both wheels; the C-contracts
   are the compatibility surface. THE GARDEN NEVER SHIPS — it is the
   methodology that grew the organism, not the organism.
4. SEED INGESTION — the cold open (added 2026-07-21; builds in M2). Cold
   start is product surface: at init (or any time) the user uploads
   markdown files and curator-style splitters break them into ATOMIC
   memories (the 128-token law) through the STANDARD create/dedup
   pipeline, landing in an approval queue — the user confirms what enters
   the Palace. Rides M2's extraction + approval-queue machinery; no new
   persistence. A palace should never start empty unless its owner wants
   it to.

**Rejected:** mono-repoing the workspace (relay law is repo-shaped and
working); container-registry distribution as the primary path (wheels +
source-deploy are simpler and registry-free); shipping the Garden
(users need the product, not our scaffolding).
*Verification:* a fresh machine with Docker + pipx and ONE OpenRouter key
reaches a working browser chat via the three local commands; a --dry-run
deploy prints a complete, correct plan without mutating anything.

### ADR-020 — Shared Palaces: combining memory across people

**Status: ACCEPTED as HORIZON (2026-07-20; D.2 047)** — end-state design
accepted now, like ADR-011; BUILDING IS FORBIDDEN before real
multi-tenant identity exists (M4 headline; ADR-011's M5 multi-principal
soak is its stress test). Required M1–M3 schema footprint: NONE — the
existing design already carries it (verified below).

**Motivation.** Different people working the same project should be able
to pool chosen memories into a COMBINED palace — the remembering
orchestra, scaled from a soloist to a section. The owner's requirement:
each user CHOOSES what to contribute; combination is consent-based and
selective, never automatic.

**Decision:**
1. A shared Palace IS a principal. `principal_id` already scopes every
   table; a team palace is simply a principal that multiple humans'
   harnesses may address. No parallel machinery.
2. CONTRIBUTION = COPY-WITH-LINEAGE, never move: contributing creates a
   new unit in the shared Palace whose first revision's `parent_uid`
   points at the contributor's source `rev_uid`. Because rev_uids are
   globally unique ULIDs in one revision DAG, CROSS-PALACE LINEAGE
   ALREADY WORKS WITH ZERO SCHEMA CHANGE — provenance (who gave what,
   from where) is the existing editor/machine/lineage record.
3. SELECTIVE AND REVOCABLE. Contribution is an explicit act through the
   panel's existing list/filter machinery; originals never leave the
   personal Palace; revocation tombstones the contributed copy (the
   shared Palace obeys the same never-delete law).
4. COLLISIONS ARE ALREADY SOLVED MACHINERY. Two teammates contributing
   overlapping knowledge hit the write-time dedup bands like any create;
   the M3 curator's merge queue and ADR-011's single conflict taxonomy
   (union / fast-forward / review) govern the rest. Combining palaces and
   reconciling divergent replicas are THE SAME MECHANISM — ADR-011's
   per-unit three-way merge, applied across people instead of machines.
5. INJECTION FROM THE UNION. An agent on a shared project draws
   candidates from the personal Palace plus subscribed shared Palaces;
   scorer v-current runs unchanged over the union; the gate shows
   PROVENANCE on every card (whose memory this is). Per-source trust
   weighting is a future scorer feature, decided by replay evidence.
6. The gating dependency is IDENTITY: real multi-tenant auth (per-human
   principals, membership, tokens) replaces M1's single bearer before any
   of this ships. Federation across separate spine deployments is
   deliberately open — OQ-19.

**Rejected:** automatic whole-palace merging (consent is the point);
moving memories out of personal palaces (contribution must be reversible
and non-destructive); a separate "team memory" schema (a shared Palace
that isn't a Palace would fork every downstream mechanism).
*Verification (at build time):* contribute → provenance lineage resolves
to the source revision; revoke → tombstone hides it from the union
without touching the original; two overlapping contributions → dedup
band fires; gate cards show contributor provenance.

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
ADR-005 table (with the v2.7 training-data hygiene filter); scorer versioning
+ offline replay + rollback; per-feature
contribution bars in gate; citation heuristic; end-of-thread extraction with
approval queue; markdown SEED INGESTION (upload → curator split →
approval queue — ADR-019 clause 4); HYBRID CANDIDATE RETRIEVAL (v2.7): the
candidate pool becomes the UNION of vector top-50 and Postgres full-text
search matches — an exact-keyword memory with a weak embedding must be able
to reach the scorer; the scorer ranks the union, nothing else changes;
a formal `candidate` status for approval-queue units (extraction + seed
ingestion) instead of overloading `active`; Context Bars port (+memory category); Memory Graph +
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
7. **UI packets are BUILT the way they will be judged (v1.14; D.2 039).**
   Any packet delivering user-facing interface (chat panes, gates, panels,
   visualizers) must verify by emulating true human use FROM THE FIRST
   PACKET, not at judgment time: drive the real rendered interface with
   browser automation exactly as a user would (click, type, scroll,
   rotate, select), screenshot every acceptance-relevant state, and assert
   on RENDERED OUTCOMES — visible text, layout, encodings — never only on
   internal state or component props. Screenshots are first-class builder
   evidence, committed under verification/<packet>/ beside the tests that
   produced them. A UI behavior that was never exercised through the real
   interface is not DONE. Rationale: rendering defects (cascade
   collisions, encoding drift, label overlap) are invisible to unit tests
   and expensive to find at refinement; the screenshot IS the test.
8. **Agent walkthroughs — SOPs for agents (v2.5; D.2 048).** Rule 7's
   scripted checks prove regressions; they do not prove EXPERIENCE. Every
   UI packet additionally ships and EXECUTES a written SOP — a
   human-style operating procedure ("open the app; create a thread; type
   this; watch what happens; now try to break it") — performed LIVE by
   the agent through interactive browser use, first person, exactly as
   the human would: look at every rendered screen, click, type, scroll,
   wait, and OBSERVE before choosing the next action. This is not
   automated testing and cannot be discharged by running a script.
   Requirements: (a) the SOP and its execution log live at
   verification/<packet>/SOP.md — every step records the action taken,
   its screenshot, and a PROSE OBSERVATION of what the agent actually saw
   and judged (surprises, friction, and wrongness are findings, not
   noise); (b) at least one UNSCRIPTED exploration segment — wander,
   click around, try odd inputs — recorded the same way; (c) observed
   defects route through the Blight Protocol; observed DESIGN friction is
   surfaced to the human gate in the handoff; (d) the judge RE-EXECUTES
   the packet SOPs at I1/J rather than only reading their logs. The
   agent's eyes on the rendered pixels are the point.

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
with current unit in body. A successful cloud-head CAS from revision n to n+1
sets `memory_unit.updated_at = now()` and appends exactly one
`memory_revision` with `revision = n+1`, `parent_uid` equal to the prior
cloud-head revision's `rev_uid`, and `body` / `label` equal to the resulting
`memory_unit` values. A failed CAS changes neither table. [folded from A-001]
Tombstone = status change, never DELETE.

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

  For scorer v0, `tokens` are maximal runs of Unicode alphanumeric characters
  after lowercase conversion. `kw` removes the exact stopword set `{a, an,
  and, are, as, at, be, by, for, from, has, he, in, is, it, its, of, on,
  that, the, to, was, were, will, with}`; each stored keyword is tokenized by
  the same rule before union. Time and human-edit ages are measured from
  `thread.snapshot_ts`, in elapsed seconds divided by 86400, with negative
  ages clamped to zero; a human edit is a `memory_revision` whose editor is
  exactly `user`. Semantic cosine is clamped to `[0,1]`. A project match
  requires a non-null thread project equal to the memory project; a null
  memory project scores 0.5. Eligible `pin=true` units are fetched outside
  the non-pinned vector pool and top-k limit, scored only to populate the
  explainability fields, ordered by `memory_id` ASC, and injected first
  regardless of threshold or budget. Their `cl100k_base` body-token costs
  reduce the regular budget to no less than zero; pins alone may exceed it.
  The regular budget is
  `min(budget_tokens, floor(budget_pct * model_context_tokens))`, and each
  regular card costs its body's `cl100k_base` tokens. The non-pinned vector
  pool orders cosine DESC then `memory_id` ASC; scored regular candidates
  order score DESC then `memory_id` ASC. Greedy selection scans that order,
  accepts at most `top_k`, and after an over-budget card continues to the
  next. Near misses are the first `near_miss_k` unselected regular candidates
  in score order, including candidates excluded by threshold, budget, or the
  top-k cap. Rank is one-based in the combined complete order: pins first,
  then all regular candidates in score order; returned lists retain those
  ranks even when intervening candidates are not returned. `kind='pinned'`
  without `pin=true` does not bypass scoring. [folded from A-007]

## C.4 Spine API (M1 surface, exact bodies)

Auth: `Authorization: Bearer $SPINE_TOKEN` on all routes. Unless a route
specifies an exact error body below, errors use RFC7807 JSON. The
`label_conflict`, `duplicate_of`, and `conflict` 409 bodies specified by
POST/PATCH `/v1/memories` are exact `application/json` responses and are the
only C.4 exceptions. [folded from A-002]

POST /v1/inject/prepare
  req: {thread_id, agent_id, machine_id, principal_id, project_key?,
        agent_kind?, prompt, model_context_tokens}
  Require `model_context_tokens > 0`; a violation returns RFC7807 422 before
  embedding or any database write. [folded from A-014]
  beh: create thread row if new (sets snapshot_ts=now()); embed prompt;
       candidates read as-of thread.snapshot_ts (latest revision ≤ snapshot_ts);
       write injection_event rows (outcome NULL); update stats.injections.
  M1 accepts exactly one successful prepare per thread, as required by C.6's
  one-injection flow. A thread row with non-null `snapshot_ts` returns
  RFC7807 409 on another prepare. An existing unstamped row may be stamped
  only when its principal, agent, machine, and project fields exactly match
  the request; mismatch returns RFC7807 409. Prompt embedding completes
  before the atomic database phase. That phase uses one repeatable-read
  transaction, stamps `snapshot_ts` from the database clock, reads and scores
  the heads visible at that boundary, writes events, and updates statistics;
  a conflict rolls back the entire phase. Each returned card writes exactly
  one `injection_event`: injected `pin=true` cards use `shown_as='pinned'`,
  other injected cards use `shown_as='injected'`, and near misses use
  `shown_as='near_miss'`; stored score, six features, and rank equal the
  response and outcome is null. To preserve the frozen card for replay and
  commit without changing C.2's DDL, the event's features JSON additionally
  contains `_memory: {label, body, pin, updated_at}` from the scored
  snapshot; the wire `features` object remains the exact six-field C.4
  shape. `stats.injections` increments once and `stats.last_injected_at` is
  set to `snapshot_ts` for each card in `injected`, including pins, and never
  for a near miss. Those server writes use C.2 CAS, append revisions with
  editor `system:inject`, origin machine from the request, and reason
  `inject/prepare`. [folded from A-008]
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
  The event batch is every `injection_event` row with the requested
  `injection_id`. Each `removed` memory ID must be distinct and name a batch
  row whose `shown_as` is `injected` or `pinned`; each `added_back` ID must
  be distinct and name a `near_miss` row; the lists must be disjoint.
  Duplicate, foreign, or wrong-class choices return RFC7807 422 with no
  write. No batch rows plus nonempty choices returns RFC7807 404. No batch
  rows plus both lists empty succeeds with the canonical zero-member C.6
  block and `wrong_removed=[]`; because A-008 persists no batch row for a
  zero-card prepare, this also accepts any unknown injection UUID with empty
  choices in M1.

  The desired commit outcome is `removed:<reason>` for each removed row,
  `kept` for every untouched injected or pinned row, and `added_back` for
  each selected near miss; an unselected near miss remains NULL. Outcomes
  transition from NULL exactly once. Repeating the same desired outcome is
  idempotent. For retry comparison, `cited` or `mid_thread_removed` is a
  descendant of `kept` when `shown_as` is injected/pinned and of
  `added_back` when `shown_as` is near_miss. Any different non-NULL outcome
  returns RFC7807 409 with no write. An all-near-miss commit with no add-back
  is necessarily a durable no-op under the frozen C.2 schema.

  Only a new NULL-to-outcome transition changes head statistics. Each newly
  removed row increments `stats.removals` once. A new `removed:never` also
  increments `stats.never_kills`, adds that event's scorer-version
  `never_bias_step` to `bias`, and changes an ACTIVE head to quarantined when
  the resulting kill count is at least that version's `quarantine_kills`;
  an already quarantined or tombstoned status is preserved. Each newly
  `added_back` row increments `stats.injections` once and sets
  `stats.last_injected_at` to the commit transaction's database clock. Load
  the two never parameters from the event's `scorer_version` row. Apply all
  new event outcomes, head changes, and revisions atomically; update each
  affected head once through C.2 CAS in memory-ID order with editor
  `system:inject`, the event's `machine_id`, and reason
  `inject/commit:<outcome>`. `wrong_removed` contains the post-stat CURRENT
  MemoryUnit for every requested `removed:wrong`, ordered by event rank.

  Final members are rows whose outcome is `kept`, `added_back`, or `cited`,
  ordered by rank ASC then memory_id ASC. Render them only from the frozen
  event `_memory` payload and `memory_kind`, never from a current head.
  [folded from A-009]
  res: {final_block: string,        # the exact rendered block (C.6) the harness injects
        wrong_removed: [MemoryUnit]} # current unit for each removed:"wrong" so the
                                     # UI opens the edit flow with a valid
                                     # expected_revision; [] when none

POST /v1/feedback            # mid-thread, ad-hoc
  req: {injection_id, memory_id, signal: "mid_thread_removed"|"cited"}
  res: {ok: true}
  Feedback targets the single `injection_event` matching both IDs; no match
  returns RFC7807 404. A new signal may transition only `kept` or
  `added_back` to the signal's literal outcome. Repeating that same signal is
  idempotent `{ok:true}` with no new write. Outcome NULL, any `removed:*`
  outcome, or the other feedback signal returns RFC7807 409.
  `mid_thread_removed` also increments the current head's `stats.removals`
  exactly once through C.2 CAS; its event transition, head update, and
  revision are one transaction using editor `system:feedback`, the event's
  `machine_id`, and reason `feedback/mid_thread_removed`. It changes no bias,
  status, citation, or other statistic. In M1, `cited` is event-log-only: it
  writes the outcome but does not change `stats.citations`, write a memory
  revision, or affect scorer v0, whose citation feature remains inert.
  [folded from A-010]

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
  Dedup comparisons include only ACTIVE units with the same principal.
  `duplicate_of` is the unit with greatest cosine similarity, breaking
  equal-score ties by `memory_id` ASC. `similar` contains every such unit
  whose score satisfies `dedup_sim <= score < dedup_dup`, ordered by score
  DESC then `memory_id` ASC; M1 applies no additional result cap. The
  configured thresholds are inclusive at `dedup_sim` and `dedup_dup` as those
  inequalities state. [folded from A-003]
  res: 201 {created: MemoryUnit}

PATCH /v1/memories/{id}
  req: {expected_revision, body?, label?, keywords?, kind?, pin?, status?,
        origin_path?, editor, reason, machine_id}
  beh: CAS per C.2 rules; the revision row gets origin_machine_id = machine_id;
       a label change colliding with another active unit → 409 {label_conflict}
       as on create.
  A mutable property whose JSON value is null is treated as omitted. With
  zero remaining mutable properties, return RFC7807 422; for an absent memory
  ID, return RFC7807 404. A supplied non-null `body` is embedded before the
  CAS, and a successful CAS writes its `body`, `embedding`, and
  `embedding_model` atomically. The CAS condition is evaluated before
  active-label uniqueness: a stale revision returns `{conflict: MemoryUnit}`.
  Any successful-revision write whose resulting status and label would
  collide with another ACTIVE unit of that principal returns
  `{label_conflict}`, including reactivation without a label change.
  [folded from A-004]
  For M1, label length is measured in Unicode code points and body length is
  measured with the `cl100k_base` tokenizer. On create, and for each non-null
  replacement value supplied to PATCH, require `len(label) <= cfg.label_max`
  and `tokens(body) <= cfg.memory_max_tokens`; a violation returns RFC7807
  422 before embedding or any database write. [folded from A-006]
  res: 200 MemoryUnit | 409 {conflict: MemoryUnit}   # current unit, per C.2 rules

GET  /v1/memories?project_key=&status=&q=&limit=&offset=
  beh: panel list; limit default 50 max 200, offset default 0;
       ordered by updated_at DESC, memory_id ASC (stable paging).
  Supplied filters are ANDed; omitted `project_key` and `status` apply no
  filter. Trim `q`; blank applies no filter, otherwise it is a
  case-insensitive literal substring match over `label` or `body`. `total` is
  the filtered count before paging. Require `1 <= limit <= 200` and
  `offset >= 0`. [folded from A-005]
  res: {items: [MemoryUnit], total, limit, offset}
POST /v1/search             req: {principal_id, query, k=10, project_key?}
                            res: {results: [MemoryCard]}  (agent tool backend)
  Require `1 <= k <= 50`; a violation returns RFC7807 422 before embedding.
  An omitted or JSON-null `project_key` applies no project filter. A non-null
  `project_key` admits only ACTIVE units whose `project_key` is NULL or
  exactly equal to the request value. Results are the first k ordered by raw
  cosine similarity DESC then `memory_id` ASC. Search applies no scorer
  threshold, weights, bias, pin priority, or candidate re-ranking; `score` is
  that raw cosine and `features` / `rank` are null. [folded from A-012]

## C.5 Config defaults (single source: spine config.py / harness config.py)

tau=0.55, top_k=8, near_miss_k=3, budget_tokens=3000, budget_pct=0.05,
half_life_time_days=14, half_life_hist_days=7, dedup_dup=0.92, dedup_sim=0.80,
never_bias_step=-0.15, quarantine_kills=3, candidate_pool=50,
embed_base_url="https://openrouter.ai/api/v1" (v2.3 — D.2 044: embeddings
route through the token broker by default, same as chat; verified live
2026-07-20 with openai/text-embedding-3-small returning 1536-dim vectors;
direct-provider URLs remain a config override; the bearer-key slot accepts
any OpenAI-compatible key — OpenRouter primary),
embed_model="openai/text-embedding-3-small" (dim 1536, provider-pluggable),
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

  Join structural lines with LF, with no blank separator lines and no
  terminal LF. Emit attributes in `label`, `kind`, `updated` order. In
  attributes escape `&`, `<`, `>`, and `"` as `&amp;`, `&lt;`, `&gt;`, and
  `&quot;`, and encode tab, LF, and CR as `&#9;`, `&#10;`, and `&#13;`. In
  body text escape only `&`, `<`, and `>`; preserve every other character and
  existing newline. Use frozen event values verbatim apart from that
  escaping. With zero members, return these four lines exactly:
  `<memory_system>`, the two literal preamble lines from the template, and
  `</memory_system>`. [folded from A-011]

Agent tools (tools_memory.py; docstrings are the model-facing spec):
- save_memory(label, body, kind, keywords?, project_scoped: bool,
  force: bool = false)
  → handles 409/similar responses by surfacing them to the model
    ("similar memory exists: ...; update it, or call again with force=true").
  Forward force unchanged to C.4 POST /v1/memories. The tool never enables
  or retries force automatically. `true` skips only the near-similar band and
  does not override label or hard-duplicate 409s. [folded from A-015]
- search_memory(query, k=5) → MemoryCards rendered compactly.
- edit_memory(label_or_id, new_body, reason) → CAS retry once on 409.
Agent instructions addition (verbatim, part of capability):
  "Save a memory when you learn a durable user preference, a correction to
   something you got wrong, a stable project fact, or a procedure the user
   wants repeated. Keep every memory ATOMIC: one fact per unit, at most a
   few sentences (hard cap 128 tokens); split larger content into multiple
   units. ALWAYS include 2-5 lowercase keywords (searchable nouns/terms —
   a memory without keywords is handicapped in retrieval). Prefer editing
   an existing memory over creating a near-duplicate.
   Never save secrets or credentials."
User command: `/remember <text>` → daemon calls POST /v1/memories with
kind=fact, editor='user', label AND 2-5 keywords auto-generated by the agent
model (one short completion produces both; v2.7 — keyword-less units were
observed handicapped on f_kw in live gate-day data), then confirms in chat.

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

  Each browser-to-daemon message occupies exactly one JSON text frame whose
  top-level value validates as the C.7 envelope. A binary frame, invalid
  JSON, non-object JSON value, or object that fails envelope validation is
  malformed. On the first malformed message, the daemon invokes no type
  handler, closes that `/ws` connection with WebSocket code 1008 and reason
  `invalid C.7 envelope`, and performs no further processing on that
  connection. [folded from A-013]

  `run_id` is a daemon-generated ULID allocated once when prompt.submit is
  accepted, including when it is queued; `prompt_id` is that inbound
  envelope's `id`. prompt.submit has a non-blank string `prompt` and requires
  outer `thread_id`. These payload members are required: run.started
  `{run_id,prompt_id}`; prompt.queued `{run_id,prompt_id}`; run.cancel
  `{run_id}`; run.delta text/thinking
  `{run_id,kind:"text"|"thinking",text:string}` or event
  `{run_id,kind:"event",event:object}`; run.usage
  `{run_id,requests,input_tokens,output_tokens}`; run.done
  `{run_id,stop_reason,partial}`; gate.open
  `{run_id,kind:"memory_gate",...}`; gate.commit `{run_id,...}`; and
  gate.dismiss `{run_id,...}`. Usage fields are non-negative integer
  cumulative totals for that run and never decrease; C.7's "incremental"
  means that updated cumulative snapshots may be emitted while the run
  advances. `stop_reason` is
  `end_turn|cancelled|error|budget_exceeded`; `partial` is false exactly for
  end_turn and true otherwise. These are minimum object members: additional
  JSON members are allowed and preserved so later gate and event contracts
  can extend them.

  thread.snapshot is bidirectional. A C→D request requires outer
  `thread_id` and payload `{request:true}`. Its D→C response carries
  `{messages,open_gate,active_run}`: `messages` is the daemon's ordered array
  of JSON message objects, including queued prompts and already-produced
  partial work; `open_gate` is null or the current gate.open payload; and
  `active_run` is null or `{run_id,prompt_id,state,usage,queued}`, with state
  `running|waiting_gate|cancelling`, usage in the run.usage shape without a
  second run_id, and queued an ordered array of
  `{run_id,prompt_id,prompt}`. Additional members are allowed and preserved.
  For M1 the daemon keeps one process-local active thread, selected by the
  latest valid thread.snapshot request or prompt.submit. On every WS connect
  it sends exactly one snapshot before live events when that thread exists;
  when none exists it sends none until a request or prompt selects one.
  Requesting an unknown thread returns the empty snapshot. Thread/run state
  survives a socket disconnect for the daemon process lifetime; reconnect
  sends the snapshot only and never replays old deltas or other prior
  events. This local selection is not a session or authorization boundary.

  A prompt received while its thread has a live run is appended once to a
  process-local FIFO and immediately acknowledged by prompt.queued. After
  every terminal run.done, the oldest queued prompt starts once: the prior
  run.done is emitted before its run.started, and the reserved run_id is
  reused. Cancellation applies only to the matching active run. The daemon
  first requests cancellation, awaits model/tool-batch termination and
  records terminal cancelled tool results, preserves all prior
  messages/output, emits gate.dismiss before run.done when a gate was open,
  and emits exactly one run.done(cancelled); no run.delta or run.usage for
  that run follows it. A duplicate cancellation while cancellation is
  pending shares that one confirmation. A stale, unknown, or already-
  terminal run_id produces error `{code:"run_not_active",run_id}` and
  cancels nothing. Queued prompts survive every terminal reason.

  Every daemon-created envelope has a fresh outer ULID `id` and timestamp;
  prompt_id supplies acknowledgement correlation. `type` accepts any
  non-blank string. The required payload validation above applies to known
  M1 behavior types. Reserved names and all other unknown types retain
  arbitrary JSON payloads and pass outer-envelope validation; an endpoint
  with a forward target forwards them unchanged, and an M1 daemon with none
  ignores them without emitting the not-implemented error. A-013 malformed-
  frame handling remains unchanged. [folded from A-016]

  In M1, daemon-authored `thread.snapshot.messages` use these minimum JSON
  objects. A user message is `{message_id,run_id,role:"user",content,state}`
  where `message_id` is the run's prompt_id, both IDs are ULIDs, content is
  a string, and state is one of `queued`, `running`, `end_turn`,
  `cancelled`, `error`, or `budget_exceeded`. An assistant message is
  `{message_id,run_id,role:"assistant",content,thinking,events,partial}`
  where `message_id` equals `run_id`, both are ULIDs, content and thinking
  are strings, events is an array of JSON objects, and partial is boolean.
  Additional JSON members are allowed and ignored by clients that do not
  understand them. A matching snapshot replaces the browser's transcript,
  open gate, active run, and usage for that thread; it is never merged with
  cached messages or prior deltas.

  The M1 browser owns a per-browser navigation catalog of
  `{thread_id,title,created_at,updated_at}` in local storage. `thread_id` is
  a browser-generated UUID, timestamps are ISO 8601 strings, and title is
  `New thread` until the first submitted prompt, then the first 48 Unicode
  code points of that prompt after collapsing whitespace, with `…` appended
  exactly when the normalized prompt exceeds 48 code points. `created_at`
  is fixed at catalog insertion; `updated_at` changes on each prompt submit.
  Creating or selecting a catalog entry sends a `thread.snapshot` request
  with payload `{request:true}` for that UUID; the first prompt creates
  daemon state through the existing prompt.submit path. The catalog is only
  local navigation metadata: snapshot remains transcript authority, the
  daemon provides no M1 thread enumeration or persistence, and
  `thread.create` gains no M1 behavior.

  A browser-authored direct-link envelope uses the literal machine_id
  `direct` until it has observed a daemon envelope, then echoes the latest
  non-blank daemon machine_id. The M1 direct daemon does not consult this
  field for identity or authority; future relay targeting supersedes the
  direct-link sentinel. Every browser-authored envelope still receives a
  fresh ULID and timestamp.

  When bounded live delivery or a connection outbox drops a subscriber, the
  daemon closes that WebSocket with code 1013 and reason
  `snapshot resync required`. The browser reconnects, requests its selected
  thread snapshot, and replaces local thread state before consuming later
  live events; it does not poll or replay buffered deltas.
  [folded from A-017]

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
- **OQ-18:** The full Palace scene (pale monumental architecture, ghost
  curator drones restructuring memory live) — dedicated design workstream.
  [M3 planning; aesthetics anchored in NATES_VISION §8]
- **OQ-19:** Shared-Palace federation — can contributions flow between
  SEPARATE spine deployments, or does a team share one spine? (ADR-020
  assumes one; federation would need cross-deployment identity + the
  ADR-011 sync path.) [M4 planning]

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
| 039 | 2026-07-20 | v1.14 B.6 rule 7: UI/visualizer packets verify by EMULATED HUMAN USE from the first packet — browser automation drives the real rendered interface, screenshots at every acceptance state are first-class builder evidence (verification/<packet>/), assertions on rendered outcomes never internals. Motivated by mock iteration: cascade collisions and encoding drift are invisible to unit tests; the screenshot is the test. Applies to H4/H5/H6 and every viz packet after | ACCEPTED |
| 040 | 2026-07-20 | v1.15 garden/NATES_VISION.md codified (GUIDANCE per 1.4): concatenated owner intent from the 2026-07-19/20 human-gate sessions — Invariant-14 soul, founding differentiators, organism/time thesis, modes-as-music with movable judge seat, ADR-012 protocol + conductor drafts, Symphony search (4 operators, portfolio budgets, MEASURED/JUDGED, lessons to Palace), the Cube (faces, selection, memory-trace sanctity, Ableton rack, aesthetics: black/white/orange chrome-seraph), stack (R3F/WebGPU hybrid, Chromium-only ≤M4), quality (B.6 r7), anti-vision. UI-surface packets read it at Boot STEP 5; full ADR-015/016/017 codification still pending human blessing | ACCEPTED |
| 041 | 2026-07-20 | v2.0 EDITOR PASS (content-preserving, mirroring 022's v0.x→v1.0 consolidation): ADR-012 gains the mode scale (Solo/Duet/Ensemble/Symphony, movable judge seat); ADR-015 walls & boundaries, ADR-016 two-ledgers/one-tree, ADR-017 Symphony search, ADR-018 Cube + plugin rack + resolved stack (R3F/WebGPU, Chromium-only ≤M4) authored from the gate sessions with Verification clauses per B.6; ADR-007 converted to a parity index; amendments A-001–A-017 folded verbatim into Part C (AMENDMENTS.md preserved as historical record; future completions still enact there first); header lineage compressed; D.1 gains OQ-17/18. No semantic change to built behavior | ACCEPTED |
| 042 | 2026-07-20 | v2.1 ADR-018 clause 6 PROCEDURAL LAW: all stage geometry is a deterministic function of work metadata, seeded by stable ids — model-like 3D parts GROWN by generators (roots from search metadata, colonies from the live directory tree, Palace from memory populations), never hand-authored; same data → same geometry, so as_of scrubbing re-runs generation; plugins parameterize generators, never emit meshes; determinism is directly judgeable (double-render diff) | ACCEPTED |
| 043 | 2026-07-20 | v2.2 ADR-018 clause 7 THEMES: aesthetics are swappable style configurations on the rack (tokens/motifs/materials, user-authorable, plugin-distributed, never code). Default = NEO-NOIR (Syd Mead tech-noir: neon on dark urban, street-level composition, holographic displays, rain-slicked materials, volumetric light — owner's vocabulary preserved verbatim in NATES_VISION §8); alternate = COBALT-SERAPH (the mock's current skin). Themes style meaning, never re-encode it; per-theme palette validation mandatory; Invariant 14 is not a style | ACCEPTED |
| 044 | 2026-07-20 | v2.3 broker-routed embeddings (owner's token-broker thesis; Invariant 13 completed): C.5 gains embed_base_url defaulting to OpenRouter, embed_model becomes the namespaced openai/text-embedding-3-small; the key slot accepts any OpenAI-compatible bearer. Verified live against OpenRouter's /embeddings before enactment. Chat AND embeddings now flow through one third-party broker by default; direct providers are overrides. New packet S7 wires config→adapter; D1 no longer requires OpenAI credits | ACCEPTED |
| 045 | 2026-07-20 | D1 factual/operations correction (no product-contract or version change): live audit proved D.2 033's "D1 executed / Cloud Run spine" status clause false; immutable row 033 remains as the historical record and this entry supersedes only that factual status claim. The foundation actually present is the active project, budget, and bare Cloud SQL instance. Garden D1 is reset as a relay-owned packet with authority narrowly bounded to the named app database/user, migration, backup protection, secrets, dedicated runtime identity, regional image repository, one Cloud Run service, and remote verification. GCS remains M4; billing/budget/D2, deletes, broad IAM, Cloud Build, and destructive recovery remain human boundaries | ACCEPTED |
| 046 | 2026-07-20 | v2.4 CHRISTENING + ADR-019: the product is NOCTURNE (night music — plays through the night so the composer hears the premiere; install name pipx install nocturne); Escher view = the Cube; Chrysopoeia = the learning loop. ADR-019 onboarding: two-secrets rule (OpenRouter always, GCP cloud-only; local mode = ONE secret), four contract commands (init/up/deploy/open), two wheels + bundled web assets + lockstep versioning, the Garden never ships; packet D3 opens after J | ACCEPTED |
| 047 | 2026-07-20 | ADR-020 SHARED PALACES (HORIZON like ADR-011; build forbidden until multi-tenant identity, M4): a shared Palace is a principal; contribution = consent-based selective COPY-WITH-LINEAGE (global rev_uid DAG already carries cross-palace provenance — zero schema footprint needed); revocation = tombstone the copy; collisions ride the existing dedup bands + curator merge queue + ADR-011 conflict taxonomy (combining palaces ≡ reconciling replicas); injection draws from the palace union with provenance in the gate; federation across spines = OQ-19 | ACCEPTED |
| 048 | 2026-07-21 | v2.5 B.6 rule 8 AGENT WALKTHROUGHS (SOPs for agents): every UI packet also executes a written human-style SOP live through interactive browser use — look, click, type, observe, judge, first person — with per-step screenshots + prose observations in verification/<packet>/SOP.md, a mandatory unscripted exploration segment, defects → Blight, design friction → human gate, and judges RE-EXECUTING SOPs at I1/J. Explicitly NOT dischargeable by scripts (rule 7 proves regressions; rule 8 proves experience). Owner's framing: traditional SOPs for humans, performed by agents | ACCEPTED |
| 049 | 2026-07-21 | v2.6 owner decisions: OQ-17 resolved — the Roots alpha channel encodes SELECTION FOCUS (selected full, others dimmed-but-present, floor 0.25), never expected value; ADR-019 clause 4 SEED INGESTION (markdown upload → curator split → approval queue; M2) so cold start is product surface; remotes renamed to the nocturne-* family with a new `nocturne` splash repo as the single new-user front door | ACCEPTED |
| 050 | 2026-07-22 | v2.7 GATE-DAY DATA + v0.2 PROPOSAL ADOPTIONS (live Palace audit + owner's Code-Puppy v0.2 sheet review; notes/scorer-evolution.md): (1) HYBRID CANDIDATE RETRIEVAL — M2 candidate pool = vector top-50 ∪ Postgres FTS matches (exact-keyword memories with weak embeddings must reach the scorer); (2) KEYWORDS MANDATE — C.6 agent instructions require 2-5 keywords per save; /remember generates label AND keywords in one completion (live data showed keyword-less units handicapped on f_kw); (3) TRAINING-DATA HYGIENE — Chrysopoeia learning/replay excludes verification/test principals (H5 fixtures observed in the live log); (4) curator CONSOLIDATION TAXONOMY merge/new/contradict/supersede + TYPED EDGE OVERLAY (1-hop, never first-pass retrieval); (5) M3 promotion blends reuse/stability/manual — never raw frequency; (6) formal `candidate` status for approval-queue units. Rejected from v0.2: questionnaire tuning (Invariant 14 — gate signals collect the same passively), SQLite local-first, discrete path-multiplier ladder (continuous f_loc superior). Entity/importance axes routed to the agentic-axes replay pipeline (notes) | ACCEPTED |

## D.3 Resolved-question index (where each folded)

OQ-1 block placement → ADR-002 · OQ-2 offline mode → ADR-003 · OQ-3 mid-thread
live reads → ADR-004 · OQ-6 presence transport → ADR-006 · OQ-7 durable
execution → ADR-001 · OQ-8 framework → ADR-001 · OQ-9 web command center →
ADR-008 · OQ-10 M1 slice → B.3 · OQ-11 identity → ADR-008 · OQ-13 pure relay →
ADR-008 · OQ-16 providers/models → C.5 · OQ-14 repo/product names → 1.0
vernacular (v1.10) · OQ-17 roots alpha → selection focus, not EV
(ADR-018, 2026-07-21)

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
