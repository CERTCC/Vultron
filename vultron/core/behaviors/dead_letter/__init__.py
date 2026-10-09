#!/usr/bin/env python
"""Dead-letter storage for activities whose object could not be resolved.

``UnresolvableObjectUseCase`` runs ``create_store_dead_letter_tree`` from
``dead_letter_tree.py``; the leaf node lives in ``nodes/`` (BTND-07-001,
BTND-07-003).  See ``specs/semantic-extraction.yaml`` SE-04-002, SE-04-003.

This is its own process area rather than part of
``vultron.core.behaviors.inbox``: the inbox package exposes only
``process_payload`` (IO-02-003), and loading any inbox module runs the
inbox pipeline, which imports the semantic registry, which imports the
use case that runs this tree.  Keeping the dead-letter tree out of the
inbox package is what keeps that import graph acyclic (CS-05-003).
"""


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
