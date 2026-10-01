---
title: RFC Review Rubric
description: >
  Living checklist for reviewing the Vultron Protocol Specification RFC
  (docs/reference/vultron-spec/, a section of pages assembled from shared
  fragments) against the codebase, system specs, notes, and design. Apply each
  round of revision; extend as new issue classes emerge.
status: active
related_specs:
  - specs/docs-build-workflow.yaml
  - specs/diataxis-requirements.yaml
related_notes:
  - notes/documentation-strategy.md
  - notes/rfc-spec-authoring.md
  - notes/site-information-architecture.md
---

# RFC Review Rubric

A reviewer agent (or human) working through the Vultron Protocol Specification
should run all checks below in order. The specification is a section of pages,
each assembled from shared fragments; `notes/rfc-spec-authoring.md` § "Page Map"
names every page and the fragments it includes. Section citations below carry
the number and name the review checks for (§ "Cross-Reference Integrity").

Items tagged `[M]` can be verified mechanically (grep, build output, diff against
codebase); items tagged `[J]` require reading and judgment.

Add items after each review round. Retire `[M]` items to the "Mechanized"
section once a linter or CI check covers them. Do not delete items that were
retired — note the covering mechanism so the reason for the rule survives.

---

## 1. Structural Completeness

Preconditions — flag any failure here before reading for content.

- `[M]` Every page in `notes/rfc-spec-authoring.md` § "Page Map" exists and
  includes exactly the fragments the map lists, in the listed order. `full.md`
  includes every fragment in document order, and each part page includes a
  contiguous run of that order.
- `[M]` The landing page and every content page include `_full-page-tip.md`;
  `full.md` does not. `full.md` is in `not_in_nav` and sets
  `search: exclude: true`.
- `[M]` The landing page `index.md` declares `contents: routing` and links every
  part page, every annex page, `open-questions.md` and `full.md`
  (`uv run docs-site --check`).
- `[J]` Each page opens with an H1 and an orientation a reader arriving from a
  search result can follow without the previous page (SG-41, SG-44).

- `[M]` Every `##` and `###` heading is followed by at least one sentence of
  prose before the next heading, table, list, or code block.
- `[M]` Every state machine section (`_rm-*`, `_em-*`, `_pec-*`,
  `_cs-dimensions`) contains at least one Mermaid diagram showing states,
  transitions, and transition labels.
- `[M]` Every subsection that describes a JSON message format contains at least
  one fenced JSON code block as a concrete example.
- `[M]` No section consists solely of bullet points with no prose framing.
- `[J]` Each section's opening prose describes what the section contains and
  why it matters — not merely what it is titled.

---

## 2. Terminology Consistency

Check against `_terminology.md` and the project glossary as authoritative
sources.

- `[M]` "case actor" does not appear where "case manager" is meant. Grep:
  `case actor` outside `_terminology.md` and explicitly marked informative
  sidebars.
- `[M]` State names are never abbreviated in headings or prose. Full names
  only:
  - VFD: *Vendor Aware, Fix Ready, Fix Deployed*
  - PXA: *Public Aware, Exploit Public, Attacks Observed*
  - RM:  *Received, Invalid, Valid, Deferred, Accepted, Closed*
  - EM:  *Non-Proposed, Active, Revised, Exited*
- `[M]` CNA is expanded as "CVE Numbering Authority (CNA)" on first use in
  each top-level section.
- `[M]` "publication" and "public awareness" are not used interchangeably.
  *Publication* = intentional act by a participant; *public awareness* = a
  condition that may arise by any means.
- `[M]` No Python field names with trailing underscores appear in wire-format
  descriptions (e.g., `end_time_` → use the JSON field name).
- `[J]` Every term used in normative text appears in `_terminology.md` or is
  defined inline at first use.
- `[J]` "event" is used consistently; distinguish embargo events from
  state-machine events when both appear in context.
- `[J]` "case owner," "case manager," and "case actor" are used for the correct
  concept at each occurrence:
  - *Case owner*: holds decision authority (who is added, when embargoes
    change, who holds the manager role).
  - *Case manager*: performs the case-management function and maintains the
    canonical case ledger.
  - *Case actor*: the specific software actor currently implementing the case
    manager role (implementation detail, not a core protocol concept).
