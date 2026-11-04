#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

# !/usr/bin/env python

"""The CVD case state graph and the desiderata the histories are scored on."""

from itertools import product

import networkx as nx

from vultron.core.case_states.validations import (
    is_valid_transition,
    valid_states,
)
from vultron.errors import (
    TransitionValidationError,
)


def _create_graph():
    states = valid_states()

    G = nx.DiGraph()
    G.add_nodes_from(states)

    # create edges when the edge is valid
    for s1, s2 in product(G.nodes, G.nodes):
        try:
            is_valid_transition(s1, s2)
        except TransitionValidationError:
            continue

        t = _diffstate(s1, s2)
        G.add_edge(s1, s2, label=t)

    return G


def _diffstate(s1, s2):
    """returns the transition between s1 and s2"""
    try:
        is_valid_transition(s1, s2)
    except TransitionValidationError:
        return None

    diff = [(c1, c2) for c1, c2 in zip(s1, s2, strict=False) if c1 != c2]
    c1, c2 = diff[0]

    assert c1.upper() == c2.upper()
    return c2.upper()


DESIDERATA = (
    ("V", "P"),
    ("V", "X"),
    ("V", "A"),
    ("F", "P"),
    ("F", "X"),
    ("F", "A"),
    ("D", "P"),
    ("D", "X"),
    ("D", "A"),
    ("P", "X"),
    ("P", "A"),
    ("X", "A"),
)
"""
Taken directly from the [paper](https://doi.org/10.1184/R1/16416771):
 Given (A,B), you prefer histories in which A precedes B over ones in which B precedes A.
"""
