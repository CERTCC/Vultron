---
title: "Message Type Reference: Formal Shorthands, AS2 Wire Forms, and the Mapping Between Them"
status: active
kind: guidance
description: >-
  Rules for writing about and changing the message-type reference pages: the
  formal message set and the AS2 wire vocabulary are different shapes, which
  name the reader gets, the mermaid node-id ratchet, what the evolved fault and
  acknowledgement mechanisms mean, keeping the Diátaxis quadrants apart, and
  the example-rendering and dispatchability gates, and the occasion rules.
related_specs:
  - specs/message-semantics-mapping.yaml
  - specs/vultron-as2-mapping.yaml
  - specs/semantic-extraction.yaml
  - specs/diataxis-requirements.yaml
  - specs/project-documentation.yaml
  - specs/received-status-handling.yaml
  - specs/rm-behavior.yaml
  - specs/participant-case-replica.yaml
related_notes:
  - notes/message-occasion-table.md
  - notes/activitystreams-semantics.md
  - notes/received-status-authorization.md
  - notes/case-state-model.md
  - notes/diataxis-framework.md
  - notes/documentation-strategy.md
  - notes/status-dimension-objects.md
  - notes/sync-ledger-replication.md
  - notes/participant-embargo-consent.md
  - notes/case-communication-model.md
---

# Message Type Reference: Formal Shorthands, AS2 Wire Forms, and the Mapping Between Them

ADR: [ADR-0083](../docs/adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md).
The mapping itself — collapses, expansions, and the evolved fault and
acknowledgement mechanisms — is documented in `docs/reference/messages/` and
explained in `docs/topics/activity_vocabulary_design.md`; do not restate it here.
The occasion table's remaining plan is `notes/message-occasion-table.md`.

## The two message sets are different shapes

The **formal message set** (`docs/reference/formal_protocol/messages.md`) is
partitioned by state machine; the **AS2 wire vocabulary** is the
`SEMANTIC_REGISTRY` (`vultron/semantic_registry/`). The mapping is many-to-many
both ways, and much of the wire vocabulary has no formal counterpart. Never treat
a shorthand and a wire activity as two names for one thing:
`specs/message-semantics-mapping.yaml` (MSM) is the normative bridge, so read it
before claiming a shorthand maps to a wire form.

- **RM moves have two wire expressions, and that is not an anomaly (ADR-0108).**
  The *act* is the report-scoped activity (`Accept(Offer(Report))` = `RV`); the
  *declaration of resulting state* is `rm_state` on a participant-status
  broadcast. A disagreement is flagged (RSH-06), not resolved by preferring one
  (RSH-08-002). Do not propose retiring either form.
- **`EP` is `Invite(Event)[context=VulnerabilityCase]` and nothing else**
  (MSM-02-001). `Create(Event)` mints terms and `Announce(Event)` reports the
  terms in force; neither proposes, so neither is tagged `EP`.
- **`GI` is an open umbrella** (MSM-04-001/002). Do not write as though the
  current split-off set is complete, and do not count it in prose (MS-16-002).
  `(GI)` identifies no activity: name the act in plain language and cite `GI`
  once per page. Actor suggestion is a `GI` expansion, not case management.
- **Case proposal is pre-case bootstrap and ledger replication is the carrier
  substrate**; document neither as case management. `unknown` and
  `unknown_unresolvable_object` are dispatcher fallbacks, never message types.

## Which name the reader gets

An activity has three names: the formal message (`RV`, "Report Valid"), the
prototype class or pattern (`RmValidateReport`), and the AS2 wire form
(`Accept(Offer(VulnerabilityReport))`). Semantics are not recoverable from the
wire form (`Accept`/`TentativeReject`/`Reject` of the same offer mean valid,
invalid, closed), so replacing a protocol name with its wire form deletes a layer.

Reader-facing docs pair the semantic name with the wire form and omit the
prototype layer: **`<semantic name>` is implemented in ActivityStreams as `<wire
form>`**, then the steps, then the JSON (DF-09-010). The semantic name follows the
row's `MappingStatus`:

| `MappingStatus` | Semantic name to use |
|---|---|
| `direct` | The formal message name and its code — "Report Valid (RV)" |
| `collapse` | All the formal names the wire form carries, stated together once, plus the field that selects between them |
| `expansion` | Plain language per act; cite the umbrella code once per page, never per activity |
| `none` | Plain language, taken from the heading `docs/reference/messages/` already gives it |

Two shapes need care. `RA`/`RD` name the *report* while their wire verbs
(`Join`/`Ignore(VulnerabilityCase)`) name the *case*: state the act and the RM
consequence separately (MSM-01-004/005). `Leave(VulnerabilityCase)` is the
canonical RM closure (ADR-0050) yet has no formal name, while `RC` is bound to
`Reject(Offer(VulnerabilityReport))`; say so rather than presenting a tidy pair.

