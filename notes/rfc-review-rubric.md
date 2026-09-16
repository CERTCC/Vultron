---
title: RFC Review Rubric
description: >
  Living checklist for reviewing the Vultron Protocol Specification RFC
  (docs/reference/vultron-spec/) against the codebase, system specs, notes,
  and design. Apply each round of revision; extend as new issue classes emerge.
status: active
---

# RFC Review Rubric

A reviewer agent (or human) working through the Vultron Protocol Specification
should run all checks below in order. Items tagged `[M]` can be verified
mechanically (grep, build output, diff against codebase); items tagged `[J]`
require reading and judgment.

Add items after each review round. Retire `[M]` items to the "Mechanized"
section once a linter or CI check covers them. Do not delete items that were
retired — note the covering mechanism so the reason for the rule survives.

---

## 1. Structural Completeness

Preconditions — flag any failure here before reading for content.

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
- `[J]` Sections that contain no normative requirements (currently §12.6 is a
  candidate) are evaluated for relocation to an informative annex.

---

## 5. Cross-Reference Integrity

- `[M]` Every `§N.M` reference resolves to an actual heading anchor. Run
  `bash .github/scripts/mkdocs-build-strict.sh` and treat any broken-anchor
  warning as a blocker.
- `[M]` Every reference to a Python source file is a clickable Markdown link
  pointing to a canonical GitHub URL — not a bare file path. The RFC must be
  usable as a standalone PDF.
- `[J]` Forward references (pointing far ahead in the document) either carry a
  one-sentence explanation of the relationship, or are eliminated by
  reordering.
- `[J]` Every callout or sidebar that says "see worked example" or "see case
  history" contains actual content, not a placeholder.

---

## 6. Codebase Alignment

Run against the current `main` branch of the implementation.

- `[M]` Every state name used in the document appears in the corresponding
  codebase enum. Diff the full list from `_terminology.md` against
  `vultron/enums/`.
- `[M]` Every message shorthand (RS, RV, RK, EP, etc.) maps to a
  `MessageSemantics` or equivalent enum value. Flag any shorthand without a
  codebase match.
- `[J]` Workflow descriptions (§11) match the actually supported flows in the
  implementation. Step through at least the single-vendor and multi-vendor
  coordinated-disclosure cases.
- `[J]` Role capability claims (§12.4) match what the codebase enforces, not
  only what the protocol intends.
- `[J]` Any "default policy" statement is verified against the current default
  configuration in the implementation.
- `[J]` Case histories and worked examples (§15) are verified against the
  current state-machine design before each publication.

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

## Mechanized (Covered by CI or Pre-commit)

Items moved here are no longer checked manually; the mechanism is noted.

| Item | Mechanism | Since |
|------|-----------|-------|
| Markdown lint (heading format, list style) | `markdownlint-cli2` pre-commit hook | pre-existing |
| MkDocs build with zero warnings | `mkdocs-build-strict.sh` CI step | pre-existing |

---

## Changelog

| Date | Change | Source |
|------|--------|--------|
| 2026-09-16 | Initial rubric created from review of PR #3265 | Review of draft RFC commit d4572cee7 |
