---
source: ISSUE-5698-trigger-list
timestamp: '2026-11-05T05:26:30.521731+00:00'
title: The unit workflow fires on composite-action changes, closing the second trigger-list
  family
type: implementation
---

Excursion recorded against #5698, fixed in PR
https://github.com/CERTCC/Vultron/pull/5898.

Found by the pre-review self-check's trigger-list item while verifying the
shell-script portability scan: a check is only installed if the workflow that
runs it fires on the change it polices (DOCBW-03-015, the #4506 shape).

Audit done: every `pull_request` path filter under `.github/workflows/` was
matched against the inputs `test/ci` and `test/metadata` read. Two families had
no path-filtered workflow running pytest on them:

1. Composite actions under `.github/actions/`. The only other job a change
   there triggers is `actions-lint.yml`, which runs actionlint, so
   `test_workflow_failure_notification.py`'s notify-failure assertions
   (CISEC-05-017, CISEC-05-018, CISEC-05-020) and
   `test_site_build_shared_action.py`'s step-order assertions never ran on a
   pull request that edited only an action. Fixed in the same PR by adding
   `.github/actions/**` to both lists.
2. Markdown guarded by a pytest ratchet (root `AGENTS.md`, `notes/*.md`,
   `.agents/**/*.md`). Already tracked by #5708 under Epic #5707.

Everything else a gate reads — `mkdocs.yml`, `specs/*.yaml`, `docker/`,
`.pre-commit-config.yaml`, `**/*.py` — is matched by some path-filtered
workflow.

Placement: both new path tests live in `test/ci/test_python_app_path_filter.py`,
which already owned this workflow's filter, rather than beside the scan they
protect. Its docstring now records one filter entry per defect that found it
(`uv.lock` #3610, shell scripts #5698, composite actions), so the next reader
sees the pattern rather than three unrelated asserts.
