---
id: "run-tests"
title: "Run canonical test-suite and capture summary"
description: "Run the repository's canonical pytest command and capture the final summary lines used by CI and automation."
author: "CERTCC / Vultron"
tags:
  - testing
  - ci
shell: "zsh"
commands:
  - 'logs="/tmp/vultron-$(basename "$(git rev-parse --show-toplevel)")"; git fetch -q origin main || { echo "fetch failed — stop and report"; exit 1; }; gate=$(PYTHONPATH= uv run targeted-tests --base origin/main --pytest); rc=$?; [ "$rc" -eq 0 ] && { eval "$gate" > "$logs-gate.log" 2>&1; rc=$?; tail -20 "$logs-gate.log"; }; echo "exit: $rc"; (exit $rc)'
inputs:
  - name: repo_root
    description: "Repository root"
    default: "."
outputs:
  - name: pytest_summary
    description: "The last 20 lines of pytest output (summary and short failure traces)"
  - name: exit_code
    description: "pytest's own exit status, printed as `exit: N` and returned as the command's status"
---

# Skill: Run Tests

**There is one local gate, and it is targeted.** Every local test gate — a
Pull Request's first push, a fix commit, a conflict merge — runs the test set
`targeted-tests` derives from a diff (PAD-18-001, PAD-18-002, PAD-18-015). No
local gate runs the whole unit or integration suite: CI runs both on every
push, faster than a 2-CPU slot does, and GitHub's required `CI gate` refuses
the merge until that run passes (PAD-18-003, PAD-18-008, ADR-0179). The gate
command is in § "The Targeted Gate" below.

| Run | Command |
|---|---|
| The gate (every local gate) | see § "The Targeted Gate" |
| One file, while writing it | `uv run pytest <path> -n 0` |
| The whole suite | CI's, not yours. `.github/workflows/python-app.yml` runs it on every push; a human can run it from [docs/developer/how-to/run-tests.md](../../../docs/developer/how-to/run-tests.md) |

The shape of every gate command is the same: **redirect, capture `$?`
immediately, tail the log, print the code last, then re-raise it.** `rc=$?`
must come directly after the
redirected command — any other command in between overwrites `$?`. The trailing
`(exit $rc)` is what makes the whole statement carry pytest's status, so the
command is safe to chain or to use as a gate.

`timeout -k 30 1800` is the run's wall-clock ceiling. Three outcomes look alike
in a short tail; tell them apart by the `exit:` line and the log:

| You see | It means |
|---|---|
| `exit: 124` (137 if the `-k` kill was needed) | The run hung and was killed. No test verdict. Report it with the log's last lines; do not re-run to "see if it passes". |
| `exit: 1` and `worker 'gwN' crashed while running <test>` | A worker died. `--max-worker-restart=0` (`addopts`) ends the run here instead of hanging. Read `/sys/fs/cgroup/memory.events`: a risen `oom_kill` means the named test is not the cause. |
| `exit: 1` and `Failed: Timeout (>Ns)` | That one test hit its per-test ceiling. The rest of the run still ran and is summarized. |
| `exit: 127` and `timeout: command not found` | No test ran: the host has no `timeout` (stock macOS). Run the gate in the devcontainer. |

See `notes/testing-pitfalls.md` § "A Dead xdist Worker Hung the Run".

`uv run python .agents/skills/shared/run-heavy.py` runs the gate in one of
this host's heavy-check slots (#5947). Every slot container on the host shares
one Docker VM, and each `-n auto` run sizes itself to its own container without
seeing the others, so a few slots cap how many run at once. The wrapper comes
before `timeout`, so time spent waiting is not charged to the run. While every
slot is taken it writes one `run-heavy: all N heavy-check slots on this host are
busy; waiting (...)` line, naming the holders, at the top of the log: a slow
start with that line is a queue, not a hang. Its exit status is the command's,
so the table above holds, plus one row:

| You see | It means |
|---|---|
| `exit: 75` and `run-heavy: gave up after 3600s` | No test ran: no slot came free within the wrapper's wait limit. Find the holders the wait line names before rerunning. |

`-n auto` runs the selected files on `pytest-xdist` workers. `test/conftest.py` sizes
`auto` to the container's cgroup CPU and memory limits
(`test/support/xdist_workers.py`): a worktree slot is capped by `SLOT_CPUS`
and `SLOT_MEMORY` (`start-dev.sh`), while `nproc` reports every host core, and
twelve workers in a 2-CPU, 6 GiB slot were OOM-killed mid-run. Set
`PYTEST_XDIST_AUTO_NUM_WORKERS` to override. Drop `-n auto` (or pass `-n 0`)
for a single-file run while writing it, where starting workers costs more
than it saves.

