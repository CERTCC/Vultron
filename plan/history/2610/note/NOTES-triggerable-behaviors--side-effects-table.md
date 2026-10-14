---
source: NOTES-triggerable-behaviors--side-effects-table
timestamp: '2026-10-12T19:34:28.913801+00:00'
title: Side Effects of Emit FOO Behaviors (side-effect table)
type: note
---

**Archived:** 2026-10-12
**Reason:** stale copy — the table predates case creation at report receipt and duplicates each trigger tree's docstring
**Superseded by:** trigger tree module docstrings under `vultron/core/behaviors/`

---

## Side Effects of "Emit FOO" Behaviors

The diagrams in `docs/topics/behavior_logic/` simplify "emit FOO" nodes to
look like single-message outputs. In practice each execution task may have
cascading side effects. Implementers MUST capture all relevant side effects
in the BT structure for each triggerable behavior, even when they are not
shown in the original diagram.

Known side effects by behavior:

| Behavior | Side effects beyond sending the message |
|---|---|
| `validate-report` (emit RV) | Create `VulnerabilityCase`; link reporter as participant; set receiver as case owner; trigger embargo resolution; link `VulnerabilityReport` to case |
| `reject-report` (emit RI hard) | Close the offer; log reason; no case created |
| `engage-case` (emit RA) | Update participant RM state to ACTIVE; log event |
| `defer-case` (emit RD) | Update participant RM state to DEFERRED; log event |
| `close-report` | Update RM state; log event; potentially trigger downstream notifications |
| `terminate-embargo` (emit ET) | Update `CaseStatus.em_state`; notify all participants; log reason |
| `propose-embargo` (emit EV/EP) | Create or update `EmbargoEvent` on case; notify participants |
| `evaluate-embargo` (emit EA) | Update local embargo acceptance state; send Accept/Reject |

The above is a non-exhaustive list. As implementation proceeds, each
triggerable behavior SHOULD document its full side-effect list in its
implementation module docstring.
