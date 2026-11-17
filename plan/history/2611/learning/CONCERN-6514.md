---
source: CONCERN-6514
timestamp: '2026-11-16T22:09:59.243795+00:00'
title: 'Epic #6506''s Tasks were cut from a migration that was never inventoried'
type: learning
---

Theme: theme:protocol-correctness — the received-runner migration gets a counted inventory and an ordered plan before more of it is built, so its Tasks stop growing and splitting mid-build.

## Summary

Epic #6506 ("A received handler only builds and runs its tree; every verdict and refusal comes from the tree's nodes") holds Tasks split off #5774 and #5775 during the `work-epic-tasks` run for #5931. Those two were filed as single size-L Tasks, but together they are an architecture migration. Nobody counted the sites first, so each builder found the real size only by reading code. One line of work split four times (#5774 → #6394 → #6476 → #6500 → #6504/#6505), and every size estimate was too small. This Concern blocks the not-yet-started children until the migration is planned.

## Surface Symptom vs. Underlying Problem

The symptom: builders stop before coding and ask for a split, again and again. The underlying problem: three cross-cutting rules each apply to about 50 files, and they were never turned into a counted, ordered plan:

1. protocol refusals live in the tree, never in `execute()`;
2. no received use case calls the store or the bridge;
3. case-scoped nodes read their case from the blackboard port (BTND-01-006).

The target design, ADR-0195 (proposed), was itself written mid-run.

What is correct and should stay: the goal; the runner `run_received_tree` (#6404); declared repeats, no-changes and refusals (#6473); the path-stage doors (#6439, #6437).

## Category

Planning / work decomposition.

## Severity

Medium. Merged work is sound, but the remaining Tasks are cut wrong and keep costing a split round each.

## Evidence

- Split chain and comments on #5774, #6394, #6414, #6476, #6500.
- Builder size estimates versus actual: #6476 B "L" turned out XL three times in a row.

## Impact if Ignored

Each further build costs a stop-and-split round. Issue count grows faster than issues close. Tasks overlap the runner and tree factories, which causes merge conflicts.

## Suggested Action

1. Decide whether ADR-0195 is the accepted target, and amend it if not.
2. Run one automated inventory on main (AST scan) that lists every site for each of the three rules, plus the SL-03-003 logging sites (#6507). Record the counts.
3. Re-cut #6506's open Tasks (#6476, #6494, #6499, #6504, #6505, #6507) from that inventory: sized by count, ordered by dependency, each one reviewable. Fold, retire or re-scope the existing ones as needed.
4. Close this Concern once the re-cut Tasks exist and their order is wired.

---

**Resolved**: 2026-11-16 — planned in PR https://github.com/CERTCC/Vultron/pull/6567, which also closes Concern #6555 (absorbed: the fixed-shape rule reaches every tree).

Decisions (user, planning interview):

- No tree factory and no node constructor takes a per-act value. Every per-act value comes from a named key in one vocabulary. The runner seeds what the event or trigger request carries; a lookup node publishes what only the store holds, and in a received tree its miss is a declared refusal. Each tree declares its input keys, which is its behavior contract.
- Scope is the full migration, not only the trees that learn their case while running.
- The work is calved across four Epics: #6549 (retitled; foundation, shared stages, close-out), #6568 (case trees), #6569 (embargo, report, status and note trees), #6506 (handler side). #2027 moves to Next with a rendering Task.

Inventory on main 6a445ec50: 0 pre-tree refusals; 4 store reads in 2 received modules; 10 post-run reader refusals in 7 files (2 of them move with the fault trees); 327 node classes and 363 factory functions take a per-act value; 90 SL-03-003 ratchet entries in 63 files.

Spec: BTND-01-004 retired (replacement BTND-01-009); BTND-01-008, BTND-01-009, BTND-03-022 and BT-25-006 to BT-25-011 added. ADR-0207 revision 2, ADR-0195 revision 4.
Notes: `notes/bt-integration.md`, `notes/bt-pitfalls.md`.

Implementation issues: #6570, #6571, #6572, #6504, #6505, #6582, #6583, #6593, #3035 (Epic #6549); #6573, #6574, #6575, #6576, #6577, #6585, #6586, #6587, #6590 (Epic #6568); #6578, #6579, #6580, #6581, #6588, #6589, #6591, #6592 (Epic #6569); #6476, #6499, #6494 (Epic #6506); #6584 (Epic #2027). #6507 retired into #6590, #6591 and #6592.
