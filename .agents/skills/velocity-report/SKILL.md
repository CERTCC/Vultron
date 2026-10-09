---
name: velocity-report
description: Run the development velocity script and interpret the resulting data to find the story the data is telling. Produces a narrative analysis of issue flow, type composition shifts, discovery vs. delivery balance, and cycle time patterns — suited for sponsor reporting, process retrospectives, or internal review. Use when the user asks for a velocity report, development tempo analysis, project health summary, or "what's the data saying about our progress".
---

# Velocity Report

## Quick start

```bash
uv run python scripts/velocity.py
```

Output lands at `plan/data/velocity.json`. Then interpret it (see below).

## Interpretation workflow

After running the script, load `plan/data/velocity.json` and work through these analytical lenses in order. Each lens produces one or two observations. Collect all observations, then synthesize into a narrative.

### 1. Discovery tempo (Idea + Concern creation rate)

- Are Idea and Concern issues being created at a steady rate, accelerating, or declining?
- A *rising* rate = active discovery phase, team is finding new unknowns
- A *declining* rate = discovery is maturing, specs are hardening
- A *flat* rate = steady-state exploration
- Flag any months where creation rate spikes — what was happening?

### 2. Discovery resolution ratio (closed / created per type)

- For Ideas: ratio < 1.0 means backlog is growing (more discovered than resolved)
- For Concerns: ratio < 1.0 means technical debt is accumulating faster than it's addressed
- Compare Idea vs. Concern ratios — are they in sync or diverging?
- Idea resolution is intentionally slower (Ideas → planning → Tasks); Concern resolution should be faster

### 3. Type composition shift over time

Look at `created_by_month` as a stacked view across all types:

- Is the Bug share *rising* over time? That signals implementation work has started and is producing breakage — a healthy sign for a project transitioning from discovery to execution
- Is the Task share *rising*? Requirements are being converted to concrete work items
- Is Untyped share *falling*? Workflow discipline is improving
- The narrative arc to look for: **Idea/Concern-heavy early → Task/Bug-heavy later**

### 4. Backlog pressure by type (`open_backlog_by_month`)

- Which types are accumulating open issues vs. staying clear?
- A growing Idea backlog = healthy (discovery outpacing planning capacity) OR concerning (ideas never get planned) — context determines which
- A growing Bug backlog = implementation quality pressure
- A growing Epic backlog = structural work is outpacing capacity to decompose

### 5. Cycle time interpretation (`cycle_time_by_type`)

Compare median days to close across types:

- **Bugs** should be fast (same-day to 2 days) — if median > 5 days, implementation is getting stuck
- **Tasks** should be 3–10 days — longer suggests over-scoping
- **Concerns** should be faster than **Ideas** — Concerns are addressed; Ideas need planning cycles
- **Ideas** with long cycle time (>10 days) = healthy planning depth; very short = Ideas being closed without full planning
- **Epics** cycle time reflects decomposition cadence, not implementation

### 6. Throughput balance (`created_by_month` vs `closed_by_month`)

- For each type: is monthly closed ≥ monthly created? If not, what's accumulating?
- Sustained deficit on any type for 2+ months = a process signal worth naming
- Bugs: should roughly balance (bugs fixed ≈ bugs found in a mature phase)
- Ideas: expect deficit during active discovery; surplus signals planning is processing faster than discovering

### 7. Net issues by reason (`net_issues_by_week`, `net_issues_by_month`)

Each row has `closed`, `closed_other`, `opened_<reason>` counts, and `net`
(`closed` minus the `separate-defect`, `debt`, and `deferred` issues opened).
Excursions and Epics are excluded; duplicate and not-planned closures sit in
`closed_other` and do not count toward `net`. Definitions:
`.agents/skills/shared/completeness-doctrine.md` § "Net Issues: Close More Than
You Open".

