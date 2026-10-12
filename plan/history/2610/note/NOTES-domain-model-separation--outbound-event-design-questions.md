---
source: NOTES-domain-model-separation--outbound-event-design-questions
timestamp: '2026-10-12T19:32:39.022168+00:00'
title: Outbound Event Design Questions (P65-6 Considerations)
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered — the outbound path is built: factories construct outbound activities and core renders wire shape only through the rendering port (notes sweep #4496)
**Superseded by:** vultron/wire/as2/factories/; ADR-0099; ARCH-20-001

---

## Outbound Event Design Questions (P65-6 Considerations)

Before implementing the outbound path (domain event → AS2 activity), consider:

- **Which events go in `core/models/`?** Domain events corresponding to
  outbound activities (e.g., `CaseCreatedEvent`, `EmbargoProposedEvent`).
  These are distinct from inbound received events.
- **Outbound serializer mapping**: Should `wire/as2/serializer.py` map each
  domain event type to AS2 one-to-one, or via a generic mapping table?
  One-to-one is safer for type checking; a table is more compact.
- **Interplay with the outbox pipeline**: Domain events emitted by handlers
  must eventually become AS2 activities written to the actor outbox. The
  serializer is the seam between these two concerns (see `specs/outbox.yaml`).
- **ADR**: Consider drafting an ADR for the domain/wire separation decision
  before implementation, to record the rationale. See `docs/adr/_adr-template.md`.
