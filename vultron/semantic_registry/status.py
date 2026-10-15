"""Status-domain semantic registry entries.

Covers both case-level and participant-level status entries.
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

from vultron.core.models.case_status import CaseStatus
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.status import (
    AddCaseStatusToCaseReceivedEvent,
    AddParticipantStatusToParticipantReceivedEvent,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.use_cases.received.status import (
    AddCaseStatusToCaseReceivedUseCase,
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    FieldValue,
    HowToGuide,
    MessagePage,
    Occasion,
    ProtocolShorthand,
)
from vultron.wire.as2.extractor import (
    AddCaseStatusToCasePattern,
    AddParticipantStatusToParticipantPattern,
)
from vultron.wire.as2.vocab.activities.case import (
    _AddStatusToCaseActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    _AddStatusToParticipantActivity,
)

ENTRIES: list[SemanticEntry] = [
    # Case status
    SemanticEntry(
        semantics=MessageSemantics.ADD_CASE_STATUS_TO_CASE,
        pattern=AddCaseStatusToCasePattern,
        event_class=AddCaseStatusToCaseReceivedEvent,
        use_case_class=AddCaseStatusToCaseReceivedUseCase,
        phrase="{actor} updated the case status",
        wire_activity_class=_AddStatusToCaseActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "a Participant learns that the public knows of the "
                    "vulnerability"
                ),
                anchor="public-awareness",
                description=(
                    "Announces evidence that the vulnerability is known to the"
                    " public."
                ),
                example="add_public_awareness_to_case",
                distinguisher=FieldValue(
                    object_type=CaseStatus, field="pxa", value=CS_pxa.Pxa
                ),
                howto=HowToGuide.STATUS_UPDATES,
                shorthand=ProtocolShorthand.CP,
            ),
            Occasion(
                when=(
                    "a Participant learns that an exploit for the "
                    "vulnerability is public"
                ),
                anchor="exploit-public",
                description=(
                    "Announces evidence that an exploit is publicly available."
                ),
                example="add_exploit_public_to_case",
                distinguisher=FieldValue(
                    object_type=CaseStatus, field="pxa", value=CS_pxa.PXa
                ),
                howto=HowToGuide.STATUS_UPDATES,
                shorthand=ProtocolShorthand.CX,
            ),
            Occasion(
                when=(
                    "a Participant observes attacks that exploit the "
                    "vulnerability"
                ),
                anchor="attacks-observed",
                description=(
                    "Announces evidence that attackers are exploiting the "
                    "vulnerability."
                ),
                example="add_attacks_observed_to_case",
                distinguisher=FieldValue(
                    object_type=CaseStatus, field="pxa", value=CS_pxa.pxA
                ),
                howto=HowToGuide.STATUS_UPDATES,
                shorthand=ProtocolShorthand.CA,
            ),
        ),
        page=MessagePage.CS,
    ),
    # Participant status
    SemanticEntry(
        semantics=MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
        pattern=AddParticipantStatusToParticipantPattern,
        event_class=AddParticipantStatusToParticipantReceivedEvent,
        use_case_class=AddParticipantStatusToParticipantReceivedUseCase,
        phrase="{actor} updated {object}'s participant status",
        wire_activity_class=_AddStatusToParticipantActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="a Vendor becomes aware of the vulnerability",
                anchor="vendor-awareness",
                description=(
                    "Announces that the report has reached the Vendor whose "
                    "participant record is the target."
                ),
                example="add_vendor_awareness_to_participant",
                distinguisher=FieldValue(
                    object_type=ParticipantStatus,
                    field="vf_state",
                    value=CS_vf.Vf,
                ),
                howto=HowToGuide.STATUS_UPDATES,
                shorthand=ProtocolShorthand.CV,
                usual_senders=(CVDRole.VENDOR,),
            ),
            Occasion(
                when="a Vendor has a fix ready",
                anchor="fix-readiness",
                description=(
                    "Announces that the Vendor whose participant record is the"
                    " target has a fix ready."
                ),
                example="add_fix_readiness_to_participant",
                distinguisher=FieldValue(
                    object_type=ParticipantStatus,
                    field="vf_state",
                    value=CS_vf.VF,
                ),
                howto=HowToGuide.STATUS_UPDATES,
                shorthand=ProtocolShorthand.CF,
                usual_senders=(CVDRole.VENDOR,),
            ),
            Occasion(
                when="a Deployer has deployed the fix",
                anchor="fix-deployed",
                description=(
                    "Announces that the Deployer whose participant record is "
                    "the target has deployed the fix."
                ),
                example="add_fix_deployment_to_participant",
                distinguisher=FieldValue(
                    object_type=ParticipantStatus,
                    field="d_state",
                    value=CS_d.D,
                ),
                howto=HowToGuide.STATUS_UPDATES,
                shorthand=ProtocolShorthand.CD,
                usual_senders=(CVDRole.DEPLOYER,),
            ),
        ),
        page=MessagePage.CS,
    ),
]
