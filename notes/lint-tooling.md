---
title: Lint Tooling Policy — Ruff Configuration, Exclusions, and Baselining
status: active
kind: guidance
description: >
  How the Python lint and format gate is configured and why: ruff as the single
  linter and formatter, scope declared in config and never on the command line,
  family-level `select` with a short annotated `ignore`, `RUF100` as the
  baselining ratchet, how to tighten the ruleset, and how to break an import
  cycle without an ADR.
related_specs:
  - specs/tech-stack.yaml
  - specs/code-style.yaml
  - specs/structured-logging.yaml
  - specs/meta-specifications.yaml
related_notes:
  - notes/devcontainer-tooling.md
  - notes/ci-workflow-authoring.md
  - notes/structured-logging.md
---

# Lint Tooling Policy — Ruff Configuration, Exclusions, and Baselining

Ruff is the sole Python linter and formatter (IMPLTS-07-017). `mypy` and
`pyright` remain separate type-checking jobs. Do not reintroduce black, flake8 or
isort alongside ruff: a superseded linter kept as a fallback is a duplicate gate
(ADR-0094).

ADR-0094 holds the measurements (timings, per-rule finding counts, rejected
options). This note holds the operating policy and carries no counts (MS-16-001).

## Invoke with no path arguments

Every caller that acts as a **gate** — a CI job, an agent skill, or a
documented developer command — MUST run exactly these, with **no paths**:

```bash
uv run ruff check          # or --fix
uv run ruff format         # or --check
```

Scope lives in the config, never in the invocation (**IMPLTS-07-021**): a scope
passed as arguments is duplicated at every call site and drifts. `pyright`
(`pyrightconfig.json`) and `mypy` (`.mypy.ini`) declare their own scope the same
way, so invoke them bare too; naming a package narrows the gate by accident.

The pre-commit hook is the one caller that passes paths, and it does not choose
them: pre-commit appends the staged filenames, and `force-exclude = true` makes
ruff apply the config's exclusions to them.

When you change scope, verify with `uv run ruff check --show-files` and diff the
list against the one from before the change. **Not** `--show-settings`, which
confirms ruff parsed a setting, not that it applied it.

## Three scoping settings that fail silently

Expect no error message from any of these.

- **`lint.exclude` needs glob form.** It is matched against each file's full
  path, so `"scripts"` parses and does nothing; write `"scripts/**"`. A bare
  directory name works only in the top-level discovery `exclude`.
