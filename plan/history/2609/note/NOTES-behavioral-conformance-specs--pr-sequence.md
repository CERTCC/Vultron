---
source: NOTES-behavioral-conformance-specs--pr-sequence
timestamp: '2026-09-17T17:10:51.110931+00:00'
title: 'Behavioral conformance: PR Sequence'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** specs/{rm,em,cs}-behavior.yaml

---

## PR Sequence

**PR 1**: Schema changes (`schema.py`) + scaffolding (three empty spec files
with correct headers, group structure, and `trigger:` annotations). Also
includes this note. Tests updated for new schema fields.

**PR 2**: RM behavioral spec content (`specs/rm-behavior.yaml` fully
populated). Primary sources: transitions.md RM tables, rm_bt.md,
msg_rm_bt.md.

**PR 3**: EM + CS behavioral spec content together (EMB + CSB). EM and CS
are tightly coupled — CS cascade chains (`enter-cs-p` → embargo teardown)
directly reference EM behavior, so separating them creates dangling
`satisfies` relationships.

**PR 4**: Docs update. Behavior logic docs annotated with spec IDs,
transitions.md cited, general_implementation.md conformance levels section.
Comes last so doc cross-references point to stable IDs.
