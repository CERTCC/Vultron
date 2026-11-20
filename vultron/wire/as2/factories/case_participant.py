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
Factory functions for outbound Vultron case-participant activities.

These are the sole public construction API for activities involving
``as_CaseParticipant`` objects. Internal activity subclasses are
imported here and MUST NOT be imported by callers.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

from datetime import datetime

from vultron.core.models._helpers import _as_id
from vultron.core.models.status_history import status_history_id
from vultron.wire.as2.context_agreement import case_uri_of
from vultron.wire.as2.factories._construct import build_activity
from vultron.wire.as2.factories._context import (
    case_target_ref,
    with_case_context,
)
from vultron.wire.as2.factories._held import as_answered
from vultron.wire.as2.vocab.activities.case_participant import (
    _AddParticipantToCaseActivity,
    _AddStatusToParticipantActivity,
    _AnnounceAdmittedActActivity,
    _ReinstateParticipantActivity,
    _RemoveParticipantActivity,
    _UpdateParticipantActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Announce,
    as_Remove,
    as_Update,
)
from vultron.wire.as2.vocab.base.objects.actors import actor_reference
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
    as_CaseParticipantRef,
)
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseRef,
)


def add_participant_to_case_activity(
    participant: as_CaseParticipant,
    target: as_VulnerabilityCaseRef,
    *,
    at: datetime,
    **kwargs,
) -> as_Add:
    """Build ``Add(CaseParticipant, target=<case>)``, the record in full.

    The CASE_MANAGER's own act bringing a participant record into the case's
    participant list (VAM-06-004, CLP-07-021).  ``context`` is the case
    unless the caller names it (CLP-07-007).  The internal class generates a
    descriptive ``name`` if none is given.

    Args:
        participant: The ``as_CaseParticipant`` added, carried inline.
        target: The ``VulnerabilityCase`` (or its URI) whose participant list
            the record joins.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``id_``).

    Returns:
        An ``as_Add`` whose ``object_`` is the participant and whose
        ``target`` and ``context`` are the case.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails, or
            ``context`` names another case than ``target``.
    """

    def _fields() -> dict[str, object]:
        fields = with_case_context(
            {
                "object_": participant,
                "target": case_target_ref(target),
                **kwargs,
            },
            target,
        )
        # The record joins the list of the case the activity is about, so
        # the two slots name one case (CLP-07-007, CLP-07-021).
        if case_uri_of(fields.get("context")) != case_uri_of(target):
            raise ValueError(
                "a participant record is added to the case its context names"
            )
        return fields

    return build_activity(
        "add_participant_to_case_activity",
        _AddParticipantToCaseActivity,
        at,
        _fields,
        also=(ValueError,),
    )


def update_participant_activity(
    participant: as_CaseParticipant,
    *,
    at: datetime,
    **kwargs,
) -> as_Update:
    """Build an Update(CaseParticipant).

    The snapshot shape of a CASE_MANAGER-authored ledger entry recording a
    change to a participant record, carrying the record in full (CLP-07-021),
    labelled ``update_case_participant``; no received use case handles it
    (ADR-0140).

    Args:
        participant: The changed ``as_CaseParticipant``.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``context``, ``id_``).

    Returns:
        An ``as_Update`` whose ``object_`` is the participant.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "update_participant_activity",
        _UpdateParticipantActivity,
        at,
        lambda: {"object_": participant, **kwargs},
    )


def add_status_to_participant_activity(
    status: as_ParticipantStatus,
    participant: as_CaseParticipantRef,
    *,
    at: datetime,
    **kwargs,
) -> as_Add:
    """Build an Add(ParticipantStatus, target=<participant>/statuses).

    The ``target`` is the participant's status history, an ordered
    collection whose newest item is its current status, and ``context`` is
    the case (ADR-0204).  An explicit ``context`` is kept; otherwise it is
    the case the status names in its own ``context`` (HP-08-008).

    Args:
        status: The ``as_ParticipantStatus`` to add.
        participant: The ``as_CaseParticipant`` (or its URI) whose status
            history the status joins.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``context``).

    Returns:
        An ``as_Add`` whose ``object_`` is the status and whose ``target`` is
        ``<participant>/statuses``.

    Raises:
        VultronActivityConstructionError: If *participant* names no record,
            no case can be named in ``context``, or Pydantic validation
            fails.
    """
    return build_activity(
        "add_status_to_participant_activity",
        _AddStatusToParticipantActivity,
        at,
        lambda: {
            "object_": status,
            "target": status_history_id(_as_id(participant) or ""),
            **with_case_context(kwargs, getattr(status, "context", None)),
        },
        also=(ValueError,),
    )


def reinstate_participant_activity(
    reinstated: str,
    target: as_VulnerabilityCaseRef,
    *,
    at: datetime,
    **kwargs,
) -> as_Add:
    """Build the Case Owner's reinstatement, ``Add(<Actor>, target=<case>)``.

    The Case Owner's own act, sent to the CASE_MANAGER only (CM-31-011,
    ADR-0199).  The ``object`` is the reinstated actor as a typed reference
    (``id`` + ``type``, AKM-05-017), not its ``CaseParticipant``.

    Args:
        reinstated: The URI of the actor being reinstated.
        target: The ``VulnerabilityCase`` (or its URI) it is reinstated in.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``id_``).

    Returns:
        An ``as_Add`` whose ``object_`` is the actor reference.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "reinstate_participant_activity",
        _ReinstateParticipantActivity,
        at,
        lambda: {
            "object_": actor_reference(reinstated),
            "target": case_target_ref(target),
            **with_case_context(kwargs, target),
        },
    )


