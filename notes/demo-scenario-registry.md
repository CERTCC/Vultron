---
title: Demo Scenario Registry — Self-Registration, Derived Paths, and the Generate-vs-Check Split
status: active
kind: guidance
description: >
  Implementation guidance for the self-registering demo scenario registry
  (ADR-0098): what the decorator carries and what is derived by convention, why
  planned scenarios stay out of it, how the MS-13-003 marker selects the spec
  groups that specify a scenario, why discovery must walk the package, why
  `.github/demo-scenarios.json` stays committed, which consumers are generated
  versus checked in place, how the CLI builds its sub-commands from
  `ActorRole` declarations, and the registry's pitfalls.
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
  - specs/meta-specifications.yaml
related_notes:
  - notes/demo-interactive-ui.md
  - notes/demo-scenario-tree.md
  - notes/demo-ci-invariants.md
  - notes/demo-ci-diagnostics.md
  - notes/demo-ci-scenario-coverage.md
  - notes/demo-future-ideas.md
  - notes/demo-scenario-authoring.md
  - notes/vocabulary-registry.md
---

# Demo Scenario Registry — Self-Registration, Derived Paths, and the Generate-vs-Check Split

Each demo module declares itself with `@scenario`
(`vultron/demo/scenario/registry.py`), and every scenario table, the CI matrix
and the CLI derive from that one source (ADR-0098, DEMOCI-11). The renderers,
checks and the `--check`/`--write` dumper live in
`vultron/metadata/demo_scenarios/` (`uv run demo-scenarios`); the
`demo-scenarios-sync` pre-commit hook runs `--check`. This note records what the
ADR alone does not make obvious.

---

## What the decorator carries, and what it must not

The decorator carries only facts the demo module is the authority for: `name`,
`label`, `participants`, `feature` and `in_pr_set`.

**Do not add path fields.** The demo module, the invariant harness and the
narrative page all derive from `name` (hyphens become underscores in file names;
see `registry.py`). A stored path can be wrong about itself; a derived path
either resolves or fails a check (DEMOCI-11-003). If a scenario cannot satisfy a
convention, change the convention or rename the file: an override field re-opens
the drift channel for every scenario.

A scenario's place in the scenario tree, its full path, is the one further
self-known fact the decorator will carry (DEMOCI-11-014). The design is planned
in [demo-scenario-tree.md](demo-scenario-tree.md) and is not built yet.

## Registration means built; planned scenarios live in the other register

A scenario gets a spec group before its demo exists. **Do not register it.** A
registered scenario is one whose module exists, and every derived-path check
depends on that; a `status="planned"` field would need per-entry exemptions.

Planned scenarios go in the planned scenario register in
[demo-future-ideas.md](demo-future-ideas.md) § "Planned scenario register": one
row per specified-but-unbuilt scenario, with the name in its own column in the
registry's name grammar, its tracking issue and its spec IDs.
`partition_problems()` (`scenario_groups.py`) fails a row that omits either, and
DEMOCI-11-010 requires every specified scenario to sit in exactly one register.

## Which spec groups specify a scenario: the MS-13-003 marker

The partition selects scenario groups by the marker MS-13-003 requires:
`trigger: {type: scenario_start, value: <name>}`, with `value` the scenario's
name (SR-02-018). `scenario_spec_groups()` reads it. The marker is the group
author's declaration, so a group without it silently belongs to neither register.

- **MS-13-004 follows:** a `scenario_start` group MUST hold at least one
  `BehavioralSpec` with non-empty `steps`; `spec-lint` fails it otherwise.
- **A `steps` block may not carry a new requirement.** It is a projection of the
  group's own statements. A state asserted only in its `expected` or
  `postconditions` is a MUST with no authority (MS-16-002); where a block must
  name a state its group does not state, cite the check that owns it (as
  DEMOMA-19-014 cites the universal Invariant 7).
