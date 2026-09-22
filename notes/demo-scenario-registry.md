---
title: Demo Scenario Registry — Self-Registration, Derived Paths, and the Generate-vs-Check Split
status: active
description: >
  Implementation guidance for the self-registering demo scenario registry
  (ADR-0098): what the decorator carries and what is derived by convention, why
  discovery must walk the package rather than import a list, why
  `.github/demo-scenarios.json` stays committed, which consumers are generated
  versus checked in place, and how the MS-13-003 marker selects the spec groups
  that specify a scenario.
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
  - specs/meta-specifications.yaml
related_notes:
  - notes/demo-ci-invariants.md
  - notes/demo-ci-diagnostics.md
  - notes/demo-ci-scenario-coverage.md
  - notes/demo-future-ideas.md
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
**Built by ISSUE-3451 and ISSUE-3480:** the checks over the remaining
hand-written prose — DEMOCI-06-002/003, the per-scenario DEMOMA-16 requirements,
the `mkdocs.yml` nav, the `notes/` tables, the no-restated-count and
no-stray-include ratchets
(`vultron/metadata/demo_scenarios/prose_checks.py`), and the planned-scenario
register and its partition
(`vultron/metadata/demo_scenarios/scenario_groups.py`, DEMOCI-11-010).
Both halves are reported by `uv run demo-scenarios --check`, so the
`demo-scenarios-sync` hook covers generated and checked consumers alike.

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
expected behaviour is agreed. Several scenarios are in that state at any time.

**Do not register them.** A registered scenario is one whose module exists, and
every derived-path check depends on that. A `status="planned"` field in the
decorator would make the registry the place where both states live and would
immediately need path checks exempted per entry — the override channel the whole
design exists to avoid.

Planned scenarios are declared by their spec group plus the **planned scenario
register** in [demo-future-ideas.md](demo-future-ideas.md) § "Planned scenario
register": one row per specified-but-unbuilt scenario, with the scenario name in
its own column and spelled in the registry's name grammar, its tracking issue,
and its spec IDs. DEMOCI-11-010 requires every spec'd scenario to sit in exactly
one of the two registers, and the partition to be checked.

That register carries the tracking issue and the spec IDs *because
`partition_problems()` fails when a row omits either* — it is not a standing
fact about the file. Before ISSUE-3480 this note asserted it was, and it was not
true: planned scenarios were spread over three tables, their names lived in
Status-column prose rather than a Scenario column, already-implemented scenarios
sat under a "Planned scenarios" heading marked `**implemented**`, and a stale
partial copy of the registry sat in the same file under "Implemented scenarios".
The claim was load-bearing for DEMOCI-11-010 and nothing checked it.

Write the check in both directions. The registry-to-prose direction alone reports
agreement while ignoring DEMOMA-16-014 and DEMOMA-16-015, which describe scenarios
that are *correctly* absent from the registry — the same blind spot that let a `vc`
row sit in a table of available demos with a spec group, a tracking issue, and no
implementation.

## Which spec groups specify a scenario: the MS-13-003 marker

The partition needs a mechanical answer to "which spec groups specify a demo
scenario", and it already has one. **MS-13-003** requires a group whose items
describe a demo scenario workflow to carry
`trigger: {type: scenario_start, value: <name>}`, and **SR-02-018** fixes
`value` as the scenario's name. That is the selector
(`scenario_groups.scenario_spec_groups()`); the marker is a declaration by the
group's author, not an inference from its wording.

Nothing enforced MS-13-003, so half the scenario groups were missing the marker
(DEMOMA-12, -19, -20, -21, -24, -25). Adding it obliges **MS-13-004** —
a `scenario_start` group MUST hold at least one `BehavioralSpec` with non-empty
`steps` — which is why ISSUE-3480 also added step blocks to DEMOMA-19, -20, -21
and -24. Each restates that group's already-normative phase list
(DEMOMA-19-014, -20-007, -21-008) as ordered ECA steps; DEMOMA-24 had no phase
list, so its block on DEMOMA-24-005 derives from DEMOMA-24-001/004/005.

**Two rules were tried and rejected.** Record them here so neither is
re-proposed:

| Rejected rule | Why it fails |
|---|---|
| A `"Scenario"` substring in the group title | Also selects `Scenario Coverage` (DEMOMA-04), `Shared Scenario Harness` (DEMOMA-23), `Causal Gating and Scenario Narratives` (DEMOMA-22) and `In-Process Fuzz Simulation Scenario` (DEMOMA-18), none of which specifies a demo scenario |
| "A group some per-scenario DEMOMA-16 requirement refines" | Selects only DEMOMA-24 and DEMOMA-25. DEMOMA-20 and DEMOMA-21 have no DEMOMA-16 refiner, so it drops half the planned set and the partition check passes vacuously over it |

