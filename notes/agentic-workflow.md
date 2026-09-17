---
title: Agentic Development Workflow
status: active
description: >
  Documents the skill-based agentic development pipeline used in this project:
  ingest-idea, learn, update-plan, and build. Explains the inputs, outputs,
  and priority-interrupt loop that governs when each skill runs.
related_notes:
  - notes/append-only-file-handling.md
  - notes/agents-md-structure.md
  - notes/git-workflow-pitfalls.md
related_specs:
  - specs/build-workflow.yaml
  - specs/history-management.yaml
---

# Agentic Development Workflow

This project uses a four-skill pipeline for AI-assisted development. Each
skill has a clearly bounded scope, well-defined inputs and outputs, and a
defined place in a **priority-interrupt loop** that governs execution order.

The pipeline is designed to be automatable: an orchestrating agent can inspect
file-change signals to decide which skill to run next, always resolving
higher-priority steps before lower-priority ones.

---

## File Roles in the Pipeline

| File | Role | Ephemeral? |
|---|---|---|
| GitHub Idea-type issues | Raw human ideas awaiting ingestion | Yes — processed and closed by `ingest-idea` |
| `plan/history/` | Archive of processed ideas, tasks, learnings | Permanent (append-only, chunked) |
| `specs/*.yaml` | Authoritative requirements | Permanent |
| `notes/*.md` | Durable design insights | Permanent |
| `AGENTS.md` | Agent conventions and patterns | Permanent |
| GitHub Project #24 | Authoritative priority scheduling (Now/Next/Later/Someday) | Live — updated via API |
| GitHub Task/Subtask Issues | Pending + in-progress tasks | Yes — closed when PR merges |
| `plan/incoming/learnings/` | Ephemeral build/bugfix observations (individual files) | Yes — files moved to history by `learn` |
| `vultron/`, `test/` | Implementation | Permanent |

---

## Incoming Learnings Queue Content Policy

`plan/incoming/learnings/` is the **exclusive upstream channel** from
code-executing skills (`build`, `bugfix`) to the `learn` skill.

Each observation is recorded as an individual file (`YYYYMMDD-SLUG.md`) with
YAML frontmatter matching the history entry format. Using individual files
instead of a shared flat file eliminates merge conflicts when multiple PRs
each have an observation to record.

### What belongs here

The queue is narrow by design. A finding gets a learning file **only** when it
is one of two things (tag it with the matching `signal:` frontmatter field, per
BW-07-002):

- `spec-gap` — behaviour implemented in code with no corresponding spec entry.
  Only externally-observable or protocol-visible behaviour qualifies; file
  locations, naming conventions, and agent guidance go to `AGENTS.md` instead
- `spec-ambiguity` — a requirement was unclear; record what interpretation was
  made so `learn` can clarify it
- `spec-contradiction` — two requirements appeared to conflict; record which
  were at odds and how the conflict was resolved
- `theme-candidate` — a general claim you believe but cannot verify from a
  single instance. It stays queued until a second independent witness
  corroborates it (BW-07-005); an uncorroborated candidate is archived
  unpromoted after 30 days (BW-07-007)

`learn` processes the `spec-*` signals before `theme-candidate` and untagged
entries (BW-07-003).

Everything else is **routed at discovery to a nearer owner, not queued**
(BW-07-004). Before completing a `build` or `bugfix` session the agent MUST run
the upward-reflection checklist (BW-07-001) — see
[`upward-reflection.md`](../.agents/skills/shared/upward-reflection.md) for the
full routing table — and send each triggered item to exactly one destination:

- Something that exists but is wrong → a GitHub `type:Concern` issue
- Something that should exist but does not → a GitHub `type:Idea` issue
- A broken tool, skill, or tracking artefact → a fix applied in the same session
- A narrow but true fact about the code → an assertion at the site (regression
  test, type annotation, or comment) in the same session
- A code-review finding in a file the change did not touch → a GitHub
  `type:Bug`/`type:Concern` issue, filed in the session that surfaced it, never
  a learning file or a PR-comment advisory (BW-07-009)

The signal values `design-question`, `concern`, `tooling-issue`, and
`process-issue` are **retired** (BW-07-002): they all named findings with a
definite owner and action, so they are now routed above rather than queued. The
`append-history` CLI rejects them for new entries and accepts them only when
parsing pre-existing archived files. A decision that was made, applied, and
shipped within the session — asking nothing of any future reader — is not a
learning at all (BW-07-008); its record is the commit, the diff, and the PR body.

