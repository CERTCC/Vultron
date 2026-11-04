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

"""
The `vultron.core.case_states.hypercube` module contains the CVDmodel class, which represents the state graph of a Coordinated Vulnerability Disclosure case.

Based on
Householder, A. D., and Jonathan Spring.
[A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://doi.org/10.1184/R1/16416771).
Tech. Rep. CMU/SEI-2021-SR-021, Software Engineering Institute, Carnegie-Mellon University, Pittsburgh, PA, 2021.

Grouped by concern (CS-18-005):

- ``graph`` — the state graph and the desiderata
- ``model`` — the :class:`CVDmodel` class and the listing script
- ``_navigation`` — its state, path and history navigation
- ``_scoring`` — its history and state scoring
"""

from vultron.core.case_states.hypercube.graph import (
    DESIDERATA,
)
from vultron.core.case_states.hypercube.model import (
    CVDmodel,
    main,
)

__all__ = [
    "CVDmodel",
    "DESIDERATA",
    "main",
]
