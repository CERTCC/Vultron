---
title: Demo Scenario Tree — Names, the Tree Index, the Prefix Check, and Test Starting Points
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
description: >
  Design for the remaining scenario-tree work (#4726): the letter-grammar names
  and how a rename keeps old URLs, the generated tree index the demo UI reads,
  the isomorphic shared-prefix check over recordings, how integration tests
  start from named points on the tree, and the Task order. The branch-point
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

# Demo Scenario Tree — Names, the Tree Index, the Prefix Check, and Test Starting Points

Vocabulary: the **Demo** section of `CONTEXT.md` (scenario tree, branch point,
choice, ending, scenario, recording). Decision records: ADR-0098 and ADR-0104,
both amended 2026-10-15. Requirements: DEMOCI-11-013 through DEMOCI-11-018.
Parent Epic: #4747.

This is the interim form. Composition (#4733) writes a branching story once and
retires each family's declarations as it lands.

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
- Byte identity is not required yet: siblings seed different actor ids,
  container slots and ports (`rcvcv` seeds named actor ids, its siblings UUIDs),
  so ids differ even where logic matches. A composed family tightens to byte
  identity, which then holds by construction; name it in `COMPOSED_FAMILIES`
  (`vultron/demo/recordings/prefix.py`).
- A container slot is not only an address. The proposer's container sets its
  default case roles (CP-01-013), so a case owner must run in the same slot
  as in its siblings, or the first entry already differs.
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

1. #4733 — composition, family by family.
2. Test starting points: #5344 (one act cheap) and #5345 (the harness, which
   stops a run at a `reach_step` mark), then the pilot #5346, then the
   migrations #5347 and #5348, and last #5349.
