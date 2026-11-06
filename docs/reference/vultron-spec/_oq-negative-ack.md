!!! warning "Open question: what a sender does after a processing fault"
    Error message types (`RE`, `EE`, `CE`) are deliberately unmodeled (ADR-0049).
    An actor that cannot process an inbound activity from an authenticated sender reports it with `Create(ProcessingFault)` (ASK-07-001).
    The fault names the failed activity and a failure class, and its receiver rules are specified ([§4.11 Faults and Acknowledgments](layers.md#411-faults-and-acknowledgments), ASK-07).
    On the sending side, a fault about an outstanding ask closes that ask (ASK-07-007), and a fault that does not say what went wrong calls for an inquiry (RMB-07-001, VP-11-005, CSB-07-001).

    Open: whether the sender resends the failed activity, drops it, or escalates to a person, and whether that choice depends on the failure class.
    Until this is settled, that choice belongs to each implementation.
