---
source: CONCERN-3280
timestamp: '2026-09-17T14:27:22.053762+00:00'
title: 'Embargo-termination authority: VP-11/VP-13 prose vs CM-03/RSH/EMB-19 operational
  corpus'
type: learning
---

## Original concern

The spec corpus contained two apparently-incompatible accounts of who may
terminate an embargo, neither marked as superseding the other. Surfaced while
reviewing PR #3265 (the Vultron Protocol Specification):

- **Participant-driven prose:** `VP-11-002` ("Participants SHALL terminate the
  embargo"), `VP-11-003` ("initiate embargo termination"), `EMB-14`
  ("Actor-Voluntary Embargo Termination", speaking of "the actor" with no role
  gate).
- **Case-manager-mediated corpus:** `CM-03-003` (shared EM state at the case
  level), `SM-10-002/003` (EM/PXA participant-agnostic), `RSH-04-001` (only the
  CASE_MANAGER emits `Add(CaseStatus)`), `EMB-19-001` (teardown announce
  authored by CASE_MANAGER; "the teardown is canonical case state"),
  `CLP-10-002` (commit skipped when `receiving_actor_id != case_actor_id`).

## What the investigation found

1. **The governing decision was already settled** — not two live designs.
   `ADR-0088` (authority is the CASE_MANAGER role), `ADR-0076`/`RSH-02-002`
   (`EmbargoTeardownAuthorizationGate` defaults to `RequireCaseOwnerApproval`),
   and above all **`CM-02-005`** ("CASE_MANAGER MUST restrict … terminating an
   active embargo … to the case owner") already positively encode the model.
   The code agrees: `terminate_embargo_bt` runs `ResolveCaseManagerNode` before
   the EM state mutation.
2. **The edges were `satisfies`, not `refines: VP-11`.** `em-behavior`/
   `cs-behavior` carry `rel_type: satisfies → VP-11-002/003`; there is no
   topic-level `refines` to VP. "Legacy layer formally upstream" was imprecise.
3. **VP-11 was not a stale un-retired file** — PR #3265 freshly transcribed the
   participant-facing paper language into the new canonical
   `vultron-protocol-spec.yaml`. The clash was a within-corpus *altitude*
   mismatch in fresh material, not old-vs-new layering.

## Resolved model (four acts, three authorities)

1. **Report** a P/X/A condition — any participant (suggested `CaseStatus` in
   `Add(ParticipantStatus)`; a claim, not canonical).
2. **Authorize** the case-level teardown — the **CASE_OWNER** (may delegate via
   an explicit permissive gate backend); `CM-02-005`, `ADR-0076`.
3. **Effect** the teardown — the **CASE_MANAGER** as single writer;
   `EMB-19-001`, `ADR-0088`.
4. **Terminate own compliance** — any participant, own PEC only; does not end
   the case embargo (`VP-13-009/017`).

The defect was confined to prose that paired a bare *Participant* subject with
*"terminate the embargo"* (the case-level object): `VP-11-002/006`, `VP-13-018`.

## Open question (recorded, not decided)

Whether the Case Owner retains discretion to keep an embargo once a P/X/A
condition is canonical. Working position: mandatory once canonical
(`DEMOMA-07-003`). Tracked at
`docs/reference/vultron-spec/_oq-embargo-termination-authority.md`.

## Discovered code gap

The PEC state machine has no `SIGNATORY → DECLINED` transition, so `VP-13-017`
("terminate compliance at any time") is unreachable once a participant accepts.

**Resolved**: 2026-09-17 — reconciled VP-11-002/006 and VP-13-017/018 prose,
added the EMB-14 authority note, and recorded the open question. PEC-withdrawal
implementation tracked in #3310.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3309>.
Spec: `specs/vultron-protocol-spec.yaml`, `specs/em-behavior.yaml`.
