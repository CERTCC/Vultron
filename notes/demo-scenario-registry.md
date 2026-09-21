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
  - notes/demo-ci-diagnostics.md
  - notes/demo-ci-scenario-coverage.md
  - notes/demo-scenario-authoring.md
  - notes/vocabulary-registry.md
  - notes/documentation-strategy.md
---

# Demo Scenario Registry — Self-Registration, Derived Paths, and the Generate-vs-Check Split

The set of demo scenarios was restated by hand in many places with nothing
enforcing agreement. ADR-0098 decided to replace those copies with one
self-registering source: each demo module declares itself, and every table and
the CI matrix derive from it. This note records the parts a future implementer or
reviewer will get wrong from the ADR alone.

**Built by ISSUE-3450:** the registry
(`vultron/demo/scenario/registry.py` — the `@scenario` decorator, `ScenarioSpec`
and `pkgutil` discovery), the renderers and the `--check`/`--write` dumper
(`vultron/metadata/demo_scenarios/`, console script `uv run demo-scenarios`),
the `demo-scenarios-sync` pre-commit hook, and the three generated consumers.
**Still pending (ISSUE-3451):** the completeness checks over the remaining
hand-written prose — DEMOCI-06-002/003, the per-scenario DEMOMA-16 requirements,
the `mkdocs.yml` nav, the `notes/` tables, and the planned-scenario partition
(DEMOCI-11-010).

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
| `docs/topics/scenarios/index.md` | build-time render (DEMOCI-11-009) | Inside the mkdocs tree, so `markdown-exec` can call the renderer; no table is committed and drift is impossible. Mind the link form — see above |
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

## Name order is the canonical order, everywhere

The registry is one sequence and the consumers previously had three different
ones: the narrative index read pedagogically (FV, FVV, FCV, …), the harness table
put the PR set first, and the sub-command table followed neither. Only one can
survive generation, so `registered_scenarios()` sorts by `name` and every
consumer takes that order. It is not a taste call — it is the one ordering rule no
consumer has to agree to, and it happens to match `pkgutil` discovery order, so
registration order and render order cannot diverge.

PR-set membership therefore reads off the `In PR set` column rather than off
position. Do not reintroduce a grouped order to make the PR set contiguous: the
grouping would then be a second, unratcheted fact about the same rows.

## A rendered link is not a MkDocs link

`docs/topics/scenarios/index.md` renders its table from an exec block, and a
`[FV](fv.md)` target printed from one **does not get rewritten**. MkDocs rewrites
relative `.md` links with a treeprocessor registered on its own `Markdown`
instance; `markdown-exec` converts the block's output on a *child* instance built
from the parent's extensions, which does not include that treeprocessor. The
`.md` href survives into the built HTML and 404s.

`mkdocs build --strict` does not catch it, because it never saw the link as an
internal one to validate — so the page builds green and every row is broken. The
renderer emits built-site URLs (`fv/`) instead, which assumes
`use_directory_urls`; that assumption is pinned by a test rather than a comment,
because flipping the setting would break every link without failing the build.

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
  set-equality check — `test_every_scenario_has_a_cli_subcommand` in
  `test/demo_unit/test_scenario_registry.py` asserts every registered name is a
  `vultron-demo` sub-command.
- **Import cost is paid per dumper invocation, not per scenario.** Importing one
  demo module costs roughly two seconds, almost all of it the shared `vultron`
  package import, so importing all of them in one process costs about the same.
  Do not "optimise" this into lazy per-scenario imports and lose whole-package
  discovery.
- **Discovery fails closed, and that is the whole point.**
  `discover_scenarios()` raises when a discovered `*_demo` module registered
  nothing, rather than returning a short tuple. A generator that quietly omits a
  scenario emits a table that looks complete — the exact defect class ADR-0098
  exists to remove — so the failure has to happen at generation time, not only in
  a test.
- **A copy-pasted decorator is the one drift no path check sees.** Copy
  `@scenario(name="fv", …)` into `fvv_demo.py` and all three derived paths still
  resolve, because they point at the module it was copied *from*. The registry
  therefore compares the declared `name` against the declaring module's
  `__module__` and refuses a mismatch. That check is skipped when `__module__` is
  not in the scenario package, so running a demo as a script (`__main__`) still
  works.
- **Splicing refuses a file with no markers.** Appending the table instead would
  leave the stale copy above the new one — two tables on one subject, which is
  what this mechanism exists to prevent. The markdown consumers are mostly
  hand-written prose, so `--write` also refuses to create one from nothing.