def remove_participant_activity(
    removed: str,
    origin: as_VulnerabilityCaseRef,
    *,
    at: datetime,
    **kwargs,
) -> as_Remove:
    """Build the Case Owner's removal, ``Remove(<Actor>, origin=<case>)``.

    The Case Owner's own act, sent to the CASE_MANAGER only (CM-31-004,
    ADR-0199).  A ``Remove`` names the collection it takes its object from
    in ``origin`` (VOC Remove).  The ``object`` is the removed actor as a
    typed reference (``id`` + ``type``, AKM-05-017), not its
    ``CaseParticipant``.

    Args:
        removed: The URI of the actor being removed.
        origin: The ``VulnerabilityCase`` (or its URI) it is removed from.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``id_``).

    Returns:
        An ``as_Remove`` whose ``object_`` is the actor reference.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "remove_participant_activity",
        _RemoveParticipantActivity,
        at,
        lambda: {
            "object_": actor_reference(removed),
            "origin": case_target_ref(origin),
            **with_case_context(kwargs, origin),
        },
    )


def announce_admitted_act_activity(
    admitted: as_Activity,
    case: as_VulnerabilityCaseRef,
    *,
    at: datetime,
    **kwargs,
) -> as_Announce:
    """Build the CASE_MANAGER's ``Announce(<the admitted act>)`` (ADR-0199).

    Sent to an actor the act concerns that the entry's fan-out does not
    reach.  The act travels inline: one this actor received is embedded as
    it arrived, every field as sent (:func:`as_answered`, DL-06-004), so it
    keeps its own author and id.  ``inReplyTo`` names the act, whose commit
    caused the ``Announce`` (ADR-0204), and ``context`` is the case.  The
    CASE_MANAGER is the ``actor``; pass it, the recipients and the derived
    ``id_``.  The sender refuses an ``inReplyTo`` that names anything but
    the act; the class itself is lenient about it, as a receiver is
    (``announce_admitted_act_received_tree``).

    Args:
        admitted: The admitted act, as this actor holds it.
        case: The ``VulnerabilityCase`` (or its URI) the act concerns.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``id_``).

    Returns:
        An ``as_Announce`` whose ``object_`` is the admitted act.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails,
            or ``in_reply_to`` names anything but the act.
    """

    def _fields() -> dict[str, object]:
        act = as_answered(as_Activity, admitted)
        # as_answered passes anything but a received activity through
        # unchanged, and the constructor refuses one that is not an activity,
        # so the id is read without assuming one.
        act_id = getattr(act, "id_", None)
        fields: dict[str, object] = {
            "object_": act,
            "in_reply_to": act_id,
            "context": case_target_ref(case),
            **kwargs,
        }
        if fields["in_reply_to"] != act_id:
            raise ValueError(
                "an announcement names the act it carries in inReplyTo"
            )
        return fields

    return build_activity(
        "announce_admitted_act_activity",
        _AnnounceAdmittedActActivity,
        at,
        _fields,
        also=(ValueError,),
    )
