!!! warning "Open question: Should `UNBOUND` and `DECLINED` collapse into one state?"
    Both `UNBOUND` and `DECLINED` mean the participant is not currently bound by any
    embargo terms.  They differ only in how they were reached: `UNBOUND` is the
    initial state and the reset destination when an embargo is terminated; `DECLINED`
    records that the participant was asked (or was `SIGNATORY` and explicitly withdrew)
    and said no.

    The operational distinction that motivates keeping them separate is:

    - `DECLINED` participants continue to receive embargo **meta-protocol messages**
      (invite, propose, accept/reject announcements) so they can re-engage.
    - `DECLINED` enables re-invitation (`DECLINED → INVITED`); the history that
      distinguishes "never asked" from "asked and refused" is preserved in the canonical
      ledger (CM-28-005) regardless.
    - The CASE_MANAGER records a `DECLINE` transition explicitly, making the participant's
      consent history auditable even after the embargo ends.

    The open question is whether these operational distinctions are **sufficient**
    to warrant two states, or whether the ledger alone is adequate provenance and
    a single "not bound" state would simplify the machine.  Collapsing the states
    would eliminate the `DECLINED → INVITED` re-invitation arc from the PEC machine
    (instead, any "not bound" participant could be re-invited), and the consent
    history would be readable only from the ledger.

    This question is not expected to be urgent — the current two-state design is
    consistent and correct — but it is recorded here so a future revision of the PEC
    model considers it explicitly.  Resolution MUST be reflected in
    `specs/case-management.yaml` (CM-18) and
    `docs/adr/0093-signatory-declined-pec-transition.md` once reached.

    Source: ADR-0093 / Concern #3142.
