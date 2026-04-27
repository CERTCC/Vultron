# Prototype Shortcuts

## Overview

Permissible shortcuts and relaxed constraints for the prototype stage.
These support iterative development while preserving traceability of
production requirements.

**Note**: Requirements marked `PROD_ONLY` in other specs may be deferred
during the prototype stage.

---

## Authentication

- `PROTO-01-001` (MAY) Omit cryptographic authentication for agent-to-agent
  communication.
  - PROTO-01-001 constrains CM-06-004

## Federation

- `PROTO-02-001` (MAY) Assume all actors are local to a single ActivityPub server.
- `PROTO-02-002` (MAY) Post direct messages to an actor's inbox without federation
  or cross-server routing.

**Note**: The intended production federation model uses AS2 as a vocabulary
(not full ActivityPub), with bilateral/multilateral trust between known peer
instances, mTLS transport, actor/inbox/outbox model, per-case CaseActors,
journal + delivery log, and connector plugins. See
`notes/federation_ideas.md` for the full federation design, open questions,
and Python stack candidates.

## Performance

- `PROTO-03-001` (SHOULD NOT) Use algorithms with exponential or worse time complexity.
  - E.g., O(2^n) is not acceptable; O(n^2) is acceptable.
- `PROTO-03-002` (SHOULD) Prefer the simplest algorithm when multiple options exist,
  even if less efficient.
- `PROTO-03-003` (SHOULD) Implement straightforward optimizations that do not
  significantly increase complexity.
- `PROTO-03-004` (SHOULD) Document known unimplemented optimizations in implementation
  notes for future reference.

## Production Deferral

- `PROTO-04-001` Specification files SHOULD tag production-only requirements
  with `PROD_ONLY` so they can be systematically identified and deferred
  during the prototype stage.
  - Tagged requirements SHOULD remain in the specification (not deleted) so
    the full production intent is preserved alongside the prototype deferral
  - Agents SHOULD treat any `PROD_ONLY` requirement as out-of-scope for
    prototype implementation unless explicitly instructed otherwise
- `PROTO-04-002` (SHOULD) Review specifications to identify requirements that should
  carry the `PROD_ONLY` tag.
  - Any requirement that cannot be practically tested without production
    infrastructure (e.g., HSMs, PKI, mTLS) or that imposes overhead
    inconsistent with rapid prototyping SHOULD carry the `PROD_ONLY` tag

## Case Prioritization

- `PROTO-05-001` (MAY) Use a stub always-engage policy (`AlwaysPrioritizePolicy`)
  in place of a real prioritization framework.
  - The intended production mechanism is SSVC (Stakeholder-Specific
    Vulnerability Categorization) or an equivalent tool that evaluates report
    content and context to produce an engage/defer decision.
  - The `PrioritizationPolicy` interface in
    `vultron/core/behaviors/report/policy.py` and the `EvaluateCasePriority` BT
    node in `vultron/core/behaviors/report/nodes.py` provide the hook point for
    this integration.
  - Note: RM is a **participant-specific** state machine. Each
    `CaseParticipant` (actor-in-case wrapper) carries its own RM state in
    `participant_status[].rm_state`, independent of other participants.
    `ReportStatus` in the flat status layer is a separate mechanism used
    only for transient pre-validation tracking (RM states that predate
    the `VulnerabilityCase` object — i.e., logically in RM.RECEIVED or
    RM.INVALID before the case is in a meaningful actionable state). Per
    ADR-0015, case creation occurs at report receipt (RM.RECEIVED);
    `VultronParticipant` records carry RM state from that point forward.

## Backward Compatibility and Change Completeness

Requirements in this section apply to changes made during the prototype phase.
There are no external downstream consumers of this codebase, so backward
compatibility is not a constraint.

- `PROTO-08-001` (MUST NOT) Add backward-compatibility shims when refactoring,
  renaming, moving, or removing code. Shims include re-export stubs, import
  aliases, wrapper functions, and deprecation stubs that exist solely to
  preserve old import paths or call signatures.
  - **Rationale**: Without shims a failing import immediately signals a missed
    call site; with a shim the missed update is invisible and accumulates as
    technical debt
- `PROTO-08-002` (MUST) Complete every code change fully — all call sites for a
  renamed, moved, or removed symbol MUST be updated in the same commit as the
  symbol change.
  - Use `grep -r` across `vultron/` and `test/` before starting to locate every
    call site
  - A clean test run after the change is the proof of completeness; no shim
    should be needed to make tests pass
- `PROTO-08-003` (MUST NOT) Preserve an old API, import path, field name, or
  function signature solely for backward compatibility.
  - If there is no functional reason beyond compatibility to keep the old form,
    remove it entirely and update all consumers
- `PROTO-08-004` `PROD_ONLY` (SHOULD) Follow a documented deprecation cycle
  with migration guidance when external consumers of the API exist.
  - `DeprecationWarning` raises or deprecation annotations are appropriate in
    production when users need a migration window; they are not appropriate as
    prototype-phase placeholders for incomplete migrations

<!-- PROTO-06-001 (Domain Model Separation) removed 2026-04-15.
     The inheritance concern it described is resolved: domain objects
     (VulnerabilityCase, VultronReport, etc.) are already pure Pydantic
     BaseModel with no AS2 inheritance. The remaining wire/domain translation
     boundary work is now tracked as a production requirement in
     specs/architecture.yaml (ARCH-12-001 through ARCH-12-007) and as
     implementation task WIRE-TRANS-01 in plan/IMPLEMENTATION_PLAN.md. -->

## Performance Testing

- `PROTO-07-001` `PROD_ONLY` Performance tests and performance assertions MAY
  be skipped or marked as expected failures during the prototype stage
  - The project is currently in the "make it work" and "make it work right"
    phases; performance optimization is premature
  - Existing tests that include performance assertions SHOULD be marked
    `@pytest.mark.skip` or `@pytest.mark.xfail` if they risk false failures
    without being critical for correctness verification
  - All performance requirements in other specs MUST carry the `PROD_ONLY`
    tag; do not add new performance requirements without this tag during the
    prototype stage
  - **Rationale**: Premature performance work distracts from correctness
    and architectural clarity; defer until exiting the prototype phase
