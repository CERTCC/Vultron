---
source: ISSUE-1563
timestamp: '2026-07-21T20:29:27.104868+00:00'
title: Decompose CaseStatus/ParticipantStatus into per-machine dimension objects
type: implementation
---

## Issue #1563 — Decompose CaseStatus/ParticipantStatus into per-machine dimension objects

Introduced five dimension classes (EmDimension, PxaDimension, RmDimension, VfdDimension, PecDimension) in vultron/core/models/dimensions.py. Replaced flat enum fields on core CaseStatus and ParticipantStatus with typed dimension objects. Wire-layer models retain flat fields; bidirectional migration validators ensure JSON compatibility. Updated 35+ test files and all BT behavior nodes that access state-machine fields.

PR: <https://github.com/CERTCC/Vultron/pull/1573>
