!!! warning "Open question: what happens when one Report becomes two Cases?"

    A Report is not a Case.
    A Report is the object of the initial `Offer`, and a Case exists only once that `Offer` is accepted.
    Two Report formats are known to be in scope, plain text and CSAF-formatted JSON, and others may follow.

    The unresolved part is what happens when the same Report reaches more than one recipient.
    Each recipient can accept and create its own Case from it, which leaves the Reporter tracking two coordination efforts for one vulnerability.
    The protocol permits this and should keep permitting it.
    It is expected to be rare, because a recipient that wants several vendors involved is better served by creating one Case and inviting them.

    The common version of this is sequential rather than simultaneous.
    A Reporter whose `Offer` goes unanswered asks a Coordinator for help, and the second `Offer` is accepted before the first.
    That argues for an `Offer` identifier unique to at least the Report and recipient pair, so the two attempts are distinguishable.

    Case merging is the candidate resolution, and it has two shapes.
    The Cases can reconcile their ledgers, which is involved.
    One Case can instead be frozen into a read-only region of the other, leaving a redirect so that requests for the frozen Case resolve to the surviving one.
    The second shape looks more practical and still needs specifying.
