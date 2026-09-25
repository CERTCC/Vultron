---
status: accepted
date: 2026-09-17
deciders: Vultron maintainers
consulted: Vultron maintainers
informed: Vultron contributors
# The decision itself is accepted, not provisional. The word appears because two
# of the *rule exclusions* it records are provisional and cite tracking issues
# (#3350, #3378) — which IMPLTS-07-019 requires them to say. Suppress the
# MS-14-002 match on that vocabulary.
lint_suppress: [status_prose_contradiction]
stakeholder_type: [project-contributor]
---

# Replace flake8, isort and black with ruff, and declare lint exclusions instead of discovering them

## Context and Problem Statement

The Python quality gate runs four tools plus a fifth that is configured but never
executed. Measured 2026-09-17, cold, in the devcontainer. The scopes are
deliberately not equal: the flake8 and black rows are the invocations in use
today, which name `vultron/` and `test/`, while the ruff rows are the bare
whole-tree invocations this decision adopts. Ruff is faster over a strictly
larger surface, so the comparison understates the gain rather than inflating it.

| Tool | Scope | Wall clock | CPU |
|---|---|---|---|
| `flake8 vultron/ test/` | 2 directories | 34.0 s | 64 s |
| `black --check vultron/ test/` | 2 directories | 3.4 s | 5 s |
| `ruff check` (rule families below) | whole tree | **0.65 s** | 0.8 s |
| `ruff format --check` | whole tree | **0.35 s** | 0.5 s |

That 34-second flake8 cost is paid on every commit that edits a file under
`vultron/` or `test/`: the pre-commit hook is `pass_filenames: false` and lints
both trees in full regardless of what is staged, and the `run-if-changed.sh`
fingerprint that guards it keys on exactly those two directories plus `.flake8`
and `uv.lock`. It is the reason `notes/devcontainer-tooling.md` instructs agents
to give `git commit` a ten-minute timeout, and the reason #3153 had to build that
fingerprint cache so the same work is not repeated across `format-code`,
`run-linters` and the hook.

Two further problems compound it:

