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

"""The VINCE connector: VINCE case records, translated to a case reading.

The translation (:func:`translate_case`) follows the VINCE crosswalk,
``docs/reference/vince_crosswalk.md`` (CRD-03).  The VINCE case reader
(:class:`VinceCaseReader`) fetches a case's records from the VINCE API and
calls it; it is installed as the ``vince`` connector plugin.
"""

from vultron.adapters.connectors.vince.case_rows import ISSUE_TRACKING_REL
from vultron.adapters.connectors.vince.crosswalk import (
    INFERRED_ROWS,
    VINCE_UNOBSERVABLE,
)
from vultron.adapters.connectors.vince.ids import vince_case_url
from vultron.adapters.connectors.vince.reader import VinceCaseReader
from vultron.adapters.connectors.vince.records import READS
from vultron.adapters.connectors.vince.translate import translate_case

__all__ = [
    "INFERRED_ROWS",
    "ISSUE_TRACKING_REL",
    "READS",
    "VINCE_UNOBSERVABLE",
    "VinceCaseReader",
    "translate_case",
    "vince_case_url",
]
