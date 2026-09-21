---
status: accepted
date: 2026-09-21
deciders: Vultron maintainers
consulted: Vultron maintainers
informed: Vultron contributors
---

# Demo scenarios self-register at import time; every scenario table and the CI matrix become derived artifacts

## Context and Problem Statement

The set of demo scenarios is restated by hand in at least eight places: the CI
matrix registry (`.github/demo-scenarios.json`), a scenario→harness table in
`test/ci/README-case-log-ratchet.md`, two tables in
`notes/demo-ci-scenario-coverage.md`, one in `notes/demo-ci-invariants.md`, a
sub-command table in `vultron/demo/scenario/README.md`, a narrative index in
`docs/topics/scenarios/index.md`, the `mkdocs.yml` nav, and prose statements in
`specs/demo-ci.yaml` (DEMOCI-06-002, DEMOCI-06-003) and
`specs/multi-actor-demo.yaml` (DEMOMA-16-002 through DEMOMA-16-011). Nothing
enforces agreement between any of them.

They have already drifted. `vultron/demo/scenario/README.md` documents a `vc`
sub-command backed by `vc_demo.py`; that file has never existed in the history of
the repository, is absent from `vultron/demo/cli.py`, and the README row is its
only mention anywhere. A reader following that table runs a command that does not
exist.

This is the third instance of one failure shape. ISSUE-3337 found two tables
mirroring the case-ledger invariant inventory, both stale, and its learning
entry records the rule: sort a mirrored table's columns into ratchetable and
not, keep and ratchet the former, delete the latter. ISSUE-3386 then proposed
ratcheting the scenario→harness table the same way. Applying that rule
scenario-wide raises a prior question — whether these tables should be
*checked* against a source of truth, or *stop being independent copies at all*.

## Decision Drivers

- A table nothing can check is a table nobody does check; an unratcheted doc
  decays into confident wrong answers, not into silence (ISSUE-3337).
- Adding a scenario currently means editing eight-plus places correctly, with no
  failure if one is missed. The cost falls on every future scenario author.
- Per-table ratchets would enforce agreement but leave the editing burden
  intact — eight hand-maintained copies that now fail loudly instead of quietly.
- The GitHub Actions `scenarios` job resolves the matrix with `jq` immediately
  after checkout, in a job with no Python environment, so the CI matrix cannot
  be computed at run time.
- `.github/demo-scenarios.json` entries are splatted directly into
  `matrix: include:`, so every key in that file becomes a matrix variable.

## Considered Options

- Ratchet each table against `.github/demo-scenarios.json`
- A new hand-maintained rich registry file, with tables generated from it
- Scenarios self-register at import time; all tables and the CI matrix derive
  from the registry

## Decision Outcome

Chosen option: **scenarios self-register at import time**, because it removes the
possibility of drift rather than detecting it, and it removes the separate
registry file that the other two options require someone to maintain.

Each demo module declares itself on its own `main()`:

```python
@scenario(
    name="fv",
    label="FV",
    participants="Finder + Vendor",
    feature="Baseline two-actor CVD",
    in_pr_set=True,
)
def main(skip_health_check: bool = False, ...) -> None:
```

The decorator carries only what the demo knows about itself. Every path is
derived by convention from `name` and asserted to resolve:

| Derived | Convention |
|---|---|
| Demo script | `vultron/demo/scenario/<name_>_demo.py` |
| Invariant harness | `test/ci/invariants/test_<name_>_invariants.py` |
| Narrative page | `docs/topics/scenarios/<name>.md` |

(`<name_>` is `name` with hyphens replaced by underscores.) All nine registered
scenarios satisfy all three conventions today, so no path data is carried and no
exception list is needed.

Discovery walks the package with `pkgutil.iter_modules`, **not** a hand-written
import list: auto-registration only sees what is imported, so an import list
would reintroduce the same silent-omission failure this decision removes. This
is the hazard already recorded for the AS2 vocabulary registry
(`notes/vocabulary-registry.md`).

Each consumer is then treated according to what it actually is:

| Consumer | Treatment |
|---|---|
| `docs/topics/scenarios/index.md` | rendered at build time by `markdown-exec`; no table is committed |
| `.github/demo-scenarios.json` | generated; narrow projection of only the keys the CI matrix consumes |
| `test/ci/README-case-log-ratchet.md` | generated between markers |
| `vultron/demo/scenario/README.md` | generated between markers |
| `notes/` scenario tables | generated columns where derivable; completeness-checked where hand-written |
| `specs/` DEMOCI-06-002/003, DEMOMA-16-002…011 | prose retained, consistency-checked |
| `mkdocs.yml` nav | completeness-checked |

Committed generated files are gated by a `--check` mode in a pre-commit hook,
exactly as `docs/adr/index.md` is gated by `adr-index-sync` today.

