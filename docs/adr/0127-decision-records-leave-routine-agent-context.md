---
status: proposed
date: 2026-10-09
created: 2026-10-09
updated: 2026-10-09
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5; notes/specs-vs-adrs.md;
  docs/adr/0120-adr-lifecycle-epochs-and-edit-tiers.md;
  docs/adr/0043-adr-status-as-confidence-signal.md
informed: Vultron contributors, agent skill authors
stakeholder_type: [project-contributor]
---

# Decision Records Leave Routine Agent Context; Specs and Notes Carry the Current State

## Context and Problem Statement

An ADR records what was decided and why, given what was known at the time.
That answer cannot go stale, because the past does not change.
But ADR bodies also accumulate implementation detail — class names, function names, module paths, counts, code samples — and that detail ages the moment the code is refactored, while the decision it was illustrating stands intact.

The cost of that aging is not maintenance effort.
It is what agents carry.
Routine task context loaded ADR bodies: `.agents/skills/deepen-context/SKILL.md` instructed an agent to read the full file for any decision in scope, selected by title match, with no cap, no manifest and no backstop — unlike the spec loading in the very next step, which has all four.
A stale-but-once-true sentence then consumes working memory on a claim that is no longer checkable, and sends an agent looking for a symbol that is not in the tree.
A statement that used to be correct pollutes context exactly as much as one that was never correct.

Measured over the corpus on 2026-10-09, at 120 numbered live records: 48 records carried at least one backticked file path or code symbol that resolves nowhere in `vultron/` or `test/`, across 217 such references.
None of those 48 was superseded or deprecated.
The decisions stood; only their descriptions of the code had aged.
The worst cases were in titles and decision outcomes rather than footnotes: ADR-0018's heading names a case-history model whose name no longer exists, ADR-0013's heading names a participant-status class since removed, ADR-0093's heading asserts a transition out of a consent state that is no longer a member of its enum, and ADR-0066 gives a default value for a retry parameter that was never built.
Separately, 70% of all ADR file edits up to that date modified records that were already written, and roughly a quarter of those were caused mechanically by a code or filesystem change rather than by any change of mind.

