---
status: accepted-provisional
status_override: >-
  Revision 2 edited in place in epoch 2 by the maintainer's choice in the planning interview
  for Concern #4479 (timers alone are the wrong signal), rather than superseded.
date: 2026-10-06
created: 2026-10-06
updated: 2026-10-12
revision: 2
deciders: Allen D. Householder
consulted: >-
  Claude Sonnet 5.5; the 2026-10-02 audit of unsupervised agent decisions (#4195);
  docs/adr/0043 (ADR status as confidence signal); specs/meta-specifications.yaml MS-14;
  Concern #4479 (the 72-hour free-edit window was too short)
informed: []
stakeholder_type: [project-contributor]
---

# ADR Lifecycle: Three Epochs and Tiered Edits

## Context and Problem Statement

The 2026-10-02 audit of pull requests merged without human review found ADRs edited in place after acceptance: ADR-0041 and ADR-0096 by #4025, and ADR-0070 and ADR-0084 rewritten wholesale under their own numbers, their chosen option replaced weeks after acceptance.
An agent, or a human, who cites an ADR by number then cites text that never said what the citation meant.
The opposite failure also exists: superseding an ADR within hours of writing it leaves a trail of dead records for a decision that was never settled.

ADR `status` is the confidence signal agents read (MS-14, ADR-0043), but nothing ties it to how long the decision has stood or to who may change it and how.
When is an ADR free to edit, when must a human be asked, and when must the change be a new ADR?

## Decision Drivers

- A citation of an ADR MUST keep meaning what it meant when it was written, once the decision has had time to be built on.
- A fresh decision needs to be fixable without ceremony while its author still holds the context.
- Agents implement against ADRs that no human has read yet; the human touch should be one specific, mandatory question, not a review gate on every edit.
- Elapsed time alone is the wrong signal that a decision has had its chance to be revised: it runs out over weekends and while an agent-written ADR sits unread, whether or not anyone is revising it.
- Every ADR must still harden eventually; none may stay undecided forever.
- The rule must be checkable from the repository alone: frontmatter, specs and tests, never a reviewer's memory.

## Considered Options

- Immutable once written: every change is a new ADR.
- Edit in place freely, with git as the record.
- Three epochs measured from `updated`, with edit tiers.

## Decision Outcome

Chosen option: "Three epochs measured from `updated`, with edit tiers", because it is the only option that gives a fresh decision room to settle, protects a settled decision's citations, and names the point at which a human must decide.
Epoch 1 ends on the first test-verified dependent or a backstop timer, whichever comes first.

### Frontmatter

- `created`: the date the ADR was first written. Immutable.
- `updated`: the date of the last *material* edit. Editorial edits, annotations and appended clarifications do not change it.
- `revision`: an integer, starting at 1, incremented by each material edit.
- `date` keeps its earlier meaning (the date first written) and is not changed.
- Existing ADRs are migrated with `created = updated = date` and `revision = 1`.

### Epochs

The timers are measured from `updated`; the dependency event is not.

| Epoch | Ends | `status` | Editing |
|---|---|---|---|
| 1 | at the first test-verified dependent, or day 14 | `proposed` | Edit in place freely. |
| 2 | at day 28 | `accepted-provisional` | Ask the human whether to edit in place or supersede. |
| 3 | never | `accepted` | Supersede; see the edit tiers. |

A test-verified dependent is a spec requirement that cites the ADR in `adr:` and whose verification names a test file that exists, counted in the tree being checked: the pull request's head for a pull-request check, `main` for the scheduled report.
It is the signal the material test asks for: once something is built on the ADR, rewriting it freely can make that thing wrong.
The first dependent ends epoch 1 and nothing more; the first implementation is often where a detail turns out wrong, and fixing it in place with the human's yes is cheaper than a superseding ADR.
The pull request that creates it, whether by adding a requirement, by adding `adr:` or a verification to an existing one, or by adding the test file, must set the ADR to `accepted-provisional` in the same change, because it is the change that moved the facts; a check against the merge base enforces it.
The day-14 and day-28 timers are a backstop for an ADR nothing tests, so that every ADR eventually hardens.
A material edit bumps `updated` and restarts both timers, but not the dependency: an ADR that has a test-verified dependent never returns to epoch 1.

Status only moves forward.
The computed epoch is a floor: a status already ahead of it stands, so a change to these timers never demotes an ADR that agents have built on as `accepted`.
A material edit that restarts the timers keeps a status already ahead, under the `status_override:` the edit already needs.
A pull request that moves a status ahead of its epoch must add or change a `status_override:` naming a human's reason; an override already on the base does not cover a new promotion, and the override is visible in the frontmatter.

The clock alone never fails a merge-blocking check, because an ADR crossing a boundary changes no commit.
A pull request that materially edits an ADR (its `updated` date changes, or the ADR is new) must leave the status on the epoch for that date or carry a `status_override:`, and a diff-based check against the merge base enforces it (#4196).
A scheduled workflow reports every other ADR whose status is behind its epoch through one self-closing tracking issue and never fails the build; a human flips the status.

### Agents and `proposed` ADRs

Agents implement against `proposed` ADRs.
A `proposed` ADR is not a draft awaiting approval before work may start; it is the working decision, and the mandatory human touch is the epoch-2 ask.
AGENTS.md's earlier wording that agents "propose architectural changes, not apply" is retired.
ADR-0115 (PR #4068) and ADR-0116 (PR #4078) are `proposed` under this rule.

### Edit tiers

1. **Editorial and annotation.** Typos, link repair, formatting, and append-only annotations (for example a dated human-ratification note naming the maintainer). Allowed in any epoch. Does not change `updated` or `revision`.
2. **Clarification.** A change that does not alter what anything built on the ADR must do. After epoch 1, append it as a dated note; do not rewrite the original text. Does not change `updated`.
3. **Material change.** A change that passes the material test: *would something built on the old text now be wrong?* It bumps `updated` and `revision`, and follows the epoch rule above.

In epoch 3 a material change to one detail, with the chosen option intact, is a dated Amendment section that quotes the replaced text.
A change of the chosen option is a new ADR that supersedes the old one; the old one is restored to its original text, marked `superseded`, and moved to `archived/` (MS-14-004).
Rewriting an accepted ADR under its own number is never correct.

### Consequences

- Good, because citations of a settled ADR stay true.
- Good, because a fresh decision can be corrected cheaply.
- Good, because the human's required involvement is one question at a known moment.
- Good, because an ADR nothing builds on can be revised for two weeks, however long it waits unread.
- Bad, because every ADR needs three extra frontmatter fields and a status lint.
- Bad, because the epoch depends on the spec corpus as well as the frontmatter, so a pull request that never touches an ADR can be required to change its status.
- Bad, because the backstop is still a fixed clock; the dependency event and the human override exist for that reason.

## Validation

`AdrFrontmatter` accepts `created`, `updated` and `revision` (`vultron/metadata/adr/schema.py`).
The status-against-epoch lint is #4196, the archive tooling is #4197, and the tooling for revision 2 is #4501.
MS-14-007 through MS-14-010 and MS-14-012 state the requirements.

## More Information

The restoration of ADR-0041, ADR-0096, ADR-0070 and ADR-0084, and the annotations on ADR-0099, ADR-0111, ADR-0113 and ADR-0114, apply this rule retroactively; they are recorded under #4195.
`notes/specs-vs-adrs.md` describes the epochs and tiers for authors.

Generated spec requirements: `meta-specifications.yaml` MS-14-007, MS-14-008, MS-14-010, MS-14-012.
