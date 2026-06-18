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

"""Domain representation of a vulnerability case."""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import Field, model_validator

from vultron.core.models.base import CoreObject
from vultron.core.models.case_ledger import compute_genesis_hash
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


class VulnerabilityCase(CoreObject):
    """Domain representation of a vulnerability case.

    Canonical core type for a ``VulnerabilityCase``.  ``type_`` is
    ``"VulnerabilityCase"`` so TinyDB stores this in the same table as
    wire-created cases and ``record_to_object`` can round-trip it via the
    wire vocabulary registry, and so this class auto-registers in
    :data:`CORE_VOCABULARY`.

    Cross-references to related objects are stored as ``str`` ID values,
    which are valid members of the corresponding wire-type union fields
    (e.g. ``VulnerabilityReportRef``, ``CaseParticipantRef``), ensuring
    DataLayer round-trip compatibility.

    When first created with an ``attributed_to`` actor and an empty
    ``case_statuses`` list, an initial :class:`CaseStatus` is appended
    automatically so that ``current_status`` never encounters an empty
    history list.

    Parent/child/sibling cross-references are stored as ID strings to
    avoid circular-reference issues during serialization.  See ADR-0017
    for the rationale.
    """

    type_: Literal["VulnerabilityCase"] = Field(
        default="VulnerabilityCase",
        validation_alias="type",
        serialization_alias="type",
    )
    case_participants: list[str | CaseParticipant] = Field(
        default_factory=list
    )
    actor_participant_index: dict[str, str] = Field(default_factory=dict)
    vulnerability_reports: list[str] = Field(default_factory=list)
    case_statuses: list[str | CaseStatus] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    active_embargo: str | None = None
    proposed_embargoes: list[str] = Field(default_factory=list)
    case_activity: list[str] = Field(default_factory=list)
    genesis_hash: str = Field(
        default="",
        description=(
            "Per-case genesis hash binding this ledger to its origin "
            "identity and timestamp (CLP-08-003)"
        ),
    )
    # ADR-0017: ID-only cross-refs to avoid graph-cycle issues
    parent_cases: list[str] = Field(default_factory=list)
    child_cases: list[str] = Field(default_factory=list)
    sibling_cases: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _compute_genesis_hash_if_missing(self) -> "VulnerabilityCase":
        """Compute ``genesis_hash`` at case creation when not explicitly set.

        Uses ``id_``, ``published``, and ``attributed_to`` (the CaseActor URI)
        as inputs to :func:`~vultron.core.models.case_ledger.compute_genesis_hash`.
        When ``attributed_to`` is present, ``genesis_hash`` MUST be non-empty
        after this validator runs — if the hash cannot be computed (e.g.,
        ``published`` is absent), a
        :exc:`~vultron.errors.VultronValidationError` is raised (fail-closed
        per CLP-08-003/CLP-08-004).  No-ops when ``genesis_hash`` is already
        set or when ``attributed_to`` is absent (genesis hash requires a
        CaseActor URI as input).

        Spec: CLP-08-002, CLP-08-003.
        """
        if not self.genesis_hash and self.attributed_to:
            self.genesis_hash = compute_genesis_hash(
                case_id=self.id_,
                created_at=self.published,
                case_actor_id=self.attributed_to,
            )
        if self.attributed_to and not self.genesis_hash:
            raise VultronValidationError(
                f"VulnerabilityCase '{self.id_}': genesis_hash could not "
                "be computed — 'published' timestamp is required "
                "(CLP-08-003)."
            )
        return self

    @model_validator(mode="after")
    def _init_case_statuses(self) -> "VulnerabilityCase":
        """Seed ``case_statuses`` with a default entry when empty."""
        if not self.case_statuses and self.attributed_to:
            self.case_statuses = [
                CaseStatus(
                    context=self.id_,
                    attributed_to=self.attributed_to,
                )
            ]
        return self

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    def add_report(self, report_id: str) -> None:
        """Append a vulnerability report ID to this case.

        Args:
            report_id: Full URI of the :class:`VulnerabilityReport` to add.
        """
        self.vulnerability_reports.append(report_id)

    def add_participant(self, participant: CaseParticipant) -> None:
        """Add a participant and update the actor→participant index.

        The participant's ``attributed_to`` actor URI is recorded in
        ``actor_participant_index`` so callers can quickly look up a
        participant by actor ID.

        Args:
            participant: A full :class:`CaseParticipant` object (full object
                required to update the index).
        """
        participant_id = participant.id_
        existing_ids = {
            p.id_ if isinstance(p, CaseParticipant) else str(p)
            for p in self.case_participants
        }
        if participant_id not in existing_ids:
            self.case_participants.append(participant_id)

        actor_ref = participant.attributed_to
        actor_id = (
            actor_ref
            if isinstance(actor_ref, str)
            else getattr(actor_ref, "id_", None)
        )
        if actor_id is None:
            return

        existing_mapping = self.actor_participant_index.get(actor_id)
        if existing_mapping is not None and existing_mapping != participant_id:
            raise VultronValidationError(
                "Participant-index divergence: "
                f"actor '{actor_id}' already mapped to '{existing_mapping}' "
                f"but add_participant received '{participant_id}'."
            )
        self.actor_participant_index[actor_id] = participant_id

    def remove_participant(self, participant_id: str) -> None:
        """Remove a participant and update the actor→participant index.

        Args:
            participant_id: Full URI of the :class:`CaseParticipant` to
                remove.
        """
        self.case_participants = [
            p
            for p in self.case_participants
            if (p.id_ if isinstance(p, CaseParticipant) else p)
            != participant_id
        ]
        actors_to_remove = [
            actor_id
            for actor_id, p_id in self.actor_participant_index.items()
            if p_id == participant_id
        ]
        for actor_id in actors_to_remove:
            del self.actor_participant_index[actor_id]

    def set_embargo(self, embargo: str | None) -> None:
        """Set the active embargo reference for this case.

        Args:
            embargo: Full URI of the active :class:`EmbargoEvent`, or
                ``None`` to clear.
        """
        self.active_embargo = embargo

    def record_activity(self, activity_id: str) -> None:
        """Append an activity ID to the case activity log.

        Idempotent — if *activity_id* is already recorded, the call is
        a no-op.

        Per AGENTS.md: store activity IDs as strings, not typed objects.

        Args:
            activity_id: Full URI of the activity to record.
        """
        if activity_id not in self.case_activity:
            self.case_activity.append(activity_id)

    @property
    def current_status(self) -> CaseStatus:
        """Return the most recent materialized :class:`CaseStatus`.

        Uses ``updated`` then ``published`` then ``id_`` as sort key to
        handle cases where timestamps may be equal or absent.

        Raises:
            ValueError: When no materialized :class:`CaseStatus` exists.
        """
        materialized = [
            s for s in self.case_statuses if isinstance(s, CaseStatus)
        ]
        if not materialized:
            raise ValueError(
                "VulnerabilityCase has no materialized CaseStatus"
            )
        return max(
            materialized,
            key=lambda cs: cs.updated or cs.published or cs.id_,
        )

    @property
    def case_status(self) -> CaseStatus:
        """Return the most recent :class:`CaseStatus` (alias for ``current_status``)."""
        return self.current_status


#: Backward-compatibility alias.  New code should import
#: :class:`VulnerabilityCase` directly.
VultronCase = VulnerabilityCase
