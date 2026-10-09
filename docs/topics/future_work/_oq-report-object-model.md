!!! warning "Open question: what occurs when one Report becomes two Cases?"

    A Report is not a Case.
    A Report is the object of the initial `Offer`.
    A Case exists only after a recipient accepts that `Offer`.
    Two Report formats are possible: plain text and JavaScript Object Notation (JSON) in the Common Security Advisory Framework (CSAF) format.
    The project has not specified either format, and more formats can follow.

    The condition occurs when the same Report goes to more than one recipient.
    Each recipient can accept the Report and make its own Case from it.
    The protocol lets this condition occur, and this behavior is intentional.
    A recipient that wants more than one vendor in the coordination can make one Case and invite each vendor to it.

    The frequent form of this condition is sequential, not concurrent.
    A Reporter receives no answer to an `Offer`, and then it asks a Coordinator for aid.
    The recipient of the second `Offer` accepts before the recipient of the first `Offer` accepts.
    Therefore each `Offer` has an identifier that is unique to a minimum of the Report and the recipient.
    The Reporter keeps a different record of each recipient and of the Case that each recipient makes.

    The Reporter cannot join two Cases into one Case, because the Reporter owns neither Case.
    A merge becomes possible when the owner of one Case learns that the other Case exists.
    A proposed design is in [ADR-0105](../../adr/0105-case-merge-freeze-and-redirect-by-owner-consent.md).
    In that design, the owner of one Case offers to merge it into the other Case, and the owner of the other Case accepts or rejects the offer.
    The offered Case then becomes read-only.
    A redirect sends each request for the frozen Case to the Case that remains.
    The Case that remains invites each participant of the frozen Case.
    Two items are still open.
    The first item is the embargo obligations of a participant that declines the invitation.
    The second item is a design that keeps both Cases open and connects them.

    Concern [#3366](https://github.com/CERTCC/Vultron/issues/3366) records this question.
