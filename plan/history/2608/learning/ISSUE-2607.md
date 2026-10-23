---
title: Pre-existing CI failure — spec coverage ratchet ceiling stale
type: learning
source: ISSUE-2607
timestamp: "2026-08-25T00:00:00Z"
signal: concern
---

**Bug #2607**: `test_protocol_spec_coverage_floor` fails on `origin/main` — uncovered count 948 exceeds ceiling 947.

**Why:** A protocol-kind spec was added (or coverage mapping removed) without tightening the ratchet. Discovered during task/1932 validation on 2026-08-25.

**How to apply:** Any PR CI run will show this failure until #2607 is fixed. Note it as pre-existing when filing PRs that hit this failure.

**Promoted**: 2026-08-27 — archived (already in specs/notes/AGENTS.md or tracked as GitHub issue). Docs PR: <pending>.