- **Keep `[tool.ruff.format] exclude = ["**/*.md"]`.** Unscoped `ruff format`
  rewrites fenced Python inside Markdown, which reaches append-only
  `plan/history/` (HM-01-005), `docs/` (DF-09-001) and the skill trees (#2952).
- **Keep `force-exclude = true`.** Without it ruff lints a file named on the
  command line even when the config excludes it, so the hook and CI disagree
  about scope. It applies `exclude` only, not `.gitignore`: a file force-added
  under a gitignored directory is linted by the hook and skipped by CI. If
  `git ls-files -ci --exclude-standard` lists one, move it or name it in
  `exclude`; do not turn `respect-gitignore` off.

## The shape of the configuration

Everything belongs in `[tool.ruff]` in `pyproject.toml`. These settings carry
obligations, and changing one silently breaks a requirement:

| Setting | Carries |
|---|---|
| `line-length` | the retired `[tool.black]` value; keeps lint and format agreed |
| `target-version` | IMPLTS-01-001, the Python floor |
| `[tool.ruff.lint.mccabe] max-complexity` | IMPLTS-07-008, the complexity gate |
| `per-file-ignores` for `__init__.py` | the re-export exemption (`F401`) |

`per-file-ignores` also holds a few **permanent** exemptions, each justified in
the comment beside it and narrowed to the directories where the reason holds
(`S311` for code that draws random outcomes by design, `S603`/`S607` for dev
tooling that shells out with argv lists). It is not a baseline store: see
"Baselining" for why.

`C901` is the project's **only** complexity gate. The `PLR09xx` counters stay
excluded: a second, differently-calibrated complexity gate can disagree with the
first, and then neither is authoritative.

There is deliberately **no `lint.exclude`**: lint covers the whole tracked Python
surface, including `scripts/` and `.agents/` (ADR-0094). Do not add a directory
exclusion to make a finding go away; baseline it. Fix a `C901` finding by
refactoring, not by raising the threshold, which weakens IMPLTS-07-008 tree-wide.

## Select families, exclude by exception

`select` names rule **families**, not individual rules, so the *exceptions* are
the reviewable surface rather than a ruleset each PR can reopen.

The `ignore` list is therefore the important artifact. **Every entry carries an
inline comment saying what the rule reports and why this project does not
enforce it** (IMPLTS-07-019): an unexplained exclusion looks like an oversight,
nobody dares delete it, and the list only grows. An acceptable reason is one of:

- **A house convention the rule contradicts** (snake-case type aliases,
  assign-then-return).
- **A cost with no requirement behind it** (PEP 695 syntax, `TYPE_CHECKING`
  blocks, quoting every `cast()` argument).
- **A competing gate already in place** (the `PLR09xx` counters versus `C901`).
- **A tracking issue, when the exclusion is provisional.** Cite the issue so the
  entry expires when it closes. No current entry is provisional.

"Too many findings to fix right now" is **not** a reason to exclude a rule
project-wide: excluding hides future violations too. Baseline instead.

## Rules that stay enabled

- **`PLC0415` (`import-outside-top-level`)**: enabled for `vultron/`, which
  carries no marker; `test/**` is exempt because a test-local import is an
  isolation idiom (CS-05-006). A new deferred import in `vultron/` fails the
  gate. Break the cycle instead: find the package `__init__` re-export that
  makes the back edge and move the shared symbol to a neutral module or the
  side that owns it, not the import (CS-05-003). A PEP 562 module
  `__getattr__` calling `importlib` is the same deferral in a form `PLC0415`
  cannot see; do not add one.
- **Prove a hoist with the fresh-import test.** A hoist that closes a cycle
  fails only when the cycle is entered at one particular module, so test
  collection order proves nothing.
  `test/architecture/test_every_module_imports_fresh.py` imports every
  `vultron/` module as the first of its cycle to load.
- **`G004` (`logging-f-string`)** and the whole `G` family run with no `ignore`
  entry and no marker: log calls take a literal template plus positional args
  (SL-01-005). See [notes/structured-logging.md](structured-logging.md).

## Baselining: `RUF100` is the ratchet

When a rule is worth enforcing but the tree is not yet clean, do **not** add it
to `ignore`. Baseline the existing findings per line with
`uv run ruff check --add-noqa`, then annotate each marker with the issue that
tracks its removal (IMPLTS-07-020):

```python
except Exception:  # noqa: BLE001  # ruff-baseline #NNNN
```

`RUF100` (`unused-noqa`) stays selected, so ruff enforces the three ratchet
properties ADR-0064 requires with no hand-maintained backlog:

- **Growth fails** — a new violation with no marker is a finding.
- **Silent progress fails** — a fixed site's leftover marker is reported unused.
- **Completion is forced** — the last marker cannot be left as decoration.

That is why lint debt gets no bespoke ratchet test, and why `per-file-ignores`
is not a baseline store: being file-scoped, it gives no signal when one of
several violations in a file is fixed.

The endpoint of a drain is **zero unjustified suppressions, not zero markers**.
CS-23-001 sanctions a broad `except` at a BT node's `update()`, at the `BTBridge`
boundary, and in py_trees `setup()`/`initialise()`; each keeps a permanent marker
whose comment states what it guards. Converting a `# ruff-baseline` marker into
a justified permanent one clears the site.

Before baselining, check whether the findings are already owned, and cite the
**existing** issue: `BLE001`, `S110` and `S112` detect the broad-except work of
epic #3329, so their markers cite it.

## How to tighten

1. Delete one line from `ignore`.
2. Run `ruff check` and read what it exposes.
3. Autofix what is mechanical; baseline the rest with a new tracking issue.
4. Keep the PR to that one rule, so a reviewer can tell which finding class
   justified which edit.

Never tighten by enabling a family. Families are the coarse dial for what is
already clean; individual rules are the dial for taking on new debt.

## The commit loop

- The ruff pre-commit hook runs **directly**, not through
  `.agents/skills/shared/run-if-changed.sh`: a whole-tree run takes about a
  second, so memoization costs a real share of the work it saves. `mypy` and
  `pyright` keep the wrapper.
- `ruff check` is cheap; run it repeatedly while editing.
- **Read `ruff check` before you `--fix`.** The tree is held at zero findings, so
  a bare `--fix` normally rewrites only files you touched. When it reports a
  finding in a file you did **not** touch (a ruff upgrade, a newly selected rule,
  a stale branch), run `ruff check --fix <paths>` on your files for that one run
  and take the rest to its own PR; a mechanical rewrite riding in an unrelated
  diff is drift (#3244). `--fix` is not a gate, so this does not break the
  no-paths rule; never encode a path into anything a gate invokes.

## Breaking an import cycle is housekeeping, not an ADR

A refactor whose only purpose is to break an import cycle (hoisting a shared type
into a leaf module, moving a function to the layer that owns its dependencies)
needs no ADR: it changes no behaviour, public contract or layer rule, so there is
no rejected alternative to record (MS-11-002, MS-11-005). Do it in the PR that
hit the cycle and say so in the body. Draft an ADR only if breaking the cycle
requires changing a layer boundary or a port, and then the ADR is about that
change.
