---
title: "Fixtures encoding a causally impossible state pass until the invariant is enforced, then all fail at once"
type: learning
timestamp: "2026-09-01T00:00:00Z"
source: ISSUE-2906
signal: concern
---

Adding the receive-path RM↔VF entailment check broke five tests in
`test/core/behaviors/status/test_partial_accept_participant_status.py`. None of
them was testing entailments. All five had fixtures pairing `rm=VALID` or
`rm=RECEIVED` with `vf=CS_vf.VF` — a state CSB-18-001 says cannot exist, chosen
only because the author needed *some* rm regression and *some* vf advance in one
snapshot.

This is a predictable cost of enforcing any new cross-field invariant, and it is
worth anticipating rather than discovering: **hand-built fixtures drift into
impossible states in exactly the fields no rule currently checks.** The fixtures
were not wrong when written; nothing could have told the author otherwise.

Two things this cost us beyond the mechanical fixture edit:

- `test_vf_write_refused_without_vendor_role` would have kept passing after the
  change while asserting the wrong cause — the role gate *and* the entailment
  both refuse `vf`, so the assertion could no longer distinguish them. It now
  uses `rm=ACCEPTED` so the role gate is the only thing that can fire. A test
  that passes for two possible reasons is weaker than it reads.
- A leak-detection test asserted specific `rmState` values on two consecutive
  ledger entries; changing the fixture rm shifted both expected values, which is
  the kind of edit that is easy to make wrong.

**Mitigation worth considering:** a fixture builder for `ParticipantStatus` that
runs `cross_machine_violations()` on what it is about to construct and raises,
so an impossible fixture fails at construction with a clear message instead of
surfacing years later as unrelated test breakage. The sync-path tests in the
same file still carry `rm=VALID` + `vf=VF` fixtures; they pass only because
`ApplyParticipantStatusFromLedgerNode` enforces no entailments (see the Concern
filed for that path).

## Audit disposition (2026-09-02)

Filed as #3046.