- `[J]` `Observer` is used with two distinct meanings: (1) a process role in
  §2 Terminology (a participant with no VFD drive obligations), and (2) the name
  of the minimum conformance capability set in §12 Conformance. The §2
  Terminology definition acknowledges this dual use and links §12 Conformance
  on its page for the capability-set meaning.
- `[J]` The `track`/`drive` distinction is defined before or alongside its
  first use. *Track* = obligation to maintain a local copy of a state machine
  from incoming transitions; *drive* = authority to initiate a transition
  that advances the shared canonical state. The term "drive obligations"
  appears in §2 Terminology (Observer definition); if the full definition
  appears later (currently §12.2 Capability Sets), §2 Terminology must carry an
  inline gloss or a forward link to the page that defines it.

---

## 3. Protocol Model Fidelity

Cross-check against codebase enums, `notes/case-ledger-authority.md`,
`notes/case-state-model.md`, and related design notes.

- `[J]` Every state transition is explicitly labeled as one of:
  1. Participant-level self-report.
  2. Participant observation submitted to the case manager.
  3. Canonical case-level transition recorded by the case manager.
- `[J]` Messages are framed as declarations of things that have *happened*, not
  as commands or requests for another participant to perform a transition.
- `[J]` No section implies a participant can unilaterally change case-level
  state (e.g., unilaterally declare EM Exited, unilaterally change canonical
  PXA state).
- `[J]` Embargo teardown is presented as a case-manager-mediated process, not a
  unilateral participant action. A participant may *report* intent to exit or
  *propose* an end date; the case manager executes teardown.
- `[J]` Centralization claims are correctly qualified: per-case centralization
  yes; one global system for all cases no; fully decentralized current
  implementation no.
- `[J]` Participant claims and canonical case state are not collapsed into a
  single step. The expected sequence is:
  1. Participant reports an observation.
  2. Case manager records the claim in the ledger.
  3. Case manager evaluates the claim against applicable rules.
  4. If warranted, case manager records a canonical state transition.
  5. If policy requires embargo teardown, case manager initiates it.
- `[J]` The claim "vendor published a patch" is never conflated with "patch is
  deployed." These are distinct protocol facts (Fix Ready ≠ Fix Deployed).
- `[M]` State machine enumeration values in the document match the codebase
  enums. Grep against `vultron/enums/` for each state name.

---

## 4. Scope Hygiene

Keep protocol text free of implementation accidents and drafting artifacts.

- `[M]` No reference to "open question N" without an inline statement of the
  question. Remove the number; retain the question if genuinely open.
- `[M]` No reference to "previous draft," "earlier wording," or "was
  previously" in normative text.
- `[M]` No Python source file path is cited as normative authority (e.g.,
  `vultron/enums/roles.py`). The spec is the authority; the implementation
  derives from it.
- `[J]` Behavior-tree implementation details (node types, tree traversal order,
  specific BT class names) appear only in explicitly marked informative
  sidebars — not in normative sections.
- `[J]` Every callout/admonition marked "informative" or "implementation note"
  is visually distinguished (admonition block) and genuinely belongs outside
  the normative text.
- `[J]` Sections that contain no normative requirements are evaluated for
  relocation to an informative annex, with its own annex page.
- `[M]` Every open question that belongs at a point-of-use location in the
  document exists as a standalone `_oq-*.md` fragment file, included both at
  point-of-use and in `_open-questions.md`. No open question is written as
  inline prose directly into `_open-questions.md` if it has a natural
  point-of-use location (i.e., the section that first implies or requires the
  missing definition).

---

## 5. Cross-Reference Integrity

- `[M]` Every link to a section targets the page that owns the section (see
  `notes/rfc-spec-authoring.md` § "Page Map") plus the heading anchor — for
  example `tracking-models.md#6-report-management-rm-state-machine-n` — and
  resolves. No link targets `index.md#…`: the landing page holds no sections.
  Run `bash .github/scripts/mkdocs-build-strict.sh` and treat any broken-anchor
  warning as a blocker.
- `[M]` Every section citation carries the number and the section name, in prose
  and in link text: "§6 Report Management (RM) State Machine", never a bare
  "§6". An annex is cited as "Annex A Worked Example: Single-Vendor CVD": the
  "—" after the annex letter in the heading is dropped, while a "—" inside a
  section name is kept ("§4 Semantic Layer — Message Meanings"). A bare number
  does not say which page the section is on.
- `[M]` Every reference to a Python source file is a clickable Markdown link
  pointing to a canonical GitHub URL — not a bare file path. The RFC must be
  usable as a standalone PDF.
