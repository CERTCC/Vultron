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


"""Store lookups that resolve a ``CaseProposal`` to the case it applies to.

A ``Create(as_CaseProposal)`` names a report, not a case.  Two nodes of the
received-side tree need the case it resolves to: the closed-case decline
(``CheckProposalCaseFullyClosedNode``) and the accept arm's case reuse
(``LoadExistingCaseNode``).  Both resolve it here, through
:func:`proposal_case_ids`, so they cannot disagree about which case a proposal
names (CS-22-001, #4650).

These are plain functions, not nodes, and store errors propagate from all of
them: each caller decides what a failure means in its own arm.

Spec: ``specs/case-proposal.yaml`` CP-05-006, CP-05-008.
"""

from collections.abc import Iterator
from typing import Any

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_proposal_admission import (
    CaseProposalAdmissionRecord,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import same_actor_id


def find_proposer_case(
    datalayer: CasePersistence, report_id: str, owner_id: str
) -> VulnerabilityCase | None:
    """Return the case for *report_id* that *owner_id* owns, or ``None``.

    The owner is the case's ``attributed_to``, compared with
    :func:`same_actor_id`, the sender guard's definition of one actor
    (#4772).  The store may hold several cases for one report (one per
    proposer, CP-05-008), so the single-row
    ``find_case_by_report_id`` lookup is only the fast path; when it returns
    another owner's case the cases are scanned for *owner_id*'s.  Store errors
    propagate.
    """
    first = datalayer.find_case_by_report_id(report_id)
    if first is None:
        return None
    if same_actor_id(first.attributed_to, owner_id):
        return first
    for case in datalayer.list_objects("VulnerabilityCase"):
        if (
            isinstance(case, VulnerabilityCase)
            and same_actor_id(case.attributed_to, owner_id)
            and report_id in _report_ids(case)
        ):
            return case
    return None


def _report_ids(case: VulnerabilityCase) -> set[str]:
    """The report ids *case* references, whether stored bare or inline."""
    return {
        entry if isinstance(entry, str) else str(entry.id_)
        for entry in case.vulnerability_reports
    }


def activity_names_proposal(activity: Any, proposal_id: str) -> bool:
    """Return True if *activity*'s top-level object is *proposal_id*.

    The object round-trips as the rehydrated ``as_CaseProposal``, as the bare URI
    storage dehydrated it to, or as a plain dict, so all three shapes are probed.
    Only the **top-level** object is compared, which is what keeps unrelated
    activities out: an ``Accept(Offer(VulnerabilityReport))`` from validate-report
    names the Offer, not the proposal.
    """
    obj = getattr(activity, "object_", None)
    if obj == proposal_id:
        return True
    if getattr(obj, "id_", None) == proposal_id:
        return True
    return isinstance(obj, dict) and obj.get("id") == proposal_id


def find_activity_for_proposal(
    datalayer: CasePersistence, proposal_id: str, activity_type: str
) -> Any | None:
    """Return a stored *activity_type* activity whose object is *proposal_id*."""
    for activity in datalayer.list_objects(activity_type) or []:
        if str(getattr(activity, "type_", "")) != activity_type:
            continue
        if activity_names_proposal(activity, proposal_id):
            return activity
    return None


def accepted_case_id(
    datalayer: CasePersistence, proposal_id: str
) -> str | None:
    """Return the case the stored ``Accept`` for *proposal_id* names.

    The ``Accept``'s ``result`` is the case the proposal produced or reused
    (CP-05-006, CP-05-008).  Like ``object_`` in
    :func:`activity_names_proposal`, it round-trips as the bare case id, as a
    rehydrated object, or as a plain dict, so all three shapes are read.
    Returns ``None`` when no ``Accept`` is stored or it names no case.
    """
    accept = find_activity_for_proposal(datalayer, proposal_id, "Accept")
    result = getattr(accept, "result", None)
    if isinstance(result, dict):
        case_id = result.get("id")
    else:
        case_id = getattr(result, "id_", result)
    return case_id if isinstance(case_id, str) and case_id else None


def proposal_case_ids(
    datalayer: CasePersistence,
    proposal_id: str,
    proposer_uri: str,
    report_id: str | None,
    *,
    admission_record_is_prior: bool,
    accepted_for_proposer_only: bool,
) -> Iterator[str]:
    """Yield the ids of the cases a proposal resolves to, the proposer's first.

    A proposal resolves to a case in one of two ways:

    - **The proposer's own case for the report** (CP-05-008).  This covers a
      new proposal id from the case's owner.
    - **The case this proposal's stored ``Accept`` names** (its ``result``).
      This covers a redelivery of the original proposal (CP-05-006), also
      after an ownership transfer, when the proposer is no longer the owner
      and the owner lookup finds nothing (#4650).  With no *report_id* it is
      the only way to find the case.

    A different proposer's case for the same report is never this proposal's
    case: that proposer gets a separate case (CP-05-008).

    The proposal id is chosen by the sender, so another actor can reuse an
    accepted proposal's id.  With *accepted_for_proposer_only* the stored
    ``Accept``'s case is yielded only when the proposal's
    ``CaseProposalAdmissionRecord`` names *proposer_uri*, so that actor is
    not led into the case and its native initialization does not write to
    it.  A former owner is still the admitted proposer.  The closed-case
    check passes ``False``: there the case is only declined, and nothing is
    written for it.

    The generator is lazy, so the ``Accept`` scan runs only when a caller asks
    for the next candidate.  The scan rehydrates every stored ``Accept``, so
    it also runs only when it can find something: when the proposal's
    ``CaseProposalAdmissionRecord`` shows that an earlier delivery accepted
    it.  The record is stored in the same ``ActTransaction`` as the
    ``Accept`` (ADR-0146), so without it no ``Accept`` for the proposal is
    stored.  A node that runs after this delivery wrote the record
    itself cannot tell that from the record, so it passes
    ``admission_record_is_prior`` as ``RecordProposalAdmissionNode`` reported
    it (``admission_record_was_prior``): ``False`` when this delivery wrote
    the record.

    Store errors propagate.
    """
    own_id: str | None = None
    if report_id is not None:
        own = find_proposer_case(datalayer, report_id, proposer_uri)
        if own is not None:
            own_id = str(own.id_)
            yield own_id

    if accepted_for_proposer_only and not _admitted_for(
        datalayer, proposal_id, proposer_uri
    ):
        return
    if _may_have_been_accepted(
        datalayer, proposal_id, admission_record_is_prior
    ):
        accepted = accepted_case_id(datalayer, proposal_id)
        if accepted is not None and accepted != own_id:
            yield accepted


def _admitted_for(
    datalayer: CasePersistence, proposal_id: str, proposer_uri: str
) -> bool:
    """Whether *proposal_id*'s admission record names *proposer_uri*.

    Compared with :func:`same_actor_id`, as ``SenderIsProposalAuthorNode``
    compares it, so the guard and this lookup agree on the proposer (#4772).
    """
    record = datalayer.read(CaseProposalAdmissionRecord.build_id(proposal_id))
    return isinstance(record, CaseProposalAdmissionRecord) and same_actor_id(
        str(record.proposer_uri), proposer_uri
    )


def _may_have_been_accepted(
    datalayer: CasePersistence,
    proposal_id: str,
    admission_record_is_prior: bool,
) -> bool:
    """Whether an earlier delivery accepted *proposal_id*, so the ``Accept``
    scan can find something."""
    if not admission_record_is_prior:
        return False
    admission_id = CaseProposalAdmissionRecord.build_id(proposal_id)
    return datalayer.read(admission_id) is not None


__all__ = [
    "accepted_case_id",
    "activity_names_proposal",
    "find_activity_for_proposal",
    "find_proposer_case",
    "proposal_case_ids",
]