### What does NOT belong here

- Completion summaries ("Task X is done") → use `uv run append-history implementation`
- Status updates ("I completed Y and Z") → use `uv run append-history implementation`
- Documentation of finished work → use `append-history` or `notes/`
- `update-plan` gap-analysis observations → write directly to `notes/*.md`

### File format

```yaml
---
title: "Short observation title"
type: learning
timestamp: 'YYYY-MM-DDTHH:MM:SS+00:00'
source: YYYYMMDD-SLUG
---

Observation body text.
```

### Lifecycle

```text
build/bugfix run
  → creates plan/incoming/learnings/YYYYMMDD-SLUG.md (committed in the PR)

learn run
  → each file promoted to specs/*.yaml, notes/*.md, or AGENTS.md
  → promotion note appended to file body
  → uv run append-history --from-file <path>  ← moves file to history, deletes source

After learn completes:
  plan/incoming/learnings/ contains only .gitkeep (ideally empty)
  plan/history/YYMM/learning/*.md contains the archived originals
```

See `specs/build-workflow.yaml` (BW-01 through BW-06) for the normative
requirements.

---

## Design Decisions

| Question | Decision | Rationale |
|---|---|---|
| Why separate `ingest-idea` from `learn`? | External ideas and internal build lessons are different sources with different quality gates | Ideas need a grill-me interview; build lessons are already structured enough to promote directly |
| Why is `update-plan` distinct from `build`? | Plan maintenance is a research task; execution is a coding task | Mixing them produces plans that drift from specs |
| Why restart the loop after each skill? | Higher-priority skills may be triggered by a lower-priority skill's outputs | Ensures design always precedes planning, planning always precedes building |
| Why no branching inside skills? | Clean boundaries enable future automation of the loop | A BT or script can inspect file-change signals to trigger the right skill |
| Why rename `IMPLEMENTATION_NOTES.md` to `BUILD_LEARNINGS.md`? | The old name implied general design notes; the new name signals a specific, focused role: a queue of code-execution observations for `learn` to promote | See `specs/build-workflow.yaml` BW-01-001 |
| Why not let `build` write directly to `notes/`? | `build`'s job is coding; documentation curation is `learn`'s domain. `BUILD_LEARNINGS.md` is the upstream channel for `build` to communicate observations; `learn` decides what to do with them | BW-01-001, BW-01-002 |
| Why delete (not strike-through) processed learnings? | `BUILD_LEARNINGS.md` is a queue, not an archive. Processed entries live in `plan/history/` via `append-history learning`. Keeping the queue clean prevents accumulation of stale noise | BW-02-002 |

---

## Large Migration Tasks: Partition by Node Shape (Type), Then Domain for Size

For tasks that migrate many nodes (e.g., Ports adoption), classify nodes by their
structural shape first (trivial reparent / read-only extra inputs / complex
output ports), then split by domain only to balance PR size. "Each PR should be a
lot of the same thing." See ISSUE-1809 for the typed-Ports chain decomposition as
the reference example.

### A single-pass mechanical refactor can exhaust the fork agent's turn limit

A fork/sub-agent runs under a hard turn cap (200 turns). A purely mechanical
edit that is nonetheless spread across enough files will hit it: in ISSUE-2490,
replacing ~120 `isinstance(VulnerabilityCase)` guards across ~60 files ran the
fork out of turns before completion, leaving a handful of files uncommitted and
some downstream `pyright` errors unaddressed. The main agent had to inspect the
stopped state and finish by hand.

Two mitigations, applied before dispatching the agent:

- **Batch by subsystem**, not one 60-file pass — e.g. `behaviors/` first, then
  `use_cases/`, then `services/` — so each batch fits comfortably inside one
  agent's budget and commits cleanly.
- **Script the mechanical part** with `sed`/`awk` (or a codemod) and reserve the
  agent for edge-case handling and the type-checker fallout only. The
  substitution itself does not need an LLM; the judgment at the boundaries does.

Corollary for the dispatching agent: after any large fork-run refactor, verify
the end state (uncommitted files, remaining occurrences, `pyright`) rather than
trusting the fork's completion report — a turn-capped stop looks like a finish.

Source: ISSUE-2490
