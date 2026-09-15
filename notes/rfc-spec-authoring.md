---
title: RFC Spec Document Authoring Decisions
status: active
description: >
  Structural and editorial decisions for building docs/reference/vultron-spec/
  from the existing draft-vultron-spec.md outline. Covers file layout,
  include strategy, open-question fragment pattern, source treatment,
  STE style, and the DAG-first authoring workflow.
related_notes:
  - notes/documentation-strategy.md
  - notes/spec-authoring-rules.md
  - notes/rfc-spec-authoring.md
related_specs:
  - specs/diataxis-requirements.yaml
---

# RFC Spec Document Authoring Decisions

This note records the structural and editorial decisions for issue #3255 —
building the complete Vultron Protocol Specification from the existing
`docs/reference/draft-vultron-spec.md` outline. These decisions are durable
conventions for anyone continuing or extending the spec document.

---

## File Layout

The document lives at `docs/reference/vultron-spec/` and is assembled by
`index.md` via `--8<-- includes`. Individual section files use semantic slug
names with a `_` prefix so they are excluded from the MkDocs nav
(via the `not_in_nav: _*.md` rule) until a deliberate "add to nav" decision
is made.

```text
docs/reference/vultron-spec/
  index.md                     ← assembled all-in-one page; the single nav entry
  _introduction.md             ← §1: Introduction
  _terminology.md              ← §2: Terminology
  _protocol-overview.md        ← §3: Protocol Overview
  _semantic-layer.md           ← §4: Semantic Layer (messages)
  _syntactic-layer.md          ← §5: Syntactic Layer (wire format)
  _rm-state-machine.md         ← §6: Report Management
  _em-state-machine.md         ← §7: Embargo Management
  _cs-dimensions.md            ← §8: Case State Dimensions
  _pec-state-machine.md        ← §9: Participant Embargo Consent
  _model-interactions.md       ← §10: Model Interactions and Cascades
  _participant-lifecycle.md    ← §11: Participant Lifecycle
  _conformance/                ← §12: Conformance (split — see below)
    _capability-sets.md
    _role-taxonomy.md
    _role-requirements.md
    _conformance-testing.md
    _capability-shapes.md
  _security.md                 ← §13: Security Considerations
  _iana.md                     ← §14: IANA / Namespace Considerations
  _annexes.md                  ← §15: Informative Annexes
  _oq-cs-ordering.md           ← open question fragment: CS ordering
  _oq-v-to-V.md                ← open question fragment: v→V drive authority
  _oq-negative-ack.md          ← open question fragment: negative acknowledgement
```

**§12 Conformance** is split into per-subsection files because it is the
longest section and its subsections are independently authorable.

**Open-question fragments** (`_oq-*.md`) are included in two places: inline
at the point of use (in the relevant section file) and collected in a
summary appendix in `_annexes.md`. Each file contains the open question as
an admonition block.

**`docs/reference/vultron-spec/includes/`** holds shared fragment files
(e.g., reusable tables, repeated admonition boilerplate). Add this path to
`not_in_nav` in `mkdocs.yml` when the directory is created.

---

## File Naming

- Section files: `_<semantic-slug>.md` (no numbers; order is determined by
  the `index.md` include sequence, not the filenames).
- §12 subsection files: `_conformance/<semantic-slug>.md`.
- Open-question fragments: `_oq-<slug>.md`.
- Shared includes: `includes/<slug>.md`.

Numbers are deliberately absent from filenames. The include order in
`index.md` is the canonical section order. If the order changes, only
`index.md` needs updating.

---

## Section Ordering: DAG-First Workflow

**Step 1 — DAG analysis before writing.** Map concept dependencies
across sections and within sections. A concept MUST NOT be used before it
is introduced. Produce authoring scratch-pads in `notes/` documenting the
confirmed section order and per-section concept introduction notes. These
scratch-pads are archived after the PR merges; the PR description draws
from them.

**Step 2 — Parallel section writes.** Subagents write each section
independently using the confirmed order and the per-section writing briefs
from the DAG analysis.

**Step 3 — Assembly and second DAG pass.** Read the assembled `index.md`
to verify no concept appears before its introduction. Section order is
adjustable because only `index.md` includes need updating.

The current draft order (§1 Introduction → §15 Annexes) is a starting
point, not a validated order. Known concerns from the initial planning:

- §4 Semantic Layer maps shorthands to wire forms that require §5 object
  types — §4.7 may need to move into §5 or reference §5 forward.
- §9 PEC is introduced in §3.2 but defined only in §9 — the §3 overview
  should use forward references, not full definitions.
- §12 Conformance before §13 Security is unusual vs. IETF RFC convention;
  may be deliberate for this document.

---

## Source Treatment

The existing draft contains `*Source:` pointers in each section. These are
**author construction notes**, not citations that appear in the published doc.

| Source type | Treatment in published doc |
|---|---|
| `specs/*.yaml` pointers | Absorb into prose; remove the pointer |
| `docs/**/*.md` pointers | Convert to `!!! info "See also"` admonition |
| `notes/*.md` pointers | Internal only; remove entirely |
| Bare YAML filenames | Never appear in published output |

The document is a **self-contained printable artifact**. A reader MUST NOT
need to chase a YAML file or implementation code to understand what a
conformant implementation must do.

"Self-contained" does not mean "duplicative." Prefer `--8<-- includes` over
rewriting content that already exists in the site. Whether to include or
rewrite is a per-section judgment call: include when the source page works
as a standalone reference; rewrite when the spec needs a tighter or more
normative framing.

---

## Annex Includes

Annex sections pull in existing site pages via `--8<-- includes`. The
included source pages MUST be readable both as standalone site pages and
as embedded annex sections. This may require light revision of the source
pages (removing or adjusting headers that assume standalone context).

Current annex → source page mapping:

| Annex | Source page |
|---|---|
| A — Single-Vendor CVD Example | `docs/tutorials/worked_example.md` |
| B — Multi-Party CVD Examples | `vultron/demo/scenario/` (derive from demo scripts) |
| C — Notation Reference | `docs/reference/notation.md` |
| D — Possible Case Histories | `docs/topics/measuring_cvd/possible_histories.md` |
| E — Relationship to ActivityPub | `notes/activitystreams-semantics.md` |
| F — Behavior Tree Reference | `vultron/core/behaviors/` (authoritative) |

---

## STE Style

Sections are written to ASD-STE100 aspirational style:

- Short sentences. Active voice. One instruction per sentence.
- Normative requirements use RFC 2119 keywords (MUST, SHOULD, MAY, etc.).
- Apply the `simplified-technical-english` skill per section after drafting.

Enforcement is aspirational (style-guide level), not linted. Protocol
vocabulary (`VulnerabilityCase`, `EV`, `EC`, etc.) is exempt from any
general word list.

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

---

## MkDocs Nav Update

When the spec is ready for publication, replace:

```yaml
- Draft Protocol Specification: 'reference/draft-vultron-spec.md'
```

with:

```yaml
- Protocol Specification: 'reference/vultron-spec/index.md'
```

and delete `docs/reference/draft-vultron-spec.md`. Also add the
`includes/` subdirectory to `not_in_nav` if it is created:

```yaml
not_in_nav: |
  ...
  reference/vultron-spec/includes/*
```

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

OQ #15 (negative acknowledgement) is resolved by the §4.6 rewrite above.
