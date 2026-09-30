---
title: Lint Tooling Policy — Ruff Configuration, Exclusions, and Baselining
status: active
description: >
  How the Python lint and format gate is configured and why: ruff as the single
  linter and formatter, family-level `select` with a short annotated `ignore`,
  and `RUF100` as the mechanism that keeps baselined findings from becoming
  permanent. Records what belongs in an `ignore` entry, how to tighten the
  ruleset, and which pitfalls the flake8-era setup left behind.
related_specs:
  - specs/tech-stack.yaml
  - specs/code-style.yaml
related_notes:
  - notes/devcontainer-tooling.md
  - notes/ci-workflow-authoring.md
  - notes/structured-logging.md
---

# Lint Tooling Policy — Ruff Configuration, Exclusions, and Baselining

> **Status: decided, not yet built.** ADR-0094 is accepted, but the configuration
> this note describes lands with **#3352**. Until it does, `ruff` is not installed,
> there is no `[tool.ruff]` table in `pyproject.toml`, and flake8, black and isort
> are still the live gate. Read what follows as the policy that governs the ruff
> config once it exists — not as a description of the current tree.
> [notes/devcontainer-tooling.md](devcontainer-tooling.md) remains authoritative
> for today's commit loop.

Ruff is to be the sole Python linter and formatter (IMPLTS-07-017). `mypy` and
`pyright` remain separate type-checking jobs. Black, flake8 and isort are retired
by ADR-0094 and MUST NOT be reintroduced alongside ruff — leaving a superseded
linter in place as a fallback recreates the duplicate-gate problem that decision
removed (the config-level form of the shim CS-15-001 prohibits for code symbols).

ADR-0094 is the decision record and holds the measurements: the timing
comparison, the per-rule finding counts behind each exclusion, and the rejected
options. This note holds the operating policy. Counts are deliberately absent
here (MS-16-001) — read them from the ADR, where they carry a measurement date.

## Invoke with no path arguments

Every caller that acts as a **gate** — a CI job, a pre-commit hook, an agent
skill, or a documented developer command — MUST run exactly these, with **no
paths**:

```bash
uv run ruff check          # or --fix
uv run ruff format         # or --check
```

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
uv run ruff check --show-files | wc -l
```

**Not** `--show-settings`. See the two silent failures below for why.

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

**`PLC0415` (`import-outside-top-level`) is excluded in the configuration
that #3352 lands with, and that entry is deleted, not kept — #3949 removes it
and places the markers, and #3950 drains them.** Its ADR-0094 row was provisional and
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
- Every genuine cycle break in `vultron/` carries a `# noqa: PLC0415` marker
  citing the issue that removes it structurally (the baseline form below; #3950
  is that issue for every cycle in the table). The marker count is the cycle
  backlog, and `RUF100` drains it.

The cycles the measurement found, grouped so the structural work has a map:

| Cycle | Files carrying the deferred import |
|---|---|
| persistence ports | `vultron/core/ports/case_persistence.py` (PEP 562 `__getattr__` re-export of `case_outbox`) |
| publication trees ↔ call-out bundles | `vultron/core/behaviors/report/publication_tree.py`, `publish_artifact_tree.py` |
| hypercube ↔ its pattern modules | `vultron/core/case_states/patterns/info.py`, `potential_actions.py` |
| BT node → use-case helper (BTND-04-003 `KNOWN_VIOLATIONS`) | `vultron/core/behaviors/case/nodes/announce.py` |
| embargo tree and nodes ↔ status/sync node packages | `vultron/core/behaviors/embargo/trigger_tree.py` (↔ `status/nodes`), `embargo/nodes/teardown.py` (↔ `sync/nodes`) |
| inbox pipeline ↔ use cases | `vultron/core/use_cases/received/unknown.py` (dead-letter tree → inbox pipeline nodes → semantic registry → `unknown`) |

Each is a CS-05-003 finding: a shared symbol that belongs in a neutral module or
on the side of the cycle that owns it. Do not add a file to this table to make a
new finding go away — a new cycle is a new reorganization, and the marker it
would carry needs its own tracking issue.

**`G004` (`logging-f-string`) was the other provisional exclusion, and it too is
deleted, not kept.** Its ADR-0094 row cited #3378, which asked whether the rewrite
target was lazy `%`-args or structured `extra=` fields. The answer is that these
were never alternatives: the template-plus-args shape decides how the *message*
gets its values (SL-01-005), while `extra=`-style record fields are the
correlation mechanism (SL-02-003) and are set by a boundary filter rather than
per call. So the rule is **enabled**, every f-string log call is rewritten to a
literal template with positional args, and no marker is placed — `G004` has no
autofix, but the rewrite is bounded and mechanical, and "too many to fix now" is
not a reason to exclude (below). The reasoning is in
[notes/structured-logging.md](structured-logging.md) § "Log-Call Shape".

With both provisional rows resolved, **no entry in `ignore` cites a tracking
issue**: every remaining exclusion rests on one of the first three standing
reasons above. A new provisional exclusion needs a new issue, and this section
should name it.

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

## Consequences for the commit loop (once #3352 lands)

Ruff will make the whole-tree lint and format gate roughly a second, which changes
three habits the flake8 era requires:

- The pre-commit ruff hook is to be invoked **directly**, not through
  `.agents/skills/shared/run-if-changed.sh`. Fingerprint memoization (#3153)
  exists to avoid repeating expensive whole-tree work; at this speed the cache
  lookup costs a meaningful fraction of the work it is avoiding, so the wrapper
  stops paying for itself. `run-if-changed.sh` stays in place for `mypy` and
  `pyright`, which remain the genuinely slow checks.
- The ten-minute `git commit` timeout that
  [notes/devcontainer-tooling.md](devcontainer-tooling.md) prescribes exists
  because the flake8 hook lints all of `vultron/` and `test/` regardless of what is
  staged. Retiring that hook removes the cause, so #3352 (AC-11) updates that note
  to say what remains instead of leaving a dead workaround prescribed. Until then
  the timeout is still needed.
- `ruff check` is cheap enough to run repeatedly while editing, rather than once
  before committing.
- **Do not run a whole-tree `ruff check --fix`** to clean up as you go: it will
  autofix files your change has nothing to do with, and a mechanical rewrite
  riding along in an unrelated diff is the drift that bit #3244. This is the one
  place the no-paths rule above does not settle the question, because it governs
  *gates* — the CI job, the hook, the skills — and `--fix` is not a gate. For an
  interactive cleanup, name the files you touched (`ruff check --fix <paths>`) and
  understand that you are deliberately narrowing scope for that one run. Never
  encode a path into anything a gate invokes.