The project had already chosen a direction on this, and it was the opposite one.
The hand-written preamble of `docs/adr/index.md` asserted that a record's value to a future reader is that they can understand the current expectation in one pass, and instructed authors to revise accepted bodies directly.
That guidance was a rational response to the loading behaviour above: while every body is routine context, the only way to keep an agent from reading a false sentence is to keep every sentence true.
It also conflicted with `docs/adr/0120-adr-lifecycle-epochs-and-edit-tiers.md`, which requires a dated amendment instead of an in-place rewrite once a record is settled, and that conflict had already cost a blocked fix (#4348, closed via #4386 only by paying the amendment ceremony).

So the question is not "how do we keep ADR bodies current".
It is "what is an ADR for, and what reads it".

## Decision Drivers

- Agent context is the scarce resource, and a stale sentence costs as much as a wrong one.
- A refactor must not acquire an obligation to update documents elsewhere in the tree; an obligation like that is paid every time or not at all, and it was not being paid.
- `docs/adr/0120-adr-lifecycle-epochs-and-edit-tiers.md` already froze the Decision Outcome and Considered Options sections of a settled record. Any answer that depends on editing those sections is in tension with it.
- Specs and notes already carry a currency obligation, with tooling that enforces it: requirement verification clauses, the phantom path and symbol checks in `vultron/metadata/specs/lint.py`, and notes frontmatter maintenance.
- `docs/adr/0043-adr-status-as-confidence-signal.md` established that the `status` field is the confidence signal agents read. Nothing equivalent exists for the currency of a body's code references, and adding one would be a second signal to keep in sync.

## Considered Options

- Keep every ADR body current, and treat a stale code reference as a defect to fix.
- Stop loading ADR bodies as routine agent context, and make specs and notes the only documents that describe the current state.
- Add a merge-blocking check that fails a pull request whose code change strands a reference in any ADR body.
- Split the largest records so each body is small enough that reading it costs little.

## Decision Outcome

Chosen option: **stop loading ADR bodies as routine agent context, and make specs and notes the only documents that describe the current state**, because it removes the cost at its source rather than paying it repeatedly, and because it is the only option compatible with the frozen-section rule the project had already adopted.

An ADR is a historical record.
It is not a description of the current codebase.
Three consequences follow for everyday work.

**A refactor is never responsible for updating an ADR.**
Renaming a symbol or splitting a module creates no obligation to touch any record that mentions it.
A stale code reference in an ADR body is therefore not a defect, and nothing in the tooling fails on one.

**A constraint future code must obey does not live in an ADR body.**
It goes to a spec requirement when it is testable, or to a `notes/` file when it is design insight, citing the record as provenance.

**A spec or note must not resolve its own meaning by pointing into an ADR body.**
Cite a record for *why*; state the rule where the reader already is.
A citation that names a numbered detail inside a body — rather than naming the record as provenance for a rule stated in full on the spot — makes the body load-bearing again and defeats this decision.

Sentences in an ADR body sort four ways:

1. A constraint future code must obey moves to a spec requirement or a `notes/` file, with the record cited as provenance.
2. The reasoning and the rejected options stay, untouched.
3. A statement about a completed migration step — "X is deleted", a struck-through progress list — is project tracking rather than decision content, and belongs in the issue that did the work.
4. A description of how the code looked when the decision was made stays, because it is part of why the decision was needed. It is written so it reads as of its time.

**The existing backlog of stale references is not work.**
This is the consequence that most distinguishes this decision from the option it replaces.
Under option one each of the 217 measured references was a defect; under this decision a reference in a record's context or validation prose is an accurate account of the code as it then stood, and scrubbing it buys nothing once nothing routinely reads it.
No issue is opened to work that backlog, and no advisory count of it is reported — a count would re-describe the same references as debt and invite the scrub back.

**Enforcement is forward-only and never blocks a refactor.**
A reference newly written into a record should resolve on the day it is written, which is a question about the pull request's own diff and not about the corpus.
A check is therefore expected to compare an edited record against the merge base and fail only on a reference the change itself adds, in the manner `vultron/metadata/adr/lifecycle.py` already compares protected sections.
A merge-blocking check keyed on code changes is rejected outright: it would reinstate exactly the obligation this decision removes.

**Some skills keep full access, and the list is written down.**
This decision narrows routine task context; it is not an instruction to stop reading records.
Decision auditing, ADR authoring, the learning workflow, issue planning and pull request triage each need bodies, and the replacement text in `.agents/skills/deepen-context/SKILL.md` is expected to name them, so the narrowing is not over-read.

### Consequences

- Good, because the cost is removed once rather than paid at every refactor, and the obligation that was not being paid is deleted rather than re-asserted.
- Good, because it agrees with the frozen-section rule of `docs/adr/0120-adr-lifecycle-epochs-and-edit-tiers.md` instead of fighting it. 106 of the 217 measured references sit inside a Decision Outcome or Considered Options section on 34 records, where option one could only have proceeded by spending a dated amendment on a rename.
- Good, because the currency obligation lands where tooling already enforces it, rather than on a document class with no verification mechanism.
- Bad, because an agent that genuinely needs a rejected option or an evaluated alternative no longer meets it by default, and must reach a record deliberately.
- Bad, because it is gated: the loading change cannot land until nothing in `specs/` or `notes/` resolves its meaning by pointing into a body, and that conversion is real authoring work.
- Neutral, because a human reader's experience is unchanged. A reader arriving at a record still meets whatever aged prose it carries, and now has the framing to read it as history.

## Validation

Compliance will be visible in three places, none of which exists yet at this revision.

The loading step in `.agents/skills/deepen-context/SKILL.md` will no longer instruct an agent to read a record body for routine work, and will carry the written exception list in its place.
The hint source that step loses — a body's prose citations of requirement IDs — will be replaced by reading the structured `adr:` edges that requirements already carry, in the record-to-requirements direction. Measured on 2026-10-09 those edges covered 610 requirements and reached 86 of the 120 live records, which is denser than the prose citations they replace.
A check in `vultron/metadata/adr/lifecycle.py` will fail a pull request that adds an unresolvable path or code symbol to a record it edits, and will recognize class names and function names, not only underscored constants — the shape the current spec-corpus check in `vultron/metadata/specs/lint.py` matches, which happens to miss every headline case above.

This record is `status: proposed` and carries no validated enforcement.
The preceding paragraphs are written in the future tense deliberately: none of those three changes is built at revision 1.

## Pros and Cons of the Options

### Keep every ADR body current, and treat a stale code reference as a defect

This was the project's guidance from 2026-07-31 (ISSUE-1777) until it was replaced on 2026-10-09.

- Good, because a reader meets only currently-accurate statements, which is exactly what is wanted while bodies are read as routine context.
- Bad, because it makes every refactor responsible for documents it has no reason to touch, and the measurement shows that obligation was not being met: 48 records had drifted, none of them retired.
- Bad, because it cannot be done without editing frozen sections. The option is in direct conflict with the edit tiers of `docs/adr/0120-adr-lifecycle-epochs-and-edit-tiers.md`, which it predates.
- Bad, because it spends the amendment ceremony — reserved for a change in what a decision means — on renames.
- Bad, because it treats a record's account of past code as an error rather than as context, which erases the very thing that explains why a decision was needed.

### Stop loading ADR bodies as routine agent context

- Good, because the arguments above, recorded under Decision Outcome and Consequences.
- Bad, because it is gated on conversion work before the benefit arrives.
- Neutral, because two house styles for annotating a removed symbol already exist in the corpus (ADR-0063 and ADR-0110 annotate inline; ADR-0067 relocates the live detail to spec requirements and says so). Neither becomes mandatory, and both remain available to an author who wants them.

### Add a merge-blocking check keyed on code changes

- Good, because it would hold the corpus at zero stale references mechanically, with no reliance on author discipline.
- Bad, because it reinstates the refactor obligation as a hard gate — the precise failure this decision removes. A rename would turn a pull request red for a sentence in a document the pull request has no reason to have read.
- Bad, because the check would fail on the clock-like property that `docs/adr/0120-adr-lifecycle-epochs-and-edit-tiers.md` already avoided for status drift: a reference goes stale in a commit that does not touch the record, so the failure lands on whoever is nearest.

### Split the largest records so each body is cheap to read

- Good, because it reduces per-record cost without changing any policy.
- Bad, because it addresses size, not staleness. A short record with a dead class name in its title is still misleading, and ADR-0018 is short.
- Bad, because splitting a record scatters its evaluated alternatives. A piece carved out of a decision inherits no rejected options, which is the one thing an ADR exists to hold.

## More Information

### Preconditions

Two must be satisfied before the loading change lands, and both are tracked as implementation issues under concern #4389:

- Nothing in `specs/` or `notes/` may resolve its meaning by pointing into a body. The known violation is the set of citations naming numbered details of `docs/adr/0099-one-object-model-as2-is-a-serialization.md`, spread across both trees; those details are defined nowhere but that body. Converting them means reflowing the ten details into a requirement group, which the record's own table mapping details to tests makes transcription rather than fresh authoring.
- A decision whose content lives nowhere but a body needs a home. Measured on 2026-10-09, 15 live records had neither a structured `adr:` edge from any requirement nor a prose mention anywhere in `specs/` or `notes/`. Most of those have a requirement group that covers the decision without pointing back, so the fix is the pointer; a few need the decision written down.

### Relationship to other decisions

- `docs/adr/0120-adr-lifecycle-epochs-and-edit-tiers.md` supplies the editing mechanics this decision assumes: epochs, edit tiers, and the frozen Decision Outcome and Considered Options sections.
- `docs/adr/0043-adr-status-as-confidence-signal.md` governs how much weight an agent gives a record it does read. This decision changes *when* a record is read, not how it is weighted.
- `docs/adr/0067-rm-nonadj-accept-and-notify.md` is the worked template, arrived at independently under #4348: its implementation-shape section now states decision-level invariants only and defers the live mapping to spec requirements whose verification clauses name the current tests, so an implementation refactor cannot invalidate it.
- `docs/adr/0003-build-custom-python-bt-engine.md` is explicitly *not* an instance of this problem. It is `status: accepted` for an approach the project reversed, which is a wrong decision record rather than a stale description, and it belongs to decision auditing.

### Realization and revisiting

This decision is realized by the implementation issues under concern #4389, in order: convert the detail-number citations; close the pointer gaps on the 15 records; then change the loading step. The forward-only check is independent of that order.

Revisit if the structured `adr:` edges prove too sparse to replace the prose hints the loading step loses, or if the written exception list grows to the point that most work is covered by an exception — either would mean bodies are routine context again under another name.

Generated spec requirements: none at this revision. The forward-only check will carry its own requirement, with a verification clause, in the pull request that builds it.
