---
title: Demo Scenario Tree — Path Declarations, Names, the Tree Index, and the Prefix Check
status: active
kind: plan
tracks:
  - "#4727"
  - "#4733"
  - "#4759"
  - "#4747"
  - "#5304"
description: >
  Design for making the demo scenario tree explicit (#4726): branch points
  defined once in a table, each scenario declaring its full path on `@scenario`,
  trigger-only choices, the letter-grammar names and how a rename keeps old
  URLs, the generated tree index the demo UI reads, and the isomorphic
  shared-prefix check over recordings. Records the mapping of today's
  scenarios onto the tree, how integration tests start from named points on it,
  and the Task order.
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
  - specs/testability.yaml
related_notes:
  - notes/demo-scenario-registry.md
  - notes/demo-interactive-ui.md
  - notes/demo-scenario-authoring.md
  - notes/demo-future-ideas.md
relevant_packages:
  - vultron/demo/scenario
  - vultron/metadata/demo_scenarios
  - test/core/use_cases/received
  - ui/src/data
---

# Demo Scenario Tree — Path Declarations, Names, the Tree Index, and the Prefix Check

Vocabulary: the **Demo** section of `CONTEXT.md` (scenario tree, branch point,
choice, ending, scenario, recording). Decision records: ADR-0098 and ADR-0104,
both amended 2026-10-15. Requirements: DEMOCI-11-013 through DEMOCI-11-018.
Parent Epic: #4747.

This is the interim form. Composition (#4733) writes a branching story once and
retires each family's declarations as it lands.

---

## Declaration shape

- **Branch points are defined once, in a table** in the scenario package: the
  deciding role, the presenter prompt ("As the Vendor, choose…"), and the
  choices, each with a label and one trigger (DEMOCI-11-013). The labels live
  nowhere else, so offline and live mode cannot disagree.
- **Each scenario declares its full path** on `@scenario`, as ordered
  (branch point, choice) pairs from the root (DEMOCI-11-014). A
  parent-scenario pointer was rejected: `rv` and `rvv` are siblings, neither a
  prefix of the other.
- **A tree node is identified by its path prefix.** A branch point is a table
  entry that labels one or more nodes: a decision can recur on one path (#2050
  invalidates, then validates), so key nodes by prefix, not by branch point.
- **Every scenario is an ending.** No path may be a strict prefix of another, or
  one scenario would be both an interior node and a leaf.

## Choices are triggers only

Every choice is one trigger POST by the branch point's role, so live mode needs
no client-side action. A presenter can take over any role at any branch point;
the scenario plays the other parties until the next branch point.

- **Other parties act between decisions.** A choice's trigger is the deciding
  role's next trigger on that path, and steps by other roles may run before it
  and after it (DEMOCI-11-013). "Keep the case" is Vendor1 accepting the
  Coordinator's suggestion of Vendor2 (`accept-actor-recommendation`), with
  the suggestion played in between.
- **"Carry on" is the role's next trigger on that path.** `rv`'s choice beside
  "invite another Vendor" is "report the fix ready" (`notify-fix-ready`), not
  "invite nobody". Write the label as what happens.
- **A silent party shows as what the other party does next** ("the Reporter
  publishes unilaterally"), not as a wait.
- **Open consideration:** the silence scenarios (#2053, #2056) may need a
  non-trigger wait or a demo-only clock trigger to show a timeout running out.
  Decide that when one of them is designed, and amend DEMOCI-11-013 then.

## Today's scenarios on one tree

Every path opens with submit, then the receiver's validate and engage. The
default embargo starts at case creation, so embargo terms are a later branch
point, not a root one. Steps in brackets are shared steps, not choices.

```text
Reporter: whom to tell?                (room for "Vendor found it itself": #2591, #3667)
├─ a Vendor → [Vendor validates; Reporter asks, Vendor answers] → Vendor: next?
│   ├─ report the fix ready ................................ rv
│   ├─ invite another Vendor ............................... rvv
│   └─ invite a Coordinator → Vendor1: keep the case?
│       ├─ keep it: accept the Coordinator's suggestion .... rvcv-extension
│       └─ offer ownership to the Coordinator .............. rvcv-handoff
└─ a Coordinator → [Coordinator validates] → Coordinator: invite whom?
    ├─ a Vendor → Vendor: join?
    │   ├─ reject the invite ............................... rcv-reject
    │   └─ accept → Reporter: next?
    │       ├─ propose new embargo terms → Vendor1: next?
    │       │   ├─ propose a revision ...................... rcvv-embargo
    │       │   └─ report the fix ready .................... rcv-embargo
    │       └─ ask the Vendor a question → [Vendor answers] → Coordinator: next?
    │           ├─ invite a second Coordinator ............. rcvcv
    │           └─ carry on: publish after the Vendor's fix  rcv
    └─ a second Coordinator → Coordinator1: keep the case?
        ├─ keep it: accept Coordinator2's suggestion ....... rccv-extension
        └─ offer ownership to Coordinator2 ................. rccv-handoff
```

Today's code does not follow this order everywhere. #4759 moves these steps,
with no pass or fail verdict changed (DEMOMA-17-002):

- `rvv`, `rvcv-extension`, `rvcv-handoff`: the notes exchange moves before the
  invites, so the Vendor's branch point follows it.
- `rcvcv`: the second Coordinator's invite moves after the notes exchange.
- `rcv-embargo`, `rcvv-embargo`: the notes exchange moves after the embargo
  proposal, so the Reporter's choice is between proposing and asking.

The exact prompts, choice labels and triggers are #4759's to write; the shape
above is what the paths must produce.

- **Future scenarios fit as new choices.** Two-reporter, split and merge
  scenarios (#3671, #4243, #4244) add actors and cases mid-path, which is why
  recordings are keyed by actor and case.
- **Open consideration: Vendor self-report** (#2591, #3667). The root branch
  point is the Reporter's, so a Vendor that finds the vul itself is not one of
  its choices. It is either a second root or the Vendor acting as the Reporter;
  decide when that scenario is designed. Its name begins with `v` either way.

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

A generated, committed, drift-tested JSON file under `ui/src/data/`
(DEMOCI-11-016), holding:

- the branch-point table;
- the tree as nested nodes from the root, each choice pointing at a child node
  or an ending;
- one entry per scenario: label, path, and recording files keyed by actor and
  case.

Follow `protocol_states.json`'s conventions for key style and the export entry
point.

## Shared-prefix check

Prove each declared branch the way position-independent code is compared: same
logic, different addresses (DEMOCI-11-017; byte identity once composed is
DEMOCI-11-018).

- Relabel each recording's ids by first appearance, drop timestamps, and require
  equal entries up to the branch point, references between objects included.
- Byte identity is not required yet: siblings seed different actor names,
  container slots and ports (`rccv-handoff` puts Coordinator1 in the vendor
  slot), so ids differ even where logic matches. A composed family tightens to
  byte identity, which then holds by construction.
- The check needs to know where each branch point falls in the ledger. Have the
  scenario report reaching each declared step to the harness, which records the
  ledger tail; composition provides the same boundary for free.
- A real ordering mismatch the check finds is fixed in that Task without
  changing any scenario's pass or fail verdict (DEMOMA-17-002).

## Test starting points

The multi-actor integration tests start from the same tree (TB-15). A **named
starting point** is a declared step on a scenario path: the point the shared-prefix
check already has each scenario report to the harness.

- **Build once, copy per test.** Once per session the harness runs a path up to
  the point, in-process, and saves each actor's store; every test loads its own
  copy (TB-15-001, TB-15-002). Sibling tests that replay the same prefix pay for
  it again and test it again, on every CI run.
- **Seed it like the recordings.** Build with the recordings' seeded id source
  and clock (#3901), so every copy is identical across runs (TB-15-003).
- **Each step is tested once.** The test that moves the case from one starting
  point to the next is the only one that runs that step; every other test runs
  only its own acts.
- **The rebuild check follows the same rule.** It proves a point rebuilds from
  its ledger when the point is built, then replays only each test's own entries
  onto the rebuilt point (TB-15-004, TB-15-005).
- **Finer states are declared steps, not new branch points.** Embargo
  negotiation states the tests need ("Vendor1 proposed a revision", "the
  CASE_MANAGER agreed") are steps on the embargo paths. They add no choice and
  no scenario.
- **A state no story reaches** (a diverged replica, a forced commit failure)
  loads the nearest point and applies the test's own change, rather than building
  a case outside the ledger (TB-15-006).
- **The copy is a SQLite `backup`, not `clone_for_actor`.** `clone_for_actor`
  opens a different actor's empty store. Every in-memory store is named from the
  actor slug (`vultron-<slug>`), so a saved point needs a name of its own, copied
  into each test's freshly named store.
- **Make one act cheap first.** One received act reread the case 90 times (743
  reads of 73 records) and re-read the whole outbox per queued `Announce`
  (`_pending_announce_index`); that per-act cost is paid on every step, starting
  points or not.

## Task order

1. #4759 — the branch-point table, path declarations and registry checks (no
   recordings needed).
2. #4727 — the tree-index exporter and the isomorphic prefix check, after #3901.
3. #4733 — composition, family by family.
4. Test starting points: the per-act read fix first, then the harness, a pilot, and
   one migration per test area (see the issues `tracks:` lists).
