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
Case lifecycle action nodes for case behavior trees.

Provides the CommitCaseLedgerEntryNode for hash-chained case ledger replication.

Per specs/sync-ledger-replication.yaml SYNC-02-002, SYNC-02-003.
"""

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.use_cases._helpers import build_activity_payload_snapshot
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)

#: Blackboard key by which a preceding read-only guard in any receive tree may
#: patch the ``object`` entry of the canonical ledger ``payload_snapshot`` read
#: by :class:`CommitCaseLedgerEntryNode`.  The value is a mapping
#: ``{"object_id": <id the patch applies to>, "fields": <wire-alias patch>}``,
#: or ``None`` when no adjudication applies.
#:
#: ``fields`` is a *patch*, not a replacement object: the guard names only the
#: fields it adjudicated, keyed by their wire aliases, and they are merged onto
#: whatever the snapshot already holds.  That keeps the recorded shape identical
#: to an unadjudicated entry's (RSH-05-009).
#:
#: Producers: :class:`~vultron.core.behaviors.status.nodes.dimension_filter.FilterParticipantStatusDimensionsNode`.
BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE = "ledger_payload_object_override"


def _extract_payload_snapshot(
    activity: Any, dl: CasePersistence | None = None
) -> dict[str, Any]:
    """Build a normalized payload snapshot for case-ledger commits."""
    event_activity = getattr(activity, "activity", None)
    if event_activity is not None:
        return cast(
            dict[str, Any],
            build_activity_payload_snapshot(event_activity, dl=dl),
        )
    snapshot = cast(
        dict[str, Any], build_activity_payload_snapshot(activity, dl=dl)
    )
    # Domain events serialize actor_id, not the wire-format actor URI.
    # Patch it in so the ledger schema's non-empty-URI check passes.
    if not snapshot.get("actor"):
        actor_id = getattr(activity, "actor_id", None)
        if actor_id:
            snapshot = dict(snapshot)
            snapshot["actor"] = actor_id
    return snapshot


#: snake_case spellings of the patchable flat status fields.  A snapshot is
#: normally serialized ``by_alias`` (camelCase), but a stale snake_case twin
#: left alongside a patched alias would let a consumer that prefers the
#: snake_case spelling read the value the receiver just refused.
_SNAKE_TWINS: dict[str, str] = {
    "rmState": "rm_state",
    "vfdState": "vfd_state",
    "emState": "em_state",
    "pxaState": "pxa_state",
    "emConsentState": "em_consent_state",
    "caseStatus": "case_status",
}

#: Producer class names recognized by the override consumer.  An override with
#: an unrecognized ``producer_type`` still applies (RSH-05-014 is a warning,
#: not a block); this set is an audit allowlist, not a security gate.
_RECOGNIZED_OVERRIDE_PRODUCERS: frozenset[str] = frozenset(
    {"FilterParticipantStatusDimensionsNode"}
)


def _merge_snapshot_object_fields(
    current: dict[str, Any], fields: dict[str, Any]
) -> dict[str, Any]:
    """Merge an adjudication patch onto a snapshot ``object``.

    One level of nesting is merged rather than replaced so that patching
    ``caseStatus.pxaState`` keeps the snapshot's ``caseStatus`` id and its other
    fields.  A ``caseStatus`` that is still a bare reference string is left
    alone — there is nothing to merge into, and clobbering it would drop the
    reference.

    ``name`` is dropped: it is a derived state summary and the sender's label
    describes the value that was just refused.
    """
    merged = dict(current)
    for key, value in fields.items():
        existing = merged.get(key)
        if isinstance(value, dict):
            if not isinstance(existing, dict):
                # Bare reference (or absent) — nothing to patch into.
                continue
            nested = dict(existing)
            for nested_key, nested_value in value.items():
                nested[nested_key] = nested_value
                nested.pop(_SNAKE_TWINS.get(nested_key, ""), None)
            merged[key] = nested
            continue
        merged[key] = value
        merged.pop(_SNAKE_TWINS.get(key, ""), None)
    merged.pop("name", None)
    return merged


def _snapshot_object_id(payload_snapshot: dict[str, Any]) -> str | None:
    """Return the ID of a payload snapshot's ``object``, inlined or not."""
    value = payload_snapshot.get("object")
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        return value.get("id") or value.get("id_") or None
    return None


