#!/usr/bin/env python
"""file: ssvc
author: adh
created_at: 3/16/23 1:38 PM
"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

from enum import IntEnum, auto


class SSVC_2_Enum(IntEnum):
    pass


class SSVC_2_Exploitation(SSVC_2_Enum):
    """Enum for the Exploitation status of a vulnerability"""

    SSVC_2_EXPLOITATION_NONE = auto()
    SSVC_2_EXPLOITATION_PROOF_OF_CONCEPT = auto()
    SSVC_2_EXPLOITATION_ACTIVE = auto()

    SSVC_2_EXPLOITATION_POC = SSVC_2_EXPLOITATION_PROOF_OF_CONCEPT

    NONE = SSVC_2_EXPLOITATION_NONE
    POC = SSVC_2_EXPLOITATION_PROOF_OF_CONCEPT
    ACTIVE = SSVC_2_EXPLOITATION_ACTIVE


class SSVC_2_Public_Value_Added(SSVC_2_Enum):
    """Enum for the Public Value Added status of a vulnerability (if published)"""

    SSVC_2_PUBLIC_VALUE_ADDED_PRECEDENCE = auto()
    SSVC_2_PUBLIC_VALUE_ADDED_AMPLIATIVE = auto()
    SSVC_2_PUBLIC_VALUE_ADDED_LIMITED = auto()

    # convenience aliases
    PRECEDENCE = SSVC_2_PUBLIC_VALUE_ADDED_PRECEDENCE
    AMPLIATIVE = SSVC_2_PUBLIC_VALUE_ADDED_AMPLIATIVE
    LIMITED = SSVC_2_PUBLIC_VALUE_ADDED_LIMITED


class SSVC_2_Report_Public(SSVC_2_Enum):
    """Enum for the Public status of a vulnerability"""

    SSVC_2_REPORT_PUBLIC_NO = auto()
    SSVC_2_REPORT_PUBLIC_YES = auto()

    # convenience aliases
    NO = SSVC_2_REPORT_PUBLIC_NO
    YES = SSVC_2_REPORT_PUBLIC_YES


class SSVC_2_Supplier_Contacted(SSVC_2_Enum):
    """Enum for the Supplier Contacted status of a vulnerability"""

    SSVC_2_SUPPLIER_CONTACTED_NO = auto()
    SSVC_2_SUPPLIER_CONTACTED_YES = auto()

    # convenience aliases
    NO = SSVC_2_SUPPLIER_CONTACTED_NO
    YES = SSVC_2_SUPPLIER_CONTACTED_YES