**isort is configured but ungated.** `[tool.isort]` (`profile = "black"`) is set
and `isort` is a declared dev dependency, but it appears in neither the CI job
set nor the pre-commit hooks, and flake8 does not check import order. #3244
(issue #3194) hit the consequence directly: a reviewer flagged import-ordering
findings that no CI gate would ever fail on, and running `isort` to fix them
reordered imports in over a hundred files unrelated to that PR — accumulated
silent drift. Until import order is gated, `isort` is a trap for any tool or PR
that runs it.

**Two `CS-*` requirements have no gate at all.** flake8 cannot see either:

| Requirement | Priority | What it requires | Detectable by |
|---|---|---|---|
| CS-02-001 | SHOULD | grouped, ordered imports | `I001` |
| CS-13-001 | MUST | UTC-aware datetimes | `DTZ001`, `DTZ005`, `DTZ011` |

Two requirements the project believes it follows and does not enforce anywhere.
The gap is not that the bar is too low; it is that nothing stands under the bar
that was already set.

Two neighbouring requirements were considered for this table and do **not**
belong in it, which is worth recording because both are easy to miscount:

- **CS-03-002 (unused imports outside `__init__.py`) is already gated.** flake8
  bundles pyflakes, so `F401` is reported today: `.flake8`'s `extend-ignore` is
  `E203,E501` and does not suppress it, and the `__init__.py: F401` exemption is
  already carried there. Ruff preserves this gate rather than adding one.
- **CS-21-001 (`None` defaults for collection fields) has no ruff rule that
  matches it.** The two candidates detect something else: `RUF012` reports mutable
  *literal* class defaults (`= []`), which is closer to the inverse of what
  CS-21-001 forbids, and every `B008` finding in `vultron/` is a FastAPI
  `Depends()` default — working dependency injection, not a collection field. So
  CS-21-001 remains ungated after this decision, and a rule that actually detects
  it would have to be written as an AST check rather than selected.

CS-23-001 (blanket `except Exception` / bare `except`) is a third case kept out of
that table, and the most instructive one: it *does* have a gate. Its `verification:` names
`test/architecture/test_no_broad_except_outside_bt_update.py`, an AST scan with a
shrink-only `_DECLARED_EXCLUSIONS` allow-list — but that ratchet covers only
`vultron/core/behaviors/`. Ruff's `BLE001`, `S110` and `S112` widen the same check
to the whole tree, so for CS-23-001 this decision adds reach to an existing gate
rather than a first gate.

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
- **C — Select every rule ruff has (`--select ALL`) and pin every current
  violation into a shrink-only `per-file-ignores` baseline.** Note this is *not*
  ruff's out-of-the-box default, which selects only `E4`, `E7`, `E9` and `F` and
  reports 3,033 findings here — narrower than flake8's current coverage, so it is
  not a candidate.

## Decision Outcome

Chosen option: **B — replace flake8, isort and black with ruff, select rule
families, and declare exclusions explicitly.**

Configuration lives entirely in `pyproject.toml` under `[tool.ruff]`:

```toml
[tool.ruff]
line-length = 79                 # the retired [tool.black] value
target-version = "py312"         # IMPLTS-01-001
force-exclude = true             # pre-commit passes filenames — see below

[tool.ruff.lint]
select = [ ... families ... ]
ignore = [ ... each with its reason ... ]

[tool.ruff.lint.mccabe]
max-complexity = 10              # IMPLTS-07-008, carried from .flake8

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]         # carried from .flake8

[tool.ruff.format]
exclude = ["**/*.md"]            # ruff formats Python inside Markdown — see below
```

Four properties of the decision matter more than the specific rule list:

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

**4. Scope lives in the config, so no invocation carries path arguments.** Every
caller — the CI job, the pre-commit hook, `run-linters`, `format-code`, a
developer at a terminal — runs exactly `ruff check` and `ruff format --check`,
with no paths. This is the reason the configuration is worth getting exactly
right: today the same conceptual check is spelled four different ways across the
skill tree, and the spellings have already drifted apart (see below). Made
normative by IMPLTS-07-021.

`pyright` already demonstrates the pattern in this repo — `pyrightconfig.json`
declares `include: ["vultron", "test"]`, which is why every caller runs a bare
`uv run pyright` and none of them disagree about scope.

### Scope, and the drift that motivated moving it into the config

Path arguments in invocations are not a cosmetic problem; they had already
produced three live inconsistencies.

**black disagreed with itself.** There is no single black scope to compare
flake8 against: `black --check .` covers the whole repository in `Makefile`, the
pre-commit hook and `create-pr`, while CI runs `black --check vultron/ test/`
(`.github/workflows/python-app.yml`) and
`docs/developer/how-to/run-linters-and-formatters.md` — the page whose entire
subject is these commands — tells developers `uv run black vultron/ test/`. So
`scripts/`, `.agents/` and root-level modules were formatted by some call sites
and by neither CI gate. That is a worse fact than "formatted but never linted":
in CI they were *neither* formatted nor linted, and which guarantee you got
depended on which command you happened to run.

**flake8 covered less than black's widest spelling.** `flake8 vultron/ test/` is
consistent everywhere, so the whole-repo black call sites formatted code no
linter ever read. `create-pr` carried a four-line comment explaining that a bare
`uv run flake8` "walks the whole repo (including `scripts/`, which carries
pre-existing C901/E741 findings no other gate covers) and fails every docs PR on
debt it did not introduce" — an accurate description of debt that existed
*because* the scopes disagreed.

**Two skills disagreed about mypy.** `create-pr` runs `uv run mypy vultron` (727
files) while the AGENTS.md commit workflow runs bare `uv run mypy` (1,380 files),
so docs PRs type-check strictly less than commits do. Bare `mypy` is already the
correct form — `.mypy.ini` scopes it — and the stray argument is simply removed.