- `[J]` Forward references (pointing to a later section, on the same page or a
  later one) either carry a one-sentence explanation of the relationship, or
  are eliminated by reordering.
- `[J]` A concept a page uses but another page defines is linked to the defining
  page at first use (SG-11). A part page is read on its own, so a definition
  that only an earlier page carries is not in scope for its reader.
- `[J]` Every callout or sidebar that says "see worked example" or "see case
  history" contains actual content, not a placeholder.
- `[J]` No section opening note or admonition instructs the reader to read a
  later subsection first when that subsection follows in document order.
  Either reorder content so the prerequisite precedes the dependent material,
  or rewrite the note as a forward pointer explaining what the later
  subsection contributes.

---

## 6. Codebase Alignment

Run against the current `main` branch of the implementation.

- `[M]` Every state name used in the document appears in the corresponding
  codebase enum. Diff the full list from `_terminology.md` against
  `vultron/enums/`.
- `[M]` Every message shorthand (RS, RV, RK, EP, etc.) maps to a
  `MessageSemantics` or equivalent enum value. Flag any shorthand without a
  codebase match.
- `[J]` Workflow descriptions (§11 Participant Lifecycle Within a Case) match
  the actually supported flows in the
  implementation. Step through at least the single-vendor and multi-vendor
  coordinated-disclosure cases.
- `[J]` Role capability claims (§12.4 Role-Specific Normative Requirements)
  match what the codebase enforces, not only what the protocol intends.
- `[J]` Any "default policy" statement is verified against the current default
  configuration in the implementation.
- `[J]` Case histories and worked examples (Annex A Worked Example:
  Single-Vendor CVD, Annex B Worked Example: Multi-Party CVD and Annex D
  Possible Case Histories) are verified against the current state-machine
  design before each publication.

---

## 7. Observer / Dissemination Accuracy

Specific to the observer role and PEC-gated information flow — a recurring
source of imprecise language.

- `[J]` Claims about what a participant "may display" are reframed as claims
  about what the **case manager may send** to a participant. Vultron controls
  dissemination; it cannot control display of information a participant already
  holds.
- `[J]` PEC gating is described in terms of the case manager's send policy, not
  in terms of participant capability to render information.

---

## 8. Readability and Concept Flow

Check after any structural reorganization or addition of new sections.

- `[J]` Every structural concept used in normative prose in §3 Protocol
  Overview or §4 Semantic Layer — Message Meanings is either defined in §2
  Terminology or accompanied by a one-sentence gloss at first use. §4 Semantic
  Layer — Message Meanings is on a different page from §2 Terminology, so a
  concept it takes from there is also linked to it. A bare forward reference
  `(§N.M)` is not sufficient for foundational concepts (`Case Actor`,
  `CaseLedgerEntry`, PEC state names, RM state names at point of gating use).
- `[J]` When a state machine's state names are used normatively in a section
  more than one major section after the defining section, a compact reminder
  (a small table or admonition listing the state names with one-word glosses)
  appears at or near the point of reuse, on the same page as the reuse.
  Minimum required coverage:
  - RM states: reminder in §9.7 Gating Full Case Delivery, §10 Model
    Interactions and Cascade Rules, and §11 Participant Lifecycle Within a Case
  - PEC states: reminder in §10 Model Interactions and Cascade Rules and §11
    Participant Lifecycle Within a Case
  - EM states: reminder in §10 Model Interactions and Cascade Rules
  - VFD states: reminder in §12.4.1 Participant-Specific CS Transitions (VFD)
- `[J]` The "four dimensions / five state machines" disambiguation (CS
  comprises two independent machines, VFD and PXA) is re-stated or explicitly
  cited wherever the five-machine count is normatively load-bearing —
  currently required at the Case Observer capability set requirements in §12.2
  Capability Sets.
- `[J]` When a transition is implied by a state machine's compound-state table
  but its drive authority is unresolved, an open-question admonition (or
  `!!! warning` citing the relevant OQ) is placed in the defining section at
  first introduction, not only in the conformance section where the gap is
  first enforced. Currently required for the `v→V` VFD transition in §8.1 VFD —
  Vendor Aware, Fix Ready, Fix Deployed.
