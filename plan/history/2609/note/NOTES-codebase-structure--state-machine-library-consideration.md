---
source: NOTES-codebase-structure--state-machine-library-consideration
timestamp: '2026-09-17T17:13:37.347581+00:00'
title: State Machine Library Consideration
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,e) transitions adopted throughout core/states/
**Superseded by:** vultron/core/states/; STACK.md (transitions>=0.9.3)

---

## State Machine Library Consideration

The RM, EM, and CS state machines are currently implemented as manually-defined
enums with no formal state machine enforcement. The
[`transitions`](https://github.com/pytransitions/transitions) Python library
provides a clean, declarative way to define state machines with guards,
callbacks, and transition tables.

**Long-term consideration**: Integrating `transitions` would make it easier to
define and maintain the RM/EM/CS state machines, enforce valid state transitions
at runtime, and generate transition diagrams for documentation. This is not a
high priority for the prototype, but may become valuable as the state machines
grow more complex or when implementing actor independence (PRIORITY 100).

**Open Question**: Should `transitions` (or an equivalent) be adopted before or
after the domain model separation (see `notes/domain-model-separation.md`)? The
state machines are a core domain concept; their implementation should live in
`vultron/core/` regardless of which library is used.

---
