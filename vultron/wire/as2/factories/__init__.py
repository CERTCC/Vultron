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
"""
Public construction API for outbound Vultron protocol activities.

Factory functions in this package are the sole public API for building
outbound Vultron activities.  Internal activity subclasses in
``vultron/wire/as2/vocab/activities/`` are implementation details used
only inside factory functions — callers MUST NOT import them directly.
See ``specs/activity-factories.yaml`` AF-01-001, AF-02-001 through
AF-02-004.

Domain modules (``report.py``, ``case.py``, ``embargo.py``,
``case_participant.py``, ``actor.py``, ``sync.py``) will be added as
factory functions are implemented (AF.2 through AF.6).
"""

from vultron.wire.as2.factories.errors import VultronActivityConstructionError

__all__ = [
    "VultronActivityConstructionError",
]
