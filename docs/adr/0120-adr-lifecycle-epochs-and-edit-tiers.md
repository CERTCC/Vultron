---
status: proposed
date: 2026-10-06
created: 2026-10-06
updated: 2026-10-06
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Sonnet 5.5; the 2026-10-02 audit of unsupervised agent decisions (#4195);
  docs/adr/0043 (ADR status as confidence signal); specs/meta-specifications.yaml MS-14
informed: []
stakeholder_type: [project-contributor]
---

# ADR Lifecycle: Three Epochs and Tiered Edits

## Context and Problem Statement

The 2026-10-02 audit of 72 pull requests merged without human review found ADRs edited in place after acceptance: ADR-0041 and ADR-0096 by #4025, and ADR-0070 and ADR-0084 rewritten wholesale under their own numbers, their chosen option replaced weeks after acceptance.
An agent, or a human, who cites an ADR by number then cites text that never said what the citation meant.
The opposite failure also exists: superseding an ADR within hours of writing it leaves a trail of dead records for a decision that was never settled.

ADR `status` is the confidence signal agents read (MS-14, ADR-0043), but nothing ties it to how long the decision has stood or to who may change it and how.
When is an ADR free to edit, when must a human be asked, and when must the change be a new ADR?

## Decision Drivers

- A citation of an ADR MUST keep meaning what it meant when it was written, once the decision has had time to be built on.
- A fresh decision needs to be fixable without ceremony while its author still holds the context.
- Agents implement against ADRs that no human has read yet; the human touch should be one specific, mandatory question, not a review gate on every edit.
- The rule must be checkable from frontmatter alone.

## Considered Options

- Immutable once written: every change is a new ADR.
- Edit in place freely, with git as the record.
- Three epochs measured from `updated`, with edit tiers.

## Decision Outcome

Chosen option: "Three epochs measured from `updated`, with edit tiers", because it is the only option that gives a fresh decision room to settle, protects a settled decision's citations, and names the point at which a human must decide.

### Frontmatter

- `created`: the date the ADR was first written. Immutable.
- `updated`: the date of the last *material* edit. Editorial edits, annotations and appended clarifications do not change it.
- `revision`: an integer, starting at 1, incremented by each material edit.
- `date` keeps its earlier meaning (the date first written) and is not changed.
- Existing ADRs are migrated with `created = updated = date` and `revision = 1`.

### Epochs

Epochs are measured from `updated`.

| Epoch | Age since `updated` | `status` | Editing |
|---|---|---|---|
| 1 | under 72 hours | `proposed` | Edit in place freely. |
| 2 | 72 hours to day 10 | `accepted-provisional` | Ask the human whether to edit in place or supersede. |
| 3 | day 10 onward | `accepted` | Supersede; see the edit tiers. |

A merged implementation that depends on the ADR may harden it to epoch 3 early.
`status` is lint-checked against the epoch computed from `updated` (MS-14-007); a human may override the computed value, and the override is visible in the frontmatter.
The lint is #4196.

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
- Bad, because every ADR needs three extra frontmatter fields and a status lint.
- Bad, because the epoch boundaries are a fixed clock; the early-hardening and human-override escapes exist for that reason.

## Validation

`AdrFrontmatter` accepts `created`, `updated` and `revision` (`vultron/metadata/adr/schema.py`).
The status-against-epoch lint is #4196 and the archive tooling is #4197.
MS-14-007 and MS-14-008 state the requirements.

## More Information

The restoration of ADR-0041, ADR-0096, ADR-0070 and ADR-0084, and the annotations on ADR-0099, ADR-0111, ADR-0113 and ADR-0114, apply this rule retroactively; they are recorded under #4195.
`notes/specs-vs-adrs.md` describes the epochs and tiers for authors.

Generated spec requirements: `meta-specifications.yaml` MS-14-007, MS-14-008.