- `[J]` No normative SHALL/MUST/MUST NOT statement is reproduced verbatim or
  near-verbatim in more than one section. Identify the canonical normative
  location; all other occurrences are rewritten as cross-references ("as
  required by §N.M *Section Name*", linked to the owning page). Common
  candidates: role-exclusivity rule, role
  self-assignment prohibition, single-writer authority, Case Owner transfer
  mechanics.
- `[J]` No informative note, provenance box, or roadmap statement is
  reproduced with near-identical language in more than one section without one
  occurrence being a cross-reference. Common candidates: PEC provenance note
  (§6 Report Management (RM) State Machine / §9 Participant Embargo Consent
  (PEC) State Machine), ActivityPub conformance roadmap (§1.3 Relationship to
  Existing Standards / §5.1 Base Vocabulary / §5.6 Transport Layer).
- `[J]` No body-text sentence asserting a normative fact (e.g., "some
  sequences carry normative weight") is immediately followed by an open
  question or admonition that contradicts or defers exactly that fact. Either
  the normative content is stated explicitly, or the positive claim is
  withdrawn and replaced with a placeholder citing the open question.

---

## 9. Content Modularity

Verify before each publication round that recurring reference items are
available as includable fragments or replicated as compact reminder
admonitions.

- `[J]` The state machine state tables for RM, EM, VFD, and PEC exist as
  standalone includable fragment files (e.g., `_rm-states-table.md`). Where
  the build toolchain supports `include-markdown`, each is re-embedded as a
  compact reminder admonition in downstream sections that rely on the state
  names. Where it does not, equivalent inline reminder admonitions are written
  at each downstream reuse point.
- `[J]` The "four dimensions / five state machines" orienting note (§3.3
  Tracking Dimensions) is available as a standalone fragment for re-inclusion
  wherever the five-machine count is normatively required (currently §12.2
  Capability Sets).
- `[J]` The shorthand-to-wire-form mapping table (§5.7 Shorthand to Wire Form
  Mapping) is available as a standalone fragment for re-inclusion in the §12.5
  Conformance Testing Approach context.
- `[J]` The named-configurations summary table (Hosting Coordinator /
  Self-coordinating Vendor / Bug Bounty Platform) is either positioned as an
  orienting preview in §3.2 What a Deployment Looks Like or §12.1 Conformance
  Model Overview, or is extractable as a fragment for that purpose.

---

## 10. Concept Lifecycle Coverage

Check when roles, object types, or message patterns are added or redefined.

- `[J]` Every role defined in §2 Terminology (`Reporter`, `Vendor`,
  `Coordinator`, `Deployer`, `Observer`, `CNA`) has substantive coverage in at
  least one state machine section or in §11 Participant Lifecycle Within a Case,
  beyond the terminology definition and conformance listing. If a role has no
  direct state machine obligations, that fact is stated explicitly rather than
  left implied by absence.
- `[J]` Every object type defined in §5.2 Object Types (`CaseProposal`,
  `CaseLedgerEntry`, `VulnerabilityCase`, `ParticipantRecord`) has a
  corresponding lifecycle description — at minimum: when it is created, what
  state transitions it records or triggers, and when it is retired or
  superseded. Object types that appear only in §5.2 Object Types and one or two
  incidental references elsewhere are flagged for lifecycle elaboration.
- `[J]` The term `Observer` is annotated in §2 Terminology as carrying two
  meanings (process role and capability set). Readers are warned at the §2
  Terminology definition; the §12 Conformance capability-set usage links back to
  it to confirm intentional overloading rather than a naming error.

---

## 11. Round-2 Finding Classes

Added after the second review round. Each is a class the earlier sections would
not have caught.

- `[J]` No stated default for a security-significant decision contradicts the
  spec corpus. Check every "the default is …" sentence against the requirement
  that sets it. The draft asserted an auto-adopt default where RSH-07-001/002 and
  ADR-0076 require defaulting to Case Owner authorization — an inversion that
  also silently invalidated an open question built on top of it.
- `[J]` A wire-form mapping that holds only for one role is stated as though it
  held for all senders. `Add(CaseStatus)` is the CASE_MANAGER's activity;
  participants send `Add(ParticipantStatus)` (RSH-04-001). A mapping table with no
  sender column will get this wrong.
- `[J]` Every normative MUST / MUST NOT traces to a spec ID or ADR. The draft
  asserted "an actor MUST NOT self-assign a role", which no spec group or ADR
  states. Invented normative content is harder to spot than a wrong citation,
  because there is nothing to check it against.
- `[M]` State machine transition tables match the implementation FSM
  transition-by-transition, in both directions: every table row exists in code,
  and every code transition appears in the table. The draft's RM table had one
  transition that does not exist, one over-permissive row, and one omission.
- `[M]` Every enum symbol cited in prose resolves against the codebase. The draft
  used `CS.P`/`CS.X`/`CS.A`, which are not members of the `CS` enum.
- `[J]` A section that delegates its mechanics to another document says whether
  that document is published, and states that conformance to the delegated part
  cannot be shown from this document alone.
- `[J]` Repeated reference content (state tables, orienting notes) is a single
  include, not a retyped copy. Two copies of a state table will diverge.
- `[J]` Where the review asks for a rename sweep, confirm the target names map
  one-to-one onto the actual states before sweeping. This round's requested EM
  names (*Non-Proposed, Active, Revised, Exited*) do not map cleanly onto the five
  implemented states, so a blind sweep would have introduced errors.
- `[M]` Region markers used by `include-markdown` `start`/`end` still exist in the
  source page. A renamed or deleted marker silently includes the wrong span.

---

## Mechanized (Covered by CI or Pre-commit)

Items moved here are no longer checked manually; the mechanism is noted.

| Item | Mechanism | Since |
|------|-----------|-------|
| Markdown lint (heading format, list style) | `markdownlint-cli2` pre-commit hook | pre-existing |
| MkDocs build with zero warnings | `mkdocs build --strict` in `docs-build-check.yml` and `deploy_site.yml` (DOCBW-03-009, DOCBW-03-010) | #3051 |
| Broken section heading anchors, on every page of the section | `mkdocs.yml` `validation.links.anchors: warn` + strict build | pre-existing |
| American spelling (SG-37) in every `docs/` file, fragments included | `codespell` pre-commit hook (`--write-changes`, `files: ^docs/.*\.md$`), dictionary and exclusions in `[tool.codespell]` in `pyproject.toml` | #3318 |
| Style-guide rules over this document's `_*.md` fragments | `lint-docs` § "Fragments and assembly units": sentence- and block-scoped rules against each fragment with its own line numbers; page-scoped rules (acronym first use, concept order, H1) against each assembling page in `notes/rfc-spec-authoring.md` § "Page Map", `full.md` included (DF-09-007, [ADR-0092](../docs/adr/0092-lint-fragments-as-source-page-rules-on-rendered-page.md)); an empty target set is a failure (DF-09-009) | #3318 |

Retired item, kept per this rubric's own rule: this document was outside
`lint-docs`' target set until #3318, because the linter read the `_` nav-exclusion
prefix as "not a page" and dropped every fragment. An American-spelling
regression reached `main` through that gap during the PR #3265 review round. The
two rows above are the covering mechanism; the `[M]` items in "Structural
Completeness" and "Terminology Consistency" are mechanical for this document
again.

---

## Changelog

| Date | Change | Source |
|------|--------|--------|
| 2026-09-16 | Initial rubric created from review of PR #3265 | Review of draft RFC commit d4572cee7 |
| 2026-09-16 | Added §8 Readability and Concept Flow, §9 Content Modularity, §10 Concept Lifecycle Coverage; extended §2 (Observer dual-use, track/drive definition), §4 (OQ fragment consistency), §5 (nav-note accuracy) — 24 additional gap items from top-to-bottom sequential audit of assembled spec | PR #3265 review comment |
| 2026-09-16 | Added §11 Round-2 Finding Classes (9 items) and two Mechanized entries; noted that `lint-docs` skips this document's fragments. Corrected §10: "Bug Bounty Operator" is not a role anywhere in the glossary, specs, notes or code — only the *Bug Bounty Platform* named configuration exists | Second review round of PR #3265 |
| 2026-09-28 | Retired the "`lint-docs` does not cover this document" warning: fragments are linted as source, page-scoped rules go to the assembled `index.md`, and `codespell` is the SG-37 floor. Two Mechanized rows added; the `[M]`-treated-as-`[J]` instruction removed | #3318 |
| 2026-10-01 | The specification is a section of pages: added page-map, tip and landing-page checks to Structural Completeness; Cross-Reference Integrity requires links to the owning page and citations with number and name; mechanized lint row evaluates page-scoped rules on every assembling page; corrected stale section numbers (the shorthand table is §5.7 Shorthand to Wire Form Mapping; the case histories are annexes) | #4060 |
