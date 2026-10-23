!!! warning "Open question: negative-acknowledgment semantics are unspecified"
    Error message types (`RE`, `EE`, `CE`) are deliberately unmodeled (ADR-0049).
    An actor that cannot process an inbound activity from an authenticated sender reports it with `Create(ProcessingFault)` (ASK-07-001).
    The three-way fault partition ([§4.11 Faults and Acknowledgments](layers.md#411-faults-and-acknowledgments), ADR-0083) provides structured error signaling where it is implemented.
    Whether the protocol needs a normative negative-acknowledgment facet, and if so what the expected sender behavior (retry, suppress, escalate) should be, remains open.
