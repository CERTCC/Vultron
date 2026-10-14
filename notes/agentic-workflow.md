---
title: Agentic Development Workflow
status: active
kind: guidance
description: >
  Rules for the skill-based agent pipeline: what goes in the incoming-learnings
  queue and what is routed elsewhere, how to size large mechanical migrations
  for a fork, how to find the full set a finding belongs to, when a passing
  check is not evidence, and how to handle a spec that disagrees with the code.
related_notes:
  - notes/agents-md-structure.md
  - notes/git-workflow-pitfalls.md
  - notes/history-management.md
  - notes/parallel-development.md
  - notes/bt-pitfalls.md
  - notes/specs-vs-adrs.md
  - notes/spec-authoring-rules.md
  - notes/coordination-agents.md
related_specs:
  - specs/build-workflow.yaml
  - specs/history-management.yaml
  - specs/parallel-development.yaml
  - specs/meta-specifications.yaml
---

# Agentic Development Workflow

Work flows through skills: `work-issue` routes an issue by type to `build`,
`bugfix` or `plan-issue`; `learn`, `update-plan`, `decision-audit` and
`review-priorities` (run in order by `reflect-cycle`) fold what the builds
learned back into specs, notes and priorities. Keep `build` and `bugfix` as two
skills: `bugfix` investigates and writes the failing test first, `build` selects
from the priority queue. Their shared phases are tracked in #3582.

---

## Incoming Learnings Queue

`plan/incoming/learnings/` is the only channel from `build` and `bugfix` to
`learn`. Each observation is its own file, so concurrent PRs never conflict on
it. `learn` promotes each file, then moves it to `plan/history/YYMM/learning/`
with `uv run append-history --from-file <path>`.

**The filename slug describes the observation; it is not the `source`.** Name
files `YYYYMMDD-<issue>-<descriptive-phrase>.md` and put the work-item id in the
`source` frontmatter (`ISSUE-3399`). One issue often yields several learnings,
so a filename derived from `source` alone collides (BW-01-003, BW-02-002).

### What belongs here

A finding gets a learning file **only** when it carries one of these `signal:`
values (BW-07-002):

- `spec-gap` — protocol-visible behaviour implemented with no spec entry. File
  locations, naming conventions and agent guidance go to `AGENTS.md` instead.
- `spec-ambiguity` — a requirement was unclear; record the interpretation made.
- `spec-contradiction` — two requirements conflicted; record which and how the
  conflict was resolved.
- `theme-candidate` — a general claim you cannot verify from one instance. It
  waits for a second independent witness (BW-07-005) and is archived unpromoted
  after 30 days (BW-07-007).

`learn` processes the `spec-*` signals first (BW-07-003).

Everything else is **routed at discovery, not queued** (BW-07-004). Run the
upward-reflection checklist before finishing a `build` or `bugfix` session
(BW-07-001; [`upward-reflection.md`](../.agents/skills/shared/upward-reflection.md))
and send each triggered item to exactly one destination:

- Something that exists but is wrong → a GitHub `type:Concern` issue.
- Something that should exist but does not → a GitHub `type:Idea` issue.
- A broken tool, skill or tracking artefact → a fix in the same session.
- A narrow, true fact about the code → an assertion at the site (test, type
  annotation or comment) in the same session.
- A code-review finding in a file the change did not touch → a `type:Bug` or
  `type:Concern` issue, never a learning file or a PR-comment advisory
  (BW-07-009).

A decision made, applied and shipped in the session is not a learning; its
record is the commit and the PR body (BW-07-008). Completion summaries go
through `uv run append-history implementation`, not the queue.

---

## Large Migrations: Partition by Node Shape, Then Domain

Classify the nodes a migration touches by structural shape first (trivial
reparent, read-only extra inputs, complex output ports), then split by domain
only to balance PR size, so each PR is a lot of the same thing (ISSUE-1809).

A fork runs under a hard 200-turn cap, and a mechanical edit spread across
enough files exhausts it; a turn-capped stop looks like a finish. Before
dispatching, batch by subsystem (`behaviors/`, then `use_cases/`, …) and script
the mechanical substitution (`sed`, a codemod), keeping the agent for edge cases
and type-checker fallout. Afterwards, verify the end state yourself:
uncommitted files, remaining occurrences, `pyright` (ISSUE-2490).

---

## Enumerate the Affected Set From Its Consumers

A finding names one site, but the defect belongs to the set that site is a
member of. Derive the set from whoever *uses* the thing, by a corpus query,
before the number or the fix goes in (ISSUE-3870):

- *At planning*, take N in "the N handlers that …" from the consumer side
  ("every module under `use_cases/received/` that calls a tree factory"), never
  from the pattern you had open.
- *At fix time*, ask of every member (every node on the path, every workflow
  that builds the artifact) what its failure does, and test each answer.
- *In a ratchet*, define membership by use, not by a `KNOWN_*` set or a name
  regex.

---

## A Passing Check Is Not Evidence It Examined What You Think

A guard, predicate or test can pass without examining its subject: it
short-circuits on an empty answer, an exemption copy survives its retirement,
or production never reaches it (ISSUE-3192).

- When a resolver, lookup or predicate starts returning a value where it used to
  return `None`/`False`/empty, read every guard that branches on the empty
  answer and ask which branch ran before.
- When an ADR removes an exemption, grep the *shape* of the exemption
  (`CVDRole.CASE_MANAGER in`, `continue`, `skip`), not the ADR number. A
  docstring stating the exemption is a suspect, not settled design.
- Before trusting a passing check, ask whether it could fail if its subject
  were wrong.

---

## Spec Text Conflicts With Code

When an implementation PR finds the spec and the code disagree, do not quietly
edit the spec to match. Ask: *would something built on the old text now be
wrong?* (ISSUE-4189)

- **No** — a clarification, corrected reference, typo or renamed symbol. Edit
  the statement in the PR.
- **Yes** — the change alters what the requirement obliges (a priority moves, a
  condition is added or dropped, a forbidden behavior is permitted). Ask the user
  in the session before editing and record the answer in the PR. Silence is not
  approval: an unsupervised run holds the PR.

Every PR that changes or removes a `statement:` or `priority:` in `specs/`
carries a `## Spec amended` section with, per ID, the before text, the after
text and the reason (`.agents/skills/shared/pr-body-guide.md`).
`bash .agents/skills/shared/spec-amendments.sh origin/main` lists the IDs.
`pr-triage` fails a diff without the section. A removed requirement ID is never
reused (MS-09-004; see [spec-authoring-rules](spec-authoring-rules.md)).
