## Open Questions

The following questions were open at the time this specification was issued.
Resolved questions have been removed from this list; their resolution is
recorded inline in the relevant section.

{% include-markdown "./_oq-cs-ordering.md" %}

{% include-markdown "./_oq-v-drive-authority.md" %}

!!! warning "Open Question 15: Negative acknowledgement"
    Error message types (`RE`, `EE`, `CE`) are deliberately unmodelled
    (ADR-0049). Unprocessable inbound messages are dead-lettered with no sender
    notification. The three-way fault partition ([§4.6](index.md#46-error-and-acknowledgement-messages), ADR-0083) provides
    structured error signalling where it is implemented, but the question of
    whether the protocol needs a normative negative-acknowledgement facet is
    open.

!!! warning "Open Question 16: Sentinel as a specified role"
    The Sentinel capability shape ([§12.4.2](index.md#1242-participant-agnostic-cs-transitions-pxa), [§12.6](index.md#126-capability-shapes-i)) is currently a design
    pattern with no spec group defining its trust relationship to a case.
    Given StatusAdoptionGate's auto-adopt default policy, an unspecified external
    reporter is a trust-model question, not merely a naming one.
