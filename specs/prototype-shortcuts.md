# Prototype Shortcuts

## Overview

Permissible shortcuts and relaxed constraints for the prototype stage.
These support iterative development while preserving traceability of
production requirements.

**Note**: Requirements marked `PROD_ONLY` in other specs may be deferred
during the prototype stage.

---

## Authentication (MAY)

- `PROTO-01-001` Omit cryptographic authentication for agent-to-agent
  communication.
  - PROTO-01-001 constrains CM-06-004

## Federation (MAY)

- `PROTO-02-001` Assume all actors are local to a single ActivityPub server.
- `PROTO-02-002` Post direct messages to an actor's inbox without federation
  or cross-server routing.

**Note**: The intended production federation model uses AS2 as a vocabulary
(not full ActivityPub), with bilateral/multilateral trust between known peer
instances, mTLS transport, actor/inbox/outbox model, per-case CaseActors,
journal + delivery log, and connector plugins. See
`notes/federation_ideas.md` for the full federation design, open questions,
and Python stack candidates.

## Performance (SHOULD)

- `PROTO-03-001` Avoid algorithms with exponential or worse time complexity.
  - E.g., O(2^n) is not acceptable; O(n^2) is acceptable.
- `PROTO-03-002` Prefer the simplest algorithm when multiple options exist,
  even if less efficient.
- `PROTO-03-003` Implement straightforward optimizations that do not
  significantly increase complexity.
- `PROTO-03-004` Document known unimplemented optimizations in implementation
  notes for future reference.

## Production Deferral (SHOULD)

- `PROTO-04-001` Tag production-only requirements with `PROD_ONLY` in
  specification files.
- `PROTO-04-002` Review specifications to identify requirements that should
  carry the `PROD_ONLY` tag.

## Case Prioritization (MAY)

- `PROTO-05-001` Use a stub always-engage policy (`AlwaysPrioritizePolicy`)
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
    only for reports that have not yet been associated with a case (i.e.,
    before a case is created from a validated report).

## Domain Model Separation (MAY)

- `PROTO-06-001` Prototype MAY allow domain objects to directly inherit from
  ActivityStreams base types (`VultronObject`, `as_Object`, etc.) without a
  translation boundary between wire representation, domain model, and
  persistence model
  - The intended production approach introduces explicit translation functions
    (`from_activitystreams`, `to_activitystreams`) at the protocol boundary
  - PROTO-06-001 constrains CM-08-001
  - PROTO-06-001 constrains CM-08-002
  - See `notes/domain-model-separation.md` for design rationale, known
    constraints of the current approach, and recommended migration steps

  **Design Note**: As the hexagonal architecture refactor progresses, the
  boundary between AS2 wire types and core domain types is becoming more
  concrete. The emerging use-cases-as-core-ports pattern (see
  `notes/use-case-behavior-trees.md` and
  `notes/architecture-ports-and-adapters.md`) may make full AS2 inheritance
  in domain objects untenable sooner than originally anticipated.
  If a `core/use_cases/` layer is formalized (post-P60), it will likely
  require domain objects free of AS2 inheritance. This shortcut SHOULD be
  revisited when stubbing `core/use_cases/` in P60-3.

## Performance Testing (MAY)

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

