---
date: 2026-08-27
source: ISSUE-2719
tags: [architecture, protocol, datalayer, anti-pattern]
---

# DataLayer fallback as a smell for masked protocol bugs

When a BT node or use-case handler reads a protocol-significant field from the
DataLayer *instead of* from the received activity message, treat it as a smell
that the handler may be masking a protocol bug or a race condition.

## The pattern

```python
# Smell: reading a field from the DataLayer that the message already carries
invite_id = event.object_id
invite = self.datalayer.read(invite_id)   # ← unnecessary DL round-trip
raw_roles = getattr(invite, "roles", None)
```

The whole point of Vultron is to demonstrate that the *protocol* works — not
that storage side-effects happen to arrive before a handler needs them.  If the
handler can only function correctly when a prior delivery has already been
processed and stored, that is a latent race condition, not a working protocol.

## The fix

Prefer reading from the received message directly:

```python
# Correct: roles come from the Accept's embedded Invite (always present)
activity = getattr(event, "activity", None)
invite_obj = getattr(activity, "object_", None)
raw_roles = getattr(invite_obj, "roles", None)
```

If the field is not in the message, that is a *protocol violation* — log it as
such and return an empty/default value.  Do not silently fall back to a
DataLayer read, which would hide the violation and make the code appear to work
only when a race is won.

## When a DL read IS correct

DataLayer reads are appropriate when the handler needs persisted state that
*cannot* arrive in the message (e.g., reading the VulnerabilityCase to compute
derived fields, or checking an idempotency guard).  The smell applies
specifically to fields that the protocol message itself is supposed to carry.

## Reference

- ISSUE-2719: `_read_invite_roles()` in `accept_invite_tree.py` read the Invite
  from the CaseActor's DataLayer instead of from `event.activity.object_.roles`.
  Race condition: the cc self-delivery might not have been processed yet when the
  Accept arrived.
- Fixed 2026-08-27 by reading from `event.activity.object_` (the raw wire Invite
  embedded in the Accept activity).
