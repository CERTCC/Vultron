# Sizing

This file is the single prose definition of the `size:` labels — what the bands
mean, who applies them, and what they are for. The band *values* are not here
either: they live in `vultron/metadata/planning/size_bands.py` and are printed
by the tool below, because a threshold a reader can retype is a threshold that
drifts.

```bash
PYTHONPATH= uv run pr-size --table     # the current bands
PYTHONPATH= uv run pr-size --acs 4     # estimate an Issue from its AC count
PYTHONPATH= uv run pr-size --base origin/main   # measure the current branch
PYTHONPATH= uv run pr-size --calibrate          # re-run the survey (below)
```

## Estimate vs. measurement

Two different questions, deliberately answered by two different inputs.

| | When | Input | Where the label goes |
|---|---|---|---|
| **Estimate** | Issue creation | acceptance-criteria count | the Issue |
| **Measurement** | PR open | diff lines (additions + deletions) | the **PR** |

The measurement is authoritative for the delivered change (PAD-05-003). The
estimate stays on the Issue and is **never overwritten** (PAD-05-010), because
keeping both is what makes estimate-versus-actual a signal anyone can query.
Landing a `size:L` estimate as a `size:XL` PR is worth knowing about.

`size:XL` is measurement-only (PAD-05-012). An Issue predicted to be bigger than
`size:L` should be **decomposed**, not labelled XL — there is no AC count that
reaches the band. XL is a retrospective finding.

Past the `size:L` AC ceiling, `pr-size --acs` prints `decompose` instead of a
label and exits 3 (PAD-05-013). Apply no `size:` label; split the Issue into
smaller ones and estimate each. The rule rests on one figure: an AC costs about
200 diff lines once its tests, specs and docs are counted, so the AC ceilings
predict the same bands the diff ceilings measure.

## Who applies them

- **Estimate**: the skill that writes the acceptance criteria — `plan-issue` and
  `update-plan` — from `pr-size --acs <N>`, and `create-issue` for the Bug and Task
  issues it writes ACs for. Skills that create an Issue *without* ACs have
  nothing to count, so they assign no `size:` label at all and say so
  explicitly: `create-issue` for an Idea or a Concern, and `process-concerns`. Do not
  add one there; an Idea or a Concern gets its estimate when `plan-issue` turns
  it into implementation Tasks.
- **Measurement**: the `pr-size-label` GitHub Actions workflow, on every push to
  every same-repo PR. **Do not set the measured label by hand.** The rule used to
  live in skill prose alone, and it was skipped on a large share of PRs (the
  survey is in the PAD-05-011 rationale); this one is now enforced. A PR from a
  **fork** is the one exception: its
  token is read-only, so the workflow skips it and no label is applied.

For a bundle the measurement is the **whole-PR** diff, not per member — one
bundle is one PR (`bundling.md`).

## What the top band means

`size:XL` does not mean "worse code". Later bug fixes per diff line stay flat
from small PRs through the largest band, so size alone marks no quality break.
It means **this PR will probably need CI repair**: above the XL floor the CI-fix
rate doubles (PAD-05-009; the figures are in the PAD-05-011 rationale).

Two consequences:

1. An XL PR needs a reason. Split it, or say in the PR body why it cannot be
   split.
2. An Issue labelled `size:XL` is **never a bundle member** (PAD-15-011). It is
   refused outright rather than given a weight, because a weight would say "fits
   alongside something smaller" and this band rules exactly that out.

## Apparent optimal size

Aim for `size:M`: a PR in that band delivers a full unit of work without the
CI repair rounds that the XL band brings. Below about 150 lines a PR pays the
full fixed cost of review and CI for very little delivered change. This is
guidance for shaping work, not a gate — nothing rejects a PR for being small.

## Recalibrating

The bands were cut at quantiles of a survey of merged PRs. `pr-size --calibrate
[--days N]` re-runs that survey over the PRs merged in the last N days (default
60) and the Issues they close: each band's share against its target share, the
diff size at each quantile the ceilings were cut at, how often the Issue
estimate matched the measured band, and the median diff per AC count. It reads
GitHub through `gh` and takes a minute or two.

Run it **quarterly**, and **after any workflow change** that could move PR size
(a new review stage, a bundling rule, a change to how Tasks are cut).

Recalibrate the bands when either drift appears:

- **Median lines per AC moves more than about 1.5×** from the last recorded
  figure, either way. The AC rule then estimates a different amount of work than
  the diff bands measure, so estimates land in the wrong band.
- **A band's share moves more than about 10 points** from its target share. Its
  ceiling no longer sits at the quantile it was cut at.

Smaller moves are window noise. Recalibrating means re-cutting the thresholds in
`size_bands.py` and replacing the survey figures, which are stated once, dated,
in the PAD-05-011 rationale (`PYTHONPATH= uv run spec-dump --ids PAD-05-011`).

### Last recorded run

The last run, its date, and the figures to compare a new run against are in the
PAD-05-011 rationale, beside the survey the current bands were cut from. They
are not copied here, so a recalibration updates one place.
