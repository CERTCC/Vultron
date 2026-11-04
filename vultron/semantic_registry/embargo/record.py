"""Registry entries for the CASE_MANAGER's own embargo and consent records."""

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
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.embargo import (
    CreateEmbargoConsentReceivedEvent,
    CreateEmbargoEventReceivedEvent,
    UpdateEmbargoConsentReceivedEvent,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    MessagePage,
    Occasion,
)
from vultron.wire.as2.extractor import (
    CreateEmbargoConsentPattern,
    CreateEmbargoEventPattern,
    UpdateEmbargoConsentPattern,
)
from vultron.wire.as2.vocab.activities.embargo import (
    _CreateEmbargoConsentActivity,
    _CreateEmbargoEventActivity,
    _UpdateEmbargoConsentActivity,
)

ENTRIES: list[SemanticEntry] = [
    # The CASE_MANAGER's own records: an embargo its case's creation wrote,
    # and its acts on consent rows, each committed as its own entry carrying
    # the record in full (ADR-0122, CLP-07-021).  Only the CASE_MANAGER commits
    # them, and a participant takes the record from the ledger, so no
    # received use case handles them (ADR-0140 item 5).
    SemanticEntry(
        semantics=MessageSemantics.CREATE_EMBARGO_EVENT,
        pattern=CreateEmbargoEventPattern,
        event_class=CreateEmbargoEventReceivedEvent,
        use_case_class=None,
        phrase="{actor} created the case's embargo",
        wire_activity_class=_CreateEmbargoEventActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the CASE_MANAGER has created a case and, with it, an "
                    "embargo such as the default embargo"
                ),
                anchor="create-embargo-event",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Create embargo event",
                description=(
                    "Carries the new embargo in full, its start and end "
                    "times included. It follows the case's genesis entry."
                ),
                example="create_embargo_event",
                notes=(
                    "Each participant learns of it from the case ledger, so "
                    "it is addressed to nobody."
                ),
            ),
        ),
        page=MessagePage.EM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.CREATE_EMBARGO_CONSENT,
        pattern=CreateEmbargoConsentPattern,
        event_class=CreateEmbargoConsentReceivedEvent,
        use_case_class=None,
        phrase="{actor} created an embargo consent row",
        wire_activity_class=_CreateEmbargoConsentActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the CASE_MANAGER creates a participant's consent row "
                    "for an embargo, such as the UNINVITED row a proposal "
                    "writes"
                ),
                anchor="create-embargo-consent",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Create embargo consent",
                description=(
                    "Carries the new consent row in full: the embargo it "
                    "answers, the participant it belongs to and its state."
                ),
                example="create_embargo_consent",
                notes=(
                    "Each participant learns of it from the case ledger, so "
                    "it is addressed to nobody."
                ),
            ),
        ),
        page=MessagePage.EM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.UPDATE_EMBARGO_CONSENT,
        pattern=UpdateEmbargoConsentPattern,
        event_class=UpdateEmbargoConsentReceivedEvent,
        use_case_class=None,
        phrase="{actor} updated an embargo consent row",
        wire_activity_class=_UpdateEmbargoConsentActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the CASE_MANAGER changes a participant's consent row, "
                    "such as an invitation timing out, the rows carried over "
                    "at activation or a change of its own consent"
                ),
                anchor="update-embargo-consent",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Update embargo consent",
                description=(
                    "Carries the changed consent row in full. A CASE_MANAGER "
                    "with an embargo stake of its own records a change of "
                    "its own consent this way, never as a Reject of the "
                    "Invite."
                ),
                example="update_embargo_consent",
                notes=(
                    "Each participant learns of it from the case ledger, so "
                    "it is addressed to nobody."
                ),
            ),
        ),
        page=MessagePage.EM,
    ),
]
