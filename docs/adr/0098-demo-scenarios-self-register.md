---
status: accepted
date: 2026-09-22
deciders: Vultron maintainers
consulted: Vultron maintainers
informed: Vultron contributors
stakeholder_type: [project-contributor]
---

# Demo scenarios self-register at import time; every scenario table and the CI matrix become derived artifacts

## Context and Problem Statement

The set of demo scenarios is restated by hand in all of the following places: the
CI matrix registry (`.github/demo-scenarios.json`), a scenario→harness table in
`test/ci/README-case-log-ratchet.md`, two tables in
`notes/demo-ci-scenario-coverage.md`, one in `notes/demo-ci-invariants.md`, a
sub-command table in `vultron/demo/scenario/README.md`, a narrative index in
`docs/topics/scenarios/index.md`, the `mkdocs.yml` nav, the header comment of
`.github/workflows/demo-integration.yml` (which names both the PR set and the
full set in prose), and prose statements in `specs/demo-ci.yaml` (DEMOCI-06-002,
DEMOCI-06-003) and `specs/multi-actor-demo.yaml` (one requirement per scenario in
the DEMOMA-16 group). Nothing enforces agreement between any of them.

They have already disagreed. `vultron/demo/scenario/README.md` lists a `vc`
sub-command backed by `vc_demo.py` in a table headed "Available scenario demos".
That file has never existed in the repository and is absent from
`vultron/demo/cli.py`, so a reader following the table runs a command that does
not exist — but the row was not a typo or a stale leftover. It was added
deliberately, in the same commit that added the VC scenario's spec group
(DEMOMA-25), as forward documentation of work that is specified, tracked by an
open issue, and not yet built. The defect is that a table of *available* demos
was the place it landed, and that nothing could tell the difference between a
scenario that exists and one that is merely intended.

That distinction is the one a registry must make, and it generalises. ISSUE-3337
found two tables mirroring the case-ledger invariant inventory, both stale, and
its learning entry records the rule: sort a mirrored table's columns into
ratchetable and not, keep and ratchet the former, delete the latter. ISSUE-3386
then proposed ratcheting the scenario→harness table the same way. Applying that
rule scenario-wide raises a prior question — whether these tables should be
*checked* against a source of truth, or *stop being independent copies at all*.

## Decision Drivers

- A table nothing can check is a table nobody does check; an unratcheted doc
  decays into confident wrong answers, not into silence (ISSUE-3337).
- Adding a scenario currently means editing every one of those places correctly,
  with no failure if one is missed. The cost falls on every future scenario
  author.
- Per-table ratchets would enforce agreement but leave the editing burden
  intact — the same hand-maintained copies, now failing loudly instead of
  quietly.
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

(`<name_>` is `name` with hyphens replaced by underscores.) Every registered
scenario satisfies all three conventions today, as do the paths the specs already
mandate for scenarios not yet built (DEMOMA-20-001, DEMOMA-21-001), so no path
data is carried and no exception list is needed.

Discovery walks the package with `pkgutil.iter_modules`, **not** a hand-written
import list: auto-registration only sees what is imported, so an import list
would reintroduce the same silent-omission failure this decision removes. This
is the hazard already recorded for the AS2 vocabulary registry
(`notes/vocabulary-registry.md`).

**Registration means built.** Specifying a scenario before building it is normal
— the spec group is how its expected behaviour is agreed before anyone writes the
demo, and four scenarios are in that state today (DEMOMA-20 `rcv-embargo`,
DEMOMA-21 `rcvv-embargo`, DEMOMA-24 `fcvd`, DEMOMA-25 `vc`). None of them may be
registered: a registered scenario is one whose module exists, and the derived-path
checks depend on that being true. Those scenarios are declared instead by their
spec group plus the planned-scenario register in `notes/demo-future-ideas.md`,
which carries the scenario name, the tracking issue and the spec IDs in their own
columns for each. Every scenario with a spec group sits in exactly one of the two,
and the partition is checked (DEMOCI-11-010).

That partition, not the registry alone, is what closes the defect this decision
started from. The `vc` row was a scenario in the second state rendered as though
it were in the first, and no check could tell the difference.

