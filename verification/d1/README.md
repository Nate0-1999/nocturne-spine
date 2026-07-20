# D1 GCP deployment evidence

Status: **RETURNED_TODO — Cloud Run default URLs do not route to the ready
service.** This is redacted packet evidence, not the independent M1 verdict
reserved by SPEC B.6. No credential, bearer token, database URL, access token,
or Secret Manager payload appears here.

## Inherited ground

Before the claim, the pushed product heads were green:

```text
Spine:   160 passed in 5.43s
Harness: 220 passed, 2 deselected in 1.54s
```

The deselected Harness tests are the intentional live-contract tests. Garden,
Spine, and Harness tracked heads matched their upstreams; only the previously
reported untracked `.DS_Store` files existed.

## Provisioned state — 2026-07-20

- Project `n8-memory-palace`, region/location `us-central1` were explicit on
  every applicable command. Ambient gcloud project state was never used.
- Cloud SQL `n8-memory-palace-db` is RUNNABLE PostgreSQL 16. Database and
  built-in user `spine` exist. Automated backups start at 03:00 UTC in
  `us-central1`, retain seven backups and seven days of transaction logs, PITR
  is enabled, and deletion protection is enabled.
- Production Alembic ran through Cloud SQL Auth Proxy, separately from the
  container lifecycle. It applied `0001` then `0002`; `alembic current`
  returned `0002 (head)`.
- Secret Manager contains version 1 of `spine-database-url`, `spine-token`, and
  `spine-openrouter-api-key`, each with a user-managed replica only in
  `us-central1`. Values were supplied through locked files and never printed.
- Runtime identity `spine-runtime@n8-memory-palace.iam.gserviceaccount.com` has
  only `roles/cloudsql.client` at project scope and
  `roles/secretmanager.secretAccessor` on each of those three secrets. The
  default compute identity was neither attached nor changed.
- Artifact Registry contains one Docker repository, `spine`, with immutable
  tags. The image tag is Spine commit
  `3b4b80314bb2376a961168d56a2114287546ad90`; its amd64 index digest is
  `sha256:86d28c235854a68e0bcf40085f690df9d6c77cc27bfc9ac8b505712364f15a7b`.
  Cloud Run resolves the amd64 platform manifest as
  `sha256:a86789f5d99ddcdb463939f66a34dbc8e391dc1c70d2e195578c705ed7de55c7`.
- Cloud Run service `n8-memory-palace-spine` uses Gen2, port 8000, max scale 1,
  the dedicated runtime identity, the Cloud SQL attachment, the three secret
  environment references, and explicit OpenRouter URL/model settings. Migrations
  are absent from the Docker command. `allUsers` has only service-scoped
  `roles/run.invoker`, leaving the app bearer as authentication.

Machine-readable redacted state is in `cloud-state.json`.

## Routing blocker

Cloud Run reports revision `n8-memory-palace-spine-00002-2bs` Ready and Active,
RoutesReady/ConfigurationsReady true, and 100% traffic. Uvicorn starts healthy
on `0.0.0.0:8000`. The service advertises both:

```text
https://n8-memory-palace-spine-713925718873.us-central1.run.app
https://n8-memory-palace-spine-7wq3wmgcoq-uc.a.run.app
```

Nevertheless, both hosts return Google's edge-generated HTML 404 for
`/healthz`, with and without the app bearer. No request entry reaches the Cloud
Run revision log. The same unauthenticated 404 reproduced through an independent
external fetch. DNS resolves all advertised front-end addresses, ingress is
`all`, the default URL is enabled, the route generation is observed, and the
service IAM policy contains `allUsers` Invoker.

The relay reasserted the documented default-URL setting and the existing
100%-to-latest route without changing the revision; neither repaired routing.
One standard redeploy of the identical immutable image and configuration
created healthy revision `00002-2bs`; the edge still returned 404. No second
service, region, load balancer, traffic tag, custom domain, broad IAM grant,
Cloud Build path, delete, or destructive replacement was attempted.

Because the request never reaches Spine, the authenticated OpenRouter
create → duplicate → prepare → commit proof and Harness remote smoke could not
honestly run. The ignored local `harness/.env` was left with no `SPINE_URL`
change. H5 remains blocked on D1.

## Handoff verification

After writing this evidence, the inherited suites remained green:

```text
Spine:   160 passed in 5.12s
Harness: 220 passed, 2 deselected in 1.25s
```

Both Ruff checks, both formatting checks, both lock checks, whitespace checks,
and JSON parsing of `cloud-state.json` passed. The two deselections remain the
intentional live-contract reservation; they are not represented as remote
evidence.

## Resume boundary

The next D1 runner should first re-read this evidence and probe authenticated
`/healthz` on the two advertised URLs. If Cloud Run routing has converged, run
the redacted API round trip, update only ignored local `SPINE_URL`, run the
typed Harness remote smoke, and finish D1. If both URLs still return edge 404
with no request log, escalate the existing service/route to Google Cloud support
or the human; do not create a second service/region or widen IAM.

All temporary files containing the generated database password, database URL,
Spine token, OpenRouter key, or short-lived access token were removed before
handoff.
