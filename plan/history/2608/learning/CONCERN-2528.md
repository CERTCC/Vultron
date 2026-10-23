---
source: CONCERN-2528
timestamp: '2026-08-28T16:40:04.789910+00:00'
title: Scatter topics/future_work/ to permanent homes
type: learning
---

Resolved issue #2528 (continuation of #601) via PR #2822.

Removed the `docs/topics/future_work/` section entirely from the site nav.
Each of the 5 pages was moved to its permanent home with a dated
historical-context admonition (2026-08-28):

| Old path | New path | Notes |
|---|---|---|
| `topics/future_work/cs_model_limitations.md` | `topics/process_models/cs/` | Terminology note: agents → Actors (ADR-0024) |
| `topics/future_work/cvd_directory.md` | `topics/other_uses/` | Links to issues #1189, #2068, #2469 |
| `topics/future_work/reward_functions.md` | `reference/measuring_cvd/` | Still open research |
| `topics/future_work/mod_sim.md` | `reference/measuring_cvd/` | Reference impl now exists |
| `topics/future_work/ontology.md` | folded into `reference/ontology/index.md` | Motivation prose + Related Work absorbed |

Cross-links updated in 5 files: `rm/index.md`, `em/index.md`,
`desirable_histories.md`, `iso_5895_2022.md`, `messages.md`.
`topics/index.md` grid card removed. mkdocs.yml Future Work nav section deleted.

No follow-up implementation issues created (scope complete in this PR).

Docs PR: <https://github.com/CERTCC/Vultron/pull/2822>
