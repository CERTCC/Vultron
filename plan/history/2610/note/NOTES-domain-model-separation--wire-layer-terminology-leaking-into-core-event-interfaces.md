---
source: NOTES-domain-model-separation--wire-layer-terminology-leaking-into-core-event-interfaces
timestamp: '2026-10-12T19:32:40.062694+00:00'
title: Wire-Layer Terminology Leaking into Core Event Interfaces
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered — received-event subclasses expose domain-named properties (report_id, case_id, ...) (notes sweep #4496)
**Superseded by:** vultron/core/models/events/; CS-12-001

---

## Wire-Layer Terminology Leaking into Core Event Interfaces

Several core use cases and trigger handlers receive event objects whose field
names (`object`, `target`, `context`, `actor`) are mapped directly from the
AS2 specification rather than using domain-meaningful names. For example, when
an Offer of a report is received, the use case should receive a field named
`report_id` rather than `object_id`. When a note is added to a case, the use
case should receive a `case_id` field rather than a generic `target_id`.

This leakage undermines the hexagonal architecture principle that the core
domain should be expressed in domain vocabulary. It also increases the
cognitive overhead for developers who must mentally translate between AS2
semantics and domain intent when reading core business logic.

**Recommended approach:** For each received-event subtype, ensure that all
fields use domain-appropriate names. Where the AS2 mapping is non-obvious,
add a comment or alias. New event subtypes introduced for Priority 90 and
beyond should follow domain naming from the start.

**Reference:** `specs/architecture.yaml` ARCH-09 (core MUST NOT leak wire
concerns); `specs/code-style.yaml` CS-12-001 (domain vocabulary in class names).