## The Targeted Gate

Every local test gate is this command. `targeted-tests` derives the set from
a diff: the test files that import a changed symbol, the mirror test file of
each changed module, each changed test file, and always `test/architecture/`
and `test/metadata/` (PAD-18-002).

```bash
logs="/tmp/vultron-$(basename "$(git rev-parse --show-toplevel)")"  # one set per worktree
git fetch origin <base> || { echo "fetch failed — stop and report"; exit 1; }
gate=$(PYTHONPATH= uv run targeted-tests --base origin/<base> --pytest); rc=$?
[ "$rc" -eq 0 ] && { eval "$gate" > "$logs-gate.log" 2>&1; rc=$?; tail -20 "$logs-gate.log"; }; echo "exit: $rc"; (exit $rc)
```

`exit 1`, not `false`, on a failed fetch: the block has no `set -e`, so a
`false` would let the next line derive the gate against a stale `origin/<base>`
and the block's final `(exit $rc)` would report the gate's status — a passing
`exit:` line over a fetch that did not happen.

The printed command starts with `run-heavy.py`, so the gate takes one of the
host's heavy-check slots, and then runs under the wall-clock ceiling. It
carries `-m ""`, so integration-marked tests among the selected files are not
deselected by the `addopts` default (PAD-18-011).

Where it runs, with the scope each one passes:

| Gate | Scope | Rule |
|---|---|---|
| A PR's first push, in `create-pr` Phase 3 | `--base origin/main` | PAD-18-001 |
| A fix commit, in `pr-execute` Phase 5 Step 3 | `--base origin/<base>` | PAD-18-002 |
| A conflict merge | `--paths <conflicted files>` | PAD-18-015 |

A skill that hands off to `create-pr` runs the linters and no suite of its
own (PAD-18-017); it may run the specific test files it is writing while it
works. A PR that changes no Python is gated by the linters and the CI mirror,
with no test run at all, and its `Suite runs:` counts both start at zero
(PAD-18-006, PAD-18-010, PAD-18-016).

**No scope escalates it.** Whatever paths the diff touches, the printed
command names files (PAD-18-003). When the diff includes shared test
infrastructure — `conftest.py`, `pyproject.toml`, `uv.lock`,
`vultron/__init__.py`, or a test fixture, factory, helper or data file —
`targeted-tests` names that path on stderr as one no targeted set bounds, and
the gate is the set it could select plus the always-selected directories
(PAD-18-012). CI's required full run covers the reach beyond it. An
integration-bearing path is gated by its importers like any other
(ADR-0143).

`targeted-tests` cannot see CI: when the fix is for a CI failure in a test
outside the printed set, append that test's file to the printed command
(PAD-18-013).

## Constraints

- Run exactly once per validation cycle; do not use `-q` or change output formatting.
- Keep the gate command's shape. A command may tail a longer window than the
  gate's `-20`, but must keep the rest intact.
- **Never end a validation command with a pipe.** A pipeline exits with its
  *last* stage's status, so `… | tail`, `… | tee … | tail`, `… | head`, and
  `… | wc` all report 0 no matter how pytest exited — a killed or failed run
  reads as success. This applies to every gate command (`pytest`, `mkdocs
  build --strict`, `ruff`, `mypy`, `markdownlint`), not just pytest, and to
  the bare `2>&1 | tail -5` form as much as to `tee | tail`.
  Redirect, capture `$?`, then re-raise it:

  ```bash
  <gate command> > /tmp/x.log 2>&1; rc=$?; tail -5 /tmp/x.log; echo "exit: $rc"; (exit $rc)
  ```

- **The `exit:` line is authoritative, not the tail.** Read it first. If the
  redirect itself fails (read-only `/tmp`, exhausted disk, `noclobber`), the
  command never runs and `tail` prints the *previous* run's summary — a
  passing-looking tail above a non-zero `exit:`. Trust the code.
- `filterwarnings = ["error"]` in `pyproject.toml` — warnings are test errors; fix root
  cause, do not suppress.
- Integration tests are excluded from the default interactive run by
  `addopts = "-m 'not integration'"`. Keep the gate's `-m ""` so
  integration-marked tests among the selected files still run (PAD-18-011).
- Treat all failures as branch-owned by default; clean-base proof is required before
  classifying as pre-existing.
- **Never re-run the gate to get more output.** Full pytest output is written
  to `"$logs-gate.log"`. Read or grep that file instead.
