---
source: ISSUE-1923
timestamp: '2026-08-03T20:04:12.256134+00:00'
title: Add actor6 service to docker-compose + seed-actor6.yaml (FCVCV)
type: implementation
---

## Issue #1923 — feat: add actor6 service to docker-compose + seed-actor6.yaml (FCVCV)

Added the `actor6` container (VendorDeployer, V2) to the multi-actor Docker
Compose stack for the FCVCV 5-party scenario (DEMOMA-19-001).

Changes: actor6 service in docker-compose-multi-actor.yml using *actor-service
anchor with VENDOR+DEPLOYER roles; seed-actor6.yaml with five peers (Finder,
Vendor, Coordinator, Coordinator2/actor5, CaseActor); actor6 added to
demo-runner depends_on and VULTRON_VENDOR_DEPLOYER_BASE_URL env var; actor6-data
named volume; service-colors.env entry; ACTOR6_HOST_PORT in integration test
usage doc; TestSeedActor6Config (8 tests).

PR: <https://github.com/CERTCC/Vultron/pull/1945>
