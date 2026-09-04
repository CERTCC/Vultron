---
title: "process-issue: 120-guard mechanical refactor hit fork agent 200-turn limit"
type: learning
timestamp: 2026-08-31T18:00:00Z
source: ISSUE-2490
signal: theme-candidate
---

The mechanical replacement of 120 `isinstance(VulnerabilityCase)` guards across ~60 files
exhausted the fork agent's 200-turn limit before completion. The agent left 1 guard
remaining (in AGENTS.md documentation — acceptable) and 4 files uncommitted.

**Mitigation**: After the fork stopped, main agent checked the state, found only 1
documentation-only guard remaining, and committed the open files manually. Then fixed
pyright errors in `participant_add.py` and `owner.py` that the fork did not address.

**For future large mechanical refactors**: consider breaking into smaller batches per
subsystem (e.g., behaviors/ first, then use_cases/, then services/) rather than a
single 60-file pass. Or use sed/awk scripts for the mechanical replacement before
running the agent for edge-case handling only.
