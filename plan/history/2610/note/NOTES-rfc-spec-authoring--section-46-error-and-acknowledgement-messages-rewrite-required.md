---
source: NOTES-rfc-spec-authoring--section-46-error-and-acknowledgement-messages-rewrite-required
timestamp: '2026-10-01T19:34:46.124917+00:00'
title: 'rfc-spec-authoring: §4.6 rewrite instructions for #3255'
type: note
---

**Archiving reason**: Superseded by delivered work: §4.6 Error and Acknowledgment Messages in docs/reference/vultron-spec/_semantic-layer.md now states the acknowledgement and fault partition, and #3255 is closed.

**Superseding pointer**: notes/rfc-spec-authoring.md; docs/reference/vultron-spec/

---

## §4.6 — Error and Acknowledgement Messages: Rewrite Required

The current draft §4.6 is **outdated**. It describes error message types
as "deliberately unmodelled" and says unprocessable messages are
dead-lettered with no sender notification. The implementation has since
added a three-way fault partition:

| Signal | When to use |
|---|---|
| `Create(ProcessingFault)` | Message received but not understood (parse failure, unknown type, format error) |
| `as:Reject` | Message understood but rejected given current case state |
| `Create(Note)` | General problem escalation to case participants |

**Sources for the §4.6 rewrite**:

- `docs/adr/0049-core-does-not-model-error-message-types.md`
- `docs/adr/0080-protocol-asks-not-suspended-behaviors.md`
- `docs/adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md`
- `specs/protocol-asks.yaml` (ProcessingFault failure class rules)
- `specs/message-semantics-mapping.yaml` (the three-way partition)
- `docs/reference/messages/` (updated per-message-type pages)
