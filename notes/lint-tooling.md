---
title: Lint Tooling Policy — Ruff Configuration, Exclusions, and Baselining
status: active
description: >
  How the Python lint and format gate is configured and why: ruff as the single
  linter and formatter, family-level `select` with a short annotated `ignore`,
  and `RUF100` as the mechanism that keeps baselined findings from becoming
  permanent. Records what belongs in an `ignore` entry, how to tighten the
  ruleset, which pitfalls the flake8-era setup left behind, and how the commit
  loop changed when ruff replaced it.
related_specs:
  - specs/tech-stack.yaml
  - specs/code-style.yaml
  - specs/structured-logging.yaml
  - specs/behavior-tree-node-design.yaml
related_notes:
  - notes/devcontainer-tooling.md
  - notes/ci-workflow-authoring.md
  - notes/structured-logging.md
---

# Lint Tooling Policy — Ruff Configuration, Exclusions, and Baselining

Ruff is the sole Python linter and formatter (IMPLTS-07-017). `mypy` and
`pyright` remain separate type-checking jobs. Black, flake8 and isort are retired
by ADR-0094 and MUST NOT be reintroduced alongside ruff — leaving a superseded
linter in place as a fallback recreates the duplicate-gate problem that decision
removed (the config-level form of the shim CS-15-001 prohibits for code symbols).

ADR-0094 is the decision record and holds the measurements: the timing
comparison, the per-rule finding counts behind each exclusion, and the rejected
options. This note holds the operating policy. Counts are deliberately absent
here (MS-16-001) — read them from the ADR, where they carry a measurement date.

## Invoke with no path arguments

Every caller that acts as a **gate** — a CI job, an agent skill, or a
documented developer command — MUST run exactly these, with **no paths**:

```bash
uv run ruff check          # or --fix
uv run ruff format         # or --check
```

The pre-commit hook is the one caller that passes paths, and it does not choose
them: pre-commit appends the staged filenames, and `force-exclude = true` (below)
makes ruff apply the config's exclusions to them, so the hook's scope is still
the config's. Its `entry` names no path of its own.

Scope lives in the config, never in the invocation (**IMPLTS-07-021**). This is
not a style preference — a scope expressed as arguments is duplicated at every
call site and drifts, and ADR-0094 records two drifts that are live in the tree
today: one tool formats the whole repository while another lints two
directories, leaving code formatted but never linted; and two skills disagree
about how much of the tree to type-check, so some pull requests check less than
commits do. `pyright` has no such problem, because `pyrightconfig.json` declares
its own scope and every caller invokes it bare. `mypy` is scoped by `.mypy.ini`
the same way — a bare `uv run mypy` is the correct form, and any invocation that
names a package is narrowing the gate by accident.

When you change scope, verify with:

```bash
uv run ruff check --show-files > /tmp/ruff-files-after.txt
```

and diff that list against the one from before the change. **Not**
`--show-settings`. See the two silent failures below for why.

## Two scoping mechanisms that fail silently

Both were found by measuring a config that read correctly. Expect no error
message from either.

**`lint.exclude` needs glob form.** `exclude = ["scripts"]` under
`[tool.ruff.lint]` resolves — `--show-settings` prints it back — and does
nothing. A bare directory name only prunes traversal in the discovery-time
top-level `exclude`; `lint.exclude` is matched against each file's full path, so
it needs `"scripts/**"`. This is why `--show-files` is the verification and
`--show-settings` is not: the latter confirms ruff *parsed* your exclusion, not
that it *applied* it.

**`ruff format` formats Python embedded in Markdown.** Unscoped, no-args
`ruff format` reaches far beyond the Python tree because it processes fenced
Python in `.md`. That includes `plan/history/`, which is append-only and
immutable once merged (HM-01-005) — the same failure as bug #2952, where a
markdown auto-fixer rewrote write-once history entries. It also reaches `docs/`,
which has its own style gate (DF-09-001), and the hard-linked `.agents/` and
`.claude/` skill trees. Black never touched Markdown, so
`[tool.ruff.format] exclude = ["**/*.md"]` is what keeps the formatter swap
faithful. Do not remove it without re-reading #2952.

**`force-exclude = true` is required.** Ruff normally lints a file named
explicitly on the command line even when the config excludes it. Pre-commit
passes staged filenames, so without this flag the hook and the CI job disagree
about scope — the exact drift this whole section exists to prevent.

