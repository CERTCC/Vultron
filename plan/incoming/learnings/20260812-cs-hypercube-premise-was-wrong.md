---
title: The "completely orphaned" premise in #2237 was wrong, and docs carried stale 64-state claims
timestamp: 2026-08-12T00:00:00Z
source: ISSUE-2237
type: learning
signal: process-issue
---

# The "completely orphaned" premise in #2237 was wrong

*Areas: case states, legacy code, documentation drift, specs.*

## What happened

Issue #2237 described `vultron/core/case_states/` as completely orphaned,
implying retirement was a deletion. Verification found **two live importers**
outside its own tree:

- `vultron/core/use_cases/query/action_rules.py` imports
  `case_states.patterns.potential_actions`, reached from the live
  `actors_get_action_rules` FastAPI endpoint.
- `vultron/core/states/cs.py:26` imports `validations.ensure_valid_state` — the
  authoritative module depends on the legacy one.

That made retirement a **migration, not a deletion**, and drove ADR-0060's
"keep, demoted" decision with two named prerequisites instead of the archive the
issue anticipated.

## Documentation drift found alongside it

All four of these asserted a 64-state hypercube or a nonexistent path, and were
corrected in the same PR:

- `notes/case-state-model.md` — "2^6 = 64-node hypercube"; the truth is 32 valid
  states, 58 valid transitions, 70 valid complete histories of 720 permutations.
- `notes/codebase-structure.md` — listed a `vultron/case_states/enums/` directory
  that does not exist.
- `notes/documentation-strategy.md` — three stale `vultron/case_states/` paths.
- `AGENTS.md` — Key Files Map had no entry for the authoritative
  `vultron/core/states/cs.py`.

## Also found: `references:` in specs YAML is silently dropped

`specs/*.yaml` files accept a `references:` key that is **not** a field on
`StatementSpec` (`vultron/metadata/specs/schema.py`). It is silently discarded by
`spec-dump` with no lint error. Two pre-existing occurrences in
`specs/inbox-orchestration.yaml` are equally dead. The real field is `adr:`,
which `spec-lint` does validate against ADR filenames.

## How to apply

- Treat an issue's characterisation of code as a hypothesis. "Orphaned",
  "unused", "dead" are claims to verify with an importer search before choosing
  between deletion and migration — the answer changes the shape of the work.
- When touching a model documented in `notes/`, grep for the model's headline
  numbers, not just its symbol names. "64" was wrong in prose that named no
  symbol at all, so a symbol grep would have missed it.
- Adding a key to a spec YAML file proves nothing. Round-trip it through
  `PYTHONPATH= uv run spec-dump` and confirm it appears, because unknown keys
  vanish without complaint.

Related: [[20260812-integration-timeout-tier]]

**Promoted**: 2026-08-17 — captured in AGENTS.md pitfall: references: key silently dropped by spec-dump; ISSUE-2290 comment.
Docs PR: TBD.
