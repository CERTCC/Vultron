---
source: ISSUE-471
timestamp: '2026-06-01T15:43:47.921806+00:00'
title: Two-actor demo tutorial
type: implementation
---

## Issue #471 — Two-actor demo — write tutorial docs/tutorials/two-actor-demo.md

Added `docs/tutorials/two-actor-demo.md`, a hands-on tutorial for the
two-actor (Finder + Vendor) CVD demo targeting users learning to run the
demo for the first time.

### Contents

- Prerequisites and setup (Docker, Docker Compose, `.env` file)
- Step-by-step run instructions with the docker compose command and
  success indicator
- Mermaid sequence diagram at the protocol state changes level (4 phases,
  milestones M1–M7)
- Per-phase narrative matching actual execution order: notes exchange (M3)
  runs before SYNC-2 verification (M2)
- Activity log interpretation guide with correct milestone markers
  (`✅` for M1, M3–M7; `✓` for M2) and real emoji prefixes
  (`🚥`/`🟢`/`🔴` for steps, `📋`/`✅`/`❌` for checks)
- Troubleshooting section with dedicated subheadings
- Cross-reference to `docs/reference/two-actor-demo-protocol.md`

Also registered the new page in `mkdocs.yml` and updated
`docs/tutorials/index.md`.

PR: [#641](https://github.com/CERTCC/Vultron/pull/641)
