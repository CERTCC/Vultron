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

from vultron.core.behaviors.sender_entitlement import AddresseeSide
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

#: When a participant sends each P/X/A report, in either wire form.
_PXA_WHEN: dict[CS_pxa, str] = {
    CS_pxa.Pxa: (
        "a Participant learns that the public knows of the vulnerability"
    ),
    CS_pxa.PXa: (
        "a Participant learns that an exploit for the vulnerability is public"
    ),
    CS_pxa.pxA: (
        "a Participant observes attacks that exploit the vulnerability"
    ),
}

#: What every participant P/X/A occasion says about the wire form.
_PARTICIPANT_PXA_NOTES = (
    "A participant status is a snapshot of every dimension the sender "
    "holds, so it can also carry an unchanged `vfState` or `dState`; the "
    "dimension that changed makes the occasion. The report is the "
    "sender's view of the case status, not a change to it. The Case "
    "Manager records the status on the sender's participant record and "
    "chooses whether to adopt the reported `pxaState` for the case, by "
    "default only with the Case Owner's authorization. Only an adopted "
    "value changes the case status, and while an embargo is active or "
    "proposed, it ends or abandons the embargo."
)


def _participant_pxa_occasion(
    *,
    anchor: str,
    heading: str,
    description: str,
    example: str,
    pxa: CS_pxa,
    shorthand: ProtocolShorthand,
) -> Occasion:
    """An occasion for a participant's own P/X/A report, which travels as
    the ``pxa`` of the case status its ``ParticipantStatus`` embeds."""
    return Occasion(
        when=_PXA_WHEN[pxa],
        anchor=anchor,
        addressee=AddresseeSide.CASE_MANAGER,
        heading=heading,
        description=description,
        example=example,
        distinguisher=FieldValue(
            object_type=ParticipantStatus,
            within="case_status",
            field="pxa",
            value=pxa,
        ),
        howto=HowToGuide.STATUS_UPDATES,
        shorthand=shorthand,
        notes=_PARTICIPANT_PXA_NOTES,
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
                when=_PXA_WHEN[CS_pxa.Pxa],
                anchor="public-awareness",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Public awareness in a case status",
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
                when=_PXA_WHEN[CS_pxa.PXa],
                anchor="exploit-public",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Exploit public in a case status",
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
                when=_PXA_WHEN[CS_pxa.pxA],
                anchor="attacks-observed",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Attacks observed in a case status",
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
                addressee=AddresseeSide.CASE_MANAGER,
                description=(
                    "Announces that the report has reached the Vendor whose "
                    "participant record is the target."
                ),
                example="add_vendor_awareness_to_participant",
                distinguisher=FieldValue(
                    object_type=ParticipantStatus,
                    field="vf",
                    value=CS_vf.Vf,
                ),
                howto=HowToGuide.STATUS_UPDATES,
                shorthand=ProtocolShorthand.CV,
                usual_senders=(CVDRole.VENDOR,),
            ),
            Occasion(
                when="a Vendor has a fix ready",
                anchor="fix-readiness",
                addressee=AddresseeSide.CASE_MANAGER,
                description=(
                    "Announces that the Vendor whose participant record is the"
                    " target has a fix ready."
                ),
                example="add_fix_readiness_to_participant",
                distinguisher=FieldValue(
                    object_type=ParticipantStatus,
                    field="vf",
                    value=CS_vf.VF,
                ),
                howto=HowToGuide.STATUS_UPDATES,
                shorthand=ProtocolShorthand.CF,
                usual_senders=(CVDRole.VENDOR,),
            ),
            Occasion(
                when="a Deployer has deployed the fix",
                anchor="fix-deployed",
                addressee=AddresseeSide.CASE_MANAGER,
                description=(
                    "Announces that the Deployer whose participant record is "
                    "the target has deployed the fix."
                ),
                example="add_fix_deployment_to_participant",
                distinguisher=FieldValue(
                    object_type=ParticipantStatus,
                    field="d",
                    value=CS_d.D,
                ),
                howto=HowToGuide.STATUS_UPDATES,
                shorthand=ProtocolShorthand.CD,
                usual_senders=(CVDRole.DEPLOYER,),
            ),
            # A participant's own view of the public state travels in the
            # case status its participant status embeds (CSB-15-003).  It is
            # a suggestion: the CASE_MANAGER judges it with the rest of the
            # status (RSH-09-003), adopts it only through StatusAdoptionGate
            # (RSH-07-001), and an adopted P, X or A ends or abandons the
            # embargo (RSH-03-001), so each is an occasion of this entry
            # (#4569).
            _participant_pxa_occasion(
                anchor="participant-public-awareness",
                heading="Public awareness in a participant status",
                description=(
                    "Announces, in the sender's own participant status, "
                    "evidence that the vulnerability is known to the public."
                ),
                example="add_public_awareness_to_participant",
                pxa=CS_pxa.Pxa,
                shorthand=ProtocolShorthand.CP,
            ),
            _participant_pxa_occasion(
                anchor="participant-exploit-public",
                heading="Exploit public in a participant status",
                description=(
                    "Announces, in the sender's own participant status, "
                    "evidence that an exploit is publicly available."
                ),
                example="add_exploit_public_to_participant",
                pxa=CS_pxa.PXa,
                shorthand=ProtocolShorthand.CX,
            ),
            _participant_pxa_occasion(
                anchor="participant-attacks-observed",
                heading="Attacks observed in a participant status",
                description=(
                    "Announces, in the sender's own participant status, "
                    "evidence that attackers are exploiting the "
                    "vulnerability."
                ),
                example="add_attacks_observed_to_participant",
                pxa=CS_pxa.pxA,
                shorthand=ProtocolShorthand.CA,
            ),
        ),
        page=MessagePage.CS,
    ),
]