**Three call sites sit outside the skill tree** and are easy to miss when auditing
for path operands, so IMPLTS-07-021's verification names them explicitly:

- `Makefile` — a `black` target (`uv run black .`), a `flake8` target
  (`uv run flake8 ${VULTRON_DIR} ${TEST_DIR}`), a `flake8-lint` target that adds
  `--exit-zero`, and an aggregate `lint` target (`lint: black mdlint flake8-lint
  mypy`). Note what that aggregate actually wires: `flake8-lint`, the
  `--exit-zero` variant — not the `flake8` target — and no pyright. The
  `--exit-zero` form must not be carried across: a target that reports findings
  without failing is the configured-but-ungated shape this decision exists to
  remove, and it would contradict IMPLTS-07-018's zero-finding gate.
- `CONTRIBUTING.md` — "formatted with Black and linted with `flake8`. Run
  `uv run flake8 vultron/ test/`". This is the invocation new contributors copy, so
  leaving it stale teaches the wrong command to exactly the audience with no other
  source.
- `docs/developer/how-to/run-linters-and-formatters.md` — a 45-line how-to whose
  whole subject is this command set, carrying `uv run black vultron/ test/` and
  `uv run flake8 vultron/ test/`. It is the third black spelling described above,
  and the one a developer following the docs will actually use.

This decision resolves the flake8/black split by **linting the whole tracked
Python surface**, not by encoding the historical asymmetry. `ruff check` therefore
declares no `lint.exclude` at all. That adds 86 findings over the flake8 scope (29
autofixable), and it makes the `create-pr` comment above obsolete rather than
permanent.

The residue is mechanical except for the complexity gate, which is where the
widening actually costs something. **Five** functions in the newly-linted surface
exceed `max-complexity = 10` under `C901`, none of them previously seen by any
gate:

| Site | Complexity |
|---|---|
| `.agents/skills/acquire-codebase-knowledge/scripts/scan.py:801` `main` | 24 |
| `scripts/apply_story_mappings.py:33` `apply_file_mappings` | 19 |
| `scripts/velocity.py:162` `build_metrics` | 18 |
| `scripts/backfill_stories.py:193` `insert_suppress_in_yaml` | 14 |
| `scripts/migrate_spec_kinds.py:35` `migrate_file` | 13 |

These are refactors, not suppressions: raising the threshold would weaken
IMPLTS-07-008 for the whole tree to accommodate tooling scripts, and excluding
the files would reintroduce the `lint.exclude` this decision removed.

**The two tools disagree about complexity, and only ruff's answer matters here.**
Running `flake8 --select C901 --max-complexity 10` over the same surface reports
**eight** functions, adding `.agents/…/scan.py:468` `search_todos`, `:632`
`detect_containers` and `:693` `collect_code_metrics` at 11 each. Ruff's mccabe
implementation scores those three at or below the threshold and does not report
them. Since ruff becomes the gate, five is the number that will fail CI — sizing
this work from flake8's output would have over-scoped it by three functions. The
same caution applies to any other count carried over from the retired tool.

`extend-exclude` is deliberately absent: `graphify-out/` and `wip_notes/` are
gitignored and ruff's `respect-gitignore` default already covers them. Adding
redundant excludes would imply they were load-bearing.

### Two scoping mechanisms that fail silently

Both of these were found by measuring the configuration rather than reading it,
and both would have shipped a config that looks correct and is not.

**`lint.exclude` requires glob form.** `exclude = ["scripts"]` under
`[tool.ruff.lint]` resolves — `ruff check --show-settings` prints
`linter.exclude = ["scripts"]` — and has no effect, because a bare directory name
only prunes traversal in the discovery-time `exclude`, whereas `lint.exclude` is
matched against each file's path. It needs `"scripts/**"`.

