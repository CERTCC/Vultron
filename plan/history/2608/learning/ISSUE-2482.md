---
title: A ref annotation that admits `str` cannot record an inline-only requirement
type: learning
timestamp: "2026-08-22T00:00:00Z"
source: ISSUE-2482
signal: spec-gap
---

CP-01-004 requires `as_CaseProposal` to carry its `as_VulnerabilityReport`
**inline**; a URI-only reference is not permitted, because the receiver may not
hold the report and no dereferencing mechanism is specified (AKM-03-001).

Nothing enforced it. The field is
`ActivityStreamRequiredRef[as_VulnerabilityReport]`, which expands to
`as_VulnerabilityReport | as_Link | str` — so a bare URI type-checks, and
`as_CaseProposal.model_validate({... "object": "urn:uuid:..."})` succeeds. The
requirement lived only in a docstring, so `_dehydrate_data` collapsed the report
like any other reference and the storage layer had nothing to consult.

**Why it was invisible.** Dehydration is only reversible when the nested object
has a record of its own, and ingress gives a record only to the **first** level of
an inbound activity's nesting. A second-level inline object collapses to an id
that no read can expand — and `model_copy`/`model_validate` do not object, so the
loss surfaced layers away as three separate "best-effort" skips, none of which
named the cause.

The existing `_KEEP_INLINE_NESTED_TYPES` set had already encountered this hazard
for Activities and `CaseLedgerEntry`, for exactly the same stated reason ("may not
have independent DataLayer records"). It was keyed on the *nested type*, so it
never generalised to "this declaring model requires this field inline".

**How to apply:**

- When a protocol requirement says a field carries an object rather than a
  reference, and the annotation still admits `str`, the requirement needs a
  second home that code can read. Declare it on the model —
  `VultronAS2Object.inline_required_refs` — not as a lookup table in the storage
  adapter, which is action at a distance from the field it governs.
- Recorded as DL-08-001 / DL-08-002 in `specs/datalayer.yaml`.
- Related trap on the same path: the received-side use case hands the tree a
  `by_alias=True` wire dump, because the `Accept` must carry the proposal inline
  on the wire (CP-05-003, MV-09-001). Rebuilding a *core* model from that dict
  drops `attributedTo`, since core declares `attributed_to` under
  `extra="ignore"`. Converting is the wire layer's job (`to_core()`); core must
  not import wire to do it (ARCH-03-001), so the caller converts and passes the
  result down. Validating a wire-spelled dict against a core model is silent
  field loss, every time.
- General shape: `extra="ignore"` plus a spelling difference plus a
  best-effort consumer equals a defect that cannot be observed at the point it
  occurs. When any two of those three are present, the third is worth checking.

**Promoted**: 2026-08-27 — already captured in specs/ (DL-08-001/002, PCR-01-003, CBT-01-003). Docs PR: <pending>.