**The registry may hold a scenario no group specifies.** `fcv-reject` does:
it is built, it is in the PR validation set, and it has a per-scenario
requirement (DEMOMA-16-011) but no DEMOMA group of its own. DEMOCI-11-010
constrains only scenarios that *have* a spec group, so this is not a partition
failure — but it is a corpus gap, tracked as ISSUE-3495. The reverse is never
legitimate: a planned-register row with no spec group is a row nothing specifies,
and `partition_problems()` reports it.

**How the per-scenario DEMOMA-16 requirements are selected.** Not by ID range —
DEMOCI-11-007 warns against it and the corpus proves the warning: DEMOMA-16-008
sits inside the apparent span and is the spec-to-test sync rule, while -014 and
-015 sit outside it and are per-scenario. The rule is what the statement *says*:
it mentions `expected-event-types list` **and** names exactly one scenario as
"the `<name>` scenario". That pair separates the eleven per-scenario
requirements from DEMOMA-16-001 (universal types, names no scenario),
DEMOMA-16-008 (names no scenario) and DEMOMA-16-012/-013 (name FCVCV but are
about event *counts* in the case-actor log, not an expected-event-types list).

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
| `notes/` scenario tables | **check in place** | Their tables interleave hand-written columns (PR-set Rationale, per-scenario event-type coverage) that the registry does not and should not hold — see below for why checking beats generating here |
| `notes/demo-future-ideas.md` planned register | check as the registry's complement | Hand-written; DEMOCI-11-010's second register |
| `.github/workflows/demo-integration.yml` header comment | delete the prose enumeration | It restated both scenario sets in a comment above the code that computes them; nothing is lost by removing it, so there is no copy left to generate or check |
| `specs/` DEMOCI-06-002/003 and the per-scenario DEMOMA-16 requirements | check only | Prose requirements; see below |
| `mkdocs.yml` nav | check completeness | Hand-written short labels |
| Any consumer's prose count | check absence (DEMOCI-11-008) | A count is another copy; the table is the count |

**The `notes/` tables are checked in place, not column-generated.** ADR-0098's
table says "generated columns where derivable", and for these two files that is
not achievable as written: only the `Scenario` column is registry-derived, and a
markdown column cannot be spliced independently of the row it heads. A generator
would have to emit whole rows including the hand-written cells it cannot know, so
adding a scenario would make it write a placeholder row and call the result
"generated". DEMOCI-11-006 and DEMOCI-11-007 — the normative requirements — say
*checked in place* for exactly this case. What the check costs is one edit by the
author who knows the hand-written cells; what it buys is that the file never
holds a cell nobody wrote. The `Spec` column of the required-event-types table is
derivable too, but from the **spec corpus** rather than the registry, so it is
checked against DEMOMA-16 rather than against `ScenarioSpec`.

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
  still hand-wires one `@main.command` block per scenario — the last hand-maintained
  copy of the scenario inventory after ADR-0098. Making the CLI a registry consumer is
  a legitimate follow-on consolidation, not part of ADR-0098; it is specified by
  DEMOCI-11-011 and tracked by CONCERN-3465 (implementation ISSUE-3475). The registry
  it consumes has landed (ISSUE-3450); until the consolidation itself lands a scenario
  can register and still have no CLI sub-command, so keep the CLI in the set-equality
  check — `test_every_scenario_has_a_cli_subcommand` in
  `test/demo_unit/test_scenario_registry.py` asserts every registered name is a
  `vultron-demo` sub-command. The consolidation follows the `ActorSession` model
  (DEMOMA-26): the per-scenario container-URL options are **not** carried by the
  decorator (that would re-open the drift channel DEMOCI-11-001 closes); instead each
  scenario module declares a role Type Object — a frozen `ActorRole`
  (`name`, `url_env`, `default_url`, `has_id`, `id_env`, plus the option's `help`
  label) list under `vultron/demo/helpers/` — that a single command factory in
  `cli.py` consumes, and a ratchet binds that role set to the scenario's `main()`
  signature. The role declaration also subsumes the module's `*_BASE_URL` constants,
  so each role is declared once. The env-var bindings and the `--help` text are ad hoc
  per scenario (the URL options key to physical container slots, not roles — e.g.
  `--c1-url` reads `VULTRON_VENDOR_BASE_URL` in `fccv-handoff` — and each option's help
  string names that slot), which is exactly why they cannot be derived from `name` and
  must be declared; the consolidation reproduces today's bindings and help text
  verbatim (behavior-neutral).
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
