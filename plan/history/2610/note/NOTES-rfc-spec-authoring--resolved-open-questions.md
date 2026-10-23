---
source: NOTES-rfc-spec-authoring--resolved-open-questions
timestamp: '2026-10-01T19:34:46.817733+00:00'
title: 'rfc-spec-authoring: Open questions resolved while writing #3255'
type: note
---

**Archiving reason**: Purely historical: an instruction for #3255, which is closed. The open questions the document still carries are the `_oq-*.md` fragments under docs/reference/vultron-spec/, collected by `_open-questions.md`; the tree is the authority on which remain open.

**Superseding pointer**: notes/rfc-spec-authoring.md; docs/reference/vultron-spec/

---

## Resolved Open Questions

These items appeared as open questions in the draft but are now settled.
Write them as normative content, not as flagged open questions.

| Item | Resolution |
|---|---|
| CS ordering constraints (OQ #12) | Content exists in `docs/topics/process_models/cs/transitions.md`; promote to normative in §8.3 |
| `v→V` drive authority (OQ #13) | Two paths: vendor self-report and third-party assertion by reporting party (see `notes/case-state-model.md`) |
| `embargo_adherence` derived vs. stored (OQ #14) | Confirmed `@computed_field` at `vultron/core/models/participant_status.py:119`; §9.6 accurate as written |
| Sentinel as specified role (OQ #16) | Not a protocol role; one informative sentence in §12.4.2 |

OQ #15 (negative acknowledgement) will be resolved when the §4.6 rewrite is complete (tracked in issue #3255).
