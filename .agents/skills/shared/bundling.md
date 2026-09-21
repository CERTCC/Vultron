# Bundling

A **bundle** is an ordered set of 1–5 open issues worked together in **one PR
that closes every member**. This file is the single definition of what a bundle
is, how one is selected, and how one is executed. `propose-bundle` selects
them; `build`, `bugfix`, and `plan-issue` execute them.

Bundling exists to amortize cost: one context load, one branch, one review
pass. A bundle of unrelated or oversized issues inverts that — it produces a
sprawling PR that is harder to review than the same work split apart, because
the reviewer has to hold several unrelated mental models at once. Two rules
keep the amortization real: a bundle is **homogeneous** (same executing skill,
one shared design idea) and **budgeted** (bounded total effort).

## Selecting a bundle

Selection has two stages. Passing the first does not make an issue a good
bundle member.

**Stage 1 — eligibility.** Can the issue be worked at all? `state == OPEN`, no
assignees, no `stale-claim` label, every `blockedBy` entry `CLOSED`, and
`subIssues.totalCount == 0` (a leaf, not a nested Epic).

**Stage 2 — fit.** Should the issue be in *this* bundle? Run the tool; do not
re-derive its rules by hand:

```bash
bash .agents/skills/shared/query-epic-subissues.sh <EPIC_NUMBER> \
  | PYTHONPATH= uv run bundle-fit [--workflow build|bugfix|plan-issue]
```

`bundle-fit` applies three signals that already exist on every candidate:

| Signal | Rule | Authority |
|---|---|---|
| `issueType` | A bundle is homogeneous by executing skill: Task/Feature → `build`, Bug → `bugfix`, Idea/Concern/Epic → `plan-issue`. Absent `--workflow`, the highest-priority candidate picks it. | `work-issue` routing |
| `Schedule` | Priority tier ordering (Now > Next > Later). A leaf with no tier inherits its Epic's; an explicit leaf tier always wins. `Someday` is never bundled. | PAD-03-001 |
| `size:` labels | Weights `size:S`=1, `size:M`=2, `size:L`=3, unsized=3 (unmeasured, not small). The bundle's total weight is capped at 6. | PAD-05 |

Sub-issue list order is manual drag-order, so it is a **tie-breaker only**,
never the priority signal.

The tool reports every candidate it held back and separates *held back by fit*
(workable, wrong bundle) from *not workable yet* (blocked, assigned,
stale-claim, non-leaf). Both belong in what you show the user.

**Grain is yours, not the tool's.** `bundle-fit` emits coherence *hints*
(shared spec IDs, shared file paths, shared topic labels) and stops there,
because `calve-epics` requires cutting by design grain and warns that cutting
by superficial theme produces plausible-looking but wrong work units. Before
proposing a bundle, state the single design idea its members share **in one
sentence**. If a member needs a different sentence, drop it and say why. If no
sentence covers two members, the Epic itself may need calving.

## Executing a bundle

An executing skill (`build`, `bugfix`, `plan-issue`) accepts one **or more**
issue numbers. Several numbers means one PR, not one issue with the rest
discarded — do not ask the user whether to take only the first.

1. **Verify homogeneity.** Query each member's type. If a member routes to a
   different skill, stop and tell the user which skill it belongs to. Do not
   silently work it or silently drop it.
2. **Claim every member.** The branch is named for the **primary** (first)
   member; the rest are claimed onto that same branch:

   ```bash
   bash .agents/skills/shared/claim-issue.sh <PRIMARY> <prefix> <slug> <OTHERS...>
   ```

3. **Deepen context once** for the shared design idea, then implement each
   member to the same standard it would get alone — its own tests, its own
   acceptance criteria, its own edge cases. A bundle amortizes context, never
   rigor.
4. **Drop a member that does not belong.** If a member turns out to be
   off-grain once you are in the code, unassign it, comment why, and leave it
   out of the PR body. A wrong bundle is corrected, not carried.
5. **One PR.** Put `- Closes #N` at the top of the body, **one line per member,
   in bundle order** (see `pr-body-guide.md`). The Changes section names each
   member's change so a reviewer can map every hunk to a closed issue. Pass the
   primary as `issue_number` to `create-pr`.
6. **Size label** is computed from the whole PR diff (PAD-05-002), not
   per member.
7. **Archive once per member** — `archive-history` takes one entry at a time,
   so call it once for each member, each carrying the same PR URL.

If the bundle cannot be finished, finish the members you can, close only
those, and say plainly which members you left and why. Never close a member
the PR did not deliver.