- Is `net` mostly at or above zero? A run of negative weeks means the backlog is growing.
- Which reason drives the negative weeks? `debt` and `separate-defect` are
  discoveries; the response is to read where they cluster (the `Where:` lines).
- Any nonzero `opened_deferred` is a process defect: name the week and find the PRs.
- Labels start at their adoption date; earlier weeks read as zero opened, not as
  a clean record. Say so rather than treating them as a baseline.
- There is no flag threshold yet. Report the numbers, and once a few weeks exist,
  say what a typical week looks like so a threshold can be chosen with evidence.

## Granularity check: monthly vs. weekly

Monthly buckets smooth over short-term spikes and can reverse conclusions
when viewed at weekly resolution. Before finalizing any observation, ask:
*would this look different week-by-week?*

Common reversals to watch for:

- A month that looks like a "surge" may be two quiet weeks bracketing one
  very active week — the monthly view overstates sustained momentum
- A month that looks "flat" may contain a sharp drop followed by a recovery —
  the monthly view masks a mid-period stall
- Cycle time medians computed monthly can be skewed by a few long-running
  issues that happen to close in the same month — weekly medians expose this

**When the monthly and weekly stories conflict, the weekly view is usually
more accurate.** Monthly conclusions should be treated as provisional until
cross-checked at weekly granularity, especially for:

- Any single-month spike (creation, closure, or cycle time)
- Any apparent trend that spans fewer than three months
- Claims about "acceleration" or "deceleration"

If the script does not yet produce weekly buckets, note this limitation
explicitly in the narrative and flag it as a future improvement.

### 8. Pipeline cost (`pipeline_cost`)

The `pipeline_cost` section is the empirical check for ADR-0126.
It is absent when the script ran with `--no-pipeline-cost`.
It has three sub-keys:

