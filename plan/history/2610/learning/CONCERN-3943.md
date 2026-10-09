---
source: CONCERN-3943
timestamp: '2026-10-07T19:49:42.539289+00:00'
title: MS-12-006 relabels protocol-worded requirements whose only code reference is
  the test path in their verification clause
type: learning
---

## Concern

MS-12-006 scans `statement` **or** `verification` of a story-less `kind: protocol` spec for a codebase construct. In #3600 the detector flagged 214 specs; **206 matched only in `verification:`**, because MS-10-003 obliges every MUST to name how it is verified and the corpus convention is a `test/…` or `vultron/…` path. Read statement by statement, about 90 of the relabeled specs are wire or state-machine obligations an independent implementer would have to satisfy — `CSB-12-002` (a Participant entering CS Public Aware MUST NOT seek new embargoes), `CLP-14-010` (gapless `log_index`), `SYNC-03-003` (idempotent replication), `RF-02-002` (`Accept` carries `object`), `MV-03-002` (blank required field is absent), the `IE` inbox status codes. They now render on the `project` page because their verification names the test that proves them.

The relabel was applied as #3600 specified (the tree is mechanical by design, ADR-0038; the issue says not to widen the detector). The open question is a spec ambiguity in MS-12-002 / MS-12-006 that neither states: **does a `verification:` clause's path count as "the spec referencing a file path"?**

- **Yes** (the current reading): a protocol requirement must be verifiable without naming this codebase, so protocol-tier `verification:` clauses should read like conformance tests, and MS-10-003's convention needs a protocol-tier variant.
- **No**: MS-12-006 should scan `statement` only, and the ~90 return to `protocol` — with their `missing_story_reference` suppressions, unless stories arrive first (#2717), which is the wrong-way ratchet #3600 set out to stop.

Under either reading, mapping these specs to existing user stories restores `protocol`, so they are the first candidates for #3601 / #2717.

<details><summary>The 90 protocol-worded specs relabeled to <code>project</code> in #3600 (one agent's reading, not adjudicated)</summary>

```text
CLP-10-015 CLP-10-016 CLP-14-003 CLP-14-006 CLP-14-009 CLP-14-010 CLP-15-001 CLP-15-003 CLP-15-006 CLP-15-007
CM-02-003 CM-02-010 CM-04-005 CM-04-009 CM-14-007 CM-16-010 CM-21-010 CM-28-007 CP-05-005
CSB-07-001 CSB-09-001 CSB-09-002 CSB-10-001 CSB-10-002 CSB-11-001 CSB-11-002 CSB-12-002 CSB-12-003 CSB-13-003 CSB-14-001 CSB-14-002 CSB-17-001 CSB-17-006 CSB-17-007 CSB-18-001
ENC-03-001 EP-05-002 IE-02-003 IE-03-001 IE-03-002 IE-03-003 IE-04-002 IE-05-001 IE-07-001 IE-08-001 IE-10-001
MSM-05-002 MSM-07-001 MSM-07-002 MSM-07-003 MSM-07-004 MSM-07-005 MSM-07-006 MSM-07-007
MV-03-002 MV-04-003 MV-05-002 MV-11-002 MV-11-003 PRM-06-002 PRM-06-005
RF-02-002 RF-02-003 RF-02-004 RF-02-005 RF-03-003 RF-03-004 RF-04-003 RF-04-004 RF-09-001
RSH-05-018 RSH-05-019 RSH-05-020 RSH-06-006 RSH-08-003 SE-01-001 SE-01-002 SE-01-004
SYNC-02-004 SYNC-03-003 SYNC-03-004 SYNC-05-001 SYNC-08-004 SYNC-15-012 VAM-01-007 VAM-01-008 VM-07-001 VM-07-002 VM-08-002 VP-17-001
```

</details>

## Asks

1. Decide the MS-12-002 / MS-12-006 reading above and record it in `specs/meta-specifications.yaml` (and `notes/spec-authoring-rules.md` § "Why MS-12-006 is scoped the way it is").
2. Re-adjudicate the 90 under that reading: map to stories where a story exists, else rewrite the verification or accept `project`.

Surfaced by #3600; the learning file `plan/incoming/learnings/20260930-3600-ms-12-006-flags-protocol-worded-requirements-through-the-test-path-in-their-verification.md` carries the evidence.

**Resolved**: 2026-10-07 — implementation tracked in #4312, #3601, #2717.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4313>.
Notes: `notes/spec-authoring-rules.md`.

Ruling: audit #4195 settled that MS-12-006 scans `statement` only.

# 4312 fixes the detector and reverts the ~90 relabels, with a one-time MS-12-007 ceiling raise

# 3601 and #2717 are reparented under #4194 as the story burn-down
