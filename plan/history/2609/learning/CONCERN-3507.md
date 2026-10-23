---
source: CONCERN-3507
timestamp: '2026-09-22T15:55:52.683003+00:00'
title: Skill validation commands hide a killed pytest run behind tee | tail
type: learning
---

The validation commands in the `build` and `create-pr` skills pipe pytest through
`tee` into `tail -5`. Two things go wrong: (1) the shell reports the exit status of
`tail`, not of `pytest` — a killed run reports success; (2) the pass/fail summary
line does not reach the log when the run is killed mid-stream. Both bit during #3504.
Fix: redirect to file then read exit code separately:
`uv run pytest ... > /tmp/pytest.log 2>&1; echo "exit: $?"; tail -5 /tmp/pytest.log`.
Sites: `build/SKILL.md` Phase 6, `create-pr/SKILL.md` Phase 3, `run-tests/SKILL.md`,
and `AGENTS.md` Agent Quickstart.

**Resolved**: 2026-09-22 — implementation tracked in #3518.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3517>.
