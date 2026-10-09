---
status: proposed
date: 2026-10-09
created: 2026-10-09
updated: 2026-10-09
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0083, ADR-0115; specs/message-semantics-mapping.yaml MSM
  (including MSM-06); specs/semantic-extraction.yaml SE-07;
  notes/message-type-reference.md
informed: []
stakeholder_type: [project-contributor]
---

# Message Vocabulary Docs Are Projections of the Semantic Registry

## Context and Problem Statement

A builder of a Vultron-compatible system needs to go from something that happened in a CVD case to the wire activity that conveys it: "a fix is ready" to `Add(ParticipantStatus)` with `vf_state=VF`.
The documentation has no page that reads in that direction.
The [Message Types](../reference/messages/index.md) pages open with a table keyed by protocol shorthand, the [Protocol Quick Reference](../reference/quick_reference.md) lists the formal message set without wire forms, and the how-to guides carry no wire examples.

The facts such a table needs are scattered, and some are written twice.
`vultron/metadata/msm/_mapping.py` restates per wire activity a shorthand and a mapping status that the MSM spec also states, and the two have disagreed: `_mapping.py` tags `Create(Event)` and `Announce(Event)` as expansions of `EP`, where MSM-02-001 maps `EP` to `Invite(Event)` alone.
Meanwhile the code already owns several of the facts: the wire pattern on each `SemanticEntry`, the sender rule each received use case declares as `sender_entitlement` (ADR-0115), and the active-voice `phrase` template (SE-07-001).

A wire activity and the situation a sender conveys with it are not one-to-one.
Three situations — vendor awareness, fix ready, fix deployed — share `Add(ParticipantStatus)`, told apart by `vf_state` and `d_state`.
Three more — public awareness, exploit public, attacks observed — share `Add(CaseStatus)`, told apart by `pxa_state`.
This ADR calls each such situation an **occasion** (defined in the [Glossary](../reference/glossary.md)): one semantics has one or more occasions.

Where does the message vocabulary documentation come from, and how is it kept consistent with the code that sends and receives the messages?

## Decision Drivers

- The table's primary framing is the CVD occasion and its wire form; the formal protocol is linked, not leading.
  ADR-0083 establishes that the two message sets answer different questions, so neither can key the other.
- Every fact has one owner; nothing a generator can derive is typed by hand.
- The table, the per-message reference sections, and the examples on workflow pages must not be able to disagree.
- Completeness is checkable: every wire activity appears, every occasion has a details section, every section is reachable.
- Links in generated content are rewritten and checked by MkDocs like hand-written links.

## Considered Options

- A hand-written YAML file as the source of the vocabulary, loaded and validated by `_mapping.py`
- A separate catalog module keyed by `MessageSemantics`, beside the registry
- Each fact on the object it is most about (event class, example function, page), assembled by a generator
- Occasions on `SemanticEntry`, projected into a committed, generated YAML file and include fragments

## Decision Outcome

Chosen option: "Occasions on `SemanticEntry`, projected into a committed, generated YAML file and include fragments", because it keeps each occasion next to the wire pattern it refines, leaves every derivable fact with its existing owner, and makes the table and the reference sections two renderings of one entry.

### The code is the source

`SemanticEntry` gains `occasions: tuple[Occasion, ...]`, with at least one per entry except the `UNKNOWN` dispatcher fallback (MSM-06-002), checked at construction.
It also gains the `page` that `RowSpec.page` in `_mapping.py` holds today.
An `Occasion` is a frozen value object holding what only a human can supply: the "when" text, an optional distinguisher (a field value, or a named state context such as the EM state that separates `EP` from `EV` on one `Invite(Event)`), a stable anchor ID, a short description, the example function to render, an optional how-to link, an optional protocol shorthand, and optional notes.

Facts that already have an owner stay there, and the one derivable fact is derived:

| Fact | Owner |
|---|---|
| Wire summary, such as `Accept(Invite(Event)[context=VulnerabilityCase])` | the entry's `ActivityPattern` |
| Who may send it | the received use case's `sender_entitlement`; an exempt use case is shown as unchecked |
| Page, and so table group | the `SemanticEntry`'s new `page` field |
| Mapping status (MSM-06-003) | derived: one occasion with one shorthand on one entry is direct, several occasions on one entry is a collapse, one shorthand on several entries is an expansion, and no shorthand is none; an `evolved` mechanism (MSM-05) cannot be counted, so its occasion declares it |

