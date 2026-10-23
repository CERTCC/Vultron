!!! warning "Open question: Case Owner discretion once a termination condition is canonical"
    Terminating a case-level embargo requires Case Owner authorization by
    default, and the CASE_MANAGER effects the teardown as the single writer of
    canonical case state. What is settled is *who* may terminate: any
    Participant may *initiate* termination (report a public/exploit/attacks
    condition, or notify intent to exit) and may terminate its *own compliance*,
    but only the Case Owner authorizes ending the embargo for the case.

    What is **not** settled is whether the Case Owner retains any discretion once
    a termination condition has been adopted as canonical case state. When public
    awareness or exploit publication ($q^{cs} \in \{\cdots P \cdots, \cdots X
    \cdot\}$) is canonical, VP-14-001/VP-14-002 read as a mandatory consequence —
    the embargo no longer protects anything — and the working position of this
    specification is that teardown is then mandatory, with the Case Owner's
    authority exercised at the point the condition is *adopted* (guarding against
    a false report) rather than as a second, separate decision to keep the
    embargo. This matches the automatic-teardown path (a canonical `CS.P` set by
    the Case Owner triggers teardown).

    Open: whether the Case Owner may decline to tear down even after the
    condition is canonical; whether the "attacks" condition (SHOULD, VP-11-006)
    differs from the "public/exploit" condition (SHALL) in this respect; and how
    a deliberate decision to keep an otherwise-terminable embargo would be
    recorded. This is expected to be a matter of discussion; the resolution MUST
    be reflected in this reference and in `specs/vultron-protocol-spec.yaml`
    (VP-11, VP-14) once reached.
