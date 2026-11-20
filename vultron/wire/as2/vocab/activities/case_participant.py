#!/usr/bin/env python
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
"""
Provides Vultron ActivityStreams Activities related to CaseParticipants
"""

# Prior TODOs (now removed):
# "remove Literals" — no redundant Literal annotations exist in current code.
# "use pydantic typing more effectively" — Field aliases and model_validator are
# idiomatic pydantic v2; no further improvement identified.

from typing import ClassVar, Self

from pydantic import Field, model_validator

from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.activities._status_history import (
    require_status_history_add,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Announce,
    as_Remove,
    as_Update,
)
from vultron.wire.as2.vocab.base.objects.actors import as_CarriedActor
from vultron.wire.as2.vocab.base.utils import name_of
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import (
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseRef,
)


class _AddParticipantToCaseActivity(as_Add):
    """The CASE_MANAGER adds a new participant record to a case (VAM-06-004).

    ``Add(CaseParticipant, target=<case>)``, with ``context`` the case: the
    record joins the case's participant list, so it is an ``Add`` naming that
    list's owner in ``target`` (CLP-07-021), carrying the record in full
    (CM-11-024).  Only the CASE_MANAGER sends it, committed as its own
    ``add_case_participant_to_case`` entry (ADR-0114), and a replica seats the
    record in the case ``target`` names (CM-11-025).

    object_: the participant record, inline
    target: VulnerabilityCase
    context: VulnerabilityCase
    """

    object_: as_CaseParticipant = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseRef = Field(...)
    context: as_VulnerabilityCaseRef = Field(...)

    inline_required_refs: ClassVar[frozenset[str]] = frozenset({"object_"})

    @model_validator(mode="after")
    def _names_its_case(self) -> Self:
        if self.target is None:
            raise ValueError("a participant record names its case in target")
        if self.context is None:
            raise ValueError("a participant record names its case in context")
        return self

    @model_validator(mode="after")
    def set_name(self) -> Self:
        """Name the record added and its case, unless a name is given.

        Produces ``"{actor} Add as_CaseParticipant {participant_id} from
        {attributed_to} to {case_id}"``, so it reads as a record joining the
        case, not the actor itself.
        """
        if self.name is not None:
            return self

        parts = []
        if self.actor is not None:
            parts.append(name_of(self.actor))
        parts.append("Add as_CaseParticipant")
        participant_id = getattr(self.object_, "id_", None)
        if participant_id:
            parts.append(str(participant_id))
        attributed_to = getattr(self.object_, "attributed_to", None)
        if attributed_to:
            parts.extend(["from", str(attributed_to)])
        parts.extend(["to", name_of(self.target)])

        object.__setattr__(self, "name", " ".join(parts))
        return self


# add ParticipantStatus to <participant>/statuses
class _AddStatusToParticipantActivity(as_Add):
    """Add a ParticipantStatus to a participant's status history (ADR-0204).

    ``target`` is ``<participant>/statuses``, the ordered history whose
    newest item is the participant's current status, and ``context`` is the
    case.
    """

    object_: as_ParticipantStatus = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: NonEmptyString  # type: ignore[assignment]

    @model_validator(mode="after")
    def _names_a_status_history_in_a_case(self) -> Self:
        require_status_history_add(self, case_history=False)
        return self


class _ReinstateParticipantActivity(as_Add):
    """The Case Owner reinstates a removed actor in a VulnerabilityCase.

    ``Add(<Actor>, target=<case>)``: the Case Owner's own act, sent to the
    CASE_MANAGER only (CM-31-011, ADR-0199).  The ``object`` is the actor as
    a typed reference (``id`` + ``type``), not its ``CaseParticipant``: the
    case has one record per actor (CM-19-003).

    object_: the reinstated actor
    target: VulnerabilityCase
    """

    object_: as_CarriedActor = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseRef = Field(...)

    inline_required_refs: ClassVar[frozenset[str]] = frozenset({"object_"})

    @model_validator(mode="after")
    def _names_its_case(self) -> Self:
        if self.target is None:
            raise ValueError("a reinstatement names its case in target")
        return self


class _RemoveParticipantActivity(as_Remove):
    """The Case Owner removes an actor from active participation in a case.

    ``Remove(<Actor>, origin=<case>)``: the Case Owner's own act, sent to the
    CASE_MANAGER only (CM-31-004, ADR-0199).  A ``Remove`` names the
    collection it takes its object from in ``origin`` (VOC Remove).  The
    ``object`` is the actor as a typed reference, not its
    ``CaseParticipant``.

    object_: the removed actor
    origin: VulnerabilityCase
    """

    object_: as_CarriedActor = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    origin: as_VulnerabilityCaseRef = Field(...)

    inline_required_refs: ClassVar[frozenset[str]] = frozenset({"object_"})

    @model_validator(mode="after")
    def _names_its_case(self) -> Self:
        if self.origin is None:
            raise ValueError("a removal names its case in origin")
        return self


class _AnnounceAdmittedActActivity(as_Announce):
    """The CASE_MANAGER announces an act it admitted (ADR-0199).

    ``Announce(<the admitted act>)``: sent to an actor the act concerns that
    the entry's fan-out does not reach, such as a removed or reinstated
    participant.  It informs and asks nothing.  The act travels inline, as
    received, keeping its own author and id; ``inReplyTo`` names it too,
    because the act's commit caused the ``Announce`` (ADR-0204), and
    ``context`` is the case.  The class does not check that ``inReplyTo``
    names the carried act: the sender's factory refuses a mismatch, and a
    receiver takes one as received, since it acts on neither (CLP-15-007).

    object_: the admitted act, inline
    in_reply_to: the admitted act's id
    context: VulnerabilityCase
    """

    object_: as_Activity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    in_reply_to: NonEmptyString = Field(default=...)
    context: as_VulnerabilityCaseRef = Field(...)

    inline_required_refs: ClassVar[frozenset[str]] = frozenset({"object_"})

    @model_validator(mode="after")
    def _names_its_case(self) -> Self:
        if self.context is None:
            raise ValueError("an announcement names its case in context")
        return self


class _UpdateParticipantActivity(as_Update):
    """Update a as_CaseParticipant.

    The CASE_MANAGER's own act recording a change to a participant record,
    such as a ``CASE_OWNER`` role moving on an ownership transfer, committed
    as its ``update_case_participant`` ledger entry (CLP-07-013).  The
    registry recognizes it, but no received use case handles it, so an inbox
    reports a received one as "no use case found" (ADR-0140).

    object_: as_CaseParticipant
    """

    object_: as_CaseParticipant = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
