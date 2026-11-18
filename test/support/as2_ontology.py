#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""A reader of the pinned AS2 ontology, for the tests that check against it.

The pinned copy is ``ontology/activitystreams2.owl``.  Where it contradicts
the AS2 Vocabulary Recommendation, the Recommendation wins, and each such
departure is recorded here with the test that keeps it honest.
"""

import re
from functools import cache
from pathlib import Path

ONTOLOGY = (
    Path(__file__).resolve().parents[2] / "ontology/activitystreams2.owl"
)

#: The classes the pinned ontology gives no named supertype: the roots
#: ``Object`` and ``Link``, and ``OrderedItems``, an ``rdf:List`` shape and
#: not an AS2 type.
ONTOLOGY_ROOTS = frozenset({"Object", "Link", "OrderedItems"})

#: Where the pinned ontology contradicts the AS2 Vocabulary Recommendation
#: (§ 3.3, "Extends"), the Recommendation wins: ``(subtype, pinned supertype)``
#: maps to the Recommendation's supertype.  The pinned copy puts ``Page``
#: under ``Object``; the Recommendation puts it under ``Document``.
RECOMMENDATION_OVER_PINNED_ONTOLOGY = {("Page", "Object"): "Document"}


def _blocks() -> list[str]:
    return [
        block.strip()
        for block in ONTOLOGY.read_text(encoding="utf-8").split("\n\n")
    ]


@cache
def pinned_ontology_supertypes() -> dict[str, list[str]]:
    """Each class of the pinned AS2 ontology, with the supertypes it names.

    Reads every name of a ``rdfs:subClassOf`` list and the named class an
    ``owl:intersectionOf`` restricts, the two forms the ontology uses.
    """
    supertypes: dict[str, list[str]] = {}
    for block in _blocks():
        match = re.match(r"as:(\w+) a owl:Class", block)
        if not match:
            continue
        named = [
            name
            for names in re.findall(
                r"rdfs:subClassOf\s+(as:\w+(?:\s*,\s*as:\w+)*)", block
            )
            for name in re.findall(r"as:(\w+)", names)
        ]
        named += re.findall(
            r"rdfs:subClassOf\s*\[\s*a owl:Class;\s*"
            r"owl:intersectionOf\s*\(\s*as:(\w+)",
            block,
        )
        supertypes[match.group(1)] = named
    return supertypes


def as2_subclass_pairs() -> list[tuple[str, str]]:
    """Each ``(subtype, supertype)`` of AS2: the pinned ontology's pairs, with
    each recorded departure replaced by the Recommendation's pair."""
    return [
        (sub, RECOMMENDATION_OVER_PINNED_ONTOLOGY.get((sub, sup), sup))
        for sub, supertypes in pinned_ontology_supertypes().items()
        for sup in supertypes
    ]


def as2_ancestry(type_name: str) -> set[str]:
    """*type_name* and every AS2 type it extends, departures applied."""
    parents: dict[str, list[str]] = {}
    for sub, sup in as2_subclass_pairs():
        parents.setdefault(sub, []).append(sup)
    seen = {type_name}
    pending = [type_name]
    while pending:
        for sup in parents.get(pending.pop(), []):
            if sup not in seen:
                seen.add(sup)
                pending.append(sup)
    return seen


@cache
def pinned_ontology_property_domains() -> dict[str, frozenset[str]]:
    """Each property of the pinned ontology, with the classes of its domain.

    A domain is one named class or an ``owl:unionOf`` list of them.  A
    property the ontology gives no domain maps to no class.
    """
    domains: dict[str, frozenset[str]] = {}
    for block in _blocks():
        match = re.match(r"as:(\w+) a owl:\w*Property", block)
        if not match:
            continue
        named = re.search(r"rdfs:domain\s+as:(\w+)", block)
        union = re.search(r"rdfs:domain\s*\[(.*?)\]", block, re.DOTALL)
        if named:
            classes = frozenset({named.group(1)})
        elif union:
            classes = frozenset(re.findall(r"as:(\w+)", union.group(1)))
        else:
            classes = frozenset()
        domains[match.group(1)] = classes
    return domains


def properties_allowed_on(type_name: str) -> set[str]:
    """The AS2 properties whose domain admits an object of *type_name*."""
    ancestry = as2_ancestry(type_name)
    return {
        prop
        for prop, domain in pinned_ontology_property_domains().items()
        if domain & ancestry
    }


__all__ = [
    "ONTOLOGY",
    "ONTOLOGY_ROOTS",
    "RECOMMENDATION_OVER_PINNED_ONTOLOGY",
    "as2_ancestry",
    "as2_subclass_pairs",
    "pinned_ontology_property_domains",
    "pinned_ontology_supertypes",
    "properties_allowed_on",
]
