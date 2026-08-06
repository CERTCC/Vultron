---
status: accepted
date: 2026-08-06
deciders: Allen D. Householder
consulted: []
informed: []
---

# ADR-0054: Retain plan/incoming/learnings/ as a File Queue; Do Not Migrate to GitHub Issues

## Status

Accepted

## Context

The `plan/incoming/learnings/` directory is an ephemeral queue used by the agentic
workflow harness. During `build` and `bugfix` sessions, agents write structured
Markdown files here when they observe spec gaps, design questions, concerns, or
other signals that need durable capture. The `orient-agent` skill reads every file
in this folder at the start of every workflow session, providing standing context
across the entire harness. The `learn` skill promotes each file's content into
`specs/`, `notes/`, or `AGENTS.md`, then physically archives it to
`plan/history/YYMM/learning/` via `append-history`.

The proposal was to replace this file queue with GitHub Issues of type `type:Learn`,
consolidating all backlog signals into the GitHub Project board and making learnings
visible alongside Concerns, epics, and tasks.

## Decision

Retain `plan/incoming/learnings/` as a local file queue. Do not migrate learning
creation or consumption to GitHub Issues.

The existing dual-queue pattern in `learn` (which already consumes both the folder
and open `type:Concern` GitHub Issues) is the correct model. The file queue handles
ephemeral, session-local signals; GitHub Issues handle durable, human-visible
backlog items. These are different concerns.

## Consequences

### Positive

- **POS-001**: `orient-agent` context loading remains a local disk operation — fast,
  offline-capable, and immune to GitHub API rate limits or network outages.
- **POS-002**: Learning creation at the end of `build`/`bugfix` sessions stays
  zero-friction: a single `Write` call with no network dependency, working even
  without connectivity.
- **POS-003**: The ephemeral-queue invariant is preserved — files are physically
  deleted after promotion, with no ambiguity between "closed" and "archived."
- **POS-004**: No changes required to the 8 skills that reference the folder
  (`build`, `bugfix`, `orient-agent`, `learn`, `reflect-cycle`, `dev-status`,
  `upward-reflection`, `decision-audit`).

### Negative

- **NEG-001**: Pending learnings are not visible on the GitHub Project board; the
  only signals are `dev-status` and the `reflect-cycle` gate.
- **NEG-002**: The learning backlog cannot be searched, filtered, or assigned via
  GitHub's UI.

## Alternatives Considered

### Migrate learnings to GitHub Issues (type:Learn)

- **ALT-001**: **Description**: Each observation that would create a `plan/incoming/learnings/`
  file instead opens a GitHub Issue with `type:Learn`. `orient-agent` queries
  `gh issue list` to load standing context. `learn` closes issues after promotion.
- **ALT-002**: **Rejection Reason**: Makes `orient-agent` network-dependent at the
  start of every harness session — a rate limit, auth failure, or outage degrades
  baseline context for all workflows. Creation friction increases at exactly the
  moment (end-of-session, possibly broken environment) when reliability matters
  most. The ephemeral-queue semantic (physical archive on promotion) has no GitHub
  equivalent. Requires encoding YAML frontmatter signal types as labels. Migration
  touches 8 skill files for a visibility benefit achievable more cheaply.

### Sentinel issue approach (hybrid)

- **ALT-003**: **Description**: Keep the file queue as-is, but have `build`/`bugfix`
  open a single GitHub Issue ("N learnings pending") as a visibility signal when
  new files are created. `learn` closes the sentinel when the folder is cleared.
- **ALT-004**: **Rejection Reason**: Adds GitHub API calls to `build`/`bugfix`
  without eliminating the network dependency concern. The sentinel issue would
  drift (stale count, duplicate opens) and add noise to the board. The existing
  `dev-status` dashboard signal is sufficient.

## Implementation Notes

- **IMP-001**: The `plan/incoming/learnings/` folder must never be referenced from
  durable docs — it is an ephemeral queue, not an archive.
- **IMP-002**: If GitHub Project board visibility of pending learnings becomes a
  genuine pain point, revisit the sentinel issue approach before migrating the
  queue itself.
- **IMP-003**: The dual-queue pattern in `learn` (file queue + `type:Concern` issues)
  is the intentional boundary: files for session-local ephemeral signals, GitHub
  Issues for human-visible durable backlog.

## References

- **REF-001**: `.claude/skills/learn/SKILL.md` — the promotion workflow
- **REF-002**: `.claude/skills/orient-agent/SKILL.md` — consumes the file queue at session start
- **REF-003**: `.claude/skills/shared/upward-reflection.md` — governs when files must be created
- **REF-004**: `plan/incoming/learnings/` — the queue itself (ephemeral; not a durable reference)
