!!! warning "Open question: Should `UNINVITED` and `DECLINED` collapse into one consent state?"
    Both `UNINVITED` and `DECLINED` mean the participant is not bound by the embargo the row answers.
    They differ only in how they were reached: `UNINVITED` is the start state of every row, written when the embargo is proposed or the participant record is created, and `DECLINED` records that the participant explicitly refused the embargo or withdrew from it.

    The operational distinctions that motivate keeping them separate are:

    - A `DECLINED` row records an answer the participant gave, so seeding and the Accept of the full-case Invite leave it declined rather than agreeing for the participant.
    - The consent rows then distinguish "never asked" from "asked and refused" without the ledger, though the ledger preserves that history (CM-28-005) regardless.
    - The CASE_MANAGER records a `DECLINE` explicitly, making the participant's consent history auditable even after the embargo ends.

    The open question is whether these operational distinctions are **sufficient** to warrant two states, or whether the ledger alone is adequate provenance and a single "not bound" state would simplify the machine.

    This question is not expected to be urgent, because the current design is consistent and correct, but it is recorded here so a future revision of the consent model considers it explicitly.
    Resolution MUST be reflected in `specs/case-management.yaml` (CM-18).

    Source: ADR-0093, ADR-0122.
