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
  - 'log="/tmp/vultron-$(basename "$(git rev-parse --show-toplevel)")-tests.log"; timeout -k 30 1800 uv run pytest -n auto --tb=short > "$log" 2>&1; rc=$?; tail -5 "$log"; echo "exit: $rc"; (exit $rc)'
inputs:
  - name: repo_root
    description: "Repository root"
    default: "."
outputs:
  - name: pytest_summary
    description: "The last 5 lines of pytest output (summary and short failure traces)"
  - name: exit_code
    description: "pytest's own exit status, printed as `exit: N` and returned as the command's status"
---

# Skill: Run Tests

| Suite | Command |
|---|---|
| Unit (default) | `log="/tmp/vultron-$(basename "$(git rev-parse --show-toplevel)")-tests.log"; timeout -k 30 1800 uv run pytest -n auto --tb=short > "$log" 2>&1; rc=$?; tail -5 "$log"; echo "exit: $rc"; (exit $rc)` |
| Integration | `log="/tmp/vultron-$(basename "$(git rev-parse --show-toplevel)")-tests.log"; timeout -k 30 1800 uv run pytest -m integration -n auto --tb=short > "$log" 2>&1; rc=$?; tail -5 "$log"; echo "exit: $rc"; (exit $rc)` |
| All | `log="/tmp/vultron-$(basename "$(git rev-parse --show-toplevel)")-tests.log"; timeout -k 30 1800 uv run pytest -m "" -n auto --tb=short > "$log" 2>&1; rc=$?; tail -5 "$log"; echo "exit: $rc"; (exit $rc)` |

The shape is always the same: **redirect, capture `$?` immediately, tail the log,
print the code last, then re-raise it.** `rc=$?` must come directly after the
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

`-n auto` runs the suite on `pytest-xdist` workers. `test/conftest.py` sizes
`auto` to the container's cgroup CPU and memory limits
(`test/support/xdist_workers.py`): a worktree slot is capped by `SLOT_CPUS`
and `SLOT_MEMORY` (`start-dev.sh`), while `nproc` reports every host core, and
twelve workers in a 2-CPU, 6 GiB slot were OOM-killed mid-run. Set
`PYTEST_XDIST_AUTO_NUM_WORKERS` to override. Drop `-n auto` (or pass `-n 0`)
for a targeted single-file run, where starting workers costs more than it
saves.

## Pre-PR Validation (create-pr only)

The full local gate runs **exactly once per tree state**, before a Pull
Request's first push, in `create-pr` Phase 3 (PAD-18-001, PAD-18-008): it is
re-run only after a fix changes the tree. A skill that hands off to
`create-pr` runs the linters and does not run these suites itself; it may run
the specific test files it is writing or changing while it works. The gate is
both suites:

```bash
logs="/tmp/vultron-$(basename "$(git rev-parse --show-toplevel)")"  # one set per worktree
timeout -k 30 1800 uv run pytest -n auto --tb=short > "$logs-unit.log" 2>&1; rc=$?; tail -5 "$logs-unit.log"; echo "exit: $rc"; (exit $rc)
timeout -k 30 1800 uv run pytest -m integration -n auto --tb=short > "$logs-integration.log" 2>&1; rc=$?; tail -5 "$logs-integration.log"; echo "exit: $rc"; (exit $rc)
```

Run the block as one shell command, so `logs` is set for each line. The
log names carry the worktree's directory name because parallel sessions
share `/tmp`: a fixed name lets one session read, or overwrite, another
session's run.

The first command covers the unit suite (integration tests excluded by
`addopts = "-m 'not integration'"`). The second explicitly runs the
integration suite. Both must pass; a branch that only breaks integration
tests must not reach a non-draft PR. A PR that changes no Python is gated by
the linters alone, and its `Suite runs:` full count starts at zero
(PAD-18-006).

## After the First Push (targeted gate)

Once a PR is pushed, CI runs the full suite on every push (ADR-0126). A local
fix commit is gated by the linters plus the **targeted set** for the branch
diff (PAD-18-002), not by the full suite:

```bash
logs="/tmp/vultron-$(basename "$(git rev-parse --show-toplevel)")"  # one set per worktree
git fetch origin <base> || { echo "fetch failed — stop and report"; false; }
gate=$(PYTHONPATH= uv run targeted-tests --base origin/<base> --pytest); rc=$?
[ "$rc" -eq 0 ] && { eval "$gate" > "$logs-gate.log" 2>&1; rc=$?; tail -20 "$logs-gate.log"; }; echo "exit: $rc"; (exit $rc)
```

The set always includes `test/architecture/` and `test/metadata/`.
`targeted-tests` escalates to the full suite itself (its `--pytest` output
becomes `pytest -m ""`) only when the branch diff touches shared test
infrastructure; an integration-bearing path is gated by its importers, and
CI runs the rest (PAD-18-003, ADR-0143). It cannot see CI: when the fix is
for a CI failure in a test outside a printed targeted set, append that test's
file to the printed command rather than running the full suite. Never append
to a `full` command: it runs every test, and a path would narrow it to one
file. `pr-execute`
Phase 5 Step 3 is the canonical caller.

## Constraints

- Run exactly once per validation cycle; do not use `-q` or change output formatting.
- Do not change `tail -5` in the pre-PR commands above. A command that tails a
  longer window (the targeted gate and `pr-execute` use `-20`) may do so, but
  must keep the rest of the shape intact.
- **Never end a validation command with a pipe.** A pipeline exits with its
  *last* stage's status, so `… | tail`, `… | tee … | tail`, `… | head`, and
  `… | wc` all report 0 no matter how pytest exited — a killed or failed run
  reads as success. This applies to every gate command (`pytest`, `mkdocs
  build --strict`, `ruff`, `mypy`, `pyright`, `markdownlint`), not just
  pytest, and to the bare `2>&1 | tail -5` form as much as to `tee | tail`.
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
- Integration tests are excluded from the default interactive run; always run
  `-m integration` explicitly in pre-PR validation, and keep the targeted
  gate's `-m ""` so integration-marked tests in the set still run.
- Treat all failures as branch-owned by default; clean-base proof is required before
  classifying as pre-existing.
- **Never re-run the test suite to get more output.** Full pytest output is
  written to `"$log"` (or `"$logs-unit.log"` /
  `"$logs-integration.log"` when both suites run, `"$logs-gate.log"`
  for the targeted gate). Read or grep those files instead.
