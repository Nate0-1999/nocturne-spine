# D1 GCP deployment evidence

Status: **DONE — one protected Cloud Run Spine passed the real broker-backed
round trip and typed Harness smoke.** This is redacted packet evidence, not the
independent M1 verdict reserved by SPEC B.6. No credential, bearer token,
database URL, access token, Secret Manager payload, memory body, or persisted
application-data identifier appears here without one-way hashing.

## Verified ground

The final source revision is Spine
`e0cf50d50283cd2c4f800272b832b8166e299cab`. In the final handoff run, its full
suite passed against pgvector Postgres and Harness's non-contract suite passed
with only the two intentional live-contract tests deselected:

```text
Spine:   160 passed in 5.19s
Harness: 220 passed, 2 deselected in 1.20s
```

Ruff lint, Ruff formatting, lockfile checks, committed OpenAPI freshness, and
whitespace checks also passed. The hidden cloud health alias leaves the
committed OpenAPI document unchanged.

## Provisioned state — re-audited 2026-07-21

- Project `n8-memory-palace` and region/location `us-central1` were explicit on
  every applicable command. Ambient gcloud project state was never authority.
- Cloud SQL `n8-memory-palace-db` is RUNNABLE PostgreSQL 16. Database and
  built-in user `spine` exist. Automated backups start at 03:00 UTC in
  `us-central1`, retain seven backups and seven days of transaction logs, PITR
  is enabled, and deletion protection is enabled. Production Alembic was run
  separately through Cloud SQL Auth Proxy and proved `0002 (head)` during the
  initial deployment; migrations are absent from the container command.
- Secret Manager contains version 1 of `spine-database-url`, `spine-token`, and
  `spine-openrouter-api-key`, each with a user-managed replica only in
  `us-central1`.
- Runtime identity `spine-runtime@n8-memory-palace.iam.gserviceaccount.com` has
  only `roles/cloudsql.client` at project scope and
  `roles/secretmanager.secretAccessor` on each of those three secrets. The
  default compute identity is not attached.
- Artifact Registry has one Docker repository, `spine`, with immutable tags.
  The Linux/amd64 image tag is the source commit above; its index digest is
  `sha256:dd06579e7447c1110ecb7c9be190d293ed79bb319d1b99b1299ee736b648cad3`.
  Cloud Run resolved the amd64 manifest as
  `sha256:975c1e68386c801cedcc3ea20e06009e54b7e9859b7d1551c4835821baaff113`.
- Exactly one Cloud Run service exists for D1: `n8-memory-palace-spine`.
  Revision `n8-memory-palace-spine-00003-pjh` is Ready/Active and receives 100%
  of default traffic. It uses Gen2, port 8000, max scale 1, the dedicated
  runtime identity, the Cloud SQL attachment, the three secret environment
  references, and explicit OpenRouter URL/model settings. Invoker IAM checking
  is disabled and the service-scoped `allUsers` Invoker binding remains, so
  transport is public while every application route remains protected by the
  static Spine bearer.

Machine-readable redacted state is in `cloud-state.json`.

## Cloud Run reserved-path diagnosis and repair

The prior D1 handoff misclassified Google's unlogged HTML 404 for `/healthz` as
a broken service route. Ordinary paths reached Spine, while the exact health
path did not. Google documents that Cloud Run reserves some paths ending in
`z` and recommends avoiding every such path:
<https://docs.cloud.google.com/run/docs/known-issues#reserved-url-paths>.

Spine Decision 016 therefore retains the specified, authenticated `/healthz`
for local and Compose acceptance and adds `/health` as a hidden alias of the
same handler for Cloud Run. On both advertised service hosts, unauthenticated
`/health` returned Spine's RFC 7807 `401` and the app-bearer request returned
`200 {"ok":true,"version":"0.1.0"}`. `/healthz` continues to receive the
expected Google edge HTML 404 in Cloud Run. Revision request logs contain the
`/health` requests and the API proof below; the reserved-path requests never
reach the container.

The earlier bounded diagnosis also disabled the Invoker IAM check without a
revision and added traffic tag `d1v` to the then-current revision. The tag is
still pinned to `n8-memory-palace-spine-00002-2bs`; it changes neither default
traffic nor resource count and was not destructively removed. No second
service, region, load balancer, custom domain, broad IAM grant, GCS resource,
Cloud Build path, delete, or replacement was used.

## Remote real-embedding round trip

Against
`https://n8-memory-palace-spine-713925718873.us-central1.run.app`, a unique,
isolated principal/project/thread completed:

```text
create:         201; embedding_model=openai/text-embedding-3-small; revision=1
hard duplicate: 409; duplicate_of_created=true; cosine score=1.0
prepare:        200; scorer_version=v0; injected=1; near_misses=0
commit:         200; final_block_nonempty=true; wrong_removed=0
```

This exercised OpenRouter's real embeddings endpoint through Spine's generic
compatible adapter. Cloud Run request logs independently show the expected API
status sequence `201, 409, 200, 200`. Correlation values are one-way SHA-256
prefixes only:

```text
run_ref=5dedbcf59b4f7b77
memory_id=e84f3d4dde21b6cc
injection_id=3197fe7fc373068e
principal/project=cbf4e53745ca8836
thread_id=537bba9f6319b860
body=f01d30328feabaf3
final_block=813541d48e288c35
```

## Typed Harness smoke

The ignored operator `harness/.env` now points `SPINE_URL` at the deployed
service and remains mode `0600`. `HarnessSettings` loaded that URL and token;
the production `SpineClient.list_memories` issued project, ACTIVE-status, and
text-query filters. Its closed response model found exactly one matching unit,
whose ID hash was `e84f3d4dde21b6cc`, revision was 2, injection count was 1,
and embedding model was `openai/text-embedding-3-small`.

The runtime configuration and evidence now agree: chat and semantic memory use
OpenRouter by default; the direct-provider OpenAI environment line remains only
a legacy override and was not deployed.
