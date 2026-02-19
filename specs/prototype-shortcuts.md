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

## Federation (MAY)

- `PROTO-02-001` Assume all actors are local to a single ActivityPub server.
- `PROTO-02-002` Post direct messages to an actor's inbox without federation
  or cross-server routing.

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
    `vultron/behaviors/report/policy.py` and the `EvaluateCasePriority` BT
    node in `vultron/behaviors/report/nodes.py` provide the hook point for
    this integration.
  - Note: RM is a **participant-specific** state machine. Each
    `CaseParticipant` (actor-in-case wrapper) carries its own RM state in
    `participant_status[].rm_state`, independent of other participants.
    `ReportStatus` in the flat status layer is a separate mechanism used
    only for reports that have not yet been associated with a case (i.e.,
    before a case is created from a validated report).