`force-exclude` applies the config's `exclude` patterns only, **not**
`.gitignore`. Discovery (`respect-gitignore`, the default) skips gitignored
paths, but a file named on the command line is linted even when it is ignored.
So a file force-added under a gitignored directory (`git add -f devlogs/x.py`)
is linted by the hook and skipped by the CI job. No tracked Python file is
gitignored today — `git ls-files -ci --exclude-standard` lists any that are —
and the fix, if one appears, is to move it or name its path in `exclude`, not
to turn `respect-gitignore` off.

## The shape of the configuration

Everything belongs in `[tool.ruff]` in `pyproject.toml`. Four settings carry
obligations forward from the tools ruff replaces, and changing any of them silently
breaks a requirement:

| Setting | Carries |
|---|---|
| `line-length` | the `[tool.black]` value it replaces; keeps lint and format agreed |
| `target-version` | IMPLTS-01-001, the Python floor |
| `[tool.ruff.lint.mccabe] max-complexity` | IMPLTS-07-008, the complexity gate, formerly in `.flake8` |
| `per-file-ignores` for `__init__.py` | the `.flake8` re-export exemption |

`per-file-ignores` also holds a few **permanent** exemptions, each justified in
the comment beside it: `S311` (non-cryptographic `random`) for the `vultron/bt/`
simulator, the demo fuzzers and `test/`, which draw random outcomes by design;
and `S603`/`S607` (subprocess with an argv list, resolved on `PATH`) for the dev
tooling in `vultron/metadata/`, `scripts/`, `.agents/` and `test/`. These are
standing reasons of the kind an `ignore` entry needs, narrowed to the directories
where they hold. They are not a baseline store — see below for why a file-scoped
list cannot be one.

`C901` is the project's **only** complexity gate. The `PLR09xx` counters
(arguments, returns, branches, statements) are excluded on purpose: a second,
differently-calibrated complexity gate can disagree with the first, and then
neither is authoritative.

There is deliberately **no `lint.exclude`**. Lint covers the whole tracked Python
surface, including `scripts/` and `.agents/` — which the flake8 configuration it
replaces never linted even though black formatted them. ADR-0094 resolved that
asymmetry by widening lint rather than preserving it, so do not reintroduce a
directory exclusion to make a finding go away; baseline the finding instead. The
widening's real cost is the handful of `C901` functions in that newly-linted
surface, tabulated in ADR-0094 — refactors, not suppressions, because raising the
threshold would weaken IMPLTS-07-008 tree-wide to accommodate tooling scripts.
When you size that work, measure it with **ruff**: ruff and flake8 implement
mccabe differently and disagree about which functions clear the threshold, and
flake8's answer is the one that stops mattering.

## Select families, exclude by exception

`select` names rule **families**, not individual rules. Curating rules one at a
time turns the config into a standing negotiation and makes the ruleset a thing
each PR can reopen. Selecting families and excluding what does not fit makes the
*exceptions* the reviewable surface, which is far smaller and far more stable.

The corollary is that the `ignore` list is the important artifact, and
IMPLTS-07-019 requires **every entry to carry an inline comment saying what the
rule reports and why this project does not enforce it**. An unexplained
exclusion is indistinguishable from an oversight: nobody dares delete it, so the
list only grows. A stated reason turns tightening into a legible one-line change
instead of an archaeology exercise.

An acceptable reason is one of:

- **A house convention the rule contradicts.** Snake-case type aliases, the
  standard file header, `assign`-then-`return` at the sites where it appears.
- **A cost with no requirement behind it.** PEP 695 syntax migrations,
  `TYPE_CHECKING` blocks, quoting every `cast()` argument.
- **A competing gate already in place.** The `PLR09xx` counters versus `C901`.
- **A tracking issue, when the exclusion is provisional.** Cite the issue
  instead of a standing rationale, so the entry expires when the issue closes.

"Too many findings to fix right now" is **not** a reason to exclude a rule
project-wide. That is what baselining is for, below. Excluding a rule hides
future violations too; baselining does not.

### Exclusions worth knowing about

