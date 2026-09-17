!!! warning "Open question: what occurs when one Report becomes two Cases?"

    A Report is not a Case.
    A Report is the object of the initial `Offer`.
    A Case exists only after a recipient accepts that `Offer`.
    Two Report formats are possible: plain text and JavaScript Object Notation (JSON) in the Common Security Advisory Framework (CSAF) format.
    The project has not specified either format, and more formats can follow.

    The unresolved condition occurs when the same Report goes to more than one recipient.
    Each recipient can accept the Report and make its own Case from it.
    The Reporter then follows two coordination efforts for one vulnerability.
    The protocol lets this condition occur, and this behavior is intentional.
    This condition is rare.
    A recipient that wants more than one vendor in the coordination can make one Case and invite each vendor to it.

    The frequent form of this condition is sequential, not concurrent.
    A Reporter receives no answer to an `Offer`, and then it asks a Coordinator for aid.
    The recipient of the second `Offer` accepts before the recipient of the first `Offer` accepts.
    Therefore each `Offer` has an identifier that is unique to a minimum of the Report and the recipient.
    The two attempts are then different from each other.

    A merge of the two Cases is the candidate solution, and a merge has two possible forms.
    In the first form, the two Cases reconcile their ledgers.
    This form is complex.
    In the second form, one Case becomes a read-only area in the other Case.
    A redirect sends each request for the frozen Case to the Case that remains.
    The second form is more practical, and the project has not specified it.
