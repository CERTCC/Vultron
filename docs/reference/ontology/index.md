# Ontology

{% include-markdown "../../includes/not_normative.md" %}

The Vultron Protocol does not make its appearance in uncharted territory, where no existing CVD systems or processes
exist.
Rather, it is offered as an improvement to interactions among humans, systems, and business processes that already
perform MPCVD around the world every day.
Thus, for adoption to occur, it will be necessary to map existing systems and processes into the semantics
(and eventually, the syntax) of whatever protocol emerges as a descendant of this proposal.

Combined with the abstract [case class model](../../howto/case_object.md), an ontology (e.g., using
[OWL](https://www.w3.org/OWL/){:target="_blank"}) can accelerate
the semantic interoperability between independent Participant processes and tools that this effort set out to improve.

A few [OWL](https://www.w3.org/TR/owl2-overview/){:target="_blank"} ontology files describe the
Vultron protocol.
These files are available in the `ontology` directory.

{% include-markdown "../../includes/ontology_tips.md" %}

- [Vultron Activitystreams Ontology](vultron_as.md)
- [Vultron Process Model Ontology](vultron_process.md)
- [Vultron Protocol Ontology](vultron_protocol.md)
- [Deterministic Finite Automata Ontology](dfa.md)
- [RFC 2119 Ontology](rfc2119.md)

## Related Ontology and Data Definition Work

It is currently unclear how this work might intersect with the NIST
[Vulnerability Data Ontology](https://github.com/usnistgov/vulntology){:target="_blank"} (a.k.a. *Vulntology*), though there may be some
opportunity for further collaboration.
The OASIS [Common Security Advisory Framework](https://oasis-open.github.io/csaf-documentation/){:target="_blank"}
also addresses a different abstraction of a closely related problem (representing vulnerability reports and advisories),
so there may be some opportunity for collaboration there as well.
