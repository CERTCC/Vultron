---
title: "FCCV-handoff: reuse existing compose services via role remapping"
type: learning
timestamp: "2026-07-22T00:00:00Z"
source: ISSUE-1216
signal: design-question
---

For the FCCV-handoff scenario the actor-to-container mapping reuses the existing
`docker-compose-multi-actor.yml` services unchanged: `vendor`→C1 (initial
CASE_OWNER), `coordinator`→C2 (new CASE_OWNER after transfer), `vendor2`→Vendor,
`case-actor`→CaseActor.

The alternative was to add new named services (`c1`, `c2`, `vendor`) to the
compose file.  Remapping was chosen because: (a) the compose file is shared
across all multi-actor scenarios and adding services would affect every job;
(b) the deterministic actor-ID pattern (`http://<hostname>:7999/api/v2/actors/<name>`)
means the seeding function controls the logical name, not the service name;
(c) the existing CI jobs already pin action versions to these service names.

The env-var bindings follow the same pattern: `VULTRON_VENDOR_BASE_URL`→C1,
`VULTRON_COORDINATOR_BASE_URL`→C2, `VULTRON_VENDOR2_BASE_URL`→Vendor.
The CLI option names (`--c1-url`, `--c2-url`) use the semantic role names to
avoid confusion at the call site, even though the underlying env vars reference
the container service names.

**Promoted**: 2026-07-28 — container naming guidance added to vultron/demo/AGENTS.md; neutral-service-name idea tracked as ISSUE-1786.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1790>0>0>0>0>0>0>.
