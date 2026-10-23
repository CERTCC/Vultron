---
source: ISSUE-1619
timestamp: '2026-07-23T19:24:00.087508+00:00'
title: rename vendor2 service to actor5; add seed-coordinator2.yaml
type: implementation
---

## Issue #1619 — FCCV-extension: add DEMOMA-13 spec group and rename vendor2 service to actor5

Renamed the `vendor2` Docker Compose service to scenario-neutral `actor5`, allowing different scenarios to seed it with different actor identities. Added `seed-coordinator2.yaml` for the FCCV-extension scenario. Resolved a merge conflict with #1638 (matrix CI refactor).

PR: <https://github.com/CERTCC/Vultron/pull/1648>
