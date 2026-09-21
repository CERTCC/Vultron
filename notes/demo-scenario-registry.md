---
title: Demo Scenario Registry — Self-Registration, Derived Paths, and the Generate-vs-Check Split
status: active
description: >
  Implementation guidance for the self-registering demo scenario registry
  (ADR-0098): what the decorator carries and what is derived by convention, why
  discovery must walk the package rather than import a list, why
  `.github/demo-scenarios.json` stays committed, and which consumers are
  generated versus completeness-checked.
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
related_notes:
  - notes/demo-ci-invariants.md
  - notes/demo-ci-scenario-coverage.md
  - notes/demo-scenario-authoring.md
  - notes/vocabulary-registry.md
  - notes/documentation-strategy.md
---

# Demo Scenario Registry — Self-Registration, Derived Paths, and the Generate-vs-Check Split

The set of demo scenarios is restated by hand in many places with nothing
enforcing agreement. ADR-0098 decided to replace those copies with one
self-registering source: each demo module declares itself, and every table and
the CI matrix derive from it. **None of this is built yet** — the registry and
the generators are tracked by ISSUE-3450, and the checks over the remaining
hand-written prose by ISSUE-3451. This note records the parts a future
implementer or reviewer will get wrong from the ADR alone.

Design rationale and the options rejected: `docs/adr/0098-demo-scenarios-self-register.md`.
Normative requirements: `specs/demo-ci.yaml` DEMOCI-11.

---

## What the decorator carries, and what it must not

The decorator carries only facts the demo module is the authority for:

| Field | Why it cannot be derived |
|---|---|
| `name` | The sub-command spelling; everything else derives from it |
| `label` | Display casing (`FVCV-handoff`, not `fvcv-handoff`) |
| `participants` | Prose: "Finder + Vendor1 → Coordinator + Vendor2" |
| `feature` | Prose: the one-line "notable protocol feature" |
| `in_pr_set` | A coverage-economics judgement; rationale lives in DEMOCI-06-002 |

**Do not add path fields.** All three paths derive from `name`:

```text
vultron/demo/scenario/<name_>_demo.py
test/ci/invariants/test_<name_>_invariants.py
docs/topics/scenarios/<name>.md
```

where `<name_>` is `name` with hyphens replaced by underscores. Every registered
scenario satisfies all three conventions, verified at the time ADR-0098 was
written, as do the paths the specs already mandate for scenarios not yet built
(DEMOMA-20-001, DEMOMA-21-001), so there is no exception list and none should be
introduced. A stored path is a path that can be wrong about itself; a derived path
either resolves or fails a check. That distinction is why the `vc` row was
possible — a hand-written table named a script that did not exist.

If a future scenario genuinely cannot satisfy a convention, change the convention
or rename the file. Adding an override field re-opens the drift channel for every
scenario, not just that one.

## Registration means built; planned scenarios live in the other register

A scenario gets a spec group before anyone writes its demo — that is how its
expected behaviour is agreed. Four scenarios are in that state today: `rcv-embargo`
(DEMOMA-20), `rcvv-embargo` (DEMOMA-21), `fcvd` (DEMOMA-24) and `vc` (DEMOMA-25).

**Do not register them.** A registered scenario is one whose module exists, and
every derived-path check depends on that. A `status="planned"` field in the
decorator would make the registry the place where both states live and would
immediately need path checks exempted per entry — the override channel the whole
design exists to avoid.

Planned scenarios are declared by their spec group plus the table in
[demo-future-ideas.md](demo-future-ideas.md), which already carries the tracking
issue and spec IDs per row. DEMOCI-11-010 requires every spec'd scenario to sit in
exactly one of the two registers, and the partition to be checked.

Write the check in both directions. The registry-to-prose direction alone reports
agreement while ignoring DEMOMA-16-014 and DEMOMA-16-015, which describe scenarios
that are *correctly* absent from the registry — the same blind spot that let a `vc`
row sit in a table of available demos with a spec group, a tracking issue, and no
implementation.

## Discovery must walk the package, never an import list

Import-time registration only sees modules that were imported. A hand-written
import list in the dumper therefore recreates exactly the silent omission the
registry exists to remove: a new demo is written, nobody adds it to the list, and
every generated table is quietly complete-looking and wrong.

Walk the package instead:

```python
for module_info in pkgutil.iter_modules(vultron.demo.scenario.__path__):
    if module_info.name.endswith("_demo"):
        importlib.import_module(f"vultron.demo.scenario.{module_info.name}")
```

Pair it with a test that asserts the registered set equals the `*_demo.py`
modules on disk. Without that test, discovery breaking is indistinguishable from
a scenario being removed — both just produce a shorter table. This is the same
hazard recorded for the AS2 vocabulary registry; see
[vocabulary-registry.md](vocabulary-registry.md).

