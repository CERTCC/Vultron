---
status: accepted-provisional
date: 2026-10-12
created: 2026-10-12
updated: 2026-10-12
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0038; specs/meta-specifications.yaml MS-12-001 through
  MS-12-008; issue #4528, PR #4520 (issue #3601)
informed: []
stakeholder_type: [project-contributor]
partially_supersedes:
  - 0038-four-tier-specification-taxonomy.md
---

# Who Must Obey a Rule Decides Its Spec Kind

## Context and Problem Statement

ADR-0038 gave every spec a `kind`, so that an implementer could filter the corpus down to the rules that bind them.
Its decision tree put one question ahead of the compliance test: "Does this reference a language construct, library, file path, class, function, module, or codebase-specific mechanism?"
A yes meant `project`.

Read literally, that question decides a spec's kind by the words in its statement.
PR #4520 (issue #3601) applied it that way and moved genuine protocol rules to `project` because their statements named code.
Those rules still bind every Vultron implementation, so the relabel hid them from the implementers the taxonomy exists to serve.

The four kinds also had no home for a third group of rules.
Addressing and delivery, HTTP status codes, and rules that only restate ActivityStreams bind every implementation, but Vultron inherits them from the standards beneath it rather than defining them.
Filed as `protocol`, they inflate what Vultron defines.
Filed as `project`, they disappear from the implementer's view.

This ADR records the maintainer's decisions from a live interview on 2026-10-12.
It settles what the kind question asks, adds a fifth kind, and says what to do with a spec that mixes kinds.

## Decision Drivers

- An implementer must be able to read a known, small set of kinds and find every rule that binds them.
- A spec's kind must not change when its wording changes but its obligation does not.
- Rules Vultron inherits must be traceable to the standard that owns them.
- A fix to a mixed spec must not trip the PR-only growth guards from #4315 (no new uncovered protocol spec, no new `missing_story_reference` carrier).

## Considered Options

- **A — Who must obey decides; add `foundation`; split mixed specs.**
- **B — Who must obey decides; add two new kinds**, one per layer of inherited standard (for example, one for ActivityStreams and ActivityPub, one for HTTP).
- **C — Who must obey decides; no new kind; record inherited rules with tags only**, leaving them `protocol`.
- **D — Keep the literal reading** of ADR-0038's step 2: naming code makes a spec `project`.

## Decision Outcome

Chosen option: **A**.
It is the only option that keeps every rule binding an implementer on the pages an implementer reads, and also separates Vultron's own rules from the ones it inherits.

### The rule

Who must obey a rule decides its kind.
Naming code never does.
A statement that names a file path, library, class, or behavior tree node is either a protocol rule spelled in this codebase's terms, which is reworded, or a mixed spec, which is split.

### The five kinds

- **`protocol`** — the Vultron layer: Vultron's message forms on the wire (including where ActivityStreams allows several forms and Vultron requires one, for example an Accept referencing the Offer), which messages are sent and when, what a receiver does given its state (including on duplicate delivery), and the state machines underlying those behaviors.
  State-machine states such as `RM.CLOSED` are protocol constructs.
  The CASE_MANAGER role and case-ledger sync are `protocol` for now; re-judge them if the protocol moves to a federated design with no CASE_MANAGER.
- **`foundation`** (new) — rules Vultron inherits from the standards beneath it: ActivityStreams 2.0, ActivityPub, HTTP.
  Examples are addressing and delivery, HTTP status codes, and rules that only restate ActivityStreams, such as every `id` being an IRI.
  A tag records which standard: `as2`, `activitypub`, or `http`.
  An implementer reads `protocol` and `foundation`.
- **`architecture`** — recommended structure that carries over to other languages but is not required for compliance.
  Behavior trees, and keeping protocol behavior inside the behavior tree, are here.
- **`project`** — this codebase only: deployment choices (for example, the CASE_MANAGER as a separate actor from the case owner), performance and operating limits, how a receiver records what it receives, and core internals.
- **`process`** — unchanged: how the project is run.

The decision tree asks, in order: how the project is run (`process`), this codebase only (`project`), inherited from a standard beneath Vultron (`foundation`), every Vultron implementation (`protocol`), and recommended structure (`architecture`).
`foundation` precedes `protocol` so that a rule that only restates a standard is not counted as Vultron's own.

### The split rule

A spec that mixes kinds is split by what other participants can observe.
The protocol half states what is emitted or observed; the project half states how this codebase does it.
The original ID keeps the protocol half, reworded so any implementation could obey it.
The implementation detail moves to a new `project` ID that links back to the original.