**`PLC0415` (`import-outside-top-level`) was excluded in the configuration that
issue #3352 landed, and #3949 deleted that entry and placed the markers; #3950
drained them, so `vultron/` carries none.** Its ADR-0094 row was provisional and
pointed at #3350, which asked whether CS-05-002's "last resort" described the
design or an aspiration. The planning measurement answered it: hoisting every
function-local import in `vultron/` to module level and importing every module
showed that the overwhelming majority hoist cleanly — habit, not cycle breaks —
and only a handful of files actually break a cycle. (Counts and the measurement
date belong in the implementation issues, not here — MS-16-001.) Most of the
tree-wide total sits in `test/`, where a test-local import is an isolation idiom
CS-05-002 was never about.

So the rule is **enabled**, and the resolution has three parts (CS-05-002,
CS-05-005, CS-05-006):

- `per-file-ignores` carries `"test/**" = ["PLC0415"]`. Test-local imports stay.
- Every habit site in `vultron/` is hoisted.
- Every genuine cycle break in `vultron/` was baselined with a `# noqa: PLC0415`
  marker citing the issue that removes it structurally (the baseline form
  below), and #3950 removed every one by reorganization. A new deferred import
  in `vultron/` fails the gate; a new cycle is a new reorganization, not a
  marker.

A hoist that closes a cycle fails only when the cycle is entered at one
particular module, so neither pytest's collection order nor one process's import
order proves it safe. `test/architecture/test_every_module_imports_fresh.py`
(integration tier) imports every `vultron/` module as the first member of its
import cycle to load, so a hoist that closes a cycle fails there, whichever
module a deployment happens to import first. It is also how to check whether a
marker is still needed: hoist the import and run that test.

The cycles the measurement found, and how #3950 broke each. Every one but the
first closed through an eager package `__init__` re-export, never module to
module, so each fix removes the one package-level edge pointing back:

| Cycle | How it was broken |
|---|---|
| persistence ports | `CaseOutboxPersistence` importers name `core/ports/case_outbox.py` directly; `case_persistence.py` lost its PEP 562 `__getattr__` |
| publication trees ↔ call-out bundles | the publication-intent contract moved to `report/publication_intent.py` (`publish_artifact_tree.py` was never in the cycle) |
| hypercube ↔ its pattern modules | `valid_states()` and `CS_EVENT_LETTERS` moved from the hypercube to `case_states/validations.py`, which imports neither the hypercube nor the patterns |
| BT node → use-case helper (BTND-04-003) | the replica-seeding helpers moved to `core/services/case_replica_seeding.py` (BT-22-005) |
| embargo tree and nodes ↔ status/sync node packages | `EmitCaseStatusUpdateNode` moved to the shared `behaviors/case_status_snapshot.py` (BTND-04-001); `sync/__init__` stopped re-exporting the announce tree; the `close_case` effect moved from `sync/nodes` to `case/nodes` |
| inbox pipeline ↔ use cases | the dead-letter tree left the inbox package for its own area, `behaviors/dead_letter/` (IO-02-003) |

Each was a CS-05-003 finding: a shared symbol that belongs in a neutral module
or on the side of the cycle that owns it. That is the pattern for a new one: find
the package `__init__` that makes the edge, then move the symbol, not the
import. A PEP 562 module `__getattr__` that calls `importlib` is the same
deferral in a form `PLC0415` cannot see; #4106 removed the last of those, from
`case/nodes`, and none should come back.

