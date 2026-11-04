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

"""BTBridge setup: reconcile the store and ports, populate the blackboard.

Per specs/behavior-tree-integration.yaml:
- BT-05-002: Sets up py_trees context with DataLayer access
- BT-05-003: Populates blackboard with activity and actor state
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import py_trees

from vultron.core.behaviors.store_scope import port_for_store, store_for_actor
from vultron.core.ports.case_persistence import CasePersistence

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort


class _BridgeSetup:
    """Store and port reconciliation and blackboard setup for :class:`BTBridge`.

    A mixin of ``BTBridge`` only; the attributes below are set by
    ``BTBridge.__init__``.
    """

    datalayer: CasePersistence
    is_leader: Callable[[], bool]
    _is_leader_explicit: bool
    trigger_activity: "TriggerActivityPort | None"
    sync_port: "SyncActivityPort | None"
    wire_render_port: "WireRenderPort | None"
    logger: logging.Logger

    def _store_for_actor(self, actor_id: str) -> CasePersistence:
        """Return the store belonging to *actor_id* (ADR-0073, BT-05-005).

        BT-05-002 and BT-05-003 put ``datalayer`` and ``actor_id`` on the
        blackboard as two independent facts.  Under per-actor storage they are
        one fact: a store is always some actor's own, so the executing actor's
        identity *determines* which store the tree operates on.  Reconciling
        them here makes every write a node performs — ``outbox_append()`` above
        all — correct by construction, rather than correct only when the caller
        remembered to inject a matching DataLayer.

        It is load-bearing wherever a tree runs as a co-hosted actor other than
        the one whose store was injected — the demo-only ``sync-log-entry``
        trigger runs as the case's CASE_MANAGER from the requesting actor's
        route.  Without reconciliation the work lands in one store and is
        queued in the other's outbox, and the outbox entry names an activity
        its own store does not hold (PCR-08-007, CM-24-004).

        Scoping is skipped unless the DataLayer reports a concrete ``actor_id``
        that differs, which leaves test doubles and any non-actor-scoped
        implementation untouched.  That fall-through is BT-05-005's one
        recorded exception: a store that cannot name its own actor has nothing
        to reconcile against.

        The guard logic itself lives in
        :func:`~vultron.core.behaviors.store_scope.store_for_actor` so that this
        node, ``WritePendingReportCaseLinkNode`` and the demo seeding helpers
        cannot drift apart on what "that actor's store" means.

        ``require_same_authority`` is set, so an executing actor under an
        authority this node does not host is refused with
        :class:`~vultron.errors.VultronUnhostedActorError` rather than handed
        a store.  ``clone_for_actor`` would mint an empty local store under the
        foreign actor's name, and keeping the injected store instead would run
        the tree as one actor against another actor's data.  Neither is
        sanctioned: a container executes trees only as actors it hosts, and a
        participant reaches a CASE_MANAGER on another container by sending it
        its own activity, never by executing a tree in its name (BT-05-005,
        CM-24-010, CM-24-011, ADR-0109).  ``execute_with_setup`` classifies
        the raise as an internal error, so a trigger that tries answers 500,
        not 422.

        Reconciling the store is necessary but not sufficient — see
        :meth:`_ports_for_store` for the other half.
        """
        return store_for_actor(
            self.datalayer, actor_id, require_same_authority=True
        )

    def _ports_for_store(
        self, store: CasePersistence
    ) -> tuple[
        "TriggerActivityPort | None",
        "SyncActivityPort | None",
        "WireRenderPort | None",
    ]:
        """Return this bridge's driven ports, rebound to *store* (DL-07-009).

        ``_store_for_actor`` reconciles the store the *nodes* write through.  The
        driven adapters on the blackboard hold a second, independent reference to
        a DataLayer — the one they were constructed with — and that reference is
        what persists an outbound activity.  Leaving it alone splits a single
        emit across two stores: ``TriggerActivityAdapter.invite_actor_to_case``
        creates the ``Invite`` in the *requesting* actor's store while
        ``EmitInviteActorToCaseNode`` appends its id to the *executing* actor's
        outbox.  Nothing raises; the outbox handler simply reports the activity
        "not found in DataLayer for actor …", skips delivery, and the invitee is
        never told it was invited (ISSUE-2548).

        No trigger runs a delegated emit any more (CM-24-010, ADR-0109): the
        invite and the ownership-transfer offer both send the requester's own
        activity to the CASE_MANAGER.  The reconciliation stays for any tree
        that runs as a co-hosted actor other than the injected store's own.

        A port this bridge was not given is *inherited* from the blackboard
        rather than left alone, because the blackboard is process-global
        (``Blackboard.storage``) and the nested-bridge pattern relies on that:
        an emit node builds its ledger-commit tree with
        ``BTBridge(datalayer=...)`` and no ports, so whatever the last execution
        wrote is what the commit tree's ``LedgerFanoutNode`` picks up.  Within
        one request that inheritance is intended — the ports belong to the
        execution in progress.  Across requests it is a store leak: a node
        hosting several actors runs actor A's trigger, then actor B's, and B's
        ``Announce(CaseLedgerEntry)`` is persisted through A's adapter into A's
        store (ADR-0073, CM-01-001).  Rebinding on the way through makes the
        inheritance safe by construction instead of safe by luck, so the port a
        nested tree reads always writes the store that tree runs in.

        Ports that do not opt in are returned unchanged; see
        :func:`~vultron.core.behaviors.store_scope.port_for_store`.
        """
        return (
            port_for_store(
                self.trigger_activity
                or self._inherited_port("trigger_activity_factory"),
                store,
            ),
            port_for_store(
                self.sync_port or self._inherited_port("sync_port"), store
            ),
            port_for_store(
                self.wire_render_port
                or self._inherited_port("wire_render_port"),
                store,
            ),
        )

    @staticmethod
    def _inherited_port(key: str) -> Any:
        """Return the port currently on the blackboard under *key*, or ``None``.

        Read straight out of ``Blackboard.storage`` rather than through a
        ``Client``: registering READ access for a key that may never have been
        written raises, and "no port has been set yet" is the ordinary case for
        the first execution in a process.
        """
        return py_trees.blackboard.Blackboard.storage.get(f"/{key}")

    def setup_tree(
        self,
        tree: py_trees.behaviour.Behaviour,
        actor_id: str,
        activity: Any = None,
        **context_data: Any,
    ) -> py_trees.trees.BehaviourTree:
        """
        Set up behavior tree with blackboard and execution context.

        Args:
            tree: Root behavior node to execute
            actor_id: ID of actor executing this tree (for state isolation)
            activity: Optional ActivityStreams activity being processed
            **context_data: Additional context to populate in blackboard

        Returns:
            Configured BehaviourTree ready for execution

        Implements:
            - BT-05-002: Sets up py_trees context with DataLayer access
            - BT-05-003: Populates blackboard with activity and actor state
        """
        self.logger.debug("Setting up BT for actor %s", actor_id)

        # Create py_trees BehaviourTree wrapper
        bt = py_trees.trees.BehaviourTree(root=tree)

        # Populate blackboard with execution context
        blackboard = py_trees.blackboard.Client(name=f"BTBridge-{actor_id}")
        blackboard.register_key(
            key="datalayer", access=py_trees.common.Access.WRITE
        )
        blackboard.register_key(
            key="actor_id", access=py_trees.common.Access.WRITE
        )

        store = self._store_for_actor(actor_id)
        trigger_activity, sync_port, wire_render_port = self._ports_for_store(
            store
        )

        blackboard.datalayer = store
        blackboard.actor_id = actor_id

        if trigger_activity is not None:
            blackboard.register_key(
                key="trigger_activity_factory",
                access=py_trees.common.Access.WRITE,
            )
            blackboard.trigger_activity_factory = trigger_activity

        if sync_port is not None:
            blackboard.register_key(
                key="sync_port",
                access=py_trees.common.Access.WRITE,
            )
            blackboard.sync_port = sync_port

        if wire_render_port is not None:
            blackboard.register_key(
                key="wire_render_port",
                access=py_trees.common.Access.WRITE,
            )
            blackboard.wire_render_port = wire_render_port

        # Write is_leader to the blackboard only when this bridge carries an
        # explicit (non-default) guard.  Default bridges do NOT overwrite the
        # key so that an outer explicit value is visible to grandchild bridges
        # (prevents a 3-level-deep inner bridge from reading _default_is_leader
        # instead of the outermost raft_fn — CLP-08-005, SYNC-09-003).
        if self._is_leader_explicit:
            blackboard.register_key(
                key="is_leader", access=py_trees.common.Access.WRITE
            )
            blackboard.is_leader = self.is_leader

        if activity is not None:
            blackboard.register_key(
                key="activity", access=py_trees.common.Access.WRITE
            )
            blackboard.activity = activity

        # Register any additional context data
        for key, value in context_data.items():
            blackboard.register_key(
                key=key, access=py_trees.common.Access.WRITE
            )
            setattr(blackboard, key, value)

        self.logger.info("BT setup complete for actor %s", actor_id)

        # No tree dump here: before the first tick every node is unrun, so it
        # would restate the tree's shape, which "Final BT state" (logged after
        # execution) repeats with each node's result (#4600).
        return bt
