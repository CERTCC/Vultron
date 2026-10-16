---
title: Demo Scenario Tree — Path Declarations, Names, the Tree Index, and the Prefix Check
status: active
kind: plan
tracks:
  - "#4727"
  - "#4733"
  - "#4736"
  - "#4759"
  - "#4747"
description: >
  Design for making the demo scenario tree explicit (#4726): branch points
  defined once in a table, each scenario declaring its full path on `@scenario`,
  trigger-only choices, the letter-grammar names with Finder renamed to
  Reporter, the generated tree index the demo UI reads, and the isomorphic
  shared-prefix check over recordings. Records the mapping of today's
  scenarios onto the tree and the Task order.
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
related_notes:
  - notes/demo-scenario-registry.md
  - notes/demo-interactive-ui.md
  - notes/demo-scenario-authoring.md
  - notes/demo-future-ideas.md
relevant_packages:
  - vultron/demo/scenario
  - vultron/metadata/demo_scenarios
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
  parent-scenario pointer was rejected: `fv` and `fvv` are siblings, neither a
  prefix of the other.
- **A tree node is identified by its path prefix.** A branch point is a table
  entry that labels one or more nodes: a decision can recur on one path (#2050
  invalidates, then validates), so key nodes by prefix, not by branch point.
- **Every scenario is an ending.** No path may be a strict prefix of another, or
  one scenario would be both an interior node and a leaf.

## Choices are triggers only

Every choice is one trigger POST by the branch point's role, so live mode needs
no client-side action.

- **"Carry on" is the next trigger that path calls.** `fv`'s choice beside
  "invite another vendor" is "start on the fix" (`notify-fix-ready`), not
  "invite nobody". Write the label as what happens.
- **A silent party shows as what the other party does next** ("the Reporter
  publishes unilaterally"), not as a wait.
- **Open consideration:** the silence scenarios (#2053, #2056) may need a
  non-trigger wait or a demo-only clock trigger to show a timeout running out.
  Decide that when one of them is designed, and amend DEMOCI-11-013 then.

## Today's scenarios on one tree

The order follows the code: every path opens with submit, then the receiver's
validate and engage. The default embargo starts at case creation, so embargo
terms are a later branch point, not a root one. Names are shown after the
Finder → Reporter rename.

```text
Reporter: whom to tell?                    (room for "Vendor found it itself": #2591, #3667)
├─ a Vendor → Vendor validates → Vendor: next?
│   ├─ start on the fix ......................................... rv
│   ├─ invite another Vendor .................................... rvv
│   └─ invite a Coordinator → Vendor1: keep the case?
│       ├─ keep it (Coordinator suggests Vendor2) ............... rvcv-extension
│       └─ offer ownership to the Coordinator ................... rvcv-handoff
└─ a Coordinator → Coordinator validates → Coordinator: invite whom?
    ├─ a Vendor → Vendor: join?
    │   ├─ reject the invite .................................... rcv-reject
    │   └─ accept → Coordinator: next?
    │       ├─ invite a second Coordinator ...................... rcvcv
    │       └─ carry on → Reporter: embargo terms?
    │           ├─ keep the default ............................. rcv
    │           └─ propose new terms → next?
    │               ├─ Coordinator terminates the embargo ....... rcv-embargo
    │               └─ Vendor1 proposes a revision .............. rcvv-embargo
    └─ a second Coordinator → Coordinator1: keep the case?
        ├─ keep it (Coordinator2 suggests a Vendor) ............. rccv-extension
        └─ offer ownership to Coordinator2 ...................... rccv-handoff
```

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
`v`, `c` and `d` (Deployer, for `fcvd`), gaining one letter per new role. A
check compares the
letters with the path. Path-generated names were rejected: inserting a branch
point upstream would rename every scenario below it, and a name is the stem of
the module, harness, narrative page, `scenario_start` marker and CI entry.

Rename plan (#4736), one PR, before the declarations land:

- `f` becomes `r` in every name; spec group IDs stay, titles and markers change.
- Actor names and the reporter's container-URL variable become Reporter.
- Old narrative-page URLs get `mkdocs-redirects` entries.
- **No sub-command aliases.** An alias table is a second list of names
  (DEMOCI-11-011); update the instructions and docs instead.

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
  container slots and ports (`fccv-handoff` puts Coordinator1 in the vendor
  slot), so ids differ even where logic matches. A composed family tightens to
  byte identity, which then holds by construction.
- The check needs to know where each branch point falls in the ledger. Have the
  scenario report reaching each declared step to the harness, which records the
  ledger tail; composition provides the same boundary for free.
- A real ordering mismatch the check finds is fixed in that Task without
  changing any scenario's pass or fail verdict (DEMOMA-17-002).

## Task order

1. #4736 — Finder → Reporter rename (no longer waits on #2677).
2. #4759 — the branch-point table, path declarations and registry checks (no
   recordings needed).
3. #4727 — the tree-index exporter and the isomorphic prefix check, after #3901.
4. #4733 — composition, family by family.
