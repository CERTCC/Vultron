---
title: Large "migrate every node" tasks split type-first, not domain-first, for homogeneous PRs
type: learning
timestamp: "2026-07-31T00:00:00+00:00"
source: ISSUE-1809
signal: process-issue
---

Issue #1809 ("Migrate remaining core/behaviors/ BT nodes to typed py_trees
Ports") was claimed under `build` but proved to be a genuine size:L that could not be a
single coherent PR: ~130 node classes / ~243 `register_key` sites across ~40
files. Per the build workflow Phase 4 (more than one prerequisite / non-trivial
work → decompose and stop), I split it into a blocked-by chain of 5 child Tasks
(#1883 → #1884 → #1885 → #1886 → #1887) and left #1809 as the umbrella parent,
blocked by all five.

**The key decision — partition by node *shape* (type) first, domain only to
balance size.** The user's directive: "each PR should be 'a whole lot of the
same thing' rather than 'a whole lot of different things.'" Classifying nodes by
shape yielded clean, near-uniform buckets:

- **Type A — trivial reparent** (~97): only inherited `datalayer`/`actor_id`
  ports; migration is base-class swap + delete boilerplate. Split across two
  tasks by domain (case/status/note/misc; report/embargo) purely for size.
- **Type B — read-only extra inputs** (~63): add `input_ports()` +
  `get_input()`.
- **Type C — WRITE/handoff** (~46): the convention-establishing task. The #1808
  pilot's `output_ports()` always returns `{}`, so there was **no established
  pattern** for a typed output port whose blackboard key is execution-scoped
  (`{noun}_{id_segment}`, BTND-03-004). That is a design decision, not a
  mechanical edit — it must be resolved once, up front, and the remaining
  Type-C nodes follow it. This is where #1809's AC-3 actually lives.
- **Type D — non-DataLayer + finalize** (~40): `_InboxNode` family, bare
  `Behaviour` gates, and composites (explicitly exempt); folds in the
  "migration complete" doc close-out (#1809 AC-4).

**Why type-first beats domain-first here:** a domain-first split (one task per
`case/`/`sync/`/…) would have forced each task to independently re-derive the
Type-C output-port convention, risking divergent conventions and re-litigating
AC-3 in every PR. Type-first isolates the one hard design question into a single
task (#1886) that all handoff-key work depends on, and makes every other PR a
mechanical, uniform sweep.

**How to apply:** When a "migrate/convert every X" task is claimed and X spans
multiple structural shapes with one hard shape and several trivial ones, split
by shape first so the hard shape's design decision is made once and the trivial
shapes become homogeneous reviewable sweeps. Chain them blocked-by when the
partitions edit overlapping files. See `notes/py-trees-ports-adoption.md` for
the recipe the trivial shapes follow.

**Promoted**: 2026-07-31 — captured in `AGENTS.md` (large migration tasks: partition by node shape pitfall).
Docs PR: TBD.
