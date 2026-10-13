---
source: NOTES-behavioral-conformance-specs--relationship-to-behavior-logic-docs
timestamp: '2026-10-12T23:47:27.083972+00:00'
title: 'Behavioral conformance specs: behavior logic docs follow-up (delivered)'
type: note
---

Archived from `notes/behavioral-conformance-specs.md` by #4497 (notes sweep): the
docs follow-up plan is delivered. The `docs/topics/behavior_logic/` pages carry
Requirements sections citing RMB/EMB/CSB IDs,
`docs/reference/formal_protocol/transitions.md` cites spec IDs inline, and the
conformance levels live in
`docs/reference/vultron-spec/_conformance/_conformance-testing.md`.

---

## Relationship to Behavior Logic Docs

`docs/topics/behavior_logic/` docs are known to be out of sync with the
implementation and contain no normative language. They should NOT be the
primary home for requirements.

After the specs are written:

- Each behavior logic doc gets a "Requirements" section at the top listing
  relevant RMB/EMB/CSB spec IDs.
- BT diagrams are demoted to "Implementation approach" sidebars with a note
  that they illustrate one conformant implementation.
- `docs/reference/formal_protocol/transitions.md` gets inline spec ID citations.
- `docs/howto/general_implementation.md` gets a conformance levels section
  (L1/L2/L3/L4).

Docs are updated *after* specs are stable, so doc cross-references point to
stable IDs.
