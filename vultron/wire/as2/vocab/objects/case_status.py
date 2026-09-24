#!/usr/bin/env python
"""
Wire-layer aliases for CaseStatus and ParticipantStatus.

Per ADR-0099 detail 3: the core class is the canonical form.
The as_-prefixed names are retained for backward compatibility.

These were the last two of the 27 paired classes, held back by #3487 because they
"differ by field *name*" — flat ``em_state``/``rm_state`` against nested
``em``/``rm`` dimensions — rather than merely by spelling.  That difference had
already dissolved before the pair was collapsed: ADR-0099 detail 5 makes a
dimension serialize as a bare state value, and the core fields carry the
``emState``/``rmState`` aliases, so both classes already emitted byte-identical
AS2.  What remained was two projections translating between forms that had become
the same form.

One piece of the deleted classes had no core equivalent and was relocated rather
than dropped: ``as_ParticipantStatus._reject_retired_vfd_keys`` now lives on
``ParticipantStatus`` (AC-4).  See its docstring for why that guard is still
load-bearing when the camelCase guards beside it are not.
"""

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

from typing import TypeAlias

from vultron.core.models.case_status import CaseStatus
from vultron.core.models.participant_status import ParticipantStatus
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP

as_CaseStatus = CaseStatus
as_ParticipantStatus = ParticipantStatus

WIRE_TYPE_MAP["CaseStatus"] = CaseStatus
WIRE_TYPE_MAP["ParticipantStatus"] = ParticipantStatus

as_CaseStatusRef: TypeAlias = ActivityStreamRef[CaseStatus]
as_ParticipantStatusRef: TypeAlias = ActivityStreamRef[ParticipantStatus]
