---
source: CONCERN-2665
timestamp: '2026-09-03T14:23:54.683031+00:00'
title: per-deployer/per-vendor dependency tracking for fine-grained VF→D causal gate
type: learning
---

## Concern

The current CSB-15-004 causal gate enforces a generic constraint: a DEPLOYER-only
actor may advance `d → D` only when *some* VENDOR participant in the case has reached
`vf.state = VF` (fix-ready). This is correct but coarse.

The finer-grained question — *which specific vendor* does a given deployer depend on
before they can deploy — has no answer in the current data model. The system
does not track which vendor produced the fix that a particular deployer is applying.

## Example gap

If a case has two vendor participants (Vendor A at `VF`, Vendor B still at `Vf`)
and a deployer that depends only on Vendor B's fix, the current causal gate would
permit the deployer to advance to `D` even though the fix they need is not ready.

## Out of scope for #2595

This gap was explicitly identified during planning for #2595 and deferred. The VFD
structural split (#2662–#2664) implements the generic gate, which is a sound
improvement over the previous state. The fine-grained dependency is a separate concern.

## Possible directions

1. Add a `depends_on: list[participant_id]` field to `ParticipantStatus` or `CaseParticipant`
2. Track vendor-deployer dependency at the case graph level (edges)
3. Leave the generic gate in place and document the known limitation

**Resolved**: 2026-09-03 — per-deployer/per-vendor pairing out of scope (too complex to
manage in real cases); implementing the generic "some vendor at VF" gate only.
Implementation tracked in #3109.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3108>.
Notes: `notes/case-state-model.md` § "CSB-15-004 Causal Gate: DEPLOYER-only d→D".
