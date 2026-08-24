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
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from vultron.core.models._helpers import _new_urn, _now_utc
from vultron.core.models.base import CoreObject
from vultron.core.models.case_ledger import compute_genesis_hash
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_event import EmbargoEvent
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
    # Admits the object, not only a reference, for the same reason
    # `case_participants` does: a recipient cannot dereference a URI it does not
    # hold, and no dereferencing mechanism is specified (AKM-03-001). While this
    # was `str | None` the object could not survive `_normalize_to_core`, so
    # every store round-trip — including the one `outbox_delivery` performs when
    # it re-serialises a queued activity — reduced a carried embargo back to a
    # bare id and the recipient was handed a reference it could never resolve.
    # Readers wanting the id should use `_as_id`/`active_embargo_id`.
    active_embargo: str | EmbargoEvent | None = None
    proposed_embargoes: list[str] = Field(default_factory=list)
    pending_embargo_proposal_index: dict[str, str] = Field(
        default_factory=dict
    )
    recommendation_recommender_index: dict[str, str] = Field(
        default_factory=dict
    )
    case_activity: list[str] = Field(default_factory=list)
    genesis_hash: str = Field(
        default="",
        description=(
            "Per-case genesis hash binding this ledger to its origin "
            "identity and timestamp (CLP-08-003). "
            "The empty-string default is intentional: rehydration paths "
            "may deserialise objects that were stored before genesis hashes "
            "were introduced. The model_validator enforces non-empty when "
            "attributed_to is present at construction time."
        ),
    )
    # ADR-0017: ID-only cross-refs to avoid graph-cycle issues
    parent_cases: list[str] = Field(default_factory=list)
    child_cases: list[str] = Field(default_factory=list)
    sibling_cases: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _compute_genesis_hash_if_missing(cls, data: Any) -> Any:
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
        if not isinstance(data, dict):
            return data
        attributed_to = data.get("attributed_to")
        genesis_hash = data.get("genesis_hash", "")
        if not genesis_hash and attributed_to:
            data = dict(data)
            if not data.get("id") and not data.get("id_"):
                data["id"] = _new_urn()
            case_id = data.get("id") or data.get("id_")
            published_val = data.get("published")
            if published_val is None:
                published_val = _now_utc()
                data["published"] = published_val
            elif not isinstance(published_val, datetime):
                try:
                    published_val = datetime.fromisoformat(str(published_val))
                    data["published"] = published_val
                except (ValueError, TypeError):
                    published_val = None
            if published_val is not None:
                data["genesis_hash"] = compute_genesis_hash(
                    case_id=case_id,
                    created_at=published_val,
                    case_actor_id=attributed_to,
                )
        if attributed_to and not data.get("genesis_hash"):
            case_id = data.get("id") or data.get("id_") or "<unknown>"
            raise VultronValidationError(
                f"VulnerabilityCase '{case_id}': genesis_hash could not "
                "be computed — 'published' timestamp is required "
                "(CLP-08-003)."
            )
        return data

    @model_validator(mode="before")
    @classmethod
    def _init_case_statuses(cls, data: Any) -> Any:
        """Seed ``case_statuses`` with a default entry when empty."""
        if not isinstance(data, dict):
            return data
        if not data.get("case_statuses") and data.get("attributed_to"):
            data = dict(data)
            if not data.get("id") and not data.get("id_"):
                data["id"] = _new_urn()
            case_id = data.get("id") or data.get("id_")
            data["case_statuses"] = [
                CaseStatus(
                    context=case_id,
                    attributed_to=data["attributed_to"],
                )
            ]
        return data

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

    def add_case_status(self, status: "CaseStatus") -> None:
        """Append a CaseStatus to this case's history.

        Validates the appended item's shape and raises
        :exc:`~vultron.errors.VultronValidationError` when a non-core
        (wire-shaped) input is passed, closing the ``append`` door for
        ``case_statuses`` (CM-27-003, ADR-0064).

        Args:
            status: A core :class:`CaseStatus` object.

        Raises:
            VultronValidationError: when *status* is not a
                :class:`CaseStatus` instance.
        """
        if not isinstance(status, CaseStatus):
            raise VultronValidationError(
                f"add_case_status expects a CaseStatus; "
                f"got {type(status).__name__}"
            )
        self.case_statuses.append(status)

    def set_embargo(self, embargo: "str | EmbargoEvent | None") -> None:
        """Set the active embargo for this case.

        Args:
            embargo: The active :class:`EmbargoEvent`, its full URI, or ``None``
                to clear. The object form is accepted so a received case can keep
                what the sender carried (AKM-03-001); see
                :attr:`active_embargo`.
        """
        self.active_embargo = embargo

    @property
    def active_embargo_id(self) -> str | None:
        """The active embargo's id, whichever shape the field holds.

        Most callers want the id and should use this rather than assuming
        ``active_embargo`` is a string — it may be the whole object when a
        received case carried one.
        """
        if self.active_embargo is None:
            return None
        if isinstance(self.active_embargo, str):
            return self.active_embargo or None
        return getattr(self.active_embargo, "id_", None)

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


def has_case_statuses(case: VulnerabilityCase) -> bool:
    """Return True when *case* has at least one CaseStatus entry.

    Use this as the single shared predicate wherever code must distinguish
    "no status history yet" from "at least one status recorded" — in both
    BT condition nodes and plain use-case guards (LST-05 / AC-5).
    """
    return bool(case.case_statuses)
