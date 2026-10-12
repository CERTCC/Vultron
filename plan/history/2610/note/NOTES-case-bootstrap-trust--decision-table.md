---
source: NOTES-case-bootstrap-trust--decision-table
timestamp: '2026-10-12T19:35:56.671373+00:00'
title: Decision Table
type: note
---

**Archived:** 2026-10-12
**Reason:** decision summary restated as rules in the note body and in CBT specs; its role row was stale (the CASE_MANAGER carries CVDRole.CASE_MANAGER)
**Superseded by:** specs/case-bootstrap-trust.yaml; notes/case-bootstrap-trust.md

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| What establishes first trust for the original report-submission path? | The report receiver sends a one-time `Create(VulnerabilityCase)` to the report submitter, as itself (ADR-0132). | The report submitter already knows who received the report; the bootstrap reuses that trust anchor to introduce the CASE_MANAGER safely. |
| Is `Announce(VulnerabilityCase)` still the first snapshot for that path? | No. After bootstrap, later snapshots come from the CASE_MANAGER via `Announce`. | Keeps initial trust establishment separate from ongoing single-writer replication. |
| What must be in the bootstrap payload? | A full case snapshot naming the report receiver (Case Owner), the CASE_MANAGER, and the report submitter when they are already in the loop. | The receiver needs both the case state and the identities required for future trust checks. |
| What roles should those participants carry? | Case creator/owner gets `CASE_OWNER`; CASE_MANAGER gets `COORDINATOR`. | Distinguishes ownership from coordination authority. |
| Is an extra ack needed before CASE_MANAGER updates are trusted? | No. Local validation of the bootstrap is enough. | Avoids an unnecessary extra round trip. |
| What if a CASE_MANAGER update arrives before bootstrap? | Queue briefly, do not apply it, then drop and warn if bootstrap never arrives. | Tolerates reordering without making ordering skew a protocol failure. |
| Who gets the replay request if bootstrap times out? | The original report receiver. | The CASE_MANAGER is not trusted yet; the replay request asks for the trust-establishing message. |
| How do late joiners establish trust? | `InviteActorToCase` from the case creator establishes trust; then the CASE_MANAGER may `Announce` the case. | Late joiners have no prior report relationship to anchor trust. |
| Can ordinary updates replace the trusted CASE_MANAGER? | No. CASE_MANAGER rotation requires an explicit transfer workflow. | Prevents silent authority takeover. |
| Do encrypted/authenticated DMs replace this bootstrap? | No. They secure transport, but they do not authorize a newly introduced CASE_MANAGER for a case. | Sender authenticity alone is weaker than case-specific authority. |

---