- `per_pr` — one record per merged PR with: `open_to_merge_hours`,
  `ci_runs`, `failed_ci_runs`, `merges_from_main`, `full_suite_runs`,
  `targeted_suite_runs` (last two `null` until #4358 populates the
  `Suite runs:` line in pr-execute's summary review).
- `weekly_pr_cost` — weekly median and total for each numeric field,
  plus `total_full_suite_runs` and `total_targeted_suite_runs`.
- `weekly_main_failures` — failed CI runs on `main` per week.

**What a "CI run" is.** One CI run is one pushed head commit: the set of
workflow runs GitHub started for it. A push that starts seven workflows is one
CI run, not seven. A commit whose runs were all cancelled or skipped is not
counted. A CI run failed when any of its workflows concluded `failure`,
`timed_out`, or `startup_failure`. The same definition applies on `main`: a
bad merge that breaks three workflows is one failed CI run on `main`.

**Analysis lenses for pipeline cost:**

**Open-to-merge time trend** (`open_to_merge_hours`)

- Is the median falling week-over-week since ADR-0126 was put in effect?
- A sustained drop with no corresponding rise in `failed_ci_runs_on_main`
  is the primary positive signal the decision targeted.
- A flat or rising median despite fewer local reruns suggests the bottleneck
  has moved elsewhere (e.g., review latency, PR queue depth).
- `total_open_to_merge_hours` is a sum of durations; read the median, not
  the total.

**CI runs per PR** (`ci_runs`, `failed_ci_runs`)

- `ci_runs` counts pushes that reached CI, so it measures iterations:
  the first push, pr-execute fix commits, and merges from main.
- A high `median_ci_runs` (e.g., > 5) with a low failure share
  suggests the suite is green but PRs required many iterations.
- Compute the failure share as `total_failed_ci_runs / total_ci_runs`
  per week; no field holds the ratio. A rising share signals flaky tests
  or systemic breakage reaching CI, not just local runs.

**Merges from main** (`merges_from_main`)

- Counts merge commits (two or more parents) in the PR whose headline
  names `main`.
- Under ADR-0126 (PAD-18-004), syncs happen only on conflict or file overlap,
  so a `median_merges_from_main` near zero is the expected outcome.
- Any week where `median_merges_from_main` is 2 or more suggests the
  conflict-driven sync rule is triggering often, which is worth investigating.
- This field cannot see the old policy's sync cost. Under the pre-#4358
  PAD-11-002 the branch was rebased, and `create-pr` cherry-picks onto a
  fresh base; neither leaves a merge commit, and a force-push replaces the
  PR's commit list.
  Do not compare post-ADR-0126 values to a pre-ADR-0126 `merges_from_main`
  baseline; read it as a trend from ADR-0126 onward.

**Suite runs** (`total_full_suite_runs`, `total_targeted_suite_runs`)

- These fields are `null` for a PR whose `pr-execute` summary carries no
  `Suite runs:` line — every PR executed before #4358 added it. Do not treat
  `null` as zero — say the data is absent.
- The full count starts at one, for `create-pr`'s first-push run (PAD-18-006),
  so a PR whose fixes all passed the targeted gate reads `1 full`.
- The script takes the line from the PR's latest summary, since the count is
  cumulative (PAD-18-006).
- Once populated: the ratio of `full_suite_runs` to `targeted_suite_runs`
  shows whether the targeted-tests gate (PAD-18-002) is doing its job.
  A high full/targeted ratio means most fix commits still run the full suite,
  which defeats the cost reduction.

**Failed CI runs on main** (`failed_ci_runs_on_main` in `weekly_main_failures`)

This is the field that **falsifies ADR-0126**.
A material rise in `failed_ci_runs_on_main` alongside a fall in
`open_to_merge_hours` means the time was saved by moving failures onto `main`
rather than catching them pre-merge — the trade was mispriced.
"Material rise" has no fixed threshold yet; report the absolute numbers and
flag any week with more than one failure on `main` for human review.
Every workflow on `main` counts, including non-test ones such as the docs
deploy; before attributing a failure to a semantic conflict, check which
workflow failed.
Once three months of data exist, set a rolling-average baseline.

#### Integrated read: the ADR-0126 trade

The decision accepted rare semantic-conflict failures on `main` in exchange for
eliminating per-PR full reruns and merge-from-main loops.
The data supports the decision when all of the following hold:

1. `median_open_to_merge_hours` is falling.
2. `failed_ci_runs_on_main` stays near zero week over week.
3. `median_merges_from_main` stays low and is not rising from ADR-0126 onward.
   The pre-ADR-0126 sync cost (captured in Concern #4015 at
   `plan/history/2610/learning/CONCERN-4015.md`) was paid in rebases, which
   this field cannot see; compare against that write-up, not against this
   field's pre-ADR values.

If `failed_ci_runs_on_main` rises materially while `open_to_merge_hours`
falls, report this explicitly: "The time saving appears real, but the
semantic-conflict risk is materializing — consider the merge queue (Idea #1863)."

## Synthesis

After working through the lenses, write a narrative with:

1. **Phase characterization** — where is the project in its arc right now? (active discovery / transitioning / execution-heavy)
2. **Healthy signals** — 2–3 specific data points that show the process is working
3. **Tension points** — 1–2 patterns that deserve attention (not necessarily problems)
4. **One sentence for sponsors** — what does this data say about the nature and pace of the work?

## Example observations from 2026-05 to 2026-07 data

- Idea creation: 14 → 34 → 45/month — accelerating discovery, not converging
- Concern creation: 22 → 28 → 41/month — technical debt awareness growing in parallel
- Bug creation: 34 (May spike) → 7 → 17 — May spike likely from initial implementation; stabilizing
- Idea cycle time median 10 days vs. Concern 1 day — Ideas are going through planning cycles; Concerns are quick-resolving
- Task creation 16 → 38 → 55/month — delivery work is ramping up alongside discovery (healthy dual-track)
- Concern resolution ratio June: 40 closed / 28 created = 1.43 — team caught up with Concern backlog in June

These are examples; run the script fresh and re-analyze — the data changes weekly.