## Why `.github/demo-scenarios.json` stays committed

It is tempting to delete the JSON and have CI compute the matrix. It cannot: the
`scenarios` job in `.github/workflows/demo-integration.yml` resolves the matrix
with `jq` immediately after `actions/checkout`, in a job with **no Python
environment** — no `setup-python`, no `uv`. Adding one to build the matrix would
put an interpreter setup in front of every demo run.

So the JSON is a **generated, committed artifact**: never hand-edited, kept
honest by `--check` in a pre-commit hook. This is the arrangement
`docs/adr/index.md` already has with `adr-index-sync`.

Two constraints on the generated JSON:

- **Keep the projection narrow** — `demo`, `test_file`, `full_suite_only` only.
  Entries are splatted into `matrix: include:`, so every key becomes a matrix
  variable visible to every step of two jobs.
- **Emit explicit booleans** for `full_suite_only`. The selection filter is
  `select(.full_suite_only == false)`; an omitted field makes a PR-set scenario
  vanish from the matrix rather than error.

The workflow's `paths:` filter still lists the JSON and still fires correctly,
because a registry change regenerates the JSON in the same commit.

## The generate-vs-check split

Not every consumer can hold a generated table, and forcing one to is worse than
checking it. Route each consumer by what it is:

| Consumer | Treatment | Why |
|---|---|---|
| `docs/topics/scenarios/index.md` | build-time render (DEMOCI-11-009) | Inside the mkdocs tree, so `markdown-exec` can call the dumper; no table is committed and drift is impossible |
| `.github/demo-scenarios.json` | generate + `--check` | CI needs it before Python exists |
| `test/ci/README-case-log-ratchet.md` | generate + `--check` | Outside the mkdocs tree — read raw on GitHub and by agents, so an include directive would render literally |
| `vultron/demo/scenario/README.md` | generate + `--check` | Same |
| `notes/` scenario tables | generate derivable columns; check the rest | Their tables interleave hand-written columns (PR-set Rationale, per-scenario event-type coverage) that the registry does not and should not hold |
| `.github/workflows/demo-integration.yml` header comment | delete the prose enumeration | It restates both scenario sets in a comment above the code that computes them; nothing is lost by removing it, so there is no copy left to generate or check |
| `specs/` DEMOCI-06-002/003 and the per-scenario DEMOMA-16 requirements | check only | Prose requirements; see below |
| `mkdocs.yml` nav | check completeness | Hand-written short labels |

**The mkdocs-tree boundary is the load-bearing distinction.** The
`include-markdown` plugin is configured, but it expands only at mkdocs build
time, and nothing in `mkdocs.yml` references `notes/` or `test/ci/`. An
`{% include-markdown %}` directive in either would render as literal text to
every reader. Only `docs/` pages can use the zero-drift treatment.

**Specs keep their prose.** A requirement that defers its content to code is a
weak requirement, and the per-scenario DEMOMA-16 requirements exist so each
scenario has a citable spec ID. Check that the enumerations agree with the
registry; do not rewrite them into pointers. The precedent is
`vultron/metadata/adr/index_gen.py`, which generates `docs/adr/index.md` but only
checks the mkdocs nav, because the nav's labels are hand-written prose.

**Do not select the per-scenario DEMOMA-16 requirements by ID range.** "DEMOMA-16-002
through DEMOMA-16-011" looks like the set and is not: DEMOMA-16-008 inside that
span is the spec↔test sync rule, DEMOMA-16-012 and -013 are FCVCV event-count
requirements, and DEMOMA-16-014 and -015 are per-scenario requirements sitting
outside it. Select by what the requirement is — one scenario's expected
event-type list — not by where its number falls.

## Pitfalls

- **A count restated in prose is another copy.** `test/ci/README-case-log-ratchet.md`
  said "nine" three times in sentences around a nine-row table. Say "the
  scenarios", and let the generated table be the count (MS-16-001).
- **Do not widen the CI invariant command to the directory.** The `_AllSkipGuard`
  in `test/ci/invariants/conftest.py` (DEMOCI-10-005) judges the whole pytest
  session, so it only catches a vacuous green because CI invokes one harness file
  at a time. Non-skipping structural tests in that directory are fine; collecting
  them *together with* a harness defeats the guard.
- **The registry is not the scenario inventory's only reader.** `vultron/demo/cli.py`
  still hand-wires one `@main.command` block per scenario. That is a legitimate
  follow-on consolidation, not part of ADR-0098; until it happens, a scenario can
  register and still have no CLI sub-command, so keep the CLI in the
  set-equality check.
- **Import cost is paid per dumper invocation, not per scenario.** Importing one
  demo module costs roughly two seconds, almost all of it the shared `vultron`
  package import, so importing all of them in one process costs about the same.
  Do not "optimise" this into lazy per-scenario imports and lose whole-package
  discovery.
