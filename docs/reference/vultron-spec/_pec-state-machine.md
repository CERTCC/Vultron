## 9. Participant Embargo Consent (PEC) State Machine [N]

!!! note "Provenance"
    PEC was not part of the original protocol design. It emerged during
    implementation of the embargo subsystem, when the case-level EM state
    proved unable to distinguish between "no embargo exists" and "this
    participant has not yet consented." It is treated as normative here because
    correct embargo semantics cannot be specified without it.

### 9.1 States

| State | Meaning |
|---|---|
| `NO_EMBARGO` | No embargo in scope for this participant (initial state; also reset destination when embargo terminates) |
| `INVITED` | Participant has received an embargo invitation; response pending |
| `SIGNATORY` | Participant has accepted current embargo terms |
| `LAPSED` | Was signatory; case embargo entered `REVISE`; not yet re-accepted |
| `DECLINED` | Explicitly declined, or timed out without responding (pocket veto) |

!!! info "See also"
    - `vultron/core/states/participant_embargo_consent.py`
    - `notes/participant-embargo-consent.md`

### 9.2 Transitions and Guards

| From | Trigger | To |
|---|---|---|
| `NO_EMBARGO` | Embargo proposed; participant invited | `INVITED` |
| `NO_EMBARGO` | Direct/implicit/self-determined consent | `SIGNATORY` |
| `NO_EMBARGO` | Refusal without formal invitation | `DECLINED` |
| `INVITED` | Accept | `SIGNATORY` |
| `INVITED` | Reject | `DECLINED` |
| `INVITED` | Timeout (pocket veto) | `DECLINED` |
| `SIGNATORY` | EM enters `REVISE` | `LAPSED` |
| `LAPSED` | Re-invitation extended | `INVITED` |
| `LAPSED` | Accept revised terms | `SIGNATORY` |
| `LAPSED` | Decline revised terms | `DECLINED` |
| `LAPSED` | Timeout (pocket veto) | `DECLINED` |
| `DECLINED` | Case owner re-invites | `INVITED` |
| Any | EM exits (`EXITED`) | `NO_EMBARGO` (RESET) |

Expressed as triggers: `INVITE` accepts `NO_EMBARGO | LAPSED | DECLINED`;
`ACCEPT` and `DECLINE` each accept `NO_EMBARGO | INVITED | LAPSED`; `REVISE`
accepts only `SIGNATORY`; `RESET` accepts any state.

!!! warning "`LAPSED` is not the timeout state"
    `LAPSED` is reached **only** from `SIGNATORY`, and **only** via the `REVISE`
    trigger. It means "prior consent no longer covers the revised terms."

    It is **not** the pocket-veto destination. Both timer paths
    (`INVITED → DECLINED` and `LAPSED → DECLINED`) terminate in `DECLINED`.
    Confusing the two is a known and recurring documentation error.

Neither `LAPSED` nor `DECLINED` is terminal — both can be re-invited.

### 9.3 Semantics of `NO_EMBARGO`

- `NO_EMBARGO` means **absence of an embargo context**, not "not yet consented"
- Direct `ACCEPT` and `DECLINE` from `NO_EMBARGO` are valid (no invitation
  required) to accommodate self-determined embargoes and implicit reporter consent
- The transition `SIGNATORY → INVITED` MUST be rejected (consent cannot be
  retroactively un-given by re-invitation)

### 9.4 Pocket Veto and RSVP Deadlines (Timer-Based Transitions)

- `INVITED → DECLINED` and `LAPSED → DECLINED` are timer-based
- An `Invite(EmbargoEvent)` MAY carry an activity-level `end_time` giving an
  explicit RSVP-by deadline. When present it is authoritative; when absent the
  configurable policy window applies (default 7 days). The pocket veto is the
  implicit form of the same mechanism, not a second one
- `Invite.end_time` (RSVP-by) MUST NOT be confused with
  `Invite.object_.end_time` (embargo expiry) — the same invitation carries both
- A minimum RSVP window (default 72h) MUST be enforced; a receiver getting a
  sub-minimum deadline MUST clamp it up rather than reject the invitation
- Enforcement authority is the CaseActor (`CVDRole.CASE_MANAGER`), evaluated
  lazily from `(end_time, now)`; no scheduler is required
- A lapse records `DECLINED` — the same state as an explicit refusal. The
  distinction is provenance, carried by the canonical ledger, not by a
  dedicated PEC state
- A late `Accept` MUST NOT be refused on deadline grounds: honour it if the
  terms are current, re-invite with current terms if they are stale, or
  acknowledge as a no-op (retaining case participation) if no embargo remains

### 9.5 Embargo Meta-Protocol Delivery to Non-Signatories

- Embargo meta-protocol messages — `Invite(Event)`, `Accept`/`Reject` thereof,
  and `Remove(Event)` — MUST be delivered even to `DECLINED` and `LAPSED`
  participants. A participant cannot be re-invited to revised terms it never
  learns about.
- Only case **content** (report details, fix status, sensitive notes) is gated on
  `SIGNATORY` status ([§9.7](index.md#97-gating-full-case-delivery)).

### 9.6 Relationship to `embargo_adherence`

`embargo_adherence` is the boolean projection of PEC state: `True` iff
PEC = `SIGNATORY`, `False` otherwise.

The implementation MUST expose `embargo_adherence` as a computed property
(e.g., Pydantic `@computed_field`) derived from `consent.state`. It MUST NOT
be a stored field that can drift from the PEC state it projects.
Consent changes MUST be applied as a PEC trigger through the validated
transition path (ADR-0048, ADR-0056).

### 9.7 Gating Full Case Delivery

Before the Case Actor delivers full case content
(`Announce(VulnerabilityCase)` carrying report details, vulnerability
description, and sensitive notes), **both** conditions MUST hold for the
recipient:

1. The participant is **admitted to the case** — RM state is at least
   `RM.RECEIVED`.
2. The participant is a **signatory to the active embargo**
   (`embargo_adherence = True`), **OR** there is no active embargo
   (`EM.NONE`).

!!! warning "The gate is admission plus consent — not completed triage"
    It is tempting to read condition 1 as `RM.ACCEPTED`. That reading is wrong
    and self-defeating: an invitee is recorded at `RM.RECEIVED` on
    `Accept(Invite)`, and reaches `ACCEPTED` only *after* receiving the full case
    and running its triage cycle ([§6.3](index.md#63-per-participant-rm-tracking)). Requiring `ACCEPTED` before delivery
    would mean a participant could never obtain the case it needs in order to
    reach the state that gates it.

    **Embargo consent — not RM progress — is the substantive gate on case
    content.** The ordering is: admit the participant at `RM.RECEIVED`, resolve
    embargo consent, then deliver the full case.

Note the consequence for [§10](index.md#10-model-interactions-and-cascade-rules-n)'s cascade ordering: `Accept(Invite)` implies consent
to any active embargo, which is what allows delivery to proceed immediately rather
than waiting on a separate consent round-trip.

---
