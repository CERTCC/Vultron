---
title: Promoting one event type required 12 coordinated spec edits because sibling requirements restate each other's counts
type: learning
timestamp: 2026-08-12T00:00:00Z
source: ISSUE-2266-spec-drift
signal: concern
---

## Observation

ISSUE-2266's AC-1 asked for one amendment: DEMOMA-16-001, four universal event types →
five. The phrase "the four universal types (DEMOMA-16-001)" turned out to be copied into
nine sibling statements (DEMOMA-16-002 … -16-011) and into two requirements in a
*different* spec file (DEMOCI-04-004, DEMOCI-06-002). Twelve coordinated edits, eleven of
them outside the literal acceptance criteria.

Doing only AC-1 would have left ten MUST-level statements asserting a count the spec
itself contradicts, and every guard would have stayed green: the registry linter validates
that `DEMOMA-16-001` resolves as a cross-reference target, not the prose wrapped around
it. A reader of `specs/demo-ci.yaml` alone would have had no signal at all.

## Why it matters

This is spec-vs-spec drift, one level above the spec-vs-code drift DEMOMA-16-008 and
CONCERN-2243 exist to fight — and strictly harder to detect, because no test can fail.
Code drift eventually shows up as a red assertion; prose drift just means whoever reads
the wrong statement first is misinformed. The engage-case story in CONCERN-2243 started
with someone reasonably concluding, from a document that was locally self-consistent,
that `engage_case` was scenario-specific.

The restated count carries no normative force. "The universal types (DEMOMA-16-001)"
says exactly as much and cannot drift. That is the cheap structural fix; the expensive one
is a linter that understands number-words next to requirement references.

## Status

Filed as **#2277** (Concern, `size:M`, Someday) with the two-option direction: strip
restated counts from cross-references repo-wide plus a convention note, or lint for
counts adjacent to a requirement id.

Partial coverage landed with #2266: `test/ci/invariants/test_universal_event_types.py`
pins DEMOMA-16-001's enumeration against the nine harness constants. The ten sibling
statements and the two DEMOCI statements remain unguarded prose — see
`20260812-universal-event-type-ratchet-not-specified.md`.

**Promoted**: 2026-08-17 — captured in GitHub #2277 (open — already tracked).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>0>0>0>0>0>0>0>0>0>.
