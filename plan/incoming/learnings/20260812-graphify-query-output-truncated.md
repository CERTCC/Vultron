---
title: Tooling — graphify query output truncates on this graph size, defeating the mandatory-graph-first rule
type: learning
timestamp: 2026-08-12
source: ISSUE-2232
signal: tooling-issue
---

The repo hook makes `graphify query` mandatory before reading source files.  On
this graph (3171 nodes) the query output exceeded the ~2000-token tool budget
and was truncated mid-result, so the surfaced subgraph could not be read as a
whole.  The usable fallback was to take the high-value node names that *did*
appear (`notes/domain-validation.md`, ADR-0034) and read those files directly.

This is worth recording because the failure is silent-ish: truncated output
still looks like an answer, so an agent can proceed on a partial map and
believe it was oriented.  For #2232 the consequential facts — that 15 wire
`type_` values shadow `CORE_VOCABULARY`, and that ~63 files both import
`as_CaseParticipant`/`as_ParticipantStatus` and call `.save(`/`.create(` — came
from direct `grep` counts, not from the graph.  The blast-radius measurement is
what drove the design away from reject-all toward normalise, so the graph was
not sufficient for the decision that mattered.

**Suggestion:** have `graphify query` degrade to a compact node-name-only
listing when the full subgraph would exceed the budget, rather than truncating
a verbose rendering. Until then, treat graph output as orientation only and
verify counts with a direct search.
