---
source: NOTES-rfc-spec-authoring--deviations-adopted-during-implementation
timestamp: '2026-10-01T19:34:47.190695+00:00'
title: 'rfc-spec-authoring: Deviations from the #3255 authoring plan'
type: note
---

**Archiving reason**: Superseded: each durable deviation is folded into the body of notes/rfc-spec-authoring.md (Include Mechanism, Page Map, Annex Sources, Section Ordering), which now states each convention directly instead of as a deviation from a plan (#4060).

**Superseding pointer**: notes/rfc-spec-authoring.md; docs/reference/vultron-spec/

---

## Deviations Adopted During Implementation

These differ from the plan above. Each was a deliberate choice made while writing
the document, recorded here so the note matches the tree.

- **Include mechanism.** This repo uses the `mkdocs-include-markdown` plugin
  (`mkdocs.yml` `plugins:`), so the syntax is
  `{% include-markdown "./_file.md" %}`, not the `pymdownx.snippets` `--8<--`
  form. The plugin's `heading-offset`, `start` and `end` arguments are what make
  annex embedding work, and `rewrite-relative-urls` (on by default) is what lets a
  fragment's relative links resolve both standalone and assembled.
- **Open-questions appendix location.** The plan put the summary appendix inside
  `_annexes.md`. It is a separate `_open-questions.md`, included last. Keeping it
  separate means the annexes stay annexes and the appendix can be reordered
  independently.
- **Shared fragment directory.** `docs/reference/vultron-spec/includes/` now
  exists and holds the reusable state tables and the four-dimensions note. It is
  covered by `not_in_nav: reference/vultron-spec/includes/*`.
- **Annex E source.** The plan pointed Annex E at
  `notes/activitystreams-semantics.md`. The annex is written in place instead,
  because the note is a design document rather than reader-facing prose, and it
  links to `docs/howto/activitypub/activities/` for worked wire examples.
- **Diagram sources.** State machine diagrams are included from the existing
  snippets under `docs/topics/`, not redrawn. The PEC diagram had to be extracted
  from `docs/topics/process_models/em/participant-embargo-consent.md` into
  `pec_state_machine_diagram.md` first; that page now includes it too, so there is
  one source.
- **Section order.** The plan flagged three ordering concerns. Two were measured
  and left alone: swapping §4 and §5 increases unresolved forward references
  rather than reducing them, and moving PEC ahead of EM creates a definitional
  cycle because PEC's states are defined by EM triggers. The third was real but
  mis-stated — §12 before §13 is correct per RFC 7322 (conformance is a body
  section, security is back matter), while §13 and §14 *were* reversed: IANA
  precedes Security. A References section was also missing and has been added.
- **File layout list.** The section-file map above omits `_abstract.md`,
  `_conformance/_intro.md`, `_open-questions.md`, `_oq-role-acquisition.md`,
  `_references.md` and the `includes/` fragments. `index.md` is the authoritative
  order.
- **Capability shapes.** §12.6 was `[I]` content inside a normative §12 and is now
  Annex G, with a short normative §12.6 retaining its one conditional MUST.