## The prototype name survives as a mermaid node id

An activity is declared as a class in `vultron/wire/as2/vocab/activities/` and as
an `ActivityPattern` in `vultron/wire/as2/extractor/_instances.py`; the names often
differ and neither list is a superset. Use that name as the mermaid **node id**
(never rendered) and put the reader-facing pair in the label.
`test/architecture/test_docs_activity_verbs.py` rejects an id in neither list and
checks the label's wire form against the registered pattern; it checks only
`subgraph as:Verb` membership, not prose mentions.

## Evolved mechanisms are not "unimplemented"

MSM records `RE`, `EE`, `CE`, `EK`, `CK` as having no AS2 wire representation:
true per shorthand, false per purpose. Faults are partitioned by failure mode and
acknowledgement is cumulative via the hash chain
(`docs/reference/messages/faults_and_acknowledgements.md`).

- **`as:Reject` is overloaded**: a receiver cannot infer "error" from the verb.
  The embargo rejection's registry name is `reject_invite_to_embargo_on_case`
  (`reject_embargo` names only BT and factory helpers), and
  `reject_case_ledger_entry` is the ledger NAK (MSM-05-002), not a refusal.
- **Never cite the `RmError`/`EmError`/`CsError`/`GmError` taxonomy**
  (MSM-05-004): those types never existed. `VultronError` in `vultron/errors.py`
  is an unrelated Python exception base.
- Do not add per-message `EK`/`CK` for ledger-carried state; hash-chain continuity
  already acknowledges it.
