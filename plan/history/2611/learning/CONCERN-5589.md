---
source: CONCERN-5589
timestamp: '2026-11-02T15:36:28.930852+00:00'
title: Catch a reordered shared story fragment at PR time
type: learning
---

Theme: theme:full-cvd-scenario-coverage — every documented CVD recipe stays runnable, and a silent change to a shared story fragment does not reach `main` unnoticed.

## Problem

Composition (#5533) moves each family's opening into one shared fragment module. A reorder or an edit inside a shared fragment changes every scenario in the family at once. Nothing in PR CI notices.

Measured on PR #5588 by moving one `choose` item past its fragment inside `COORDINATOR_INVITES_VENDOR`:

| Check | Result on the mutated tree |
|---|---|
| `test/demo_unit/test_story.py` (40 tests) | pass |
| `test/architecture/test_scenario_reports_every_step.py` | pass |
| `TestComposedFamilies` byte-identity check (DEMOCI-11-018) | pass |
| `export-demo-recordings --scenario rcv --scenario rcv-reject --report-changes` | **exit 3**, both `steps.json` changed |

Two reasons the byte-identity check cannot catch it:

1. It reads the two **committed** recordings and compares them with each other. A code change that does not regenerate them leaves its input untouched.
2. Even regenerated, a reorder inside the *shared* prefix moves both scenarios of the family identically, so they stay byte-identical to each other. The check only fails when the two openings diverge, which composition makes structurally hard.

The recordings freshness check is the thing that catches it, and it runs daily on `main` and files a refresh Task rather than failing (`.github/workflows/demo-recordings.yml`, deliberately — a full regeneration is a 60-minute job). So between a composition PR and the next day's run, the evidence for DEMOMA-17-002 is a manual command.

## Why it is worth closing

Issues #5534, #5535 and #5536 each compose two to four more scenarios onto a shared opening, and #5537 removes the hand-placed `reach_step` that is today the redundant second statement of each path. After that, a shared fragment is the only place a scenario's acts are written

## Suggested shape

Regenerating only the composed families is cheap because `record_scenario` runs the scenario in-process with routed in-memory nodes — no containers. The two scenarios of `{rcv, rcv-reject}` regenerate in under two minutes in the dev container. A PR-time check over `COMPOSED_FAMILIES` only would therefore cost roughly a minute per family and grow with the migration, unlike a full-tree regeneration.

Open questions for whoever takes it:

- Add it to the existing `Tests (pytest)` job, or its own job? A separate job gives a named status per family.
- Assert "no change" (fails the PR, author regenerates and commits) or "regenerate and diff" (same thing, clearer error)?
- Does it belong to DEMOCI-11-018's `verification:` clause, or a new requirement? Today DEMOCI-11-018 obliges a property of the committed recordings, and this check is about the committed recordings matching the code — a different claim.

## Acceptance

- A reordered or edited shared story fragment that changes any composed family's recording fails a PR check.
- The check's cost is proportional to the number of composed families, not to the whole tree.
- The reorder experiment above is pinned as a test or recorded in the issue's closing notes, so the gate is not itself vacuous.
- `notes/demo-scenario-tree.md` § "Composition" drops the manual-gate instruction once the gate exists.

**Resolved**: 2026-11-02 — implementation tracked in #5613; follow-up Ideas #5614 (differential base-vs-head recording check on demo PRs) and #5615 (readable domain-terms plot).
Docs PR: <https://github.com/CERTCC/Vultron/pull/5612>.
Spec: `specs/demo-ci.yaml` (DEMOCI-11-034, DEMOCI-11-035).
Notes: `notes/demo-scenario-tree.md`.

Decision: a generated, drift-checked plot manifest of each composed story
(choices and fragment names in order), free at PR time. Rejected: comparing a
fresh recording with the committed files, byte or normalized — the recording
clock ticks on every read, #5591 races, and it would make PRs regenerate
recordings, which the daily run exists to avoid (#3901).
