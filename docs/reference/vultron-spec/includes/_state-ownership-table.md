| Machine | Ownership | Written by |
|---|---|---|
| Report Management (RM) | Participant-specific | The participant is the source, and the `CASE_MANAGER` records each value on the participant's record. The `CASE_MANAGER` also writes the invitee's initial `Received` when it sends the stub Invite, keeps `Received` when the invitee accepts it, and writes `Closed` when the invitee rejects it. |
| Vendor aware, Fix ready, fix Deployed (VFD) | Participant-specific | The participant is the source, and the `CASE_MANAGER` records each value on the participant's record. For a vendor invitee, the `CASE_MANAGER` also writes the initial `vfd` when it sends the stub Invite, and `Vfd` when the invitee accepts or rejects it. |
| Embargo Management (EM) | Shared case state | The `CASE_MANAGER` only |
| Public aware, eXploit public, Attacks observed (PXA) | Shared case state | The `CASE_MANAGER` only |
| Participant Embargo Consent (PEC) | Per-participant | The `CASE_MANAGER` only |
