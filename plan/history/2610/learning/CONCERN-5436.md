---
source: CONCERN-5436
timestamp: '2026-10-29T14:02:26.535804+00:00'
title: CSB-06 made an observed attack set Public Aware
type: learning
---

Theme: theme:requirements-traceability — decide whether an observed attack makes a vulnerability public, so the CS receive rules agree with the CS model.

## Concern

CSB-06-001, CSB-06-002 and CSB-06-003 say that a participant that receives CA (attacks observed) while the vulnerability is not public sets **both** Public Aware and Attacks Observed (`···p·a → ···P·A`). Their rationale cites a "constraint C-16". No other requirement, note or decision record defines C-16.

The rest of the specification says that an attack does not make a vulnerability public:

- CSB-17-003 makes only `vP` and `pX` ephemeral, so `pxA` is a state a case can rest in.
- CSB-17-002 and CSB-17-008 allow a CS transition to change exactly one dimension, and require a receiver to reject a transition that changes two at once.
- §8.2 of the Protocol Specification (`docs/reference/vultron-spec/_cs-dimensions.md`) says an attack can be detected without its mechanism being understood or disclosed, so `pxA` is a legitimate resting state.
- The CS transition grammar (`docs/topics/process_models/cs/transitions.md`) has `vfdpxa → A → vfdpxA`.

Found while reconciling the Case Tracking Models page (#4898). That page states the CSB-17 reading. The CSB-06 receive rules are not rendered on it.

## Question

Does observing an attack imply public awareness?

- If **no**: reword CSB-06-001 to CSB-06-003 to set only A (`···p·a → ···p·A`), and remove the C-16 rationale.
- If **yes**: the CS model, CSB-17-002, CSB-17-003, CSB-17-008 and §8.2 need to change, and C-16 needs a definition.

Governing specs: CSB-06, CSB-17, CSB-18-004

**Resolved**: 2026-10-29 — fixed directly as a spec bug; no implementation issue (code already sets only the attacks bit). Observing attacks is evidence of exploitation, not public information about the vulnerability. CSB-06-001/002/003/005/010 reworded; CSB-14-002 retired (replaced by CSB-17-002).
Docs PR: <https://github.com/CERTCC/Vultron/pull/5440>.
Spec: `specs/cs-behavior.yaml`.
