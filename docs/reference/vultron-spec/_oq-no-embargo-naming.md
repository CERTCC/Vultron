!!! warning "Open question: two machines have a state called \"no embargo\""
    Embargo Management has a *None* state meaning no embargo is in effect for the
    case. Embargo consent has a *No Embargo* state meaning no embargo is in scope
    for one participant. The reference implementation spells both `NO_EMBARGO` —
    in the embargo enumeration as an alias for `NONE`, and in the consent
    enumeration as a state in its own right.

    The two are genuinely different states in different machines, and they can
    legitimately disagree. But sharing a name invites the reading that the consent
    state is a projection of the case's embargo state, which is exactly the
    conflation these two machines exist to prevent.

    Open: whether the consent state should be renamed to something that states its
    meaning more plainly, whether the embargo alias should be dropped, and whether
    either can be changed without altering the values that appear in the case
    ledger. Until that is settled, this specification names the machine wherever
    the distinction matters.
