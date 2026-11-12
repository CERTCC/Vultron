!!! warning "Open question: disputing an asserted vendor awareness"
    The first VFD transition — `v→V`, vendor becomes aware — has two drive paths.
    The vendor can report it for itself, and the CASE_MANAGER or the Case Owner can assert it on the vendor's behalf ([§13.4.1 Participant-Specific CS Transitions (VFD)](conformance.md#1341-participant-specific-cs-transitions-vfd)).
    The protocol expects evidence of the notification to ground that assertion, and the reference implementation does not check for it.

    Open questions: can the subject Vendor dispute an awareness that another party asserted for it?
    Is transport-level delivery success, a Hypertext Transfer Protocol (HTTP) 200 response, enough evidence for the assertion?

    Do not infer a rule from this document's silence.
