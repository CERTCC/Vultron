---
name: deepen-context
description: >
  Load task-specific context after the target issue is known. The caller
  passes focus hints (e.g., "wire layer", "BT integration", "embargo
  lifecycle") and this skill reads the relevant glossary sections, notes
  files, ADRs, and codebase reference files, and loads the governing specs
  (emitting a Spec manifest). Run after orient-agent, once the issue to be worked has been
  selected and read. Replaces study-project-docs Phase B.
---

# Skill: Deepen Context

Load task-specific context after the target issue is known. The caller
provides focus hints; this skill reads only what is relevant.

## Inputs

The calling skill passes one or more focus hints describing what area of
the codebase or design the task touches. Examples:

- `"wire layer"` — AS2 parsing, extraction, activity patterns
- `"BT integration"` — behavior tree nodes, blackboard, py_trees
- `"embargo lifecycle"` — EM state machine, PEC transitions
- `"case state model"` — RM/CS/EM state machines, CaseStatus
- `"adapter layer"` — FastAPI inbox, SQLite data layer, emitters
- `"testing"` — pytest fixtures, test data quality, integration tests

The caller also passes the **spec floor**: every spec ID or group ID cited
in the issue, plan, or PR (for example, the issue's `Governing specs:`
line). Pass an empty floor explicitly when none are cited.

## Procedure

### Step 1 — Read relevant glossary sections and notes

**Glossary.** The term index from `orient-agent` gives each section of
`docs/reference/glossary.md` a line range. Read the sections matching the
focus hints (read by offset/limit, not the whole file). Also read
**Flagged Ambiguities** when the task names, renames, or introduces a domain
term.

**Notes.** `notes/README.md` is the index of active design notes, with a
**Load when** line per file. It is ~1000 lines — larger than most notes it
indexes — so grep it for the focus-hint terms, or read its **Load when**
lines, rather than reading it whole. Then read the `notes/*.md` files it
points at. Most tasks need 1–3.

Always-relevant notes for implementation work:

- `notes/architecture-hexagonal.md` — layer rules and import constraints
- `notes/codebase-structure.md` — common pitfalls and file organization
- `notes/triggers-test-coverage.md` — **always read when the task adds or
  touches any `SvcXxxUseCase` class**; documents which trigger use-cases
  require a dedicated test file under `test/core/use_cases/triggers/`

Read additional notes files based on focus hints. When in doubt, read
rather than skip — missing context causes incorrect implementation.

### Step 2 — Read relevant ADRs

Read the ADR index (`docs/adr/index.md`), then identify and read any ADRs
relevant to the current task. Focus on ADRs whose titles match the task's
domain (e.g., behavior trees, hexagonal architecture, ActivityStreams,
DataLayer). Read the full ADR file for any decision that is in scope — except
that the largest ADRs run past 1000 lines, so for those grep for the task's
terms and read the sections around the hits.

**Weight each ADR by how settled it actually is — do not treat every ADR as
equally solid fact.** An ADR that is genuinely `status: accepted`, not
contradicted by its own prose, and not violated by the code prevents
re-litigating a settled choice: build on it, don't reopen it. But an ADR is
**challengeable — validate it against the current code before relying on it**
when any of these hold:

- its `status:` is blank, `proposed`, `deprecated`, or `superseded`;
- its `status:` says `accepted` but the prose hedges (e.g. "formed in sand",
  "not concrete", "provisional", "forward-looking", "SHOULD refine this ADR");
- the section it sits under in `docs/adr/index.md` disagrees with its own
  `status:` field;
- the code you are about to touch appears to contradict what the ADR asserts.

When a relevant ADR is challengeable, say so to the caller and check the claim
against the code rather than inheriting the premise. If the ADR looks wrong or
stale — not just imprecise for your task — that is a landmine worth routing to
the `decision-audit` skill rather than quietly working around it.

### Step 3 — Load governing specs (REQUIRED)

This step runs after notes and ADRs because they cite spec IDs and sharpen
the focus hints; it runs before the code scan so requirements shape what
the scan looks for. Do not skip it, even for small tasks.

Always pass `--text`. Without it every load is a single line of JSON, so
printing one shows a truncated prefix of one unreadable token.

1. **Cross-cutting (always):**

   ```bash
   PYTHONPATH= uv run spec-dump --cross-cutting --text
   ```

2. **Floor (always):** load every spec ID the caller passed, plus their
   dependencies.

   ```bash
   PYTHONPATH= uv run spec-dump --ids <ID>,<ID> --deps --text
   ```

   Group IDs in the floor (e.g. `CS-02`) go to `--group` instead of `--ids`.

   The floor is every spec or group ID cited **anywhere** in the issue, plan,
   or PR — a `Governing specs:` line, a `References:` line, or body prose all
   count. An issue with no such line has an *empty* floor, not a missing step:
   record `none — <reason>` and carry on. Do not treat an absent line as
   licence to skip selection; on a measured run the floor was empty and the
   two requirements that most constrained the change were found only by the
   backstop.

3. **Selected:** from the spec map loaded by `orient-agent`, choose the
   topics and groups that match the focus hints **and** the issue text.
   When in doubt, include the group — a missed requirement costs more
   than extra context.

   ```bash
   PYTHONPATH= uv run spec-dump --topic <A>,<B> --text
   PYTHONPATH= uv run spec-dump --group <ARCH-01>,<CS-02> --text
   ```

   `--text` gives id, priority, and statement. Drop it for a specific group
   when you need rationale, dependencies, tags, or verification to interpret
   it — that form is JSON, so read it with `jq` rather than printing it.

4. **Emit a Spec manifest** to the caller in exactly this format:

   ```text
   Spec manifest
   Loaded (floor): <ids from issue/plan/PR, or "none — <reason>">
   Loaded (cross-cutting): <the topic IDs --cross-cutting returned>
   Loaded (selected): <topic/group id> — <one-line reason>; ...
   Considered, skipped: <group id> — <one-line reason>; ...
   ```

   List every group ID in full: `RMB-01 RMB-02 RMB-03`, never a range like
   `RMB-01..03`, which nothing parses.

   The manifest makes spec selection auditable: reviewers can see what was
   loaded and what was deliberately skipped. Callers carry the manifest into
   the PR body, and check it against the code with `spec-backstop` (below).

**Backstop — resolving the manifest against the changed files.** Selection is
judgment; `spec-backstop` derives the same question from the code
independently. Save the manifest to a per-issue path so concurrent agents do
not overwrite each other, then run it:

```bash
# Before any code exists — the files the work will touch:
PYTHONPATH= uv run spec-backstop --manifest /tmp/spec-manifest-<issue>.txt \
  --paths <file> <file>

# Once a diff exists, drop --paths; the branch diff is the default:
PYTHONPATH= uv run spec-backstop --manifest /tmp/spec-manifest-<issue>.txt
```

Run it here with `--paths`, before writing code — that is where a missed
requirement is still cheap to act on. `build` and `bugfix` re-run it against
the real diff before they finish.

It derives the spec groups governing the code (tests that import a changed
symbol, mirror-path tests, statements naming a changed module or symbol,
markers in changed tests) and exits 1 listing every **MUST** group the
manifest neither loaded nor skipped. For each one, load it
(`spec-dump --group <G> --text`), check the change against it, then add it to
`Loaded (selected)` or `Considered, skipped` with a reason. Re-run until exit
0. **INFO** groups are advisory: incidental importers, hub symbols, catch-all
suites, and SHOULD/MAY-only groups. Skim them; you are not required to resolve
them.

**What a pass does and does not mean.** It is a floor, not a ceiling. The
backstop only sees what the code already says, so it is silent on a
requirement no changed file or test names yet — on a measured run it missed
the two groups most central to the change while flagging fourteen peripheral
ones. Exit 0 means nothing derivable was missed; it never means the selection
is complete. Two notes weaken it further, and both are printed:
`no deterministic signal for: <file>` (that file's selection rests on your
judgment alone) and `no Python source in the diff` (a docs-only or
YAML-only change, where the tool derives nothing at all).

Do **not** run `spec-dump` with no filters, and do not read raw
`specs/*.yaml` files directly.

### Step 4 — Read relevant codebase reference files

Read from `docs/reference/codebase/` based on task scope:

| File | Read when |
|---|---|
| `ARCHITECTURE.md` | Always for implementation tasks |
| `STRUCTURE.md` | When navigating unfamiliar modules |
| `CONVENTIONS.md` | When writing new code |
| `STACK.md` | When adding or evaluating dependencies |
| `TESTING.md` | When writing or reviewing tests |
| `CONCERNS.md` | When assessing risk or technical debt |
| `INTEGRATIONS.md` | When working on external integrations |

### Step 5 — Scan the codebase

**Compose-before-create (blocking pre-coding step — all domain types):**
Load `.agents/skills/shared/compose-before-create.md` and apply the
per-subsystem search targets for every subsystem the task touches. Use the
focus hints to determine which subsystems are in scope, then run the
corresponding searches before reading any target implementation file:

| Focus hint keyword | Subsystem to search |
|---|---|
| use cases, handler, trigger | `vultron/core/use_cases/` |
| wire layer, AS2, pattern, activity | `vultron/wire/as2/` |
| adapter, FastAPI, delivery, emitter | `vultron/adapters/` |
| BT, behavior tree, node, blackboard | `vultron/core/behaviors/` |
| demo, scenario, helper | `vultron/demo/helpers/` |

Do not read any target implementation file until this search is complete. If
an existing artifact covers the requirement, compose or subclass it — do not
re-implement.

**BT integration (BTC-01-001, BTND-07-005):** After the compose-before-create
scan, also apply the base-class and AC-1 compliance checks from
`vultron/core/behaviors/AGENTS.md` § "Compose Before Create: Node Discovery
Gate".

Search `vultron/` and `test/` directly (grep, code search) — this is the
default. Do not assert missing functionality without evidence from code
search.

**Graphify (optional seam-tracing aid).** When the task spans a seam (e.g.
wire layer → BT integration), the graph can trace the connection. Check it
first — the graph is gitignored, per-worktree, and often stale:

```bash
bash .agents/skills/shared/graph-freshness.sh
```

Only on exit 0, use `graphify path "<ConceptA>" "<ConceptB>"` or
`graphify explain "<ClassName>"`, then verify against source. Do not rely on
community names (they degrade as the graph is updated) or on `graphify query`
output (it truncates on this graph's size), and verify any count with grep.

## Notes

- Focus hints come from the calling skill after it has selected and read
  the target issue. For `build` and `bugfix`, the issue body describes
  what is needed; use that as the basis for hints, and pass its
  `Governing specs:` line as the spec floor.
- For `plan-issue`, this skill runs at Phase 3, *before* the grill-me
  interview at Phase 4, so the first pass has only the issue text to work
  from. Re-invoke it after the interview with the areas grill-me surfaced as
  additional hints, carrying the same floor.
- **Planning and docs-only work still needs a manifest.** Step 3 is not
  conditional on writing code: the Task bodies `plan-issue` creates draw
  their `Governing specs:` lines from the manifest, so skipping it leaves
  every downstream build with an empty floor. Run the backstop with
  `--paths` naming the files the plan or fix will touch. For a docs-only
  change it will report that it derived nothing — that is expected, and it
  means your selection is the only check.