Worse, **neither `--show-settings` nor `--show-files` will tell you which form you
wrote.** `--show-settings` echoes the broken value back as though it were live, and
`lint.exclude` is not reflected in `--show-files` at all: both forms list the
supposedly-excluded files identically, because `--show-files` reports discovery,
which `lint.exclude` happens after. The only signal that distinguishes them is the
finding count. So a `lint.exclude` entry must be verified by asserting on findings —
add the exclusion, confirm the count drops by exactly the findings you meant to
drop — and no `--show-*` flag substitutes for that.

**`ruff format` formats Python embedded in Markdown.** Left unscoped, no-args
`ruff format` reaches 3,576 files rather than the 1,384-file Python surface,
because it processes fenced Python in `.md`. The great majority of those Markdown
files are under `plan/history/`, which is append-only and immutable once merged
(HM-01-005); 40 of them carry a `python` fence and so are candidates for
rewriting, and 19 would actually be reformatted as the tree stands. Any of those
19 is a rerun of bug #2952, where `mdlint.sh --fix` rewrote write-once history
entries. It would also rewrite `docs/` (which has its own style gate, DF-09-001)
and the hard-linked `.agents/`/`.claude/` skill trees. Black never touched
Markdown, so `[tool.ruff.format] exclude = ["**/*.md"]` is what makes the
formatter swap faithful.

**`force-exclude = true` is required, not optional.** Ruff normally lints a file
named explicitly on the command line even when the config excludes it. Pre-commit
passes staged filenames, so without this flag the hook and the CI job would
disagree about scope in exactly the way this decision exists to prevent.

### The exclusions and their reasons

Measured 2026-09-17. Counts are recorded here — a dated decision record — and
deliberately not restated in `specs/` or `notes/` (MS-16-001).

| Excluded | Findings suppressed | Reason |
|---|---|---|
| `PLC0415` import-outside-top-level | 2,426 | Function-local imports are this codebase's cycle-break idiom. CS-05-002 calls the pattern a "last resort"; at this scale it is the norm. That contradiction is real and is tracked as #3350 — it is a premise question, not a lint question, and enabling the rule before it is answered would either bury the tree in noise or force thousands of rewrites toward an unagreed target. |
| `TC006` runtime-cast-value | 654 | Would quote the type argument of every `cast()` call. Pure churn. |
| `TRY003` raise-vanilla-args | 567 | Would require one exception class per distinct message string. |
| `PLR2004` magic-value-comparison | 412 | Overwhelmingly test literals, where a named constant reduces clarity. |
| `PLR0904`, `PLR0911`–`PLR0917` | 495 | Argument, return, branch and statement counts. `C901` at `max-complexity = 10` is this project's chosen complexity gate (IMPLTS-07-008); a second, differently-calibrated one would compete with it. |
| `G004` logging-f-string | 194 | A legitimate rule — f-strings defeat logging's lazy formatting — but the rewrite has no agreed target, because the choice between lazy `%`-args and structured `extra=` fields belongs to the structured-logging requirements (`specs/structured-logging.yaml`). Provisional, tracked as #3378. |
| `TC001`, `TC002`, `TC003` | 113 | Would force `if TYPE_CHECKING:` blocks across the tree. |
| `RET504` unnecessary-assign | 86 | Assign-then-return is more readable at the sites where it appears. |
| `RUF001`–`RUF003` ambiguous-unicode | 47 | Fires on prose and docstrings, not code. |
| `TRY300`, `SIM105`, `SIM117` | 170 | Style preferences (`else` after `try`, `contextlib.suppress`, combined `with`). Nested `with` is frequently the clearer form. |
| `UP040`, `UP047` PEP 695 syntax | 52 | Type-alias and generic-syntax modernization with no requirement behind it. |
| `PYI042` snake-case-type-alias | 35 | `snake_case` type aliases are established house style. |
| `E501`, `E203` | — | Line length and slice whitespace belong to the formatter. Carried over verbatim from `.flake8`'s `extend-ignore`. |
| `EXE` family (not selected) | 850 | `EXE001` fires on every file carrying the standard `#!/usr/bin/env python` + CMU copyright header — a file template, not a defect. Excluded by not selecting the family, so no `ignore` entry is needed. |

