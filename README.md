# nocturne-spine

`nocturne-spine` is NOCTURNE's Memory Palace service and migration package. It
is released in lockstep as a dependency of the public `nocturne-ai`
distribution.

The service owns the extraction consent boundary at `/v1/extractions` and
`/v1/approval-queue`. Pending units use the internal `candidate` lifecycle
state and are excluded from ordinary memory listing, search, and injection.
Queue decisions are append-only; approval enacts the proposed verdict through
revisioned head changes and typed lineage edges, while denial revision-
tombstones the candidate as rejected.

New users should start at the [NOCTURNE quickstart](https://github.com/Nate0-1999/nocturne)
and install `nocturne-ai`; they do not need to install this package separately.
