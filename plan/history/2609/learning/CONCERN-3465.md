---
source: CONCERN-3465
timestamp: '2026-09-21T18:16:45.326772+00:00'
title: Demo CLI hand-wires a click block per scenario
type: learning
---

## Summary

`vultron/demo/cli.py` declares one `@main.command` block per scenario demo, each
~80 lines of click options that differ only in which container URLs the scenario
takes. Nine such blocks account for most of the file's 1300 lines. After #3450
this is the **only** remaining place a scenario must be declared a second time.

## Surface symptom vs. underlying problem

The surface reading is "that file is long and repetitive" — a tidiness
complaint, easy to deprioritise. The underlying problem is that it is a second
declaration point for the scenario set, which is the exact defect class ADR-0098
set out to remove. #3450 made the `@scenario` decorator the sole declaration
point for the CI matrix, the scenario tables and the narrative index, so a
scenario now cannot be missing from any of those. It can still be missing from
the CLI — and the CLI is how a human runs it. A registered scenario with no
sub-command is a scenario nobody can invoke.

What is already correct and should be left alone: the registry's decision to
carry no path fields, and the derived-path conventions. This is not a request to
add CLI data to the decorator. The scenario-specific part of each block is the
set of container-URL options, which is genuinely per-scenario.

## Category / Severity

Duplication / debt, with a correctness edge (a scenario can be unreachable).
Low: #3450 added `test_every_scenario_has_a_cli_subcommand`, so an omission
fails a test rather than being discovered by a human typing a command that does
not exist. That test is what makes this debt rather than a bug.

## Resolution

**Resolved**: 2026-09-21 — implementation tracked in #3475 (blocked on the
registry landing, #3450 / PR #3464).

The plan follows the `ActorSession` (DEMOMA-26) consolidation model: a frozen
`ActorRole` Type Object (`name`, `url_env`, `default_url`, `has_id`, `id_env`)
declared per scenario module and consumed by a single command factory in
`cli.py` that iterates `registered_scenarios()`; the nine hand-wired blocks are
deleted (no shims). A ratchet binds each scenario's role set to its `main()`
signature. The env-var bindings are ad hoc per scenario (they key to physical
container slots, not roles — e.g. `--c1-url` reads `VULTRON_VENDOR_BASE_URL` in
`fccv-handoff`), which is why they cannot derive from `name` and must be
declared; the refactor reproduces today's bindings verbatim (behavior-neutral).

Docs PR: <https://github.com/CERTCC/Vultron/pull/3474>.
Spec: `specs/demo-ci.yaml` (DEMOCI-11-011).
Notes: `notes/demo-scenario-registry.md`.
