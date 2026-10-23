!!! warning "Open question: does a case ledger need distributed consensus?"

    Each case has one writer.
    The actor that enacts CASE_MANAGER is the only author of the canonical hash-chained case ledger.
    Each Participant Case Replica is a projection of that ledger (PCR-03-001, PCR-03-002).
    This is an intentional simplification.
    This single-writer regime needs no consensus protocol.
    The hash chain also keeps the history tamper-evident, and each Participant can verify it independently.

    It is not clear if one writer is correct for each case.
    A case that has two parties, a finder and a vendor, has too few Participants for useful consensus.
    A case can also have many vendors, coordinators, and deployers.
    Such a case can possibly divide the coordination authority across the Participants, and not hold it in one actor.
    The append-only hash-chained ledger has properties now that a consensus artifact needs.

    The working position is that a simple case keeps one CASE_MANAGER.
    A distributed model adds to that position, and it does not replace it.
    Epic [#1158](https://github.com/CERTCC/Vultron/issues/1158) records this research.
    The project defers the work until the current protocol model becomes stable.