Worked example: default-embargo creation.
The protocol half is that other participants never observe the intermediate Proposed state.
The project half is that this codebase applies PROPOSE and ACCEPT atomically in one behavior tree node.

The original ID keeps the protocol half because its user stories, test markers, and citations stay with it.
The growth guards then see no new uncovered protocol spec and no new suppression.

### Scope of this decision

This decision changes the rule, the schema, and the tooling.
It does not re-judge the corpus: the suppressed and story-less protocol specs are #3601's, and the sweep that relabels inherited-standard rules to `foundation` is #4529's.

### Checks that protect implementers

Checks that exist to protect implementers apply to the implementer-facing kinds, `protocol` and `foundation`.
These are test coverage, traceability to user stories, and the code-reference detector that finds mixed specs.
Which of those kinds each check covers at a given time is policy, recorded in the check's governing spec (SR-05-004 and SR-05-005, SR-11-003 and SR-11-004, MS-12-006) and in `notes/spec-authoring-rules.md`.
A check may cover fewer than both kinds while the corpus catches up, and widens as it does.
For example, user stories for behavior Vultron inherits from ActivityStreams, ActivityPub and HTTP are not yet backfilled (the story work under #2717, such as #4513).

### Changing a kind keeps its tests

Changing a spec's kind never removes the tests or test markers that already verify it, whatever the destination kind (MS-12-011).
A test is evidence that a rule holds, and relabeling the rule does not change whether it holds.

### Consequences

- Good, because a rule's kind now follows from its obligation, so rewording a statement cannot move it out of an implementer's view.
- Good, because inherited rules are separated from Vultron's own and each names the standard that owns it.
- Good, because the split rule keeps the protocol half on its original ID, so a split never trips a growth guard.
- Bad, because "who must obey" is a judgement: the detector can only flag the mechanical symptom (a code token in an implementer-facing statement), not decide the kind.
- Bad, because while a check covers only one of the implementer-facing kinds, a relabel between them can move a spec out of that check; a relabel sweep has to keep that move from becoming a way around the check until it widens.
- Neutral, because the CASE_MANAGER role and case-ledger sync are classified for the current, centralized design and are expected to be re-judged if that design changes.

## Validation

- `SpecKind` in `vultron/metadata/specs/schema.py` has the five values, and its docstring carries the definitions above.
- `spec-lint` fails a `foundation` spec whose effective tags name no standard (MS-12-009), and its MS-12-006 message advises rewording or splitting, never relabeling.
- Each check that protects implementers names the kinds it covers in its governing spec (SR-05-004, SR-05-005, SR-11-003, SR-11-004, MS-12-006).
- A PR that changes a spec's kind and drops the marker it had at the merge base fails (MS-12-011).
- Every kind has a docs page under `docs/reference/specs/`, enforced by `test/metadata/specs/test_kind_page_coverage.py`.

## Pros and Cons of the Options

### A — Who must obey decides; add `foundation`; split mixed specs

- Good, because an implementer reads exactly two kinds, and both are complete.
- Good, because one tag per inherited rule records the source standard without multiplying kinds.
- Bad, because the corpus has to be re-judged against the new rule, in follow-up work.

### B — Two new kinds

- Good, because the standard is visible in the kind itself.
- Bad, because the split between the two kinds is arbitrary: ActivityPub delivery is HTTP, and an HTTP status code answers an ActivityPub request.
- Bad, because every kind multiplies the docs pages, filters, and gates that must handle it, for no difference in who must obey.

### C — Tags only, no new kind

- Good, because the schema does not change.
- Bad, because inherited rules stay `protocol`, so the protocol page still overstates what Vultron defines, and a filter on `kind` cannot separate them.
- Bad, because a tag is optional metadata, while a kind is required on every spec and checked by every gate.

### D — Keep the literal reading

- Good, because it is mechanical.
- Bad, because it decides a kind by wording, and moved genuine protocol rules out of the implementer's view in PR #4520.

## More Information

This ADR partially supersedes ADR-0038: it replaces the four tiers with five and replaces the decision tree's second question.
ADR-0038's move from six kinds to named portability tiers stands.

Generated spec requirements: `specs/meta-specifications.yaml` MS-12-002, MS-12-003, MS-12-005, MS-12-006, MS-12-009, MS-12-010 and MS-12-011, and `specs/spec-registry.yaml` SR-02-005, SR-05-004 and SR-05-005.
