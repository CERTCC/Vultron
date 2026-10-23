---
source: NOTES-documentation-strategy--do-work-behaviors
timestamp: '2026-09-17T17:21:04.773444+00:00'
title: 'Do Work Behaviors: Human and Agent Tasks'
type: note
---

**Archived:** 2026-09-17
**Reason:** (b) duplicates the fuller enumeration in notes/do-work-behaviors.md
**Superseded by:** notes/do-work-behaviors.md

---

## "Do Work" Behaviors: Human and Agent Tasks

The behavior tree documentation defines a `do work` parallel node as a
container for tasks that are largely **outside the protocol's automated scope**.
These represent work participants must perform that results in protocol-visible
state transitions.

**`do work` sub-behaviors** (from `docs/topics/behavior_logic/do_work_bt.md`):

- **Deployment** — deploying a fix (triggers `D` event in CS)
- **Develop fix** — developing a patch (triggers `F` event in CS)
- **Report to others** — coordinating with other participants
- **Publication** — publishing vulnerability information (triggers `P` event)
- **Monitor threats** — watching for exploits/attacks (triggers `X`, `A` events)
- **Assign CVE ID** — identifier assignment (external coordination)
- **Acquire exploit** — obtaining exploit samples for analysis
- **Other work** — participant-specific tasks (explicitly a placeholder)

**Automation potential** (not yet analyzed systematically):

- **High automation potential**: CVE ID assignment requests (structured API
  calls to CVE Numbering Authorities), monitoring for exploit publication
  (external feed integration), monitoring for active attacks (threat intel
  feeds).
- **Medium automation potential**: Structured reporting to other participants
  (message composition and sending is automatable; decision to report is not).
- **Low automation potential**: Fix development, fix deployment, embargo
  negotiation — these require domain expertise and human judgment.

**Implication for the prototype**: The `do work` items are natural candidates
for posing as tasks to a human or AI agent. Future UI design or agent
integration should expose these as actionable work items given the current
case state (see `notes/case-state-model.md` for the potential actions
framework).

---
