---
source: CONCERN-2260
timestamp: '2026-08-13T14:17:54.375897+00:00'
title: 'Core ParticipantStatus wire concerns: rendering belongs behind a port, not
  on the model'
type: learning
---

Docs PR: <https://github.com/CERTCC/Vultron/pull/2285>
ADR: ADR-0063
Impl chain: #2286 → #2287 / #2288 → #2289 (Epic #2222)

## What the concern claimed, and what was actually true

CONCERN-2260 flagged two things on core `ParticipantStatus`: `alias_generator=to_camel`
(an ARCH-12-003 violation) and a `_migrate_flat_fields` validator accepting flat wire
spellings. It asked for a migration plan covering the canonical persisted key shape and
the legacy-row read path.

**The stated blocker was false.** `Record.from_obj` calls
`model_dump(mode="json", serialize_as_any=True)` with **no** `by_alias`
(`vultron/adapters/driven/db_record.py:367-369`), so persisted rows are already
snake_case. Removing `alias_generator` does not change the persisted key shape and
implies no persistence-schema migration. Verified by dumping
`Record.from_obj(ParticipantStatus(...)).data_` and inspecting the keys. Combined with
"no stale data exists — nobody uses this code in prod yet", the entire legacy-row
question dissolved.

Generalisable: **when an issue states a blocker, check whether the blocker exists before
planning around it.** Two of this concern's three questions were answered by one
`model_dump` call. The plan that would have been written from the issue text as given
(persisted-shape decision + legacy-row migration path) would have been mostly wasted
work.

## The actual defect was the opposite of the one reported

The concern framed `alias_generator` as an over-permissive core model. The real problem
is that it is **insufficient**: core and wire `ParticipantStatus` differ *structurally*
(core nests `consent: PecDimension`, wire carries a flat `emConsentState`), so an alias
generator cannot bridge them. `build_add_participant_status_snapshot` therefore
hand-patched the dumped dict — a partial reimplementation of
`as_ParticipantStatus.from_core()` living in core, covering one field of one type.

The tell was findable by asking what the mechanism was *for* rather than whether it was
*allowed*: a layering rule cited a violation, but the hand-patch next to it showed the
mechanism didn't even work. **A workaround that needs per-field special-casing to reach
its goal is evidence the capability is in the wrong layer, not that the rule is wrong.**

The pattern had also replicated: `dimension_filter._build_patch` writes
`patch["caseStatus"] = {"emState": ..., "pxaState": ...}` and
`accept_invite._build_snapshot` hand-builds a wire-spelled fallback dict. Three sites
independently reinvented a little wire spelling.

## Reframing by asking what the artefact is FOR

The decisive move in the interview was not resolving "may core import wire?" but
answering "what are case ledger entries FOR?". Grounding in CLP-07-001 (payloadSnapshot
MUST be the verbatim AS2 activity or a deterministic canonical normalization),
CLP-01-003/004 (the ledger is the replication substrate) and CLP-07-006 (nested objects
inline as full objects) established that snapshots are outward-facing wire contracts for
receiver replay. camelCase is *correct* there — which makes rendering a wire-layer
responsibility, and the import question a detail rather than the crux.

The candidate design that did *not* survive this reframing was moving ledger **writing**
behind a port. CLP-09-002 forbids bare canonical commits from any production call site
outside the guarded composition, and CLP-10-005..008 constrain `execute()`. So only entry
*rendering* moves; the role-gated commit stays in `CommitCaseLedgerEntryNode`. **Checking
a proposed seam against the authorization specs before committing to it prevented an ADR
that would have contradicted CLP-09.**

## Removing a shim without a guard is a silent data-loss bug

Deleting `_migrate_flat_fields` alone would make a flat `rm_state` key *silently
discarded* (`extra="ignore"` is the Pydantic default) and `rm.state` default to
`RM.START` — a whole RM ladder lost with no error. Codified as SDO-03-005, and as an
AGENTS.md pitfall.

A methodological note: the first attempt to test this simulated shim removal by
subclassing `ParticipantStatus` and assigning the validator to a no-op. It still returned
`RM.RECEIVED`, because Pydantic registers validators in `__pydantic_decorators__` and
attribute patching does not disable them. **Patching a Pydantic validator by attribute
assignment silently does nothing** — the inconclusive result looked like a passing
result. Testing the underlying mechanism instead (confirm `extra` is `ignore`, confirm a
bogus key is accepted) gave the real answer.

## Re-enumerate against current main before finalising

`ADR-0061` (per-dimension ParticipantStatus adjudication) landed after the planning
baseline was taken, and its new `_to_core_status` helper **explicitly depends on the
shim** — its docstring says "the core model's `_migrate_flat_fields` validator accepts
that shape, so a dump-and-revalidate normalises both". A fifth consumer appeared mid-plan
in an area under active change. Caught only by re-running `grep -rn 'by_alias=True'
vultron/core/` after the branch was freshened, before opening the PR. Captured as
ARCH-20-007 (no dump-and-revalidate normalisation).

The same re-enumeration corrected a spec entry that was about to ship wrong: the original
ARCH-20-001 verification said "no module under `vultron/core/` passes `by_alias=True`",
which is unsatisfiable — core legitimately dumps already-wire objects on the
verbatim-capture path. **Scoping a MUST to the property you actually mean (core-*branch*
objects) matters; an unsatisfiable verification criterion gets ratcheted, and this whole
concern is what a ratchet costs after two years.**

## Scoping decision

The user's instruction was "fix it all in one go. yes it's big, but piecemeal stuff has
led us into issue propagation hell" — this area generated #1991 → #2232 → #2260 → #2268,
each fix creating the conditions for the next report. The plan does the comprehensive
version (all 8 classes, port + adapter, all rendering sites, #1991 closed) decomposed
into four *ordered, individually-mergeable* steps rather than one giant PR or four
independent ones. Each step leaves main working; the chain must complete.
