---
title: "DEMOCI-11-054 names `vultron/demo/` as the base-versus-head job's trigger, but the recorder also reads the compose file, so a conforming job can miss a change that moves every recording"
type: learning
timestamp: "2026-11-09T23:30:00Z"
source: ISSUE-6026
signal: spec-gap
---

## Trigger

You are writing or reviewing the `paths:` filter of a CI job whose requirement
states the trigger as a source directory. Check what the code the job runs
actually reads: a requirement that names the *subject* directory is not a list
of the job's inputs, and a filter copied from the requirement can leave the
check installed and unreachable on a pull-request shape it exists to police.

## Claim

DEMOCI-11-054 obliges the base-versus-head comparison only "on a pull request
that changes a file under `vultron/demo/`". The in-process recorder reads one
input outside that tree: `compare-demo-runs` calls `load_topology()`, which
reads `docker/docker-compose-multi-actor.yml` for each cast slot's URL and
default case roles, and feeds both into every scenario's run (DEMOCI-11-020,
DEMOCI-11-032). A changed slot URL or default role therefore changes what every
scenario records, and a job triggered on exactly the requirement's stated set
would not start. The requirement's trigger is narrower than the set of inputs
its own comparison depends on.

The open question for `learn`: does DEMOCI-11-054's trigger become "a file the
recording depends on", enumerated or derived, or does it stay a named directory
with the compose file added? The second keeps the requirement checkable against
the workflow; the first keeps it true as the recorder grows inputs, but needs a
way to decide the set.

## Evidence

Found by the pre-push review of #6174 (#6026), which named it as the #4506
shape: a `MUST NOT` whose verification could not run. `demo-verdict.yml` now
lists the compose file as a superset of the requirement's trigger, with
`test_it_runs_on_a_pull_request_that_changes_the_demo` asserting it against
`topology.COMPOSE_PATH` rather than a retyped literal. So nothing is broken
today — the requirement is what under-specifies, and a future implementer
reading DEMOCI-11-054 alone would write the narrower filter.

## How to apply

When a requirement states a CI trigger as a path, read the entry point the job
runs and list what it opens. Where the two sets differ, implement the superset
(a wider trigger never violates a stated one) and record the difference, as
this file does, rather than narrowing the job to match the prose.
