# Ontology

{% include-markdown "../../includes/not_normative.md" %}

The Vultron Protocol does not make its appearance in uncharted territory, where no existing CVD systems or processes
exist.
Rather, we propose it as an improvement to interactions among humans, systems, and business processes that already
perform MPCVD around the world every day.
Thus, for adoption to occur, it will be necessary to map existing systems and processes into the semantics
(and eventually, the syntax) of whatever protocol emerges as a descendant of our proposal.

Combined with the abstract [case class model](../../howto/case_object.md), an ontology (e.g., using
[OWL](https://www.w3.org/OWL/)) could accelerate
the semantic interoperability between independent Participant processes and tools that we set out to improve at the
beginning of this effort.

We have provided an example of a [Vultron Protocol OWL Ontology](../../reference/ontology/index.md)
that is intended to be a starting point for further discussion and refinement.

## Related Ontology and Data Definition Work

It is currently unclear how this work might intersect with the NIST
[Vulnerability Data Ontology](https://github.com/usnistgov/vulntology) (a.k.a. *Vulntology*), but we anticipate that there may be some
opportunity for further collaboration.
Also, we recognize that the OASIS [Common Security Advisory Framework](https://oasis-open.github.io/csaf-documentation/)
is addressing a different abstraction of a closely related problem (representing vulnerability reports and advisories),
so we believe that there may be some opportunity for collaboration there as well.