**`G004` (`logging-f-string`) was the other provisional exclusion in the
configuration that #3352 landed with, and that entry too was deleted, not
kept — #3991 removed it.** Its ADR-0094 row cited #3378, which asked whether the
rewrite target was lazy `%`-args or structured `extra=` fields. The answer is these
were never alternatives: the template-plus-args shape decides how the *message*
gets its values (SL-01-005), while `extra=`-style record fields are the
correlation mechanism (SL-02-003, built by #3992) and are set by a boundary
filter rather than per call. So the rule is **enabled**: #3991 rewrites every
f-string log call to a literal template with positional args and places no
marker. Ruff's `G004` fix is available only under `--preview --unsafe-fixes` and
declines a placeholder that carries a conversion or format spec (`{x!r}`,
`{x:>5}`), so the bulk is autofixed one category at a time per ADR-0094 and the
residue is hand work; either way the rewrite is bounded, and "too many to fix
now" is not a reason to exclude (above). The reasoning is in
[notes/structured-logging.md](structured-logging.md) § "Log-Call Shape: Template
Plus Lazy Arguments (SL-01-005)".

With #3991 landed, the `G004` entry is gone, the whole `G` family runs with no
`ignore` entry and no `# noqa: G00x` marker, and a new f-string log call fails
the gate. With the `PLC0415` entry gone too (#3949), **no entry in `ignore`
cites a tracking issue**: every remaining exclusion rests on one of the first
three standing reasons above. A new provisional exclusion needs a new issue, and
this section should name it.

## Baselining: `RUF100` is the ratchet

When a rule is worth enforcing but the tree is not yet clean, do **not** add it
to `ignore`. Baseline the existing findings per line and enforce the rule going
forward:

```bash
uv run ruff check --add-noqa
```

Then annotate each inserted marker with the issue that tracks its removal, per
IMPLTS-07-020:

```python
except Exception:  # noqa: BLE001  # ruff-baseline #NNNN
```

This works because `RUF100` (`unused-noqa`) stays selected. Ruff therefore
enforces all three ratchet properties by itself:

- **Growth fails** — a new violation with no marker is a finding.
- **Silent progress fails** — fix a site and leave its marker behind, and
  `RUF100` reports the marker as unused.
- **Completion is forced** — the last marker cannot be left as decoration.

That is the property set ADR-0064 demanded of a ratchet, obtained with no
hand-maintained backlog sets and nothing for a maintainer to remember. It is why
this project does **not** write a bespoke ratchet test for lint debt, and why
`per-file-ignores` is not an acceptable baseline store: being file-scoped, it
gives no signal when one of several violations in a file is fixed.

Note the endpoint of a baseline drain is **zero unjustified suppressions, not
zero markers**. CS-23-001 sanctions a broad `except` at a behavior-tree node's
`update()`, at the `BTBridge` execution boundary, and in py_trees
`setup()`/`initialise()` — each of which keeps a permanent marker carrying an
inline comment stating what it guards and why. Converting a `# ruff-baseline`
marker into a justified permanent one is a valid way to clear a site.

Before baselining a rule, check whether its findings are already owned. Ruff
often just puts a detector on work that is already tracked, in which case the
marker should cite the **existing** issue rather than a new one. `BLE001`, `S110`
and `S112` are the standing example: they detect the CS-23-001 broad-except
eradication carried by epic #3329, so they add a gate, not a backlog.

## How to tighten

1. Delete one line from `ignore`.
2. Run `ruff check` and read what it exposes.
3. Autofix what is mechanical; baseline the rest per the section above with a
   new tracking issue.
4. Keep the PR to that one rule. A tightening PR that touches several rules is
   unreviewable, because a reviewer cannot tell which finding class justified
   which edit.

Never tighten by enabling a family. Families are the coarse dial for what is
already clean; individual rules are the dial for taking on new debt.

## Consequences for the commit loop

Ruff makes the whole-tree lint and format gate roughly a second, which changed
the habits the flake8 era required:

- The pre-commit ruff hook is invoked **directly**, not through
  `.agents/skills/shared/run-if-changed.sh`. Fingerprint memoization (#3153)
  exists to avoid repeating expensive whole-tree work; at this speed the cache
  lookup costs a meaningful fraction of the work it is avoiding, so the wrapper
  stops paying for itself. `run-if-changed.sh` stays in place for `mypy` and
  `pyright`, which remain the genuinely slow checks.
- The ten-minute `git commit` timeout that
  [notes/devcontainer-tooling.md](devcontainer-tooling.md) used to prescribe
  existed because the flake8 hook linted all of `vultron/` and `test/` regardless
  of what was staged. The ruff hook lints only the staged files, so that cause is
  gone; that note records what remains.
- `ruff check` is cheap enough to run repeatedly while editing, rather than once
  before committing.
- **Read `ruff check` before you `--fix`.** CI and the hook hold the tree at zero
  findings, so a bare `ruff check --fix` normally rewrites only the files your
  change touched — which is why `run-linters` and `format-code` run it bare. When
  `ruff check` reports a finding in a file you did **not** touch (a ruff upgrade,
  a newly selected rule, a branch behind `main`), do not `--fix` the whole tree:
  a mechanical rewrite riding along in an unrelated diff is the drift that bit
  #3244. Name the files you touched (`ruff check --fix <paths>`) for that one run,
  and take the rest to its own PR. This is the one place the no-paths rule above
  does not settle the question, because it governs *gates* — the CI job, the
  hook, the skills' checks — and `--fix` is not a gate. Never encode a path into
  anything a gate invokes.
