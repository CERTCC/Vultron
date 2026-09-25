---
source: CONCERN-3243
timestamp: '2026-09-25T19:37:03.191794+00:00'
title: Per-requirement spec anchors render but fail mkdocs --strict
type: learning
---

## Concern

`docs_render.py` emits a per-requirement anchor for every spec, as raw HTML in
the ID table cell:

```python
anchor = _spec_anchor(spec.id)
id_cell = f'<a id="{anchor}"></a>`{spec.id}`'
```

The anchor reaches the built site — `site/reference/specs/protocol/index.html`
contains `id="mv-03-002"` — so a requirement-level deep link works in a browser.
But `mkdocs build --strict` refuses it:

```text
WARNING - Doc file 'topics/case_ledger_sync.md' contains a link
  '../reference/specs/protocol.md#mv-03-002', but the doc
  'reference/specs/protocol.md' does not contain an anchor '#mv-03-002'.
Aborted with 1 warnings in strict mode!
```

The validator only sees anchors declared with heading attr-list syntax
(`{#mv-03}`), which is why *group*-level links such as
`protocol.md#clp-15` pass and requirement-level links cannot.

## Why it matters

Prose that cites a specific requirement is forced to link to its whole group
instead, so the reader lands on a section and has to search for the entry. The
failure mode is also actively misleading: the warning says the anchor "does not
contain", when it does — an author reasonably concludes they got the anchor
format wrong and gives up rather than suspecting the validator.

The per-spec anchors are clearly *intended* to be link targets — otherwise
`_spec_anchor(spec.id)` would not be emitted at all — so today the feature is
built and unusable.

## Suggested fix

Options, roughly in order of preference:

1. Register the per-spec anchors where mkdocs can see them (emit each requirement
   as a heading with `{#id}`, or add the ids via a small
   `mkdocs.yml` hook / plugin that declares them).
2. Keep raw-HTML anchors but document the limitation next to `_spec_anchor`, so
   the next author links to the group deliberately rather than by trial and error.

## Discovery

Hit while adding a requirement citation during `check-docs-sync` for PR #3233
(ISSUE-3217); the link was downgraded to the group anchor to get the build green.
Routed per the upward-reflection checklist (BW-07-009).

**Resolved**: 2026-09-25 — implementation tracked in #3735.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3734>.

Notes: `notes/documentation-strategy.md`.

Root cause (confirmed at planning): `markdown-exec` reports only headings from exec-block output to the parent Markdown instance, so MkDocs anchor validation never sees raw-HTML ids emitted by the spec renderer. Fix: an `on_page_content` hook registering rendered-HTML ids, verified by a prototype `--strict` build.
