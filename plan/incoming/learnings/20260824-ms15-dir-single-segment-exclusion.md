---
title: MS-15 directory check — single-segment forms excluded (2+ segment threshold)
type: learning
timestamp: 2026-08-24
source: ISSUE-2012
signal: design-question
---

The `_SPEC_DIR_RE` regex requires **two or more path segments** (e.g. `vultron/core/`) rather than matching any trailing-slash form (e.g. `devlogs/`). This 2-segment minimum was chosen because single-segment directory refs appear in specs as:

- Runtime output dirs (`devlogs/`) — gitignored, won't exist in CI → false positive
- CI-context refs (`dependabot/` in GitHub Actions prose) — not a filesystem path → false positive
- HTTP endpoint paths with stripped leading slash would otherwise be caught by the absolute-path guard, but single-segment API paths like `demo/` could still appear

Prototype against the live registry confirmed: all 11 missing directory refs with the naive check were single-segment false positives (4× `devlogs/`, 2× `/demo/`, 2× `/trigger/`, 1× `dependabot/`) or multi-segment real stale refs (`vultron/core/behaviors/shared/`, `docs/topics/scenarios/`). The 2-segment threshold produces zero false positives and catches the two real stale refs.

The issue description mentioned "trailing-slash-optional forms" as a sub-decision — implemented as trailing-slash-required (the regex captures the trailing slash) since the directory form is unambiguous with it and the file regex already handles file paths without trailing slashes.