Two consequences of this split are deliberate and worth stating.

**`.github/demo-scenarios.json` stops being a source of truth and becomes a
derived artifact.** DEMOCI-02-003's rationale currently calls it "the source of
truth for which scenarios run"; that authority moves to the decorators. The file
remains committed — the `scenarios` job has no Python with which to generate it —
and remains in the workflow's `paths:` filter, which still fires correctly
because a registry change regenerates the JSON in the same commit. The
projection stays narrow (`demo`, `test_file`, `full_suite_only`) so the matrix
context gains no new variables.

**Specs keep enumerating scenarios in prose, and are checked rather than
rewritten.** A requirement that defers its content to code is a weak
requirement, and DEMOMA-16-002 through DEMOMA-16-011 exist precisely so each
scenario has a citable spec ID. This mirrors `vultron/metadata/adr/index_gen.py`,
which generates `docs/adr/index.md` but only checks the mkdocs nav for
completeness because the nav's labels are hand-written. Generate what is
derivable; check what is prose.

### Consequences

- Good, because adding a scenario becomes a single edit — writing the demo — and
  omitting a consumer is no longer possible.
- Good, because `docs/topics/scenarios/index.md` becomes incapable of drifting
  rather than merely monitored for it.
- Good, because a registered scenario missing its harness, script, or narrative
  page fails a check, which is the defect class that produced the phantom `vc`
  row.
- Good, because the PR-set membership flag is stated once, next to the demo,
  instead of in five places (README column, notes minimum-set table, workflow
  header comment, DEMOCI-06-002, DEMOCI-06-003).
- Bad, because a generated table cannot be hand-edited for a one-off wording
  fix; the fix must go to the decorator or the renderer.
- Bad, because the dumper imports every demo module, coupling docs builds and the
  pre-commit hook to demo-module import health. Mitigated by those modules being
  import-safe today: module scope holds only `logging.getLogger`,
  `os.environ.get` defaults, and string constants.
- Neutral, because scenario metadata is prose (participants, one-line feature)
  living in Python decorators rather than a data file. This follows
  `vultron/metadata/msm/`, where one data model already feeds many rendered
  tables via `render_page(slug)`.

## Validation

- A test asserts `pkgutil` discovery registers every `*_demo.py` module in
  `vultron/demo/scenario/`, so a new demo that forgets the decorator fails.
- A test asserts each registered scenario's three derived paths resolve on disk.
- The `--check` mode of the dumper, wired as a pre-commit hook, fails when any
  committed generated artifact is stale.
- Consistency tests bind DEMOCI-06-002, DEMOCI-06-003, DEMOMA-16-002…011 and the
  `mkdocs.yml` nav to the registry.

## Pros and Cons of the Options

### Ratchet each table against `.github/demo-scenarios.json`

The shape ISSUE-3386 proposed, applied per table.

- Good, because it is the smallest change and needs no new module.
- Good, because it follows an established in-repo pattern
  (`test/ci/invariants/test_diagnostic_map_sync.py`).
- Bad, because it enforces agreement without reducing the editing burden: eight
  copies still need hand-editing, and a red test is the reward for forgetting
  one.
- Bad, because it cannot catch the phantom `vc` row: that row is in the *demo
  inventory*, a population the CI matrix registry does not describe.

### A new hand-maintained rich registry file

One YAML or Python data file holding label, participants, feature, paths and
flags, with every table generated from it.

- Good, because generation removes drift among the consumers.
- Good, because prose cells stay diffable in one place.
- Bad, because it adds a file that must be kept in step with the demo modules —
  moving the drift boundary rather than removing it, and preserving exactly the
  failure that produced the phantom `vc` row.

### Scenarios self-register at import time

- Good, because the demo module is the only place that can know a demo exists.
- Good, because path conventions mean no path data is stored, so a renamed or
  missing file fails instead of being silently described.
- Bad, because registry contents are only as complete as package discovery;
  `pkgutil` traversal is load-bearing and needs its own test.
- Neutral, because CI-policy data (`in_pr_set`) lives next to the demo rather
  than in CI config. Its rationale stays in DEMOCI-06-002.

## More Information

Source: ISSUE-3386, which proposed the narrower per-table ratchet. The
column-triage rule this decision generalises comes from ISSUE-3337. The phantom
`vc` row is tracked separately.

Prior art in this repository, all of it load-bearing for the design above:
`vultron/metadata/msm/render.py` (one data model, many rendered tables),
`vultron/metadata/adr/index_gen.py` (generate plus check-for-completeness, with a
`--check` pre-commit hook), `docs/reference/messages/*.md` (build-time rendering
via `markdown-exec`), and `vultron/wire/as2/vocab/` (import-time
auto-registration and its discovery hazard).

Generated spec requirements: `demo-ci.yaml` DEMOCI-11.
