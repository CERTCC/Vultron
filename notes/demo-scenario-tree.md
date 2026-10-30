---
title: Demo Scenario Tree — Names, Index, Prefix Check, Composition, Starting Points
status: active
kind: plan
tracks:
  - "#4733"
  - "#4747"
  - "#5303"
  - "#5304"
  - "#5344"
  - "#5345"
  - "#5346"
  - "#5347"
  - "#5348"
  - "#5349"
  - "#5533"
  - "#5534"
  - "#5535"
  - "#5536"
  - "#5537"
description: >
  Design for the remaining scenario-tree work (#4726): the letter-grammar names
  and how a rename keeps old URLs, the generated tree index the demo UI reads,
  the isomorphic shared-prefix check over recordings, how integration tests
  start from named points on the tree, how a branching story is written as
  composition on one fixed cast, and the Task order. The branch-point
  table and the `@scenario` path declarations are built; their rules live in
  demo-scenario-registry.md.
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
  - specs/testability.yaml
  - specs/case-proposal.yaml
related_notes:
  - notes/demo-scenario-registry.md
  - notes/demo-interactive-ui.md
  - notes/demo-scenario-authoring.md
  - notes/demo-future-ideas.md
relevant_packages:
  - vultron/demo/scenario
  - vultron/demo/recordings
  - vultron/metadata/demo_scenarios
  - test/core/use_cases/received
  - ui/src/data
---

# Demo Scenario Tree — Names, Index, Prefix Check, Composition, Starting Points

Vocabulary: the **Demo** section of `CONTEXT.md` (scenario tree, branch point,
choice, ending, scenario, recording). Decision records: ADR-0098 and ADR-0104,
both amended 2026-10-15; ADR-0098 amended again 2026-10-30. Requirements:
DEMOCI-11-013 through DEMOCI-11-025.
Parent Epic: #4747.

The `@scenario(path=...)` declarations are the interim form. Composition
(§ "Composition") writes a branching story once and retires each family's
declarations as it lands.

---

## The tree is declared in code

The branch-point table (`vultron/demo/scenario/branch_points.py`) and each
scenario's `@scenario(path=...)` are the tree; `scenario_tree()` in
`registry.py` merges the paths and discovery fails unless every scenario is one
ending (DEMOCI-11-013, DEMOCI-11-014). The declaration rules are in
[demo-scenario-registry.md](demo-scenario-registry.md) § "The path and the
branch-point table". Read the tree there, not from a copy here.

- **Open consideration: silence scenarios** (#2053, #2056) may need a
  non-trigger wait or a demo-only clock trigger to show a timeout running out.
  Decide that when one of them is designed, and amend DEMOCI-11-013 then.
- **Future scenarios fit as new choices.** Two-reporter, split and merge
  scenarios (#3671, #4243, #4244) add actors and cases mid-path, which is why
  recordings are keyed by actor and case.
- **Open consideration: Vendor self-report** (#2591, #3667). The root branch
  point is the Reporter's, so a Vendor that finds the vul itself is not one of
  its choices. It is either a second root or the Vendor acting as the Reporter;
  decide when that scenario is designed. Its name begins with `v` either way.
- **Siblings share logic, not yet bytes.** The steps before a branch point
  must be the same across its siblings, note text and order included. The
  shared-prefix test fails when they drift; fix the order in the scenario
  without changing a verdict (DEMOMA-17-002), then regenerate the recordings.
  A shared step goes in one helper (`reporter_asks_vendor_timeline`,
  `vendor_answers_workaround`), so its siblings cannot drift apart.
- **Regenerate every scenario together.** One seed and one cast mean a run
  draws the same ids in every scenario, so a single fresh recording beside
  stale siblings fails the pairwise check even when nothing drifted.

## Names

Names keep the letter grammar: the leading letters spell the roles that join, in
order, and a suffix names the outcome (DEMOCI-11-015). The letter set is `r`,
`v`, `c` and `d` (Deployer, for `rcvd`), gaining one letter per new role. The
grammar is a convention kept in review, with no check: some joins happen in
scripted steps no choice records (`rcvv-embargo`'s late Vendor2 invite), so a
check would need the recordings, which is more upkeep than demo names are worth.
Path-generated names were rejected: inserting a branch
point upstream would rename every scenario below it, and a name is the stem of
the module, harness, narrative page, `scenario_start` marker and CI entry.

Write the two-party scenario `rv` in lowercase everywhere, labels and prose
included: uppercase `RV` is the Report Valid message shorthand, and the docs
acronym list keeps only that meaning.

A renamed scenario keeps its spec group ID and its old narrative-page URL, via
a `mkdocs-redirects` entry in `mkdocs.yml`. It gets **no sub-command alias**: an
alias table is a second list of names (DEMOCI-11-011), so update the
instructions and docs instead (#4736).

## Tree index

Built: `uv run export-demo-tree` writes `ui/src/data/scenario_tree.json`
(DEMOCI-11-016); its shape is in the exporter's docstring
(`vultron/metadata/demo_scenarios/export_tree.py`). Two rules for work on it:

- **Case keys come from the recordings.** Each recording is listed under the
  `caseId`s its entries carry, so a recording refresh that changes a case id
  needs a re-export too; the `demo-tree-sync` hook and the drift test say so.
- **Choices follow the table's order**, not discovery order, so adding a
  scenario never reorders the siblings the presenter sees.

## Shared-prefix check

Each declared branch is proved the way position-independent code is compared:
same logic, different addresses (DEMOCI-11-017; byte identity once composed is
DEMOCI-11-018). The test is `TestSharedPrefixes` in
`test/demo_unit/test_recordings.py`, over the committed recordings.

- Each recording's ids are relabeled by first appearance and its timestamps
  dropped; the entries must then be equal up to the branch point, references
  between objects included.
- Byte identity is not required yet: siblings still place their shared steps
  by hand, so the order can differ even where the logic matches. The addresses
  no longer can — one cast and one seed (DEMOCI-11-020, DEMOCI-11-025). A
  composed family tightens to byte identity, which then holds by construction;
  name it in `COMPOSED_FAMILIES` (`vultron/demo/recordings/prefix.py`).
- A container slot is not only an address. The proposer's container sets its
  default case roles (CP-01-013), which is why only the three fixed-role slots
  declare any: a case owner holds the same roles in every sibling, or the first
  entry already differs.
- The check reads where each branch point falls from the step marks. A
  scenario calls `harness.reach_step(branch_point, choice, by=actor_id)` where
  it makes the decision, before another role's steps that run ahead of the
  choice's trigger; inside a phase it calls the module-level `reach_step`. A
  shared helper takes a hook instead (`before_answer=step_reporter(...)` on the
  invite chain). The recorder commits the marks as `steps.json` beside each
  recording and refuses a run that leaves a declared step unmarked.
- The harness also checks the `by` actor holds the branch point's role; the
  rule is in [demo-scenario-registry.md](demo-scenario-registry.md) §
  "The path and the branch-point table".

## Composition

A branching story is written once: shared steps up to a branch point, then one
continuation per choice (DEMOCI-11-019, ADR-0098). Rules for the work:

- **Fragments and named prefixes.** A story fragment is one step of a story,
  run against the story's state (the cast's sessions and the case). A named
  prefix is a fixed sequence of fragments and choices that several scenarios
  start with ("the Coordinator invites the Vendor"). Both live in
  `vultron/demo/helpers/`. Name a prefix for every shared stretch: assembling
  siblings from fragments alone lets one of them slip in a step before the
  branch point.
- **A scenario assembles its story.** Its module keeps its name-derived file
  (DEMOCI-11-003) and its `main()`, and states its story as one sequence: a
  named prefix, then `choose(branch point, choice)` items and fragments. The
  whole story reads top to bottom in one file.
- **The path is read off the choices.** The registry derives the path from
  the `choose` items, so the tree index (DEMOCI-11-016) follows the code with
  no new sync step. The runner records each step mark as it passes a `choose`,
  so a composed scenario places no `reach_step` by hand. During migration the
  registry accepts either form; a composed scenario that also declares
  `path=` fails discovery (DEMOCI-11-024).
- **A fragment takes the cast, not a container.** The cast and the tree-wide
  seed are fixed (DEMOCI-11-020, DEMOCI-11-025), so a story fragment is handed
  the cast's sessions and the case, and names no container of its own.
- **Clear process-global registries between runs.** One seed means the second
  scenario in a process redraws the first one's ids, so a runner that plays
  more than one story must reset them — `reset_blackboard()` is the one that
  bit, because py_trees refuses a blackboard client id it already holds.
- **Specs stay whole stories.** Each scenario's spec group and its DEMOMA-16
  list of required semantic types describe the whole story, written by hand,
  so the run is checked against the spec, not against the code. Each group
  names the shared opening its story starts with in one line. Give a shared
  stretch its own spec group only when one change to it must be edited in
  several scenario groups.
- **Verdicts do not move.** Every migration is a consolidation, so no
  scenario's pass or fail may change in it (DEMOMA-17-002). A migrated family
  is named in `COMPOSED_FAMILIES`, which turns on its byte-identity check.

## Test starting points

The multi-actor integration tests start from the same tree (TB-15). A **named
starting point** is a declared step on a scenario path: the point each scenario
reports to the harness with `reach_step` for the shared-prefix check
(DEMOCI-11-017), so the harness that builds a point stops a run there.

- **Build once, copy per test.** Once per session the harness runs a path up to
  the point, in-process, and saves each actor's store; every test loads its own
  copy (TB-15-001, TB-15-002). Sibling tests that replay the same prefix pay for
  it again and test it again, on every CI run.
- **Seed it like the recordings.** Build with the recordings' seeded id source
  and clock (#3901), so every copy is identical across runs (TB-15-003).
- **Each step is tested once.** The test that moves the case from one starting
  point to the next is the only one that runs that step; every other test runs
  only its own acts (TB-15-002).
- **The rebuild check follows the same rule.** It proves a point rebuilds from
  its ledger when the point is built, then replays only each test's own entries
  onto the rebuilt point (TB-15-004, TB-15-005).
- **Finer states are declared steps, not new branch points.** Embargo
  negotiation states the tests need ("Vendor1 proposed a revision", "the
  CASE_MANAGER agreed") are steps on the embargo paths. They add no choice and
  no scenario, so the branch-point table stays the tree's only choices
  (DEMOCI-11-013).
- **A state no story reaches** (a diverged replica, a forced commit failure)
  loads the nearest point and applies the test's own change, rather than building
  a case outside the ledger (TB-15-006).
- **The copy is a SQLite `backup`, not `clone_for_actor`.** `clone_for_actor`
  opens a different actor's empty store. Every in-memory store is named
  `<base>-<slug>` from the configured base and the actor slug (`vultron-<slug>`
  by default), so a saved point needs a name of its own, copied into each test's
  freshly named store (#5345).
- **Make one act cheap first.** In #5344's profile one received act reread the
  case 90 times (743 reads of 73 records); that per-act cost is paid on every
  step, starting points or not. `_pending_announce_index` already reads only
  the outbox rows queued since its last snapshot (#4906).

## Task order

1. Composition, one PR per step, in this order: the story runner, piloted on
   `rcv` and `rcv-reject` (#5533); the rest of the
   "Coordinator invites Vendor" subtree, `rcvcv`, `rcv-embargo` and
   `rcvv-embargo` (#5534); the two-coordinator subtree, `rccv-*` (#5535); the
   vendor-first half, `rv`, `rvv` and `rvcv-*` (#5536); then retiring `path=`
   and hand-placed `reach_step` (#5537).
2. Test starting points: #5344 (one act cheap) and #5345 (the harness, which
   stops a run at a `reach_step` mark), then the pilot #5346, then the
   migrations #5347 and #5348, and last #5349.
