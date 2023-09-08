# CVD Directory

{% include-markdown "../../includes/not_normative.md" %}

The idea of CVD embargoes implies a means of dividing the world into 

1. those who belong in the embargo 
2. those who do not

Because _authentication_ is not the same as _authorization_, we cannot simply rely on knowing who a Participant
is; we also have to be able to identify *why* they are *relevant* to a particular case.

Thus, we must ask: 

!!! question 

    How do Participants find other relevant potential Participants to invite to a case?

!!! tip inline end "security.txt"

    Vendors can improve their discoverability by using a
    `security.txt` file on their websites. See [securitytxt.org](https://securitytxt.org) and [RFC 9116](https://www.rfc-editor.org/rfc/rfc9116.html)
    for more information.

In small CVD cases, the answer might be straightforward: The affected product comes from a known Vendor,
so the only question to answer is how best to contact them.
As a first approximation, Internet search engines offer a de facto baseline CVD directory service simply because they
allow any potential Reporter to search for `<vendor name> vulnerability report` or similar terms to find an
individual Vendor contact.

But in larger MPCVD cases, there are a few entangled
problems:

1.  It can be difficult and inefficient to collect contact information
    for all possibly relevant parties.

2.  Even if contact information is widely available using searchable
    resources, many Vendors' preferred contact methods might preclude
    automation of mass notification (or require customized integration
    to ensure interoperability between report senders and receivers).
    Some Vendors only want email. Others require Reporters to create an
    account on their bespoke bug-tracking system before reporting.
    Others ask for submissions via a customized web form. These and [other examples](https://vuls.cert.org/confluence/display/CVD/4.2+Reporting)
    hinder the interoperability of MPCVD processes.

3.  It is not always clear which *other* Vendors' products contain the
    affected product, which limits the ability for an MPCVD cases to follow the software
    supply chain.

4.  Sometimes vulnerabilities arise in protocols or specifications where
    multiple implementations are affected. It can be difficult to
    identify Vendors whose products implement specific technologies.
    Software reverse engineering methods can be used to identify
    affected products in some cases.

5.  At the same time, some Vendors treat their product's subcomponents
    as proprietary close-hold information for competitive advantage;
    this might happen, for example, with OEM or white label licensing agreements.
    While it is certainly their prerogative to do so, this desire to
    avoid disclosing internal components of a product can inhibit
    discovery---and therefore disclosure to the Vendor---that a
    vulnerability affects a product.


!!! tip inline end "For more information"

    - [FIRST Teams](https://www.first.org/members/teams/)
    - Disclose.io [website](https://disclose.io/programs/) and on [GitHub](https://github.com/disclose/diodb)

When it comes to larger scale MPCVD, the inefficiency of ad hoc contact
collection via search engines is evident. Creating a directory of
software Vendors and Coordinators and their vulnerability disclosure
programs would be a step in the right direction. Community-operated
directories such as the FIRST member list or Disclose.io serve as
proof-of-concept of the value such systems can provide. We
especially like the open source model that [Disclose.io](https://disclose.io/) uses, which
solicits contributions from the community.

But further improvements to MPCVD contact management could be made by
standardizing the following:

-   contact information records and the APIs to access them

-   contact methods, including common protocols such as the one we just
    proposed, in conjunction with common data object models and
    vocabularies or ontologies

-   SBOM publication and aggregation services

-   mechanisms for Vendors to register their interest in specific
    technologies

The last of these suggested improvements is not without its challenges.
It is difficult to prevent adversarial parties (including Participants
who might be competitors or have motives incompatible with
CVD principles) from registering interest in receiving vulnerability reports about
technologies in others' products.