- **Do not select by title or by DEMOMA-16 refiners.** A "Scenario" substring
  also matches DEMOMA-04, -18, -22 and -23, none of which specifies a scenario. "A
  group some DEMOMA-16 requirement refines" drops groups no DEMOMA-16 item
  refines, and the partition check then passes vacuously over them.
- **Check both directions.** `test_every_registered_scenario_is_named_by_a_spec_group`
  catches a built scenario with no group; its exception set is empty, and a new
  exception is argued in that constant's comment. A planned-register row with no
  group is never allowed.
- **Select the per-scenario DEMOMA-16 requirements by content, not ID range**
  (DEMOCI-11-007). One is per-scenario when it names an expected-event-types list
  **and** exactly one scenario as "the `<name>` scenario"; IDs inside the apparent
  range are not per-scenario and some outside it are.

## Discovery must walk the package, never an import list

Import-time registration sees only imported modules, so a hand-written import
list recreates the silent omission the registry removes. `discover_scenarios()`
walks `vultron.demo.scenario` with `pkgutil` and imports every `*_demo` module;
use it, not `registered_scenarios()`, wherever completeness matters
(DEMOCI-11-002). A test asserts the registered set equals the `*_demo.py`
modules on disk, because broken discovery otherwise looks like a removed
scenario. The same hazard applies to the AS2 vocabulary registry
([vocabulary-registry.md](vocabulary-registry.md)).

## Why `.github/demo-scenarios.json` stays committed

The `scenarios` job in `.github/workflows/demo-integration.yml` resolves its
matrix with `jq` right after checkout, with no Python environment. So the JSON is
a generated, committed artifact, never hand-edited, kept honest by `--check`.

- **Keep the projection narrow** (`demo`, `test_file`, `full_suite_only`):
  entries are splatted into `matrix: include:`, so every key becomes a variable
  in every step.
- **Emit explicit booleans** for `full_suite_only`: the filter is
  `select(.full_suite_only == false)`, so an omitted field drops a PR-set
  scenario from the matrix instead of erroring.

## The generate-vs-check split

Route each consumer by what it is:

| Consumer | Treatment | Why |
|---|---|---|
| `docs/` pages (`docs/topics/scenarios/index.md`, `docs/tutorials/container_demos.md`) | build-time render (DEMOCI-11-009) | Inside the mkdocs tree, so `markdown-exec` calls the renderer and nothing is committed; mind the link form (below) |
| `.github/demo-scenarios.json` | generate + `--check` | CI needs it before Python exists |
| `test/ci/README-case-log-ratchet.md`, `vultron/demo/scenario/README.md` | generate + `--check` | Outside the mkdocs tree, read raw, so an include directive would render literally |
| `notes/` scenario tables | check in place (DEMOCI-11-006/007) | Rows interleave hand-written columns; a generator would have to write cells nobody wrote |
| `vultron/demo/cli.py` sub-commands | built at import time (DEMOCI-11-011) | No committed copy at all |
| `specs/` DEMOCI-06-002/003 and per-scenario DEMOMA-16 | check only | A requirement keeps its prose so it stays citable |
| `mkdocs.yml` nav | check completeness | Hand-written labels |
| `docs/topics/scenarios/*.md` narrative pages | check page set and frontmatter (DEMOCI-11-012) | Hand-written prose |
| Any consumer's prose count | check absence (DEMOCI-11-008) | A count is another copy; the table is the count |

**Name each column's authority.** In the checked `notes/` tables, `Scenario`
comes from the registry, `Spec` from the spec corpus, `Covered by minimum set`
membership from `in_pr_set`, and the event-type ticks from each harness's
`_XXX_EXPECTED_EVENT_TYPES` constant (read by AST, so the hook never imports a
test module). A column with no named authority goes unratcheted and drifts.

**The mkdocs-tree boundary is load-bearing.** `include-markdown` expands only at
build time and only under `docs/`; in `notes/` or `test/ci/` it renders as
literal text.

