!!! warning "Open question: does a case ledger ever need distributed consensus?"

    Every case has one writer.
    The actor enacting CASE_MANAGER is the sole author of the canonical, hash-chained case ledger, and every Participant replica is a projection of it (PCR-08).
    That is a deliberate simplification.
    A single writer needs no consensus protocol, and the hash chain still makes the history tamper-evident and independently verifiable.

    Whether it holds for every case is open.
    A two-party finder and vendor case has too few Participants for consensus to mean anything.
    A case with dozens of vendors, coordinators, and deployers might want coordination authority distributed rather than vested in one actor, and the append-only hash-chained ledger already has properties a consensus artifact would need.

    The working position is that simple cases keep a single CASE_MANAGER, and that any distributed model is an addition rather than a replacement.
    Research is tracked under epic [#1158](https://github.com/CERTCC/Vultron/issues/1158), deferred until the current protocol model stabilizes.