Each consumer is then treated according to what it actually is. The routing below
is a summary for the reader of this decision; **`specs/demo-ci.yaml` DEMOCI-11 is
the authority**, and each row names the requirement that owns it rather than
restating its terms — a table here that paraphrased them would be a second copy
with no test able to say which was current (MS-16-002), which is exactly how the
`notes/` row below drifted before ISSUE-3451 corrected it.

| Consumer | Treatment | Owned by |
|---|---|---|
| `docs/topics/scenarios/index.md` | rendered at build time by `markdown-exec`; no table is committed | DEMOCI-11-009 |
| `.github/demo-scenarios.json` | generated; narrow projection of only the keys the CI matrix consumes | DEMOCI-11-004 |
| `test/ci/README-case-log-ratchet.md` | generated between markers | DEMOCI-11-005 |
| `vultron/demo/scenario/README.md` | generated between markers | DEMOCI-11-005 |
| `notes/` scenario tables | checked in place, not column-generated | DEMOCI-11-006, DEMOCI-11-007 |
| `notes/demo-future-ideas.md` planned register | hand-written; checked as the complement of the registry | DEMOCI-11-010 |
| `.github/workflows/demo-integration.yml` header comment | the prose enumeration is deleted in favour of the code below it; no copy survives to check | DEMOCI-11-008 |
| `specs/` DEMOCI-06-002/003 and the per-scenario DEMOMA-16 requirements | prose retained, consistency-checked | DEMOCI-11-007 |
| `mkdocs.yml` nav | completeness-checked | DEMOCI-11-007 |

**Why the `notes/` tables are checked rather than column-generated.** Only their
`Scenario` column is registry-derived, and a markdown column cannot be spliced
independently of the row it heads: a generator would have to emit whole rows
including the hand-written cells it cannot know, so adding a scenario would make it
write a placeholder row and call that "generated". DEMOCI-11-006 states the
generate-or-check disjunction for exactly this case. Because the check asserts the
column *equals* the registry in registry order, no row can be added, dropped,
misspelled or reordered without failing.

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
requirement, and the per-scenario DEMOMA-16 requirements exist precisely so each
scenario has a citable spec ID. (Those requirements are not a contiguous ID
range: DEMOMA-16-008 is the spec↔test sync rule, DEMOMA-16-012 and -013 are
FCVCV event-count requirements, and the per-scenario requirements for scenarios
not yet built are DEMOMA-16-014 and -015. A check must select them by what they
are, not by a numeric span.) This mirrors `vultron/metadata/adr/index_gen.py`,
which generates `docs/adr/index.md` but only checks the mkdocs nav for
completeness because the nav's labels are hand-written. Generate what is
derivable; check what is prose.

### Consequences

- Good, because adding a scenario becomes a single edit — writing the demo — and
  omitting a consumer is no longer possible.
- Good, because `docs/topics/scenarios/index.md` becomes incapable of drifting
  rather than merely monitored for it.
- Good, because a registered scenario missing its harness, script, or narrative
  page fails a check, which is the defect class the `vc` row belonged to.
- Good, because "specified but not yet built" becomes a state a scenario can be
  in explicitly, checked as the complement of the registry rather than left to
  whichever table someone wrote it into (DEMOCI-11-010).
- Good, because the PR-set membership flag is stated once, next to the demo,
  rather than separately in the README column, the notes minimum-set table, the
  workflow header comment, DEMOCI-06-002 and DEMOCI-06-003.
- Bad, because a generated table cannot be hand-edited for a one-off wording
  fix; the fix must go to the decorator or the renderer.
- Bad, because the dumper imports every demo module, coupling docs builds and the
  pre-commit hook to demo-module import health. Mitigated by those modules having
  no import-time side effects today — module scope holds only logger acquisition,
  environment-variable defaults, constants, aliases, and the `__main__` guard.
- Neutral, because scenario metadata is prose (participants, one-line feature)
  living in Python decorators rather than a data file. This follows
  `vultron/metadata/msm/`, where one data model already feeds many rendered
  tables via `render_page(slug)`.

## Validation

- A test asserts `pkgutil` discovery registers every `*_demo.py` module in
  `vultron/demo/scenario/`, so a new demo that forgets the decorator fails.