### The artifacts are projections

One generator assembles the registry into a YAML file and a set of `include-markdown` fragments: the whole table, one slice per message page, and one fragment per occasion.
Both are committed and gated by a pre-commit `--check` hook that regenerates them and fails on any difference.
No one edits them by hand; a change to their text is a change to the code that owns it.
`_mapping.py` becomes the Pydantic loader and validator of the YAML.
This replaces the build-time rendering that MSM-06-001 requires with generation checked at commit time, so implementing this ADR revises MSM-06-001; the spec stays as written until then.
The YAML carries a `format_version` from the start, but it is not a published interface; publishing it belongs to protocol versioning (#2959).

### The pages include the projections

- [Message Types](../reference/messages/index.md) opens with the full table: When… | Send | Sent by | Distinguished by | Details, with the shorthand, where one exists, in the Details link text.
  Groups follow page order, lifecycle first (report, case proposal, case and participants, embargo, case status, general), then protocol mechanics (faults and acknowledgments, ledger replication).
- Each message page includes its slice and one generated section per occasion, anchored by the occasion's ID.
  Hand-written introductions and addenda stay on the page around the includes.
- How-to guides include an occasion's fragment where a step sends it, with the JSON example collapsed.
  The reference section lists those pages under "Seen in", derived from the include directives.
- The Protocol Quick Reference keeps its formal table and links to the occasion table.

Fragments rather than `markdown_exec` blocks, because MkDocs does not rewrite a `.md` link printed from an exec block, so a generated table of links would 404 without `--strict` noticing.

### Consequences

- Good, because a builder can look up any occasion and read its wire form, sender rule, and details in one row.
- Good, because the shorthand-and-status drift that mis-tagged `EP` cannot recur: the status is computed.
- Good, because a how-to example and its reference section are one fragment, so the Diátaxis split stays clean under DF-01-003: the parts are separated and the embedded part links to its canonical page.
- Bad, because human-facing prose moves into the dispatch registry modules, which grow accordingly.
- Bad, because roughly one committed fragment per occasion adds many small generated files.
- Bad, because how-to guides carry wire examples again, which a reader of the earlier split (#3003) may take for a regression without this ADR.

## Validation

- The `--check` hook fails when the committed YAML or fragments differ from a fresh generation.
- A test fails when a non-exempt `MessageSemantics` has no occasion, a field-valued distinguisher is not a value of its field's enum, an anchor ID is not unique, or an occasion's example does not dispatch to its own entry.
- A test fails when an occasion section on a message page is referenced by no table row, or a row's anchor resolves to no section.

## Pros and Cons of the Options

### A hand-written YAML file as the source

- Good, because content is data, readable and editable without Python.
- Bad, because the wire summary and the sender rule would be typed by hand and checked against the code, a second copy of facts the code owns.
- Bad, because it adds a second list beside the registry, the shape that let `_mapping.py` drift from MSM.

### A separate catalog module

- Good, because docs prose stays out of the registry modules.
- Bad, because it is `_mapping.py` with more fields: a parallel list keyed by `MessageSemantics` that has to be kept in step.

### Each fact on the object it is most about

- Good, because each fact sits on its most specific owner.
- Bad, because one occasion is assembled from three or four places, so no one can read or review an occasion whole.

### Occasions on `SemanticEntry`, projected

- Good, because an occasion sits beside the pattern it refines, and `SemanticEntry` is already "all dispatch components for a single `MessageSemantics` value".
- Good, because derivable facts are derived, and only judgment is written.
- Bad, because the registry modules carry prose.

## More Information

- Epic #4417 tracks the work; Idea #4418 is the lookup table and pages; Bug #4419 fixes the `EP` mis-tagging.
- [ADR-0083](0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md) — why the formal message set and the wire vocabulary are different shapes; this ADR adds the occasion as the unit that joins them.
- [ADR-0115](0115-received-handlers-check-sender-entitlement.md) — the sender rule this table reports.
- `notes/message-type-reference.md` — design guidance for the message pages.
