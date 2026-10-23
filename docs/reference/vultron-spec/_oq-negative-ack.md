!!! warning "Open question: negative-acknowledgment semantics are unspecified"
    Error message types (`RE`, `EE`, `CE`) are deliberately unmodeled
    (ADR-0049). Unprocessable inbound messages are dead-lettered with no sender
    notification. The three-way fault partition
    ([§4.6 Error and Acknowledgment Messages](layers.md#46-error-and-acknowledgment-messages), ADR-0083) provides
    structured error signaling where it is implemented, but whether the
    protocol needs a normative negative-acknowledgment facet — and if so,
    what the expected sender behavior (retry, suppress, escalate) should be —
    remains open.
