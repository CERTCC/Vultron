---
source: CONCERN-5118
timestamp: '2026-10-26T18:54:49.947772+00:00'
title: Most spec relationships predate the SR-13 definitions and have not been checked
  against them
type: learning
---

## Summary

SR-13 (from #4481) now defines what each `rel_type` asserts and which end is upstream. #4481 resolved every loop, and #5114 checked every `constrains` link. The rest of the corpus was written before those definitions existed and has not been checked against them: the `refines`, `depends_on`, `implements`, `satisfies`, `derives_from`, `extends`, `verifies`, `part_of` and `supersedes` links.

A link pointing the wrong way passes spec-lint unless it closes a loop. It still sends the "what does a change to this requirement affect?" walk the wrong way. Two kinds were found while writing the definitions:

- `CM-12-001` and `CM-14-001` each recorded `supersedes CM-22-001`, while their notes said CM-22-001 is the replacement.
- The `VAM … satisfies MSM …` links ran opposite to every other MSM/VAM link.

Both were fixed in #5116, which suggests more exist.

## Why it matters

The definitions make edge direction meaningful, so a wrong link is now a wrong answer to an impact query rather than just loose wording.

## Possible approaches

- Audit by type, cheapest signal first. For example, flag each link whose target's statement cites the source, a likely sign that the link sits on the wrong end, then judge the flagged links by hand.
- Or sample a random set per type to estimate the error rate before deciding whether a full pass is worth it.

Where: `specs/*.yaml` (the `relationships:` fields)

Governing specs: SR-13-001, SR-13-002, SR-13-003, SR-13-004, SR-13-006, SR-13-007, SR-13-008, SR-13-009, SR-13-011, SR-13-012

**Resolved**: 2026-10-26 — the pilot (HP, CS, ARCH, OX) is done in PR #5206; the
sweep is tracked in #5207, #5208, #5209, #5210, #5211, #5212 and #5213.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5206>.
Spec: `specs/spec-registry.yaml` (SR-13-017, SR-13-018).
Notes: `notes/spec-authoring-rules.md`.
