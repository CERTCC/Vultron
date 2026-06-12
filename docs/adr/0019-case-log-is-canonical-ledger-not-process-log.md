---
status: accepted
date: 2026-06-12
deciders: Vultron maintainers
consulted: notes/case-log-authority.md, notes/sync-log-replication.md, specs/case-log-processing.yaml
---

# Case Log Is a Canonical Protocol Ledger, Not a Process Log

## Context and Problem Statement

The canonical case log (`CaseLogEntry` chain authored by the CaseActor) and
the per-actor runtime process log (Python `logging` output) serve fundamentally
different purposes, but the distinction has not been carved deeply enough to
prevent agents and code from conflating them.

Evidence: A two-actor demo run (case
`urn:uuid:0f69d289-734f-47af-afd2-37091895371a`, 2026-06-12) revealed
synthetic checkpoint events such as `demo_verification` being committed to
the canonical case log with empty `payloadSnapshot` fields, alongside the
absence of the actual protocol-significant activities (`validate_report`,
`accept_report`, `propose_embargo`, `accept_embargo`, `notify_*`,
`close_case`, `add_note`) that *should* be in the log.

This concern (#923) and its parent epic (#788) make clear that the project
needs an explicit, ADR-level decision separating the two logs so future
agents and contributors stop using `record_event()` as a generic "log this
thing" sink.

## Decision Drivers

- The canonical case log is replicated to all participants and forms the
  authoritative shared history of the case; its contents are protocol-visible.
- The process log is per-actor, ephemeral, and intended for operators and
  developers; it must never be replicated or relied on for protocol semantics.
- Conflation has demonstrably caused real bugs (empty `payloadSnapshot`
  entries, missing protocol activities, hash-chain divergence).
- A spec entry alone has not been sufficient to prevent this conflation;
  an ADR carries the "do not re-litigate" weight needed to make the
  separation durable.

## Considered Options

- A. **Single log, multiple severity levels** — record everything in the
  canonical case log, with a severity field distinguishing protocol events
  from diagnostics.
- B. **Two distinct logs with strict separation** — the canonical case log is
  exclusively for CaseActor-authored records of protocol-significant
  assertions; runtime diagnostics, demo checkpoints, and any other
  per-actor observability go to Python `logging` (the process log) and
  are never replicated.
- C. **Status quo (implicit separation)** — rely on convention and
  scattered spec/notes guidance to keep the two apart.

## Decision Outcome

Chosen option: **B — two distinct logs with strict separation**.

The canonical case log MUST contain only CaseActor-authored
`CaseLogEntry` records whose `payloadSnapshot` is the verbatim AS2
activity (or a normalized, deterministic snapshot) that was accepted as
a protocol-significant assertion. Runtime diagnostics, demo
checkpoints, troubleshooting markers, and any other per-actor
observability MUST use the per-actor process log (Python `logging`) at
the level prescribed in `specs/structured-logging.yaml`. Process-log
content MUST NOT enter the canonical case log under any circumstance.

The commit boundary of the canonical case log is therefore an enforcement
point: a runtime guard at the CaseActor's commit path SHOULD reject
entries that do not meet canonical entry criteria, so violations fail
fast instead of silently polluting replicated history.

### Consequences

- Good, because participant replicas can be reconstructed deterministically
  from the canonical log alone, without filtering out diagnostic noise.
- Good, because the canonical log's hash chain only depends on
  protocol-significant content, so unrelated runtime events cannot perturb
  it.
- Good, because operators can use the process log freely without affecting
  protocol correctness or replica convergence.
- Good, because the ADR creates an unambiguous reference future agents can
  cite when reviewing code that calls `record_event()` or appends to the
  canonical log.
- Bad, because existing call sites that currently emit synthetic events
  into the case log must be migrated to the process log or removed.
- Bad, because adding a commit-boundary guard introduces a new runtime
  check that must be carefully placed to avoid blocking legitimate
  CaseActor writes.

## Validation

- `specs/case-log-processing.yaml` `CLP-07` codifies the normative
  separation as MUST-level requirements.
- A new runtime guard at the CaseActor commit boundary rejects
  non-canonical entries (tracked in a follow-on implementation issue).
- The CI two-actor demo invariant assertion job (tracked in a follow-on
  implementation issue) includes a `non-empty payloadSnapshot` check
  that fails the build when synthetic entries are committed.

## More Information

- ADR-0018 — Canonical Case History Convergence on `CaseLogEntry` —
  established the single-writer convergence; this ADR sharpens the
  *content* boundary of that single writer's log.
- Concern #923 — Two-actor demo case log: hash-chain fork, oscillation
  loop, and 17 protocol correctness findings — the empirical evidence
  motivating this ADR.
- Epic #788 — Converge CaseEvent flow onto canonical CaseLogEntry.
- `notes/case-log-authority.md` — design rationale for the canonical
  entry model.
- `notes/sync-log-replication.md` — replication invariants that depend on
  canonical-log purity.
- `specs/structured-logging.yaml` — process-log conventions and levels.

Generated spec requirements: `case-log-processing.yaml` CLP-07-001
through CLP-07-005.
