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

Provides :func:`announced_case_id`, which names the case an Announce carries;
the guard that judges a copy of a case the replica already holds by the
ledger tail it names (SYNC-16-006); the action node that seeds, or replaces,
the local case with the announced ``VulnerabilityCase``, stores embedded
participants, and links any matching report-case associations; and the node
that asks for the entries a replacing copy is ahead of the replica's chain
by (SYNC-16-007).  The sender check is not here: the received tree's factory
composes it from the use case's declared rule (HP-01-008).

Per ``specs/mpcvd-cases.yaml`` MV-10-003 (create if absent),
``specs/participant-case-replica.yaml`` PCR-02-003 and PCR-02-004 (an
authoritative update if present), and ADR-0142.

The composite tree factory is in ``announce_case_received_tree.py`` at
the process-area root per BTND-07-003.
"""

from typing import Any, cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.idempotency import FlaggedRepeatGuardMixin
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_copy_position import CaseCopyPosition
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.services.carried_embargo import store_carried_embargo
from vultron.core.services.case_copy import CaseCopyVerdict, judge_case_copy
from vultron.core.services.case_replica_seeding import (
    link_report_case_links,
    normalize_participant_refs,
    store_embedded_participants,
)
from vultron.errors import (
    VultronNotFoundError,
    VultronValidationError,
    VultronWiringError,
)

#: Blackboard key: whether the announced copy replaces a case this replica
#: already holds, written by :class:`CaseCopyNotStaleNode` and read by
#: :class:`RequestCaseCopyBackfillNode`.
CASE_COPY_REPLACES_KEY = "case_copy_replaces"


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


class CaseCopyNotStaleNode(
    FlaggedRepeatGuardMixin, DataLayerConditionWithPorts
):
    """Guard: a copy of a case this replica holds may replace it (SYNC-16-006).

    A replica that does not hold the case yet seeds it from any copy
    (PCR-02-003): ``SUCCESS``.  One that holds it compares the ledger tail
    the copy names (SYNC-16-005) with its own position
    (:func:`~vultron.core.services.case_copy.judge_case_copy`):

    - the replica is already past the tail: ``FAILURE`` with ``is_stale``
      set, logged at INFO; the handler reports ``SKIPPED`` and the case is
      unchanged;
    - it holds a different entry at the tail's index: ``FAILURE`` with
      ``is_conflict`` set, logged at ERROR; the handler reports ``REFUSED``
      and the case is unchanged;
    - otherwise ``SUCCESS``: the copy replaces the case.

    A copy that names no tail cannot be told from a stale one, so a replica
    holding the case refuses it (``FAILURE``, WARNING).

    Writes ``/case_copy_replaces`` on every ``SUCCESS``: ``True`` when the
    copy replaces a held case, ``False`` for a first seed.
    """

    _REPEAT_FLAG = "is_stale"

    OUTPUT_PORTS: dict[str, PortInformation] = {
        CASE_COPY_REPLACES_KEY: PortInformation(data_type=bool, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {CASE_COPY_REPLACES_KEY: f"/{CASE_COPY_REPLACES_KEY}"}

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
        #: True only after the copy was found stale (SYNC-16-006).
        self.is_stale = False
        #: True only after the copy was found to conflict with the chain.
        self.is_conflict = False

    def update(self) -> Status:
        self.is_stale = False
        self.is_conflict = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self._resolve_case_replica(self.case_id) is None:
            # Regime 2 (ADR-0087): no replica yet, so this is a first seed.
            self._set_output(CASE_COPY_REPLACES_KEY, False)
            return Status.SUCCESS

        tail = getattr(self.case_obj, "ledger_tail", None)
        if tail is None:
            self.feedback_message = (
                f"the copy of case '{self.case_id}' names no ledger tail, so"
                " this replica cannot tell it from a stale one (SYNC-16-005)"
            )
            self.logger.warning(
                "%s: refusing Announce '%s' from '%s': %s",
                self.name,
                self._request.activity_id,
                self._request.actor_id,
                self.feedback_message,
            )
            return Status.FAILURE

        judgement = judge_case_copy(self.case_id, tail, self.datalayer)
        if judgement.verdict is CaseCopyVerdict.CONFLICT:
            self.is_conflict = True
            self.feedback_message = judgement.reason
            self.logger.error(
                "%s: case copy '%s' in Announce '%s' from '%s' conflicts with"
                " this replica's ledger; case unchanged: %s",
                self.name,
                self.case_id,
                self._request.activity_id,
                self._request.actor_id,
                judgement.reason,
            )
            return Status.FAILURE
        if judgement.verdict is CaseCopyVerdict.STALE:
            self.is_stale = True
            self.feedback_message = judgement.reason
            self.logger.info(
                "%s: skipping case copy '%s' in Announce '%s' from '%s';"
                " case unchanged: %s",
                self.name,
                self.case_id,
                self._request.activity_id,
                self._request.actor_id,
                judgement.reason,
            )
            return Status.FAILURE
        self.logger.debug("%s: %s", self.name, judgement.reason)
        self._set_output(CASE_COPY_REPLACES_KEY, True)
        return Status.SUCCESS


class RequestCaseCopyBackfillNode(DataLayerActionWithPorts, StateWriteCapable):
    """Ask for the entries a replacing copy is ahead of this chain by.

    Runs after :class:`SeedAnnouncedCaseNode`.  When the copy replaced a
    case this replica held (``/case_copy_replaces``) and its tail is ahead of
    the replica's chain, the case now reflects entries the chain lacks
    (SYNC-16-007).  The node records the copy's tail
    (:class:`~vultron.core.models.case_copy_position.CaseCopyPosition`), so
    each of those entries is stored as a no-op when it arrives, and sends
    the sender ``Reject(CaseLedgerEntry)`` carrying the replica's own tail,
    which the CASE_MANAGER answers by replaying from it (SYNC-03-002).

    The ``Reject`` names the last entry the chain stores.  A replica whose
    chain stores none has no entry to name; it logs that at WARNING and
    sends nothing, and the first entry the CASE_MANAGER fans out next arrives
    as a forward gap whose own ``Reject`` asks for the rest (SYNC-14-002).

    Raises:
        VultronWiringError: A ``Reject`` is due and no ``sync_port`` was
            injected.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        CASE_COPY_REPLACES_KEY: PortInformation(data_type=bool, required=True),
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            CASE_COPY_REPLACES_KEY: f"/{CASE_COPY_REPLACES_KEY}",
            "sync_port": "/sync_port",
        }

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
        self._replaces = False
        self._sync_port: SyncActivityPort | None = None

    def initialise(self) -> None:
        super().initialise()
        self._replaces = bool(self.get_input(CASE_COPY_REPLACES_KEY))
        try:
            self._sync_port = cast(
                SyncActivityPort, self.get_input("sync_port")
            )
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None

    def update(self) -> Status:
        if not self._replaces:
            return Status.SUCCESS
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None

        tail = getattr(self.case_obj, "ledger_tail", None)
        if not isinstance(tail, LedgerPosition):
            raise VultronValidationError(
                f"{self.name}: the copy replacing case '{self.case_id}'"
                " names no ledger tail; the guard admits none (SYNC-16-006)"
            )
        judgement = judge_case_copy(self.case_id, tail, self.datalayer)
        if tail.log_index <= judgement.chain_index:
            return Status.SUCCESS
        self.datalayer.save(
            CaseCopyPosition(
                case_id=self.case_id,
                log_index=tail.log_index,
                entry_hash=tail.entry_hash,
            )
        )
        chain_tail = judgement.chain_tail
        if chain_tail is None:
            self.logger.warning(
                "%s: case '%s' was replaced by a copy at entry %d, but this"
                " replica's chain stores no entry for a Reject to name; the"
                " next entry fanned out asks for the rest (SYNC-14-002)",
                self.name,
                self.case_id,
                tail.log_index,
            )
            return Status.SUCCESS
        if self._sync_port is None:
            raise VultronWiringError(
                f"{self.name}: sync_port must be injected to ask for the"
                " entries a replacing case copy is ahead by (SYNC-16-007)"
            )
        self.logger.info(
            "%s: case '%s' replaced by a copy at entry %d, ahead of this"
            " replica's chain at %d; sending Reject(CaseLedgerEntry) to '%s'"
            " (SYNC-16-007)",
            self.name,
            self.case_id,
            tail.log_index,
            chain_tail.log_index,
            self._request.actor_id,
        )
        self._sync_port.send_reject_log_entry(
            entry=chain_tail,
            tail_hash=chain_tail.entry_hash,
            actor_id=self.actor_id,
            to=[self._request.actor_id],
        )
        return Status.SUCCESS