class CommitCaseLedgerEntryNode(DataLayerActionWithPorts):
    """
    Commit a hash-chained CaseLedgerEntry and fan it out to all case participants.

    Creates a :class:`~vultron.core.models.case_ledger_entry.VultronCaseLedgerEntry`,
    persists it, and queues one ``Announce(CaseLedgerEntry)`` activity per
    participant to the actor's outbox.  The :class:`OutboxMonitor` delivers
    queued activities reactively — this node only writes to the outbox.

    ``case_id`` is resolved in order:

    1. Constructor parameter (if provided at tree-build time).
    2. ``case_id`` key in the py_trees blackboard (written by a prior node
       such as :class:`CreateCaseNode` or :class:`PersistCase`).

    If ``case_id`` cannot be resolved, the node returns ``FAILURE`` so the
    enclosing BT sequence propagates the error (ARCH-15-001).

    ``event_type`` and ``object_id`` are derived from the ``activity``
    blackboard key (the inbound :class:`~vultron.core.models.events.base.VultronEvent`
    placed there by :class:`~vultron.core.behaviors.bridge.BTBridge`).

    Per specs/sync-ledger-replication.yaml SYNC-02-002, SYNC-02-003.
    """

    def __init__(
        self,
        case_id: str | None = None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._sync_port: Any = None

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        ports["activity"] = PortInformation(data_type=object, required=False)
        ports["sync_port"] = PortInformation(data_type=object, required=False)
        ports["ledger_payload_object_override"] = PortInformation(
            data_type=object, required=False
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "activity": "/activity",
            "sync_port": "/sync_port",
            "ledger_payload_object_override": f"/{BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE}",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._case_id_bb: str | None = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            self._case_id_bb = None
        try:
            self._activity: Any = self.get_input("activity")
        except (NoDataAvailable, NotImplementedError):
            self._activity = None
        try:
            self._sync_port = self.get_input("sync_port")
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None
        try:
            self._ledger_payload_object_override: Any = self.get_input(
                "ledger_payload_object_override"
            )
        except (NoDataAvailable, NotImplementedError):
            self._ledger_payload_object_override = None

    def _resolve_case_id(self) -> str | None:
        return self._case_id or self._case_id_bb

    def _resolve_activity(self) -> Any | None:
        return self._activity

    def _resolve_payload_object_override(
        self, payload_snapshot: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Return a substitute ``object`` entry for the payload snapshot.

        A preceding read-only guard may have adjudicated the inbound assertion
        and published the portion the receiver actually accepts (RSH-05).  The
        canonical entry must record *that*, not the raw claim, otherwise the
        refused value is hash-chained and replicated to every participant.

        The override is a **patch**, not a replacement object: the guard names
        only the fields it adjudicated and they are merged onto the snapshot's
        existing ``object``.  That keeps the snapshot in the same wire shape the
        un-adjudicated path produces — flat ``rmState``/``vfdState``, nested
        ``caseStatus``, ``@context``, ``emConsentState``, ``cvdRole`` — which
        every replica and the invariant harness rely on (RSH-05-009,
        CLP-07-001, CM-18-006).  A whole-object replacement built in core would
        instead emit core dimension objects, since core must not import the wire
        layer to convert (ADR-0009, ADR-0017).

        The override names the object ID it applies to and is honoured only
        when the snapshot's ``object`` refers to the same ID: the py_trees
        blackboard is process-global and not cleared between executions, so an
        unmatched override is a leftover from an earlier run and is ignored.
        """
        override = self._ledger_payload_object_override
        if not isinstance(override, dict):
            return None
        fields = override.get("fields")
        if not isinstance(fields, dict) or not fields:
            return None
        # RSH-05-014: warn when producer_type is present but unrecognized.
        producer_type = override.get("producer_type")
        if (
            producer_type is not None
            and producer_type not in _RECOGNIZED_OVERRIDE_PRODUCERS
        ):
            self.logger.warning(
                "%s: ledger_payload_object_override from unrecognized"
                " producer '%s' — applying override (RSH-05-014)",
                self.name,
                producer_type,
            )
        # RSH-05-013: hard-fail on any unrecognized wire alias in fields.
        unknown = set(fields) - set(_SNAKE_TWINS)
        if unknown:
            raise VultronValidationError(
                f"ledger_payload_object_override contains unrecognized wire"
                f" alias(es) {unknown!r} — fix the producer (RSH-05-013)"
            )
        current = payload_snapshot.get("object")
        if not isinstance(current, dict):
            return None
        if _snapshot_object_id(payload_snapshot) != override.get("object_id"):
            return None
        return _merge_snapshot_object_fields(current, fields)

    def _activity_metadata(
        self, activity: Any | None, case_id: str
    ) -> tuple[str, str, dict[str, Any]]:
        if activity is None:
            return case_id, "case_event", {}

        object_id = getattr(activity, "activity_id", case_id)
        semantic_type = getattr(activity, "semantic_type", None)
        event_type = (
            semantic_type.value
            if semantic_type is not None
            else getattr(activity, "activity_type", "case_event")
            or "case_event"
        )
        payload_snapshot = _extract_payload_snapshot(
            activity, dl=self.datalayer
        )
        return object_id, event_type, payload_snapshot

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        case_id = self._resolve_case_id()
        if not case_id:
            self.logger.error(
                f"{self.name}: no case_id available — cannot commit ledger"
                " entry"
            )
            return Status.FAILURE

        activity = self._resolve_activity()
        if activity is None:
            self.logger.warning(
                "%s: no activity on blackboard for case '%s' — skipping"
                " log entry",
                self.name,
                case_id,
            )
            return Status.FAILURE

        object_id, event_type, payload_snapshot = self._activity_metadata(
            activity, case_id
        )

        # Normalize context to case_id for activities that predate the case
        # (e.g., Offer(VulnerabilityReport) submitted before the case existed).
        if payload_snapshot and payload_snapshot.get("context") != case_id:
            payload_snapshot = dict(payload_snapshot)
            payload_snapshot["context"] = case_id

        # Record the portion of the assertion the receiver accepts, when a
        # preceding guard adjudicated it (RSH-05).
        if payload_snapshot:
            try:
                replacement = self._resolve_payload_object_override(
                    payload_snapshot
                )
            except VultronValidationError as exc:
                self.logger.error(
                    "%s: refusing ledger commit for case '%s':"
                    " override validation failed: %s",
                    self.name,
                    case_id,
                    exc,
                )
                return Status.FAILURE
            if replacement is not None:
                payload_snapshot = dict(payload_snapshot)
                payload_snapshot["object"] = replacement
                self.logger.info(
                    "%s: snapshotting the accepted portion of object '%s'"
                    " for case '%s' (RSH-05)",
                    self.name,
                    _snapshot_object_id(payload_snapshot),
                    case_id,
                )

        tree = create_commit_log_entry_tree(
            case_id=case_id,
            object_id=object_id,
            event_type=event_type,
            payload_snapshot=payload_snapshot,
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(
            tree=tree,
            actor_id=self.actor_id,
            sync_port=self._sync_port,
        )
        if result.status == Status.SUCCESS:
            self.logger.info(
                "%s: committed log entry '%s' for case '%s'",
                self.name,
                event_type,
                case_id,
            )
            return Status.SUCCESS
        self.logger.error(
            "%s: failed to commit log entry for case '%s': %s",
            self.name,
            case_id,
            result.feedback_message,
        )
        return Status.FAILURE


def create_guarded_commit_case_ledger_entry_tree(
    case_id: str | None = None,
) -> py_trees.composites.Selector:
    """Create a guarded commit subtree for canonical case-ledger entries.

    The commit runs only when the executing actor holds ``CVDRole.CASE_MANAGER``
    for the case; see :func:`create_case_manager_gated_tree` for the gate's
    failure-mode semantics.

    Called internally by :func:`create_receive_activity_tree`.  Direct callers
    in tree-factory modules are a CLP-10-006 ordering violation; use
    ``create_receive_activity_tree`` instead.
    """
    from vultron.core.behaviors.case.nodes.role_gates import (
        create_case_manager_gated_tree,
    )

    return create_case_manager_gated_tree(
        name="GuardedCommitCaseLedgerEntryBT",
        case_id=case_id,
        children=[CommitCaseLedgerEntryNode(case_id=case_id)],
    )


def create_receive_activity_tree(
    name: str,
    case_id: str | None,
    precondition_guards: list[py_trees.behaviour.Behaviour],
    effect_nodes: list[py_trees.behaviour.Behaviour],
) -> py_trees.composites.Sequence:
    """Compose a receive-side BT with CLP-10-006 ordering.

    Structurally enforces the correct receive-side ordering::

        [*precondition_guards] → GuardedCommit(receipt) → [*effect_nodes]

    Precondition guards are read-only checks that may return FAILURE to abort
    the tree before any state is written.  The guarded commit ledgers receipt
    of the triggering activity (which is on the blackboard before any node
    runs, placed there by ``BTBridge.execute_with_setup``).  Effect nodes
    perform state transitions, outbox enqueues, and participant mutations —
    all of which happen only after the receipt is recorded.

    When ``case_id`` is ``None`` the commit step is omitted entirely,
    preserving behaviour for trees that receive no explicit case context.

    Per ``specs/case-ledger-processing.yaml`` CLP-10-006.
    """
    children: list[py_trees.behaviour.Behaviour] = list(precondition_guards)
    if case_id is not None:
        children.append(
            create_guarded_commit_case_ledger_entry_tree(case_id=case_id)
        )
    else:
        logger.debug(
            "create_receive_activity_tree(%s): case_id is None"
            " — commit step omitted",
            name,
        )
    children.extend(effect_nodes)
    return py_trees.composites.Sequence(
        name=name,
        memory=False,
        children=children,
    )
