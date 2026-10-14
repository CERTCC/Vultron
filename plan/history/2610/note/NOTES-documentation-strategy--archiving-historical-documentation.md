---
source: NOTES-documentation-strategy--archiving-historical-documentation
timestamp: '2026-10-14T14:27:24.858351+00:00'
title: 'documentation-strategy: archiving historical documentation'
type: note
---

Archived from `notes/documentation-strategy.md` by #4498: the proposal is
delivered. `docs/howto/case_object.md` is now a moved-page stub pointing at
The Case Model, and historical and working-record pages are handled by the
working-record exclusion in `notes/site-information-architecture.md` (#3528).
The rule that `docs/reference/formal_protocol/` stays normative is kept in the
note.

---

## Archiving Historical Documentation

As the prototype matures, some documentation may be appropriate to archive
into a clearly marked "historical" section rather than delete:

- `docs/howto/case_object.md` — original UML design superseded by
  ActivityStreams model; worth preserving as historical reference.
- Some `docs/topics/process_models/` content — predates ActivityStreams;
  may be worth preserving with a note about its historical context.
- `docs/reference/formal_protocol/` — still normative; do NOT archive.

A reasonable convention: add a front-matter note to historical docs stating
the document predates the ActivityStreams implementation and may not reflect
current design. This preserves historical context without causing confusion.
