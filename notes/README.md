# Design Insights and Implementation Notes

This directory captures **durable design insights** for the Vultron project.
Unlike `plan/IMPLEMENTATION_NOTES.md` (which is ephemeral and may be wiped),
files here are committed to version control and MUST be kept up to date as the
implementation evolves.

## Contents

| File | Topics |
|------|--------|
| `bt-integration.md` | Behavior tree design decisions, py_trees patterns, simulation-to-prototype strategy |
| `activitystreams-semantics.md` | Activity model, state-change notification semantics, response conventions, vocabulary examples |

## Conventions

- Each file focuses on a specific topic area.
- Write insights as **durable guidance for future agents** (not status
  reports).
- When a lesson is learned during implementation, add it here (not just in
  `plan/IMPLEMENTATION_NOTES.md`).
- Cross-reference from `AGENTS.md` where relevant.