class SeedAnnouncedCaseNode(DataLayerActionWithPorts, StateWriteCapable):
    """Seed, or replace, the local case with a received ``VulnerabilityCase``.

    On first receipt the node saves ``case_obj`` and stores any embedded
    participants and linked report-case associations (MV-10-003,
    PCR-02-003).  For a case this replica already holds, the copy is an
    authoritative update (PCR-02-004): the guard before this node has
    judged it current by its ledger tail (SYNC-16-006), so the node
    replaces the stored case with it and refreshes participants, reports
    and links.  The case is saved without the tail, which describes the copy
    and is never a value of the case file (SYNC-16-005).

    On both paths the ``EmbargoEvent`` the case names is held *before* the
    case is saved, and a case naming one this store cannot read is refused
    with ``FAILURE`` and nothing saved (EMB-18-003).

    Returns ``SUCCESS`` in both paths, ``FAILURE`` on such a refusal, a
    persist error, or a missing DataLayer.
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
            # the copy current by its ledger tail (PCR-02-004, SYNC-16-006).
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
            _store_embedded_reports(self.case_obj, self.datalayer)
            store_embedded_participants(
                self.case_obj,
                self.datalayer,
                self.case_id,
                authoritative=True,
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
            link_report_case_links(self.datalayer, self.case_obj)
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
