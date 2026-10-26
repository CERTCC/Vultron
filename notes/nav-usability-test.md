---
title: Nav Usability Test — Running It, When to Rerun, and the Current Verdict
status: active
kind: guidance
description: >
  How to run the agent usability test that gates a navigation change
  (ADR-0136): the committed personas and tasks, the two stages, the scoring
  and pass rule, the rerun policy, and the verdict on the tabbed nav.
related_notes:
  - notes/site-information-architecture.md
related_specs:
  - specs/diataxis-requirements.yaml
---

# Nav Usability Test

ADR-0136 gates a navigation change on an agent usability test: the proposed
nav passes when it is no worse than `main`'s nav on task success and no task
stalls at the home page. The essentials are in
[site-information-architecture.md](site-information-architecture.md)
§ "Validation". This note is how to run it, and the verdict it last gave.

## The suite is fixed before the proposed nav is seen

`notes/nav-usability/suite.yaml` holds five personas, each with explicit "you
don't know X" constraints, and their tasks. Each lookup task names every page
that answers it; a thread task's destination is its persona's start page.
`load_suite` refuses a persona with no thread task, so every persona keeps
one (ADR-0136 § Validation).

Edit the suite only when no proposed nav is under test, and commit it before
the run that uses it. A task written while the proposed tree is in view gets
written to fit it. Destinations are page paths, never nav labels, so a task
survives any nav change that keeps its pages.

## Running it

All commands are `uv run nav-usability …` (`vultron/metadata/docs/nav_usability.py`).

1. **Tree test (Stage 1).** `prompt --persona P [--config X]` prints the
   briefing: the persona, the label tree with no paths, and the persona's
   tasks. Give it to a fresh agent of a smaller model with no other context
   and no tools beyond reading that one file; it answers with a label path per
   task, or gives up. `score` resolves each path and appends the result to a
   results file, refusing a file recorded for a different nav hash.
2. **Walkthrough (Stage 2).** Only for tasks the two navs score differently,
   or that fail on either. Build each site, then drive one session per task
   with `walk --start SITE`, `walk --go N`, and `walk --found` or
   `walk --give-up`. The walker shows page text and numbered links only: no
   search, a click budget of eight, and giving up is an outcome.
3. **Tally.** `tally --baseline B --proposed P [--stage 1|2]` applies the pass
   rule and exits non-zero on a fail.

Give the agent a label path, not a node number: an agent reading the briefing
through a line-numbered viewer answers with the file's line numbers. Answers
may prefix the site name or skip a level; the earlier labels only locate the
entry.

Scoring:

| Outcome | Meaning |
|---|---|
| `success` | the chosen entry opens a destination page |
| `near` | the chosen entry is a group holding a destination; counts as a miss |
| `fail` | anything else |
| `gave-up` | no answer; counts as a miss |

A miss that ends at a top-level page with no children (the home page, or the
CERT/CC link) is a **stall at the home page**, which fails the nav outright.

## Cost controls

- Results are keyed on the hash of `mkdocs.yml`'s nav, in
  `notes/nav-usability/results-*.yaml`. Reuse the baseline file until `main`'s
  nav changes.
- Start with one run per pairing; add runs (`score --run 2`) only where the two
  navs disagree. The tally averages runs per task.

## Rerun policy (guidance, not CI)

Rerun only on a structural nav change: tabs or second-level groups added,
removed, renamed or reordered, or a page moving between tabs. A single rename
or move needs only the tree test; a new top level needs both stages.

## What it cannot show

An agent catches a nav that cannot work; it cannot show that a person finds one
natural, and agents guess jargon better than people do. A human cold read stays
an open goal (ADR-0102, ADR-0136).

## Current verdict

<!-- Filled in by the run that gates #4684. -->
