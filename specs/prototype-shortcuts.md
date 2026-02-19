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