Selecting the remaining families across the whole tracked Python surface (1,384
files) leaves **2,219 findings**: 1,338 safe-autofixable, 305 more fixable with
`--unsafe-fixes`, and roughly 576 requiring hand work.

That surface is *nearly* but not exactly the set black covered, and the two tools'
file counts are a trap: both report **1,385**, but they are counting different
sets, and neither equals the 1,384-file tracked Python surface.

| | Count | Difference from `git ls-files '*.py'` |
|---|---|---|
| `git ls-files '*.py'` | 1,384 | — |
| `ruff check --show-files` | 1,385 | **+ `pyproject.toml`**, which ruff lints for the `RUF2xx` rules |
| `black --check .` | 1,385 | **+ `vultron/_version.py`**, gitignored (`.gitignore:145`) and skipped by ruff's `respect-gitignore` default |

Both extras are correct behaviour rather than gaps: the generated version file is
not a formatting target, and `pyproject.toml` genuinely is a ruff lint target. But
the coincidence means **no equality check between these three numbers holds**.
"ruff and black report the same count" passes by accident and proves nothing;
"ruff reports the tracked Python surface" is simply false. Any scope assertion has
to compare the file *lists*, not their lengths — for example, that
`ruff check --show-files` equals `git ls-files '*.py'` plus `pyproject.toml`
exactly.

