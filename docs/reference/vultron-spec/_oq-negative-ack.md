!!! warning "Open question: negative-acknowledgement semantics are unspecified"
    Error message types (`RE`, `EE`, `CE`) are deliberately unmodeled
    (ADR-0049). Unprocessable inbound messages are dead-lettered with no sender
    notification. The three-way fault partition
    ([§4.6](index.md#46-error-and-acknowledgement-messages), ADR-0083) provides
    structured error signaling where it is implemented, but whether the
    protocol needs a normative negative-acknowledgement facet — and if so,
    what the expected sender behavior (retry, suppress, escalate) should be —
    remains open.