- A test asserts each registered scenario's three derived paths resolve on disk.
- A test asserts the scenarios named by scenario spec groups partition exactly
  into the registered set and the planned register, so a specified scenario can
  be neither silently missing nor described as available before it exists.
- The `--check` mode of the dumper, wired as a pre-commit hook, fails when any
  committed generated artifact is stale.
- Consistency tests bind DEMOCI-06-002, DEMOCI-06-003, the per-scenario DEMOMA-16
  requirements and the `mkdocs.yml` nav to the registry.

## Pros and Cons of the Options

### Ratchet each table against `.github/demo-scenarios.json`

The shape ISSUE-3386 proposed, applied per table.

- Good, because it is the smallest change and needs no new module.
- Good, because it follows an established in-repo pattern
  (`test/ci/invariants/test_diagnostic_map_sync.py`).
- Bad, because it enforces agreement without reducing the editing burden: every
  copy still needs hand-editing, and a red test is the reward for forgetting
  one.
- Bad, because it cannot catch the `vc` row: that row is in the *demo
  inventory*, a population the CI matrix registry does not describe.

### A new hand-maintained rich registry file

One YAML or Python data file holding label, participants, feature, paths and
flags, with every table generated from it.

- Good, because generation removes drift among the consumers.
- Good, because prose cells stay diffable in one place.
- Bad, because it adds a file that must be kept in step with the demo modules —
  moving the drift boundary rather than removing it, and preserving exactly the
  failure the `vc` row belonged to.

### Scenarios self-register at import time

- Good, because the demo module is the only place that can know a demo exists.
- Good, because path conventions mean no path data is stored, so a renamed or
  missing file fails instead of being silently described.
- Bad, because registry contents are only as complete as package discovery;
  `pkgutil` traversal is load-bearing and needs its own test.
- Neutral, because CI-policy data (`in_pr_set`) lives next to the demo rather
  than in CI config. Its rationale stays in DEMOCI-06-002.

## More Information

**Revised in place when the checks were built (ISSUE-3451, ISSUE-3480).** The
decision is unchanged; two statements in the body were not accurate and have been
corrected rather than appended to, per
[Revising vs. amending an ADR](index.md#revising-vs-amending-an-adr).

- The consumer table's `notes/` row read "generated columns where derivable". It
  now reads "checked in place", which is what DEMOCI-11-006 and DEMOCI-11-007 —
  the normative requirements — always said; the table row was the looser
  statement, and the implementation is what surfaced the gap.
- The Decision section asserted that `notes/demo-future-ideas.md` "already carries
  the tracking issue and spec IDs for each". **It did not.** There was no single
  planned register, planned scenario names lived in Status-column prose, and
  implemented scenarios sat under a "Planned scenarios" heading marked
  `**implemented**`. ISSUE-3480 built the register the partition check needs, and
  the sentence now describes what exists. Recorded rather than silently fixed
  because DEMOCI-11-010 was written on that premise.

The selector the partition check uses is **MS-13-003's** existing marker,
`trigger: {type: scenario_start, value: <name>}`, rather than anything new: see
`notes/demo-scenario-registry.md` § "Which spec groups specify a scenario" for
the two rules that were tried and rejected.

Source: ISSUE-3386, which proposed the narrower per-table ratchet. The
column-triage rule this decision generalises comes from ISSUE-3337. The `vc` row
this decision's Context section describes was removed in the PR that recorded
this ADR; the VC scenario it documented remains specified by DEMOMA-25 and
DEMOMA-16-015 and tracked by ISSUE-2591, and is listed among the planned
scenarios in `notes/demo-future-ideas.md`.

Prior art in this repository, all of it load-bearing for the design above:
`vultron/metadata/msm/render.py` (one data model, many rendered tables),
`vultron/metadata/adr/index_gen.py` (generate plus check-for-completeness, with a
`--check` pre-commit hook), `docs/reference/messages/*.md` (build-time rendering
via `markdown-exec`), and `vultron/wire/as2/vocab/` (import-time
auto-registration and its discovery hazard).

Generated spec requirements: `demo-ci.yaml` DEMOCI-11.
