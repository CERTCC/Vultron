---
status: accepted-provisional
date: 2026-11-02
created: 2026-11-02
updated: 2026-11-02
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; issues #3560, #3794, #5545, #5494, #5543, #5544; PR #5502;
  ADR-0006
informed: []
stakeholder_type: [project-contributor]
---

# Publish the Site on a Weekday Schedule From Tags

## Context and Problem Statement

The public site deployed only when a maintainer merged `main` into the `publish` branch.
That merge was a deliberate manual step, and it was skipped for seventeen months: `publish` sat 6,966 commits behind `main`.
A week after the `v2026.10.0` release it was already 570 commits behind again.

How does the site keep up with `main` without a manual step, while never publishing a `main` whose CI is red?

## Decision Drivers

- The site must follow green `main` within a working day, with no person in the loop.
- A red `main` must never publish.
  Push CI on `main` is path-filtered and cancels superseded runs, so "every check on this commit passed" cannot be read per commit.
  The open `ci:main-failure` issues that `notify-failure` keeps per workflow already say "this workflow is red on `main`", and that state carries over path filters.
- What is live must be nameable and restorable, by a tag that nothing moves.
- A tag pushed with the default `GITHUB_TOKEN` starts no other workflow, so the run that tags must also deploy.
- The tag ruleset (#5545) refuses an update, a deletion or a non-fast-forward of a `publish-*` or `v*` tag, but not a creation: a repository ruleset cannot grant the GitHub Actions app a bypass, so restricting creation would block this workflow's own tag push.
  Any account that can push can therefore create a `publish-*` tag.
- The release versioning of ADR-0006 stays unchanged.

## Considered Options

1. **Keep the `publish` branch.** A maintainer merges `main` into `publish`, and each push to `publish` deploys.
2. **Deploy every merge to `main`.** Each push to `main` deploys once CI passes (the first design of PR #5502).
3. **Weekday scheduled publish from tags.** A scheduled job tags the tip of `main` and deploys that tag, gated on the open failure issues; manual runs publish on demand or roll back.

## Decision Outcome

Chosen option: "Weekday scheduled publish from tags", because it is the only option that removes the manual step and still gives each publish a name that cannot move.
Option 1 is the manual step that failed.
Option 2 publishes many times a day, before the slower push workflows on the same commit have finished, and leaves no name for what is live.

The decision has these parts:

- **Schedule.** The publication workflow runs at 06:07 UTC, Monday to Friday, and publishes the tip of `main`.
- **CI gate.** A run does not publish while a blocking workflow has an open `ci:main-failure` issue carrying that workflow's label.
  The blocking workflows are the ones whose failure means `main` is broken: Python application, Demo Integration, Spec Check, UI, Lint Markdown and Actions Lint.
  Scheduled bookkeeping workflows do not block, and neither does the publication workflow itself, which would block its own recovery.
  The list lives in the publication workflow.
  While a blocking workflow's run on `main` is unfinished, on the candidate commit or on one of its ancestors, the gate waits up to one hour, then treats the commit as red.
  The ancestors count because push CI is path-filtered: a docs-only tip starts no Python run, so the run that judges its code can be the one for an earlier commit.
- **When blocked.** The run skips, writes the reason to its run summary, and stays green.
  It never falls back to an older commit: an older commit was either already published or was skipped for a reason of its own.
- **Tag.** Each publish creates one annotated tag `publish-YYYY-MM-DD.N` (UTC date, N from 1 and always present) on the deployed commit, after the deploy succeeds.
  Its message records the trigger (scheduled, manual, manual with the CI gate skipped, rollback) and the actor.
  The newest `publish-*` tag therefore always names what is live.
  Every tag is kept, and nothing moves or deletes one.
  The gate names the tag before the build, because every page's footer prints it (#5544), and the tag job creates exactly that name.
  The deploy and the tag cannot succeed or fail together; when the tag push fails after a deploy, the failure notice says the live site is untagged, and re-running the tag job finds any tag an earlier attempt pushed instead of adding a second.
- **Skip rule.** A scheduled run skips a commit that already has a `publish-*` tag that this workflow made, so the schedule never publishes a commit twice and never undoes a rollback.
  "This workflow made it" means an annotated tag whose tagger is `github-actions[bot]`.
  A tag with any other tagger, or a lightweight tag with no tagger, does not trigger the skip; the run publishes and names the ignored tag in its summary.
  Without the tagger check, a hand-pushed tag on the tip of `main` would silently suppress a publish with no failing check.
  The tagger field is what the tag's author wrote, so the check guards against an accidental tag, not against a push-capable account that sets out to forge one.
- **Manual publish.** A manual run from `main` applies the same CI gate, unless its "skip CI gate" input is set, which the tag message records.
  It does not apply the skip rule: a manual run is a deliberate request, for example to roll forward after a rollback.
  No trigger skips the site's publication checks.
- **Rollback.** A manual run from `main` whose `rollback-to` input names a `publish-*` or `v*` tag redeploys that tag's commit without the CI gate and creates a new `publish-*` tag on it whose message reads "rollback to `<tag>`, by `@user`."
  The run starts from `main`, not from the tag, because a manual run executes the copy of the workflow file stored at the ref it starts from.
  A run from a tag would execute the tag's copy: for every tag made before this decision, a workflow with no gate and no tag step.
  It would also let anyone who can push a tag deploy a commit carrying an edited workflow, since tag creation is unrestricted.
  For the same reason the target commit must be in `main`'s history, so only reviewed content is redeployed.
  The rollback builds and checks the target commit with that commit's own publication checks: a newer record of served URLs names pages the older commit never built.
  A target commit that lacks the local actions its build loads, as the releases up to `v2024.4.3` do, is refused before anything is built.
  Rollback creates a tag; it never moves one.
- **Least privilege.** Building, deploying and tagging run as separate jobs.
  The build runs project code with a read-only token; only the deploy job can deploy, and only the tag job can push.
- **One run at a time.** Scheduled, manual and rollback runs share one concurrency group that never cancels a running publish.
  The tag counter is computed inside it, from the local and the remote tags.
  A hand-made tag can still take the name between the gate and the tag job; the tag job then fails instead of renumbering, since a renumbered tag would not be the one the deployed footer names.
  The group covers the whole run, the gate's wait included, so two runs never interleave their deploy and tag steps.
  GitHub keeps one pending run per group, so a newer queued run replaces an older queued one, which ends as cancelled with no failure notice.
- **Release by promotion.** A formal release is a `v*` tag promoted from a `publish-*` tag, built in a follow-up (#5543).
  The `v*` tags and setuptools-scm's `tag_regex` (ADR-0006) are unchanged; `publish-*` tags match neither `tag_regex` nor `git_describe_command`, so they never change the package version.
- **Retiring `publish`.** No workflow deploys from the `publish` branch.
  The branch itself is retired once a week of scheduled publishes has succeeded (#5494).

### Consequences

- Good, because the site follows green `main` within a working day with no person in the loop.
- Good, because every publish has a name, and a rollback is one manual run.
- Good, because the gate reuses the failure issues the project already keeps, and needs no per-commit reading of path-filtered CI.
- Bad, because a workflow that is red for a reason unrelated to the site, such as a flaky demo, stops publication until its issue closes.
  The manual "skip CI gate" input is the escape.
- Bad, because a merge waits up to a working day, or longer over a weekend, before it is live.
- Neutral, because the tagger check stops an accidental tag, not a deliberate forgery by an account that could already push to `main`.

## Validation

`test/ci/test_publish_gate.py` tests the gate's decisions (blocked, wait-then-skip, already tagged, foreign tag ignored, publish, CI gate skipped, rollback, rollback target off `main`) and the tagging, against real annotated and lightweight tags in a scratch repository.
It also checks the publication workflow's triggers, blocking list, job order and permissions, concurrency group and failure notification.

## More Information

Generated spec requirements: `docs-build-workflow.yaml` DOCBW-06-007 through DOCBW-06-031.
