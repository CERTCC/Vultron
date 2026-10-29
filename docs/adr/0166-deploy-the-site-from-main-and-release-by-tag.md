---
status: accepted-provisional
date: 2026-10-29
created: 2026-10-29
updated: 2026-10-29
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; issue #3560; specs/docs-build-workflow.yaml DOCBW-03-008,
  DOCBW-03-012, DOCBW-06; ADR-0006 (release versioning)
informed: []
stakeholder_type: [project-contributor]
---

# Deploy the Site from Main, and Make a Release Only a Tag

## Context and Problem Statement

The documentation site was deployed only when a pull request from `main` merged into a separate `publish` branch.
That merge was a manual step in each release, so the site went stale whenever nobody remembered it.
Once, `publish` sat thousands of commits behind `main` for more than a year.
Each release then put a large, rarely reviewed batch of pages live at once.
That is the condition in which a withheld page or a dropped URL slips through.

The site already says which build it shows, not which release.
The strict build and the publication checks already gate the deploy itself.

When should the site deploy, and what, if anything, holds a deploy back?

## Decision Drivers

- A step that needs a human to remember it will lapse.
- Each docs change should be checked as it merges, not in a release-sized batch.
- A brake on deploys should be a setting a maintainer can turn on or off, not a branch that changes how the code flows.
- A bad deploy must be easy to roll back.
- Every URL the site has served must keep answering (DOCBW-03-008), so a page's URL must be recorded before it goes live.

## Considered Options

- Deploy from `main` on every merge, gated by the deploy's own build and publication checks
- Deploy from `main` on a schedule (for example, nightly)
- Keep `publish`, and have a bot fast-forward it from `main`
- Keep the per-release merge into `publish`

## Decision Outcome

Chosen option: "Deploy from `main` on every merge", because it is the only option that needs no human step and checks each change as it lands.

- Every merge to `main` deploys the site.
  The deploy builds the site strictly and runs every publication check before it uploads anything.
  A failed check stops the upload, leaves the last good site live, and opens a failure issue.
- Deploys queue; none is cancelled part-way through.
  A burst of merges collapses into the running deploy and the newest queued one.
- A page's URL is due when its pull request merges.
  So every pull request that builds the site must record each page it builds in the committed list of served URLs, and the deploy checks this again for the commit it ships.
- The brake is the hosting environment's deployment rules, not a branch.
  The rules name the branches and tags that may deploy, and can require a reviewer.
  The maintainer decided not to require a reviewer.
- A rollback is a manual deploy run from an earlier release tag.
  That tag's own workflow and checks build that tag's site.
- A release is a tag plus a GitHub Release.
  It no longer moves the site.
- The `publish` branch stays in place for one release cycle as a fallback, and is then retired.

### Consequences

- Good, because the site never drifts from `main`.
- Good, because a docs defect is found at the merge that caused it, not at the next release.
- Good, because a release no longer has a site step to forget.
- Bad, because a content error merged to `main` is live within minutes.
  The environment's reviewer rule is the remedy if that becomes a problem.
- Bad, because every pull request that adds a page must also record its URL.
  The check names the command that does this.
- Neutral, because the site still shows a build, not a release.
  Docs pinned to a release (versioned docs) remain a separate, optional decision.

## Validation

The publication workflow's trigger, its concurrency setting, and the order and reach of its gates are asserted by CI verification tests.
The requirements they verify cite this ADR.

## Pros and Cons of the Options

### Deploy from `main` on every merge

- Good, because no human step can lapse.
- Good, because a broken build shows up on the merge that broke it.
- Bad, because there is no review between merge and live, unless the environment requires one.

### Deploy from `main` on a schedule

- Good, because there are fewer deploys.
- Bad, because a broken build shows up hours after the pull request that caused it, when its author has moved on.

### A bot fast-forwards `publish`

- Neutral, because it deploys as often as the first option.
- Bad, because it adds a moving part that protects nothing: the environment's rules do the braking job better.

### Keep the per-release merge into `publish`

- Good, because a human looks at the site before it ships.
- Bad, because the step lapses, as it did, and each release ships a large batch of unreviewed pages.

## More Information

ADR-0006 governs how releases are versioned.
This ADR does not change it; it only removes the site from what a release does.

Generated spec requirements: `docs-build-workflow.yaml` DOCBW-03-012, DOCBW-06-005.