The largest hand-work cluster is exception handling, and it is **already owned
elsewhere**. Epic #3329 covers it: #3325 eradicated broad `except Exception` from
`vultron/core/` and closed during this planning when PR #3338 merged, and #3326
carries the remainder as a scheduled task. (#3340 is adjacent but is typed `Idea`
and overlaps #3326's scope, so it is not a work item a baseline marker can point
at — which is why the markers cite #3326.) Ruff's `BLE001`, `S110` and `S112` are
therefore not new work — they
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
- Good, because CS-02-001 and CS-13-001 gain gates they have never had, and
  CS-23-001's existing gate widens from `vultron/core/behaviors/` to the whole
  tree. Not CS-21-001: no selected rule detects what it forbids (see above).
- Good, because every caller invokes the same two commands with no arguments, so a
  scope change is one edit to one file rather than a search for every spelling. The
  three live drifts described above (black's own three spellings, black vs flake8,
  and `mypy vultron` vs `mypy`) are all resolved, and `scripts/` becomes linted for
  the first time.
- Bad, because the residue is baselined as in-tree `# noqa` markers rather than
  configuration, which is visible churn in the diff. Accepted: the markers are
  what make `RUF100` a working ratchet, and they are line-precise rather than
  file-scoped.
- Bad, because `ruff format` reformats files that black formatted differently.
  Measured at 245 of 1,384 files at `line-length = 79` — the two formatters
  already agree on most of the tree, so this is a bounded mechanical diff and not
  the whole-tree rewrite it was initially assumed to be.
- Bad, because two of the scoping keys fail silently when written the obvious way
  (`lint.exclude` with a bare directory name; `format` without a Markdown
  exclusion), and in the `lint.exclude` case neither `--show-settings` nor
  `--show-files` reveals which form you wrote — only the finding count does.
  Mitigated by recording both above, with the finding-count check, so the next
  editor of this config does not rediscover them.
- Neutral, because the eight `PLR09xx`/`TRY003`/`TC00x` exclusions could each be
  revisited independently; none of them blocks anything.

## Validation

- CI runs a single `lint-ruff` job executing `ruff check` and
  `ruff format --check` (IMPLTS-07-005, IMPLTS-07-018). The `build` job gates on
  it, and the mandatory `notify-failure` wiring (CISEC-05-001) is preserved.
- A single pre-commit hook invokes ruff directly, without the
  `run-if-changed.sh` wrapper.
- **No invocation anywhere carries a path argument** (IMPLTS-07-021). The check is
  mechanical, and the search must cover every call site named above — including the
  two outside the skill tree, which are the ones a narrower grep misses:

  ```bash
  grep -rn "ruff \(check\|format\)" \
    .github/ .agents/ docs/ .pre-commit-config.yaml Makefile CONTRIBUTING.md
  ```

  No hit may carry a path operand.
- Scope is verified by comparing the file *list*, not a count:
  `ruff check --show-files` must equal `git ls-files '*.py'` plus `pyproject.toml`.
  Counting is not enough — three different numbers here coincide at 1,385/1,384
  for unrelated reasons (see above). Neither `--show-settings` nor `--show-files`
  can verify a `lint.exclude` entry at all; that one is checked on finding counts.
- `RUF100` remaining selected is the mechanism that validates the baseline:
  a stale marker fails the gate (IMPLTS-07-020).
- The absence of `.flake8`, `[tool.black]` and `[tool.isort]`, and of the three
  dependencies, is the evidence that this is a replacement and not an addition.
  CS-15-001 is about code symbols rather than tooling, but the same reasoning
  applies: a superseded tool left in place as a fallback is the config-level form
  of the compatibility shim that requirement prohibits.

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

### C — Every rule ruff has, with a shrink-only `per-file-ignores` baseline

- Good, because CI is green on arrival with no cleanup at all, and new code is
  clean by default.
- Bad, because `--select ALL` yields **64,254** findings on this tree, dominated by
  categories this project has deliberately chosen against — most of the volume is
  missing-docstring and annotation rules that no requirement asks for. A baseline
  that large is not a debt record; it is a way of not making the decision. For
  scale, the same measurement puts option B's selected families at 7,412 findings
  before its `ignore` list and **2,219** after it.
- Bad, because `per-file-ignores` is file-scoped, so fixing one of several
  violations in a file is invisible — the "silent progress fails" property is lost
  and has to be rebuilt as a bespoke test.

## More Information

- Source idea: #2199, with corroborating evidence from #3244 / #3194.
- **Implementation of this decision: #3352.** Nothing described here exists in the
  tree yet — ruff is not installed, `[tool.ruff]` is absent, and flake8, black and
  isort remain the live gate until that issue lands. #3353 carries the
  exception-adjacent rules whose baseline markers this decision creates.
- Ratchet-shape precedent, and the evidence that non-forcing ratchets stall:
  ADR-0064 § "Ratcheting across the steps".
- Precedent for a lint-tooling decision recorded as an ADR: ADR-0092.
- Follow-on questions deliberately left open, each cited as the reason for a
  provisional exclusion: #3350 (`PLC0415` vs CS-05-002) and #3378 (`G004` vs the
  structured-logging requirements).
- Exception-handling findings are owned by epic #3329, not by this decision:
  #3325 (closed via PR #3338), #3326.
- Policy write-up for future maintainers: `notes/lint-tooling.md`.
- All measurements in this record were taken on 2026-09-17 with ruff 0.16.8, at
  `origin/main` `9ea51249d` except the per-exclusion counts in the table above,
  taken a few hours earlier at `d2d5df9b2`. #3325 landed between the two, which
  moved the exception-rule counts by roughly a percent of the total. The
  `ruff format` file counts were taken on the working tree rather than at
  `9ea51249d`, so they include the three Markdown files this decision itself adds;
  that is why they do not reproduce exactly from a clean checkout of either commit.
  All of these are point-in-time evidence for the decision, not requirements —
  every count here will drift, and none of them is restated in `specs/` or
  `notes/` (MS-16-001).

Generated spec requirements: `tech-stack.yaml` IMPLTS-07-017 through
IMPLTS-07-021, with IMPLTS-07-005 and IMPLTS-07-008 amended and IMPLTS-07-001,
IMPLTS-07-004, IMPLTS-07-013 and IMPLTS-07-014 retired.
