---
source: NOTES-devcontainer-tooling--never-run-pyright-beside-pytest-n-auto
timestamp: '2026-11-06T23:46:27.716279+00:00'
title: 'Retired: never run pyright beside pytest -n auto (no local gate runs pyright)'
type: note
---

Retired because no local gate can produce the collision this section warned
about. PAD-18-027 forbids a local gate from running pyright at all — CI's
`lint-pyright` job owns it, and the required `CI gate` refuses a merge until
it is green — and PAD-18-008 forbids a gate before a first push from running
the full unit or integration suites. So the two commands that had to be kept
apart are no longer both local.

The part of the advice that still holds has a home: the per-host heavy-check
lock, in the same note's section "Run Every Heavy Local Check Through the
Per-Host Lock", still caps how many heavy local runs share a host, and the
timeout-trip signature it describes is in
`notes/testing-pitfalls.md`.

Superseded by: specs/parallel-development.yaml PAD-18-027 and PAD-18-008
(ADR-0179), implemented in `.agents/skills/run-linters/SKILL.md`,
`.agents/skills/create-pr/SKILL.md`, `.agents/skills/pr-execute/SKILL.md` and
`vultron/metadata/planning/ci_mirror/_registry.py`. Delivered by #5949.

---

## Never Run `pyright` Beside `pytest -n auto`

Run the slow linters and the suites one at a time. A whole-tree `pyright` and an
`-n auto` suite together exhaust the container's memory: `pyright` exits 247 with
no output, and — the part that costs time — the suite's markdown-rendering and
AST-scanning tests trip `pytest-timeout` and report as failures. A timeout trip
with no assertion in its traceback, in a test that does not touch the diff, is
the signature; re-run that test alone before believing it (#3156). The
per-host lock (below) caps how many heavy runs share the host; it does not
stop one agent running both at once, so still run them in turn.
