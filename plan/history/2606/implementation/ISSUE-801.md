---
source: ISSUE-801
timestamp: '2026-06-09T17:48:30.458678+00:00'
title: Wire actor types moved to wire subclasses
type: implementation
---

## Issue #801 — Wire-branch actor types: replace re-export with proper wire subclasses

Replaced the wire `vultron_actor.py` core re-export shim with concrete wire-branch actor classes that inherit from `as_Actor`, preserving AS2 concerns in the wire layer while keeping adapter actor resolution compatible.

Updated wire actor tests to assert vocabulary mappings and verify core-to-wire `model_validate()` round-trip behavior for shared actor fields.

PR: [#851](https://github.com/CERTCC/Vultron/pull/851)
