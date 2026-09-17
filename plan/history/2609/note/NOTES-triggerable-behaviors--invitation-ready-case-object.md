---
source: NOTES-triggerable-behaviors--invitation-ready-case-object
timestamp: '2026-09-17T17:32:56.100020+00:00'
title: Invitation-Ready Case Object
type: note
---

**Archived:** 2026-09-17
**Reason:** (b) superseded — proposed RedactedVulnerabilityCase subclass/redact() was never built; resolved differently via CM-09/stub-objects
**Superseded by:** CM-09; notes/stub-objects.md

---

## Invitation-Ready Case Object

**Design Decision**: `VulnerabilityCase` SHOULD support a `RedactedVulnerabilityCase`
subclass for invited-but-not-yet-accepted participants. (resolved — blocks
resolved; see `specs/case-management.yaml` CM-09-*)

The preferred design is:

- A `RedactedVulnerabilityCase` subclass of `VulnerabilityCase` containing
  only the fields relevant to an invitee who has not yet accepted.
- A `redact(invitee_id)` method on `VulnerabilityCase` that returns a
  `RedactedVulnerabilityCase` with appropriate fields omitted or redacted.
  Not all redactions are complete omissions — some fields may be
  partially redacted.
- Type hints enforce that redacted versions appear only where expected, and
  that a full `VulnerabilityCase` is never passed where only a redacted
  view is appropriate.
- **Opsec ID constraint**: The ID of a `RedactedVulnerabilityCase` MUST be
  completely unrelated to the full case ID. This prevents attackers who
  obtain a redacted case ID from inferring the full case ID.
- **Per-invitee unique IDs**: Each invitee MUST receive a distinct
  `RedactedVulnerabilityCase` ID so that observing one redacted ID provides
  no information about the size of the participant list or the identities
  of other invitees. (Assuming eventual encryption, this makes it very
  difficult to reconstruct the invite list.)

This is a PRIORITY 300 design item. For the prototype, the `Invite`
activity MAY reference the case by ID only, leaving the invitee to
request full details upon acceptance.

**Cross-reference**: `specs/case-management.yaml` CM-09-*,
`specs/encryption.yaml`

---
