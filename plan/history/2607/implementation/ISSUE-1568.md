---
source: ISSUE-1568
timestamp: '2026-07-21T19:14:44.870456+00:00'
title: relocate legacy bt CVD demo out of vultron/demo
type: implementation
---

## Issue #1568 — ARCH: relocate legacy bt demos out of vultron/demo and add demo→bt import ratchet

Relocated the CVD self-simulation demo from `vultron/demo/vultrabot.py` to
`vultron/bt/base/demo/cvd.py` (joining pacman/robot siblings) and added an AST
ratchet (`test/architecture/test_demo_no_bt_imports.py`) enforcing ARCH-01-006
— `vultron/demo/` MUST NOT import `vultron/bt/**` except the CLI aggregator
(`KNOWN_VIOLATIONS = {vultron/demo/cli.py}`).

Repointed the `vultrabot` and `vultrabot_cvd` console scripts at the relocated
module; `vultrabot` had been broken (pointed at deleted
`vultron/scripts/vultrabot.py`). Made `main(args=None)` self-parse args so
console-script entry points work while preserving the click-CLI Namespace path.
Updated the relocated test import and doc references.

Full suite green (5910 passed); black/flake8/mypy/pyright clean; mkdocs build
succeeds with zero new strict warnings.

PR: <https://github.com/CERTCC/Vultron/pull/1569>
