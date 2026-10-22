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

"""BT leaf nodes for received Announce(VulnerabilityCase) activities.

Provides :func:`announced_case_id`, which names the case an Announce carries,
and the action node that seeds, or replaces, the local case with the
announced ``VulnerabilityCase``, stores embedded participants, and links any
matching report-case associations.  The guard that judges a copy of a held
case by its ledger position, and the node that asks for the entries it is ahead
by, are in :mod:`.case_copy`.  The sender check is not here: the received
tree's factory composes it from the use case's declared rule (HP-01-008).

Per ``specs/mpcvd-cases.yaml`` MV-10-003 (create if absent),
``specs/participant-case-replica.yaml`` PCR-02-003 and PCR-02-004 (an
authoritative update if present), and ADR-0142.

The composite tree factory is in ``announce_case_received_tree.py`` at
the process-area root per BTND-07-003.
"""

from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.case_copy import (
    required_position,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.services.carried_embargo import store_carried_embargo
from vultron.core.services.case_replica_seeding import (
    link_report_case_links,
    normalize_participant_refs,
    store_embedded_participants,
)
from vultron.errors import (
    VultronNotFoundError,
    VultronValidationError,
)


def announced_case_id(
    request: AnnounceVulnerabilityCaseReceivedEvent, case_obj: Any
) -> str:
    """The id of the case *request* announces as *case_obj*.

    Raises:
        VultronValidationError: The event carries no activity, the activity
            no object, the object is not a ``VulnerabilityCase``, or the case
            has no id.  The message is the refusal's reason.
    """
    if request.activity is None:
        raise VultronValidationError("Announce carries no activity")
    if case_obj is None:
        raise VultronValidationError("Announce carries no case object")
    if getattr(case_obj, "type_", None) != "VulnerabilityCase":
        raise VultronValidationError(
            "Announce object is not a VulnerabilityCase"
            f" ({type(case_obj).__name__})"
        )
    # Read the id itself: ``_as_id`` falls back to ``str(obj)`` and so never
    # reports a case-typed object that has none.
    case_id = getattr(case_obj, "id_", None)
    if not isinstance(case_id, str) or not case_id:
        raise VultronValidationError("Announced case object has no id")
    return case_id


def _store_embedded_reports(case_obj, datalayer) -> None:
    """Persist full VulnerabilityReport objects embedded in *case_obj*.

    Per CBT-01-012: receiving handlers store domain objects by iterating
    embedded collections.  Only full objects (not bare string refs) are
    saved; bare IDs are skipped since the object data is not available.

    Duck-type check: an embedded object has a non-None ``id_`` attribute and
    a ``type_`` of ``"VulnerabilityReport"``.  Bare string references are
    skipped cleanly.
    """
    for report_ref in getattr(case_obj, "vulnerability_reports", []):
        if isinstance(report_ref, str):
            continue
        report_id = getattr(report_ref, "id_", None)
        report_type = getattr(report_ref, "type_", None)
        if not report_id or str(report_type) != "VulnerabilityReport":
            continue
        if datalayer.read(report_id) is None:
            datalayer.save(report_ref)


class SeedAnnouncedCaseNode(DataLayerActionWithPorts, StateWriteCapable):
    """Seed, or replace, the local case with a received ``VulnerabilityCase``.

    On first receipt the node saves ``case_obj`` and stores any embedded
    participants and linked report-case associations (MV-10-003,
    PCR-02-003).  For a case this replica already holds, the copy is an
    authoritative update (PCR-02-004): the guard before this node has
    judged it current by its ledger position (SYNC-16-006), so the node
    replaces the stored case with it, position included, and refreshes
    participants, reports and links, in one transaction.  A case stored at a
    position ahead of the replica's chain stores the entries up to it as
    no-ops (SYNC-16-007).  A re-delivery of the same Announce
    (MV-10-004) takes the same judgement: at the case's own position it is
    current and replaces the case with itself; once the chain is past it,
    it is stale and skipped.

    On both paths the ``EmbargoEvent`` the case names is held *before* the
    case is saved, and a case naming one this store cannot read is refused
    with ``FAILURE`` and nothing saved (EMB-18-003).

    Returns ``SUCCESS`` in both paths, ``FAILURE`` on such a refusal, a
    first-seed persist error, or a missing DataLayer.  A store failure while
    replacing rolls the replacement back and raises.
    """

    def __init__(
        self,
        case_id: str,
        case_obj: VulnerabilityCase | Any,
        request: AnnounceVulnerabilityCaseReceivedEvent,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.case_obj = case_obj
        self._request = request

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        # Hold the embargo the case names before saving it, on either path,
        # and refuse a case naming one this store cannot read (EMB-18-003).
        try:
            store_carried_embargo(self.case_obj, self.datalayer)
        except (VultronNotFoundError, VultronValidationError) as exc:
            self.feedback_message = (
                f"Refusing announced case '{self.case_id}': it names an"
                f" active embargo this store cannot read (EMB-18-003): {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        existing = self.datalayer.read(self.case_id)
        if existing is not None:
            # Replace path: the replica holds the case, and the guard judged
            # the copy current by its ledger position (PCR-02-004, SYNC-16-006).
            # Refresh participants and reports, then save the copy with
            # string participant refs so the row never carries inline
            # sub-objects (#2233 write-path).
            self.logger.info(
                "%s: replacing case '%s' with the copy from actor '%s'"
                " (PCR-02-004)",
                self.name,
                self.case_id,
                self._request.actor_id,
            )
            self._replace()
            return Status.SUCCESS

        try:
            # Store participants first so their standalone records exist before
            # we normalise case_participants to string IDs, then save the case
            # with only ID refs (no inline objects) — #2233 write-path fix.
            store_embedded_participants(
                self.case_obj, self.datalayer, self.case_id
            )
            # Persist a copy whose case_participants are string IDs only.
            # model_copy avoids direct field assignment (CM-27-001, #2295).
            _case_to_save = self.case_obj.model_copy(
                update={
                    "case_participants": normalize_participant_refs(
                        self.case_obj
                    )
                }
            )
            self.datalayer.save(_case_to_save)
            _store_embedded_reports(self.case_obj, self.datalayer)
            link_report_case_links(self.datalayer, self.case_obj)
            self.logger.info(
                "%s: seeded case '%s' from actor '%s'",
                self.name,
                self.case_id,
                self._request.actor_id,
            )
            return Status.SUCCESS
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3768
            self.feedback_message = str(exc)
            self.logger.error(  # noqa: TRY400  # ruff-baseline #3353
                "%s: failed to seed case '%s': %s",
                self.name,
                self.case_id,
                exc,
            )
            return Status.FAILURE

    def _replace(self) -> None:
        """Replace the held case with the copy, as one transaction.

        The participants, reports and the case at the copy's ledger position
        (SYNC-16-005) commit together or not at all, so a failure part-way
        leaves no replica half replaced (ADR-0146).  A store failure raises,
        and the handler reports it as an internal error.

        The embargo the copy carries is stored before, outside the
        transaction, on both paths (:meth:`update`): it is an immutable
        record copied as received (CM-23-016), so one left stored by a failed
        replacement is the record a redelivery stores again, not a half
        replacement.
        """
        assert self.datalayer is not None
        # The guard admitted the copy, so it names a position (SYNC-16-006).
        required_position(self.case_obj, self.case_id, self.name)
        with self.datalayer.transaction():
            _store_embedded_reports(self.case_obj, self.datalayer)
            store_embedded_participants(
                self.case_obj,
                self.datalayer,
                self.case_id,
                authoritative=True,
            )
            # Persist a copy whose case_participants are string IDs only.
            # model_copy avoids direct field assignment (CM-27-001, #2295).
            self.datalayer.save(
                self.case_obj.model_copy(
                    update={
                        "case_participants": normalize_participant_refs(
                            self.case_obj
                        )
                    }
                )
            )
            link_report_case_links(self.datalayer, self.case_obj)
