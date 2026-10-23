---
source: NOTES-triggerable-behaviors--three-way-report-validation
timestamp: '2026-09-17T17:32:55.815872+00:00'
title: Three-Way Report Validation
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) delivered
**Superseded by:** validate/invalidate/reject triggers; TRIG-03-004

---

## Three-Way Report Validation

The current `rm_validation_bt.md` documentation describes a binary
outcome (valid / invalid), but the protocol and implementation support
three distinct outcomes:

| Outcome | Protocol message | Trigger behavior | Semantics |
|---------|-----------------|-----------------|-----------|
| Accept | `Accept(Offer(Report))` | `validate-report` | Report is credible and in scope; case creation follows |
| Tentative reject | `TentativelyReject(Offer(Report))` | `invalidate-report` | Report cannot be validated yet ("soft close") |
| Hard reject | `Reject(Offer(Report))` | `reject-report` | Report is definitively out of scope or invalid ("hard close") |

**Documentation gap**: The "D" branch of `rm_validation_bt.md` currently
only models the soft-close (TentativelyReject) path. It SHOULD be split
into:

1. A condition: "reject outright?" (is the report clearly out of scope or
   fraudulent?)
2. A hard-close branch emitting `Reject(Offer(Report))`
3. The existing soft-close branch emitting `TentativelyReject(Offer(Report))`

The evaluation nodes in the "C" branch (evaluate credibility / evaluate
validity) SHOULD produce structured outputs (e.g., `credible: bool`,
`valid: bool`, plus optional analyst notes) that feed into a policy
evaluation step determining which of the three outcomes to produce. These
values need not be strictly binary in a full implementation; intermediate
confidence levels may be appropriate.

**Design Decision**: The `reject-report` trigger MUST require a `note`
field (reason is required; resolved — see `specs/triggerable-behaviors.yaml`
TB-03-004 and `specs/code-style.yaml` CS-08-001).
The `note` field MUST be present; it SHOULD be non-empty. This decision
led to a broader schema-validation pattern: optional string fields
throughout the codebase follow "if present, then non-empty" (CS-08-001).

---
