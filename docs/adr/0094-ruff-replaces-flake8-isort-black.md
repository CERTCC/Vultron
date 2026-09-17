---
status: accepted
date: 2026-09-17
deciders: Vultron maintainers
consulted: Vultron maintainers
informed: Vultron contributors
---

# Replace flake8, isort and black with ruff, and declare lint exclusions instead of discovering them

## Context and Problem Statement

The Python quality gate runs four tools plus a fifth that is configured but never
executed. Measured on `vultron/` + `test/` on 2026-09-17, cold, in the
devcontainer:

| Tool | Wall clock | CPU |
|---|---|---|
| `flake8 vultron/ test/` | 34.0 s | 64 s |
| `black --check vultron/ test/` | 3.4 s | 5 s |
| `ruff check` (rule families below) | **0.65 s** | 0.8 s |
| `ruff format --check` | **0.35 s** | 0.5 s |

That 34-second flake8 cost is paid on *every* commit that edits a Python source
file: the pre-commit hook is `pass_filenames: false` and lints the whole tree.
It is the reason `notes/devcontainer-tooling.md` instructs agents to give
`git commit` a ten-minute timeout, and the reason #3153 had to build a
fingerprint cache (`run-if-changed.sh`) so the same whole-tree work is not
repeated across `format-code`, `run-linters` and the hook.

Two further problems compound it:

**isort is configured but ungated.** `[tool.isort]` (`profile = "black"`) is set
and `isort` is a declared dev dependency, but it appears in neither the CI job
set nor the pre-commit hooks, and flake8 does not check import order. #3244
(issue #3194) hit the consequence directly: a reviewer flagged import-ordering
findings that no CI gate would ever fail on, and running `isort` to fix them
reordered imports in over a hundred files unrelated to that PR — accumulated
silent drift. Until import order is gated, `isort` is a trap for any tool or PR
that runs it.

**Several `CS-*` requirements have no gate at all.** flake8 cannot see them:

| Requirement | What it forbids | Detectable by |
|---|---|---|
| CS-23-001 | blanket `except Exception` / bare `except` | `BLE001`, `S110`, `S112` |
| CS-02-001 | ungrouped imports | `I001` |
| CS-21-001 | `None` defaults for collection fields | `RUF012`, `B008` |
| CS-13-001 | naive (non-UTC) datetimes | `DTZ001`, `DTZ005`, `DTZ011` |
| CS-03-002 | unused imports outside `__init__.py` | `F401` |

These are `MUST` requirements the project believes it follows and does not
enforce. The gap is not that the bar is too low; it is that nothing stands under
the bar that was already set.

The question is therefore not "should we add ruff" but "what is the smallest
tool set that enforces the requirements we already have, and how do we choose a
ruleset without turning every future PR into a fresh argument about rules?"

## Decision Drivers

- Lint cost is paid many times per day, locally and in CI; it is the dominant
  friction in the commit loop.
- A gate that is configured but not run (isort) is worse than no gate, because it
  accumulates drift that surfaces as unreviewable diffs.
- Existing `CS-*` `MUST` requirements need enforcement, not new requirements.
- Rule exclusions must be **deliberate, stated, and revisitable** — a maintainer
  should be able to read why something is off and turn it on later, without
  re-deriving the analysis.
- A cleanup path must be reviewable: mechanical changes and semantic judgement
  calls must not land in the same diff.
- Per ADR-0064, a ratchet with no forcing function does not finish. The
  `strict=False` xfails for #1991 and #1992 sat green-and-ignored.

## Considered Options

- **A — Add ruff alongside flake8 and black, then grow a `select` list.** The
  approach proposed in #2199 as originally written.
- **B — Replace flake8, isort and black with ruff; select rule families and
  declare a short annotated `ignore` list.**
- **C — Adopt ruff's full default ruleset and pin every current violation into a
  shrink-only `per-file-ignores` baseline.**

## Decision Outcome

Chosen option: **B — replace flake8, isort and black with ruff, select rule
families, and declare exclusions explicitly.**

Configuration lives in `pyproject.toml` under `[tool.ruff]`, carrying
`line-length = 79` (matching the retired `[tool.black]` setting),
`target-version = "py312"` (IMPLTS-01-001), family-level `select`,
`[tool.ruff.lint.mccabe] max-complexity = 10` (which carries IMPLTS-07-008 over
from `.flake8`), and `per-file-ignores = { "__init__.py" = ["F401"] }` (which
carries the equivalent `.flake8` entry).

Three properties of the decision matter more than the specific rule list:

**1. Exclusions are declared, not discovered.** Every entry in `ignore` carries
an inline comment stating what it suppresses and why. That block is the
authoritative record of what this project has deliberately chosen not to enforce.
Tightening later is deleting one line and fixing what it exposes — a legible,
self-contained PR. This is made normative by IMPLTS-07-019 so the practice cannot
erode into an unexplained list.

**2. The forcing function is `RUF100`, not a bespoke ratchet.** The residue that
cannot be autofixed is baselined with `ruff check --add-noqa`, each marker
carrying the issue that tracks its removal. Because `RUF100` (`unused-noqa`) is
selected, ruff itself fails when a site is fixed and its marker left behind, and
fails when new code introduces a violation without a marker. That is the full
property set ADR-0064 required of a ratchet — growth fails, silent progress
fails, completion forces the marker's deletion — with no hand-maintained backlog
sets and nothing for a maintainer to remember. It also operates per line rather
than per file, which a `per-file-ignores` baseline cannot do.

**3. Family-level `select` with a short `ignore` beats rule-by-rule curation.**
Enumerating rules individually makes the config a standing negotiation. Selecting
families and excluding the ones that do not fit makes the *exceptions* the thing
under review, which is a much smaller and more stable surface.

### The exclusions and their reasons

Measured 2026-09-17. Counts are recorded here — a dated decision record — and
deliberately not restated in `specs/` or `notes/` (MS-16-001).

| Excluded | Findings suppressed | Reason |
|---|---|---|
| `PLC0415` import-outside-top-level | 2,423 | Function-local imports are this codebase's cycle-break idiom. CS-05-002 calls the pattern a "last resort"; at this scale it is the norm. That contradiction is real and is tracked as #3350 — it is a premise question, not a lint question, and enabling the rule before it is answered would either bury the tree in noise or force thousands of rewrites toward an unagreed target. |
| `TC006` runtime-cast-value | 654 | Would quote the type argument of every `cast()` call. Pure churn. |
| `TRY003` raise-vanilla-args | 564 | Would require one exception class per distinct message string. |
| `PLR2004` magic-value-comparison | 409 | Overwhelmingly test literals, where a named constant reduces clarity. |
| `PLR0904`, `PLR0911`–`PLR0917` | 480 | Argument, return, branch and statement counts. `C901` at `max-complexity = 10` is this project's chosen complexity gate (IMPLTS-07-008); a second, differently-calibrated one would compete with it. |
| `G004` logging-f-string | 194 | A legitimate rule — f-strings defeat logging's lazy formatting — but the fix interacts with the structured-logging requirements (`specs/structured-logging.yaml`). Deferred as its own decision rather than smuggled in here. |
| `TC001`, `TC002`, `TC003` | 92 | Would force `if TYPE_CHECKING:` blocks across the tree. |
| `RET504` unnecessary-assign | 86 | Assign-then-return is more readable at the sites where it appears. |
| `RUF001`–`RUF003` ambiguous-unicode | 39 | Fires on prose and docstrings, not code. |
| `TRY300`, `SIM105`, `SIM117` | 165 | Style preferences (`else` after `try`, `contextlib.suppress`, combined `with`). Nested `with` is frequently the clearer form. |
| `UP040`, `UP047` PEP 695 syntax | 52 | Type-alias and generic-syntax modernization with no requirement behind it. |
| `PYI042` snake-case-type-alias | 35 | `snake_case` type aliases are established house style. |
| `E501`, `E203` | — | Line length and slice whitespace belong to the formatter. Carried over verbatim from `.flake8`'s `extend-ignore`. |
| `EXE` family (not selected) | 846 | `EXE001` fires on every file carrying the standard `#!/usr/bin/env python` + CMU copyright header — a file template, not a defect. Excluded by not selecting the family, so no `ignore` entry is needed. |

Selecting the remaining families leaves **2,133 findings**: 1,309 safe-autofixable,
301 more fixable with `--unsafe-fixes`, and roughly 523 requiring hand work.

The largest hand-work cluster is exception handling, and it is **already owned
elsewhere**. Epic #3329 covers it: #3325 (merged during this planning) eradicated
broad `except Exception` from `vultron/core/`, and #3326 and #3340 carry the
remainder. Ruff's `BLE001`, `S110` and `S112` are therefore not new work — they
are a mechanical detector for an eradication already in flight, and their residue
is baselined with markers citing **#3326**, not a new issue. The exception-adjacent
rules those issues do *not* cover (`TRY400`, `TRY004`, `B017`, `B904`, `TRY301`,
`TRY203` — `logger.error` where `logger.exception` belongs, type checks that raise
the wrong class, `pytest.raises(Exception)` as a vacuous assertion, missing
`raise ... from`) are separate concerns and are tracked on their own.

### Consequences

- Good, because the lint and format gate drops from 37.4 s to 1.0 s, removing the
  dominant cost in the commit loop and the reason for the ten-minute `git commit`
  timeout.
- Good, because four tools become two (ruff, plus mypy and pyright for typing) and
  `isort`'s ungated-drift trap is closed by making import order a hard gate.
- Good, because `run-if-changed.sh` is no longer needed for lint or format; it is
  retained only for mypy and pyright, which remain the genuinely slow checks.
- Good, because CS-02-001, CS-03-002, CS-13-001 and CS-21-001 gain gates they have
  never had.
- Bad, because the residue is baselined as in-tree `# noqa` markers rather than
  configuration, which is visible churn in the diff. Accepted: the markers are
  what make `RUF100` a working ratchet, and they are line-precise rather than
  file-scoped.
- Bad, because `ruff format` reformats files that black formatted differently.
  Measured at 247 of 1,399 files at `line-length = 79` — the two formatters
  already agree on 82% of the tree, so this is a bounded mechanical diff and not
  the whole-tree rewrite it was initially assumed to be.
- Neutral, because the eight `PLR09xx`/`TRY003`/`TC00x` exclusions could each be
  revisited independently; none of them blocks anything.

## Validation

- CI runs a single `lint-ruff` job executing `ruff check` and
  `ruff format --check` (IMPLTS-07-005, IMPLTS-07-018). The `build` job gates on
  it, and the mandatory `notify-failure` wiring (CISEC-05) is preserved.
- A single pre-commit hook invokes ruff directly, without the
  `run-if-changed.sh` wrapper.
- `RUF100` remaining selected is the mechanism that validates the baseline:
  a stale marker fails the gate (IMPLTS-07-020).
- The absence of `.flake8`, `[tool.black]` and `[tool.isort]`, and of the three
  dependencies, is the evidence that this is a replacement and not an addition
  (CS-15-001 forbids leaving the superseded tooling in place as a fallback).

## Pros and Cons of the Options

### A — Add ruff alongside, then grow a `select` list

- Good, because it is the least disruptive first step and keeps every existing
  gate intact.
- Bad, because it makes the situation *worse* on the axis that motivated the work:
  a fifth tool is added and none removed, so the commit loop gets slower.
- Bad, because "tighten the list later" has no forcing function. Nothing fails if
  the tightening PRs never land, and there is no partial-progress signal inside a
  category. ADR-0064 rejected exactly this shape with in-repo evidence.
- Bad, because it leaves `isort` configured-but-ungated indefinitely.

### B — Replace flake8, isort and black with ruff (chosen)

- Good, because it takes the full speed win immediately rather than deferring it
  behind a cleanup that may never complete.
- Good, because the exclusion list is a small, readable, revisitable artifact
  rather than an implicit consequence of which rules nobody got around to
  enabling.
- Bad, because the first PR is large: config, autofixes, a formatter swap and the
  removal of three tools.
- Neutral, because it does not touch mypy or pyright, which remain separate jobs.

### C — Full default ruleset with a shrink-only `per-file-ignores` baseline

- Good, because CI is green on arrival with no cleanup at all, and new code is
  clean by default.
- Bad, because the default ruleset yields 7,191 findings on this tree, dominated
  by categories this project has deliberately chosen against. A baseline that
  large is not a debt record; it is a way of not making the decision.
- Bad, because `per-file-ignores` is file-scoped, so fixing one of several
  violations in a file is invisible — the "silent progress fails" property is lost
  and has to be rebuilt as a bespoke test.

## More Information

- Source idea: #2199, with corroborating evidence from #3244 / #3194.
- Ratchet-shape precedent, and the evidence that non-forcing ratchets stall:
  ADR-0064 § "Ratcheting across the steps".
- Precedent for a lint-tooling decision recorded as an ADR: ADR-0092.
- Follow-on questions deliberately left open: #3350 (`PLC0415` vs CS-05-002).
- Exception-handling findings are owned by epic #3329, not by this decision:
  #3325 (merged), #3326, #3340.
- Policy write-up for future maintainers: `notes/lint-tooling.md`.
- All measurements in this record were taken on 2026-09-17 with ruff 0.16.8
  against `origin/main` at `9ea51249d`, except the per-exclusion counts in the
  table above, taken a few hours earlier at `d2d5df9b2`. #3325 merged between the
  two, which moved the exception-rule counts by roughly a percent of the total.
  These are point-in-time evidence for the decision, not requirements — every
  count here will drift, and none of them is restated in `specs/` or `notes/`
  (MS-16-001).

Generated spec requirements: `tech-stack.yaml` IMPLTS-07-017 through
IMPLTS-07-020, with IMPLTS-07-005 and IMPLTS-07-008 amended and IMPLTS-07-001,
IMPLTS-07-004, IMPLTS-07-013 and IMPLTS-07-014 retired.