- **`RK` is a reply outside the case** (RMB-08-003, RMB-08-004, #4325, #4560):
  an addressee of the report's `Offer` sends it to the reporter, at any time
  after the report arrives, case or no case. It is never sent or forwarded to
  the CASE_MANAGER and never ledgered, so PCR-08-001 states it as an exception.
  The reporter checks the sender against its own record of the Offer, so the
  declared kind is `NAMED_ACTOR` and "Sent by" carries the addressee wording.

## Keep the three quadrants apart

DF-01-003: rationale goes to `docs/topics/activity_vocabulary_design.md`, encoding
facts and JSON examples to `docs/reference/messages/`, task sequences to the
how-to tree.

- A wire example **copied** into a how-to page is a quadrant collapse; one
  **included** from the same fragment the reference renders is not (ADR-0128).
- Decide whether a how-to page has a task by whether it names an action the
  reader takes, not by its directory; a page with none is retired, not reshaped.
- Collapse signals: a noun-phrase title in the how-to tree (DF-04-003 wants "How
  to [Action]"), no imperatives or steps, mostly design rationale, or a
  `not_normative.md` banner. A missing banner is no evidence either way.
- Cross-link domain rationale that already has a home instead of duplicating it.

## Examples

- Examples are `markdown_exec` blocks calling
  `vultron.wire.as2.vocab.examples.vocab_examples`; follow the generated sections
  under `docs/reference/messages/_occasions/sections/` and
  `docs/reference/activitypub/objects.md`.
  `docs/reference/specs/protocol.md` is the exemplar for **mapping tables**
  (`render_for_kind`), not for examples. Tables are committed `include-markdown`
  fragments instead (ADR-0128, § Occasions), because MkDocs does not rewrite links
  printed from an exec block; an example carries no link, so it stays an exec block.
- A new example function needs a matching `obj_to_file` call in
  `vocab_examples.main()`, or `test/architecture/test_vocab_examples_current.py`
  fails. The generator randomizes IDs and timestamps, so generate into a temp
  directory and copy across only the files you added.
- **An example must be dispatchable.** Set every discriminator field its
  `ActivityPattern` requires (`object_`, `target_`, `context_`); there is no
  `origin_` field, so `origin` never affects dispatch.
  `test/architecture/test_vocab_examples_dispatchable.py` requires each example
  to match exactly one pattern and asserts its collected count (DF-09-009).
- **Do not narrow the collector.** It takes every function with zero *required*
  parameters returning an `as_Activity`; requiring zero parameters or
  `as_TransitiveActivity` silently skipped real examples, the false-clean
  signal DF-09-009 forbids.
- **A green dispatchability run covers only the example corpus**, not every
  activity Vultron emits: a factory with no exported example is invisible to it
  (#3471). Add an example to cover a factory; widening the argument rule does not.
- Keep `_KNOWN_UNDISPATCHABLE` and its collected-names guard even while empty; a
  new entry needs the per-entry strict xfail the table's comment describes.

## Occasions (ADR-0128, MSM-08)

- Occasions are declared on `SemanticEntry` (value objects in
  `vultron/semantic_registry/_occasion.py`), and `MappingStatus` and the
  discriminator are derived from them by `vultron/metadata/msm/_mapping.py`; do
  not enter either by hand.
- **An occasion names its example by `vocab_examples` function name**, not by
  holding the function, so the dispatch registry never imports the example
  corpus at server start. `test/test_semantic_registry_occasions.py` resolves
  every name and checks the example dispatches to its own entry.
- **Each occasion's example shows its own distinguisher** (MSM-08-003): a
  dispatch check alone passes an example carrying another occasion's field value.
- Derived mapping rows follow registry order, which is dispatch order, not
  reading order.
- **The occasion table is generated; never edit it by hand.** `uv run
  msm-occasions --write` projects the registry into
  `vultron/metadata/msm/occasions.yaml` and the fragments under
  `docs/reference/messages/_occasions/`; the `msm-occasions-sync` hook runs
  `--check`, and `test/metadata/test_msm_occasions.py` is the CI backstop
  (MSM-06-001).
- **Fragments render from the re-parsed YAML, not from the registry**, so the
  YAML carries every fact a fragment shows; a new column is a field on
  `OccasionRow` plus a renderer change.
- **The fragments are in `exclude_docs`**: built alone, a table's links would be
  checked against the wrong page, and each fragment would publish a URL.
  `include-markdown` reads them from disk, so the links are checked on the host
  page.
- **The table fragments avoid the name `*table*.md`**: `lint-docs` exempts that
  name as generated, and their cells are occasion prose it must check (DF-09-007).
- **The example stays an exec block inside the section fragment**: its IDs are
  minted per run, so a committed copy could never pass `--check`.
- **A pipe in a "Send" cell is a `<code>` element with entities.**
  Python-Markdown shows `\|` literally inside a backtick span, GFM splits the
  cell at a bare `|`, and `markdownlint --fix` rewrites an unprotected
  `(Event)[context=…]` as a reversed link.
- **The formal message name is `ProtocolShorthand.formal_name`**, held to
  `docs/reference/formal_protocol/messages.md` by
  `test/test_semantic_registry_occasions.py`.
- **An expansion's rows link by section heading, with no shorthand**
  (DF-09-010, MSM-08-008). That covers `GI` and also `RV`, `RI` and `RC`, which
  the Full-Case Invite replies carry; the link text and the heading are one
  string (the formal name and code when the shorthand is the occasion's own,
  otherwise the occasion's declared `heading`).
- **How the pages include them**: `messages/index.md` opens with `lookup.md`;
  each message page includes its slice, then one section per occasion in the
  slice's dispatch order (`em.md` keeps its reading order). Hand-written text (the
  introduction, an addendum, sections for shorthands with no wire activity) stays
  around the includes; an addendum follows the section's JSON example, which is
  the section's last block.
- **Include paths start with `./`**: `include-markdown` resolves a path with no
  `./` or `../` prefix against `docs/`, so `"_occasions/lookup.md"` finds nothing.
- **The mapping status is in the generated section, not the table** (MSM-06-003):
  the table's columns serve a sender.
- `test/metadata/test_msm_occasions.py` checks each page includes its slice once,
  each section once and on no other page, and no page has an exec block of its
  own (MSM-06-001, MSM-08-004); `mkdocs build --strict` and `docs-links` check
  the rendered links.

### How-to embeds and "Seen in" (#4432)

- **A how-to step that sends an occasion includes
  `_occasions/embeds/<anchor>.md`, never the section.** The embed is a
  generated variant of the same YAML row: an `!!! info` box with no heading,
  holding the sender's facts, a **Reference** link to the canonical section and
  the example in a collapsed `??? example`. Do not cut the section with
  `start=`/`end=` and wrap it by hand: the collapse and the link would be typed
  per step. The formal definition, mapping status and notes stay in the section.
- **An embed has no heading**, so a host gains no `{ #anchor }` or TOC entry
  that could collide with the reference page's.
- **"Seen in" is read from include directives, never typed.**
  `embedding_pages` reads every `docs/` page outside the fragment directory
  with `include_directives(..., existing=False)`, so a directive counts before
  its embed exists and one `--write` settles it; the fragments include nothing,
  so `--check` cannot loop. The hook watches all of `docs/` and `mkdocs.yml`.
  The row's `howto` link became `seen_in` (`format_version` 2).
- **Refused or skipped hosts**: an embed on any message page is refused (the
  page carries the section), as is one in a fragment another page includes
  whole (the reader sees the host); a `draft_docs`/`exclude_docs` page is
  skipped, since production withholds it.
- **A declared guide must embed its occasion.** `derive_table` fails when
  `Occasion.howto` names a guide that does not include the embed. Declare the
  guide whose step sends the occasion, or none: `Create(CaseParticipant)` is the
  CASE_MANAGER's ledger entry for an inert record and no guide's step sends it
  (#4576). Two steps send an activity no occasion fits yet (#4578).
