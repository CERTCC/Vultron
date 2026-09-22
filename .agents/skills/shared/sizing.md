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

## Who applies them

- **Estimate**: the skill that creates the Issue (`plan-issue`, `update-plan`,
  `new-item`), from `pr-size --acs <N>`.
- **Measurement**: the `pr-size-label` GitHub Actions workflow, on every push to
  every PR. **Do not set the measured label by hand.** The rule used to live in
  skill prose alone, and a survey of 692 PRs merged 2026-07-22..2026-09-22 found
  40% of them carrying no `size:` label and `size:S` applied correctly 24% of the
  time. Prose-only rules degrade at that rate; this one is now enforced.

For a bundle the measurement is the **whole-PR** diff, not per member — one
bundle is one PR (`bundling.md`).

## What the top band means

`size:XL` does not mean "big". It means **review probably did not cover this**.

Across the surveyed window, review findings held steady at roughly 4.5 per 1000
diff lines from 200 lines through 1000, then fell to 3.5 (1000–1499), 2.7
(1500–2499) and 1.5 (2500+). True defect density does not drop threefold in
large PRs, so the falling detection rate is review saturation, not cleaner code.
CI-fix rate roughly doubles across the same boundary, and median time-open jumps
from under two hours to over eleven.

Two consequences:

1. An XL PR needs a reason. Split it, or say in the PR body why it cannot be
   split.
2. An Issue labelled `size:XL` is **never a bundle member** (PAD-15-011). It is
   refused outright rather than given a weight, because a weight would say "fits
   alongside something smaller" and this band rules exactly that out.

## Apparent optimal size

Roughly **300–800 diff lines**, with a ceiling near 1000. Below ~150 lines a PR
pays the full fixed cost of review and CI for very little delivered change;
above ~1000 detection quality degrades and elapsed time jumps an order of
magnitude. This is guidance for shaping work, not a gate — nothing rejects a PR
for being small.