**Narrative pages carry no status claim.** `narrative_pages.py` refuses a page
whose stem names no registered scenario (no CI run exercises it) and refuses
`status:` or `maturity:` frontmatter: a page cannot know whether its scenario
passes, and the live answer is the demo-integration workflow (MS-16-002). A
missing page is `missing_derived_paths`'s finding, not this check's.

## The CLI is a registry consumer, and `ActorRole` is what lets it be one

`vultron/demo/cli.py` builds one sub-command per discovered scenario
(DEMOCI-11-011). The options are not derivable from the name: URL options key to
container slots rather than roles (see
[demo-scenario-authoring.md](demo-scenario-authoring.md) § "Docker Compose
Service Names Are Not Actor Names"), and which actors take an id varies by
scenario.

**Do not move option metadata onto `@scenario`.** DEMOCI-11-001 confines the
decorator to facts every derived artifact uses. Each scenario module declares
instead:

- `ROLES: list[ActorRole]` (`vultron/demo/helpers/actor_roles.py`), in `main()`
  parameter order. It also defines the module's `*_BASE_URL` constants, so each
  env-var/default pair is written once.
- `CLI_HELP: str`, the sub-command's `--help` body.

Load-bearing details:

- **Order is stated once, in `role_kwarg_names()`.** The factory and
  `test/architecture/test_scenario_roles_match_main_kwargs.py` both read it; do
  not re-derive it in either.
- **The signature ratchet checks both directions.** A `main()` keyword no role
  declares gets no option, so the scenario silently runs against its fallback
  constant — a working-looking demo pointed at the wrong container.
- **No hand-declared sub-command.** A stray `@main.command(name="rv")` would
  shadow the generated one with every runtime check green;
  `test_no_scenario_subcommand_is_hand_declared` checks the AST, and a sibling
  test asserts `cli.py` imports no `*_demo` module by name.
- **Per-scenario asymmetries are pinned by name** in
  `test/demo_unit/test_scenario_cli_factory.py` § `TestDeclaredDivergences`, so
  "regularising" them fails a test.

## Name order is the canonical order, everywhere

`registered_scenarios()` sorts by `name`, which matches `pkgutil` discovery
order, and every consumer uses that order. PR-set membership reads off the
`Covered by minimum set` column, not position. Do not reintroduce a grouped order
to make the PR set contiguous: the grouping would be a second, unratcheted fact
about the same rows.

## A rendered link is not a MkDocs link

A `[rv](rv.md)` link printed from a `markdown-exec` block is **not** rewritten:
the block renders on a child `Markdown` instance without MkDocs's link
treeprocessor, so the `.md` href 404s on the built site and
`mkdocs build --strict` stays green. The renderer emits built-site URLs (`rv/`),
which assumes `use_directory_urls`; a test pins that assumption.

## Pitfalls

- **A count restated in prose is another copy.** Say "the scenarios" and let the
  table be the count (MS-16-001, DEMOCI-11-008).
- **Do not widen the CI invariant command to the directory.** The
  `_AllSkipGuard` in `test/ci/invariants/conftest.py` (DEMOCI-10-005) judges the
  whole session, so it catches a vacuous green only because CI runs one harness
  file at a time.
- **Do not make imports lazy.** Importing one demo module costs about the same as
  importing all of them (the shared `vultron` import dominates); lazy
  per-scenario imports would lose whole-package discovery.
- **Discovery fails closed.** `discover_scenarios()` raises when a `*_demo`
  module registers nothing, because a short table looks complete.
- **A copy-pasted decorator is caught by module name.** The registry refuses a
  declared `name` that does not match the declaring module's `__module__`
  (skipped for `__main__`, so script runs still work); the derived paths alone
  would still resolve to the copied-from module.
- **Splicing refuses a file with no markers.** Appending would leave two tables
  on one subject, so `--write` also refuses to create a consumer from nothing.
