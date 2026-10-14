---
source: NOTES-behavioral-conformance-specs--statementspec-vs-behavioralspec-selection
timestamp: '2026-10-12T23:47:29.864523+00:00'
title: 'Behavioral conformance specs: StatementSpec vs BehavioralSpec selection (duplicate
  of spec-authoring-rules)'
type: note
---

Archived from `notes/behavioral-conformance-specs.md` by #4497 (notes sweep): the
StatementSpec-versus-BehavioralSpec guidance duplicated
`notes/spec-authoring-rules.md` § "Spec Item Format Is Field Presence, Not a
Class You Pick" and § "`steps` Carries the Action of an ECA Rule" (ADR-0101,
MS-13-001/002). The demo-scenario-group material (the MS-13-003 marker as the
registry declaration, MS-13-004, and the steps-block-is-a-projection rule) is kept
once, in `notes/demo-scenario-registry.md` § "Which spec groups specify a
scenario". The short protocol-group reminder stays in the trimmed note.

---

## StatementSpec vs BehavioralSpec Selection

Use the MS-13 decision tree (from `specs/meta-specifications.yaml`) when choosing
between `StatementSpec` and `BehavioralSpec` for a spec item:

- **Use `BehavioralSpec`** when the item is an ECA rule — it carries a typed
  condition (`preconditions`), an action sequence (`steps`), or a terminal
  assertion (`postconditions`). A demo scenario workflow, a received-message
  handler sequence, and a multi-step handshake all qualify, and so does a
  single-action rule with a typed precondition.
- **Use `StatementSpec`** when the item is a bare capability constraint,
  behavioral property, or structural rule carrying none of those three fields.

**The format is the fields, not a class you pick** (ADR-0101). `BehavioralSpec`
requires at least one of `preconditions`, `steps`, or `postconditions`; an item
supplying none of them *is* a `StatementSpec`, and no consumer can tell otherwise.
Read the choice off the fields, and do not treat ordering as the discriminator:
`steps` carries the *action* half of an ECA rule, so a single-step item such as
`CSB-09-002` ("emit CV to announce the transition") is correct even though a
one-element sequence asserts no order. Likewise a typed precondition with no
`steps` — `RMB-13-001`'s "MUST be in RM Accepted before sending RS" — is the
intended shape, not a format choice half-made. See
[spec-authoring-rules](spec-authoring-rules.md) § "Spec Item Format Is Field
Presence, Not a Class You Pick".

A common anti-pattern: embedding numbered sub-steps inside a `StatementSpec` statement
field (e.g., `M1 (…), M2 (…), M3 (…)` milestone lists, or `(1) do A; (2) do B` handler
sequences). This violates MS-05-001 (no inline prose explanations) and hides start
states, ordering, and terminal conditions from conformance tooling. Extract those steps
into `BehavioralSpec.steps[]` instead.

One caveat when clearing such a hit: an inline `(1) … (2) …` list is sometimes a
genuine *set* rather than a sequence — the three separate top-level trees
`SBT-01-002` requires, one per message-type use case; the assertions one test file
must make — and moving it into `steps[]` would assert an order the requirement
does not have. Reword or suppress those; only convert the ones that really are
ordered.

### Demo scenario groups

Every demo scenario workflow group follows the `BehavioralSpec` pattern
established in `DEMOMA-12`. The group carries
`trigger: {type: scenario_start, value: <scenario-name>}` (per MS-13-003). Individual
items describing ordered protocol exchanges use `BehavioralSpec`; items expressing
terminal-state requirements or infrastructure constraints (`MUST reach final state X`,
`MUST add a CI job`) remain `StatementSpec`.

**The marker is not a formatting convention — it is the registry declaration.**
Since ISSUE-3480, `trigger: {type: scenario_start, value: <name>}` is the *only*
mechanical answer to "which spec groups specify a demo scenario"
(`vultron/metadata/demo_scenarios/scenario_groups.py::scenario_spec_groups()`),
and DEMOCI-11-010's two-register partition is computed from it. So omitting the
marker no longer merely skips a lint rule: it removes the group from the
partition, and the scenario it specifies silently belongs to neither the scenario
registry nor the planned register. Two title-based selection rules were tried and
rejected — see `notes/demo-scenario-registry.md` § "Which spec groups specify a
scenario" so neither is re-proposed.

Since MS-13-004 (CONCERN-1650), `spec-lint` hard-errors when a `scenario_start`
group contains no `BehavioralSpec` item with non-empty `steps`. The
`.github/workflows/spec-check.yml` CI workflow enforces this on every `specs/**`
change. New scenario spec authors should ensure at least one `BehavioralSpec`
item with a non-empty `steps` list is present, or the spec-lint CI check will
fail.

Keep a `steps` block a *projection* of the group's own statements. Its `expected`
and `postconditions` fields are not a place to record a requirement that lives
nowhere else: a state asserted only inside an ECA block is a MUST no other entry
carries, which is the copy-without-an-authority MS-16-002 forbids. Where a block
must name a state its group does not state, cite the check that owns it —
DEMOMA-19-014's postcondition points at the universal Invariant 7 rather than
restating RM closure.

### Protocol behavioral groups

Protocol behavioral groups (RMB, EMB, CSB) are authored in the ECA idiom: the
condition goes in typed `Precondition` fields, and `steps` is reserved for the
cases where the action is itself normative — often a single step, which is the
action and not an ordering claim. See the `cs-behavior.yaml` reference for the
trigger-at-group / ECA-at-item pattern and its precondition types (`rm_state`,
`em_state`, `cs_pattern`, `role`).

Do not read "these groups are behavioral" as "every item in them is a
`BehavioralSpec`". Under ADR-0101 the class follows the fields, and a substantial
minority of CSB and EMB items — bare invariants with none of `preconditions`,
`steps`, or `postconditions` — are `StatementSpec`s. An `isinstance` check over a
CSB or EMB group will not match all of it.
