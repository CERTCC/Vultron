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
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, Literal

from pydantic import Field, ValidationInfo, computed_field, model_validator

from vultron.core.models._helpers import (
    INBOUND_CONTEXT_KEY,
    _as_id,
    _new_urn,
    most_recent_status,
    now_utc,
)
from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.case_ledger import compute_genesis_hash
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register import (
    EmbargoRegisterEntry,
    RegisterChange,
    apply_register_step,
    repeated_ids,
    replaces_violations,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.wire_keys import wire_key
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    derive_em,
    register_invariant_violations,
)
from vultron.errors import VultronNotFoundError, VultronValidationError

logger = logging.getLogger(__name__)


def _present_key(data: dict[str, Any], field_name: str) -> str:
    """Return the spelling of *field_name* that *data* carries.

    The AS2 spelling when present (an inbound case, ADR-0099 detail 2), else
    the field name, so a validator writes back under the key it read.
    """
    as2 = wire_key(field_name)
    return as2 if as2 in data else field_name


def _genesis_published(data: dict[str, Any], inbound: bool) -> datetime | None:
    """Return the ``published`` time a genesis hash is computed from.

    Only an *omitted* ``published`` outside the inbound path is this process
    authoring the case, so only then is one minted (and written into *data*).
    An explicit ``None`` or blank, or any omission on inbound, is a received
    case that claimed no time; minting one would give each receiver its own
    genesis for the same case (ISSUE-3257, ADR-0103).
    """
    if "published" not in data and not inbound:
        minted = now_utc()
        data["published"] = minted
        return minted
    published_val = data.get("published")
    if published_val is None or published_val == "":
        return None
    if isinstance(published_val, datetime):
        return published_val
    try:
        parsed = datetime.fromisoformat(str(published_val))
    except (ValueError, TypeError):
        return None
    data["published"] = parsed
    return parsed


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
    # DL-08-001: the register's entries carry the embargo object when a sender
    # carried it, so recipients can read the terms back without a dereference
    # mechanism (AKM-03-001).
    inline_required_refs: ClassVar[frozenset[str]] = frozenset(
        {"embargo_register"}
    )
    # Every reference slot below carries ``NonEmptyString`` for its IRI form:
    # a blank reference names nothing, so it is refused at construction rather
    # than stored and dereferenced later (CS-08-001, ARCH-10-001).
    case_participants: list[NonEmptyString | CaseParticipant] = Field(
        default_factory=list
    )
    actor_participant_index: dict[NonEmptyString, NonEmptyString] = Field(
        default_factory=dict
    )
    vulnerability_reports: list[NonEmptyString | VulnerabilityReport] = Field(
        default_factory=list
    )
    case_statuses: list[NonEmptyString | CaseStatus] = Field(
        default_factory=list
    )
    notes: list[NonEmptyString] = Field(default_factory=list)
    # Owner-chosen summary for use in the case stub (CM-17-010, MV-10-001).
    # The case owner sets this before emitting a stub Invite; the factory
    # refuses to build a stub if this field is absent (AC-2 of #4165).
    # ``NonEmptyString | None`` follows the "if present, then non-empty" rule
    # (CS-08-002): None means "not yet set"; an empty or blank string is
    # refused at construction time.
    stub_summary: NonEmptyString | None = None
    # One entry for every embargo ever proposed on the case, appended and never
    # removed (ADR-0122).  EM, the active embargo and the open proposals are
    # all read from it; it changes only through
    # :meth:`apply_embargo_register_step`.
    embargo_register: list[EmbargoRegisterEntry] = Field(default_factory=list)
    # The proposal Invite that relayed each *open* proposal (EP-09); an entry
    # leaves with its proposal (EP-08-003).
    pending_embargo_proposal_index: dict[NonEmptyString, NonEmptyString] = (
        Field(default_factory=dict)
    )
    recommendation_recommender_index: dict[NonEmptyString, NonEmptyString] = (
        Field(default_factory=dict)
    )
    case_activity: list[NonEmptyString] = Field(default_factory=list)
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
    parent_cases: list[NonEmptyString] = Field(default_factory=list)
    child_cases: list[NonEmptyString] = Field(default_factory=list)
    sibling_cases: list[NonEmptyString] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _compute_genesis_hash_if_missing(
        cls, data: Any, info: ValidationInfo
    ) -> Any:
        """Compute ``genesis_hash`` at case creation when not explicitly set.

        Uses ``id_``, ``published``, and ``attributed_to`` (the case owner's
        actor id, CP-09-001, CM-02-008) as inputs to
        :func:`~vultron.core.models.case_ledger.compute_genesis_hash`.  This is
        the single definition of a case's genesis hash (CLP-08-002): the owner
        is the anchor on every creation path, including a case a CaseActor
        creates from the owner's ``CaseProposal``, because the CaseActor acts
        as the owner's delegated proxy.  A creator therefore sets
        ``attributed_to`` and lets this validator compute the hash; it does
        not pass a hash of its own.

        When ``attributed_to`` is present, ``genesis_hash`` MUST be non-empty
        after this validator runs — if the hash cannot be computed (e.g.,
        ``published`` is absent), a
        :exc:`~vultron.errors.VultronValidationError` is raised (fail-closed
        per CLP-08-003/CLP-08-004).  No-ops when ``genesis_hash`` is already
        set — a received case keeps its sender's hash; one that carries none
        derives it here from its carried inputs (ADR-0103) — or when
        ``attributed_to`` is absent (genesis hash requires an owner as
        input).

        Both spellings of each input are read: the class is its own wire class
        (ADR-0099 detail 3), so an inbound case arrives as ``attributedTo`` and
        ``genesisHash``.  On the inbound path (ADR-0103) an omitted or blank
        ``published`` is the sender claiming no time, never a cue to mint one.

        Spec: CLP-08-002, CLP-08-003.
        """
        if not isinstance(data, dict):
            return data
        inbound = (
            isinstance(info.context, dict)
            and INBOUND_CONTEXT_KEY in info.context
        )
        attributed_to = data.get("attributed_to") or data.get(
            wire_key("attributed_to")
        )
        hash_key = _present_key(data, "genesis_hash")
        genesis_hash = data.get(hash_key, "")
        if not genesis_hash and attributed_to:
            data = dict(data)
            if not data.get("id") and not data.get("id_"):
                data["id"] = _new_urn()
            case_id = data.get("id") or data.get("id_")
            published_val = _genesis_published(data, inbound)
            if published_val is not None:
                data[hash_key] = compute_genesis_hash(
                    case_id=case_id,
                    created_at=published_val,
                    owner_actor_id=attributed_to,
                )
        if attributed_to and not data.get(hash_key):
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
        """Seed ``case_statuses`` with a default entry when empty.

        Reads both spellings (ADR-0099 detail 2), and writes the seed under the
        one already present so it is not shadowed by an empty camelCase list.
        """
        if not isinstance(data, dict):
            return data
        statuses_key = _present_key(data, "case_statuses")
        attributed_to = data.get("attributed_to") or data.get(
            wire_key("attributed_to")
        )
        if not data.get(statuses_key) and attributed_to:
            data = dict(data)
            if not data.get("id") and not data.get("id_"):
                data["id"] = _new_urn()
            case_id = data.get("id") or data.get("id_")
            data[statuses_key] = [
                CaseStatus(
                    context=case_id,
                    attributed_to=attributed_to,
                )
            ]
        return data

    @model_validator(mode="after")
    def _set_cs_context(self) -> VulnerabilityCase:
        """Point every inline :class:`CaseStatus` at this case.

        A case status belongs to the case that holds it, so a carried
        ``context`` that names another case (or none) is rewritten to this
        case's id.  This is the invariant the deleted
        ``as_VulnerabilityCase.set_cs_context`` held on the wire class; it moved
        here with the collapse (ADR-0099 detail 3).
        """
        if not any(
            isinstance(cs, CaseStatus) and cs.context != self.id_
            for cs in self.case_statuses
        ):
            return self
        statuses: list[str | CaseStatus] = [
            (
                cs.model_copy(update={"context": self.id_})
                if isinstance(cs, CaseStatus) and cs.context != self.id_
                else cs
            )
            for cs in self.case_statuses
        ]
        object.__setattr__(self, "case_statuses", statuses)
        return self

    @model_validator(mode="after")
    def _register_keeps_invariants(self) -> VulnerabilityCase:
        """Refuse a register that breaks ADR-0122's invariants, repeats an id or has a bad ``replaces``.

        Fail-fast at construction (ARCH-10-001): a received or stored case
        whose register no step could have produced is refused, rather than
        derived into an EM state the table does not define.
        """
        ids = self.register_embargo_ids
        problems = register_invariant_violations(
            entry.status for entry in self.embargo_register
        )
        repeated = repeated_ids(ids)
        if repeated:
            problems.append(f"embargoes {repeated} have more than one entry")
        problems.extend(replaces_violations(self.embargo_register))
        if problems:
            raise ValueError(
                f"VulnerabilityCase '{self.id_}' embargo register: "
                + "; ".join(problems)
            )
        return self

    @model_validator(mode="after")
    def _inline_participants_hold_every_row(self) -> VulnerabilityCase:
        """Refuse an inline participant missing a row for a register entry.

        Every participant holds one consent row per register entry (ADR-0122),
        and the content gate reads them; a received case that breaks this is
        refused here, at the edge, rather than faulting later when
        ``active_participants`` reads a row that is not there.  A bare
        participant reference carries no rows to check.
        """
        embargo_ids = self.register_embargo_ids
        problems: list[str] = []
        for participant in self.case_participants:
            if not isinstance(participant, CaseParticipant):
                continue
            missing = participant.missing_rows(embargo_ids)
            if missing:
                problems.append(
                    f"participant '{participant.id_}' has no consent row for"
                    f" {missing}"
                )
        if problems:
            raise ValueError(
                f"VulnerabilityCase '{self.id_}': " + "; ".join(problems)
            )
        return self

    @model_validator(mode="after")
    def _stamp_em_at_construction(self) -> VulnerabilityCase:
        """Stamp the register's EM onto the current status a case arrives with.

        A stored or received case's status carries an EM copy that may
        predate, or disagree with, its register; the register wins
        (ADR-0122).  Like :meth:`_set_cs_context`, this replaces the status
        with a copy rather than assigning through the model (ARCH-21-004).
        """
        self._stamp_em()
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

    def add_participant(self, participant: CaseParticipant) -> bool:
        """Add a participant and update the actor→participant index.

        The participant's ``attributed_to`` actor URI is recorded in
        ``actor_participant_index`` so callers can quickly look up a
        participant by actor ID.  The participant also gets an
        ``UNINVITED`` consent row for every entry already in the embargo
        register (ADR-0122), so it holds a row for each embargo the case has
        ever had; rows it already holds are kept.  This writes to
        *participant* too, so the caller persists both records — the
        participant after this call.

        Args:
            participant: A full :class:`CaseParticipant` object (full object
                required to update the index).

        Returns:
            ``True`` when *participant* gained a consent row, so the caller
            knows the record needs saving.
        """
        wrote_rows = participant.write_uninvited_rows(
            self.register_embargo_ids
        )
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
            return wrote_rows

        existing_mapping = self.actor_participant_index.get(actor_id)
        if existing_mapping is not None and existing_mapping != participant_id:
            raise VultronValidationError(
                "Participant-index divergence: "
                f"actor '{actor_id}' already mapped to '{existing_mapping}' "
                f"but add_participant received '{participant_id}'."
            )
        self.actor_participant_index[actor_id] = participant_id
        return wrote_rows

    def add_case_status(self, status: CaseStatus) -> None:
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
        # EM is the register's, never the appended status's (ADR-0122).
        self._stamp_em()

    def append_case_status(self, **kwargs: Any) -> None:
        """Append a new CaseStatus derived from the current one with fields overridden.

        Inherits all fields from ``current_status`` then applies ``kwargs``,
        so passing ``pxa_state=CS_pxa.Pxa`` keeps every other dimension.
        Timestamps are bumped to ensure the new entry sorts as
        ``current_status``.  EM is not a status field to set: it is derived
        from the embargo register (ADR-0122), so ``em_state`` is refused.

        Raises:
            VultronValidationError: when ``em_state`` is passed.
        """
        if "em_state" in kwargs:
            raise VultronValidationError(
                "append_case_status: EM is derived from the embargo register"
                " (ADR-0122); change the register instead of the status."
            )
        current = self.current_status
        latest = current.updated or current.published
        now = datetime.now(UTC)
        if latest is not None and latest >= now:
            now = latest + timedelta(microseconds=1)

        # Map the flat pxa kwarg to its nested dimension so that model_copy
        # (which does not re-run validators) applies it correctly.
        pxa_update: dict = {}
        passthrough: dict = {}
        for k, v in kwargs.items():
            if k == "pxa_state":
                pxa_update["state"] = v
            else:
                passthrough[k] = v

        pxa = (
            current.pxa.model_copy(update=pxa_update)
            if pxa_update
            else current.pxa
        )

        self.add_case_status(
            current.model_copy(
                update={
                    **passthrough,
                    "pxa": pxa,
                    "context": self.id_,
                    "published": now,
                    "updated": now,
                }
            )
        )

    # ------------------------------------------------------------------
    # Embargo register (ADR-0122)
    # ------------------------------------------------------------------

    def apply_embargo_register_step(
        self,
        changes: list[RegisterChange],
        *,
        threat_signal: bool = False,
    ) -> None:
        """Apply one register step, the only writer of the case's embargoes.

        The step is checked whole by
        :func:`~vultron.core.models.embargo_register.apply_register_step`
        and refused, leaving the case untouched, when any rule breaks.  An
        entry that has left ``PROPOSED`` takes its relay record out of
        ``pending_embargo_proposal_index`` with it (EP-08-003); a record for
        an embargo the register has not recorded yet stays (EP-09-007).  The
        current :class:`CaseStatus` is stamped with the derived EM, so the
        copy it carries on the wire never disagrees with the register.

        Raises:
            VultronInvalidStateTransitionError: the step breaks a register
                rule or invariant.
        """
        register = apply_register_step(
            self.embargo_register, changes, threat_signal=threat_signal
        )
        # A participant held inline must already hold the new entries' rows
        # when the register is assigned, or the row check refuses the
        # assignment (validate_assignment).  Stored participants get theirs
        # from the lifecycle service, which persists them (ADR-0122).
        embargo_ids = [entry.embargo_id for entry in register]
        for participant in self.case_participants:
            if isinstance(participant, CaseParticipant):
                participant.write_uninvited_rows(embargo_ids)
        self.embargo_register = register
        if not all(
            self.proposal_is_undecided(i)
            for i in self.pending_embargo_proposal_index
        ):
            self.pending_embargo_proposal_index = {
                embargo_id: invite_id
                for embargo_id, invite_id in (
                    self.pending_embargo_proposal_index.items()
                )
                if self.proposal_is_undecided(embargo_id)
            }
        self._stamp_em()

    def proposal_is_undecided(self, embargo_id: str) -> bool:
        """Whether *embargo_id* may still be answered as a proposal.

        True for a ``PROPOSED`` entry, and for an embargo the register has
        not recorded yet: a replica indexes a relayed Invite when it arrives,
        which can be before ledger replay records the proposal (EP-09-007).
        False once the entry has left ``PROPOSED`` (EP-08-003), and for every
        embargo once one has terminated: nothing is proposed after that
        (EP-08-004, register invariant 4).
        """
        entry = self.embargo_register_entry(embargo_id)
        if entry is None:
            return not any(
                e.status == EmbargoRegisterStatus.TERMINATED
                for e in self.embargo_register
            )
        return entry.status == EmbargoRegisterStatus.PROPOSED

    def _em_stamped_statuses(self) -> list[str | CaseStatus] | None:
        """``case_statuses`` with the current status's EM copy set from the register.

        ``None`` when there is no materialized status or its copy already
        agrees.  The status is replaced by a copy, never mutated, so a status
        object a caller handed in is left as it was.
        """
        materialized = [
            s for s in self.case_statuses if isinstance(s, CaseStatus)
        ]
        if not materialized:
            return None
        current = most_recent_status(materialized)
        em = self.em_state
        if current.em.state == em:
            return None
        stamped = current.model_copy(update={"em": EmDimension(state=em)})
        return [stamped if s is current else s for s in self.case_statuses]

    def _stamp_em(self) -> None:
        """Write the derived EM onto the current status's copy (ADR-0122).

        Bypasses assignment validation like :meth:`_set_cs_context`: the copy
        differs only by a freshly validated ``EmDimension`` (ARCH-21-004).
        """
        statuses = self._em_stamped_statuses()
        if statuses is not None:
            object.__setattr__(self, "case_statuses", statuses)

    @property
    def register_embargo_ids(self) -> list[str]:
        """The embargo id of every register entry, in register order."""
        return [entry.embargo_id for entry in self.embargo_register]

    def embargo_register_entry(
        self, embargo_id: str
    ) -> EmbargoRegisterEntry | None:
        """The register entry for *embargo_id*, or ``None`` when it has none."""
        return next(
            (e for e in self.embargo_register if e.embargo_id == embargo_id),
            None,
        )

    def embargo_register_status(
        self, embargo_id: str
    ) -> EmbargoRegisterStatus:
        """The register status of *embargo_id*, the input every consent write needs.

        Raises:
            VultronNotFoundError: the register has no entry for *embargo_id*;
                a consent row exists only for a register entry (ADR-0122).
        """
        entry = self.embargo_register_entry(embargo_id)
        if entry is None:
            raise VultronNotFoundError(
                "EmbargoRegisterEntry", f"{embargo_id} on case {self.id_}"
            )
        return entry.status

    @property
    def em_state(self) -> EM:
        """The case's EM state, derived from its embargo register (ADR-0122)."""
        return derive_em(entry.status for entry in self.embargo_register)

    @property
    def active_embargo(self) -> str | EmbargoEvent | None:
        """The embargo in force — the object when one was carried, else its id.

        A view of the register's ``ACTIVE`` entry.  Most callers want the id
        and should use :attr:`active_embargo_id`.
        """
        return next(
            (
                entry.embargo
                for entry in self.embargo_register
                if entry.status == EmbargoRegisterStatus.ACTIVE
            ),
            None,
        )

    @property
    def active_embargo_id(self) -> str | None:
        """The id of the register's ``ACTIVE`` entry, or ``None``."""
        return _as_id(self.active_embargo)

    @property
    def proposed_embargo_ids(self) -> list[str]:
        """The ids of the open proposals: the register's ``PROPOSED`` entries."""
        return [
            entry.embargo_id
            for entry in self.embargo_register
            if entry.status == EmbargoRegisterStatus.PROPOSED
        ]

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

        Recency is resolved by ``updated`` then ``published`` via
        :func:`most_recent_status`. When both are absent the status sorts to
        the bottom (``datetime.min``); among equals the last appended wins.
        ``id_`` MUST NOT be used as a tiebreaker because its scheme is an
        implementation artefact, not a time proxy (CM-29-001).

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
        return most_recent_status(materialized)

    @property
    def case_status(self) -> CaseStatus:
        """Return the most recent :class:`CaseStatus` (alias for ``current_status``)."""
        return self.current_status

    # ------------------------------------------------------------------
    # Entitlement to case content (CM-10-004, ADR-0114)
    # ------------------------------------------------------------------

    def is_active_participant(self, participant: CaseParticipant) -> bool:
        """True when *participant* is entitled to this case's content.

        The one active-participant check (CM-10-004, ADR-0114 § "Inert and
        active").  A participant is **active** when all hold:

        1. it has joined the case — seated by the case initialization
           sequence or accepted its stub Invite (``participant.joined``);
        2. it has not been removed (``participant.removed``, CM-31-001);
        3. when this case has an active embargo (:attr:`embargo_in_force`),
           its consent row for the active embargo is ``AGREED``
           (:meth:`CaseParticipant.is_signatory`, CM-18-001).

        Every other participant is **inert**.  A removed participant is inert
        whatever its embargo consent: a removed signatory stays bound but
        receives no content (CM-31-008, ADR-0116).  RM ``CLOSED`` is deliberately
        not part of this check: a closed participant still receives the
        ledger entries that let its replica learn how the case ended (the
        ``case_fully_closed`` signal, CM-23-002), and only the sends that
        name CM-23-004 or ask for consent leave it out
        (:mod:`vultron.core.participants.recipients`).  The answer is computed from the
        replicated participant record and this case's own status, never
        stored, so every replica derives the same answer.  Recipients are
        selected through :mod:`vultron.core.participants.recipients`, which
        resolves each roster entry to its record and asks this method.
        """
        if not participant.joined or participant.removed:
            return False
        if not self.embargo_in_force:
            return True
        return participant.is_signatory(self.active_embargo_id)

    @property
    def embargo_in_force(self) -> bool:
        """True when this case's register has an ``ACTIVE`` entry.

        Read from :attr:`active_embargo_id`, the same fact the consent
        bookkeeping keys on (``embargo_lifecycle.pec``): an entry is
        ``ACTIVE`` from its activation until a revision supersedes it or the
        embargo is terminated, so it holds through a revision (EM
        ``REVISE``).  A proposal alone does not make one.
        """
        return self.active_embargo_id is not None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def active_participants(self) -> list[str]:
        """The ids of the participants this case finds active (CM-31-003).

        Published as ``activeParticipants`` and never stored as a field: it
        is :meth:`is_active_participant` applied to every participant record
        the case carries inline, in roster order (ADR-0116).  A case put on
        the wire carries its participant records inline
        (``_case_for_wire``), so the published view is complete there.  A
        bare participant reference is not provably active and is left out
        of this list; while any roster entry is a bare reference the AS2
        dump leaves ``activeParticipants`` out altogether
        (:meth:`_as2_unpublished_fields`), so the case never publishes a
        partial view as if it were exact.  A case read from the store holds
        references only, so in-process callers select recipients through
        :mod:`vultron.core.participants.recipients`, which resolves each
        reference to its record, not through this view.

        Reading a dump back in strips a value that matches the derived one
        and refuses one that contradicts it (``CoreObject``'s computed-field
        check, ARCH-23-005), so a case's own dump round-trips despite
        ``extra="forbid"``.
        """
        return [
            entry.id_
            for entry in self.case_participants
            if isinstance(entry, CaseParticipant)
            and self.is_active_participant(entry)
        ]

    def _as2_unpublished_fields(self) -> frozenset[str]:
        """Leave ``activeParticipants`` out while a roster entry is a reference.

        The check needs each participant's record; a bare reference cannot be
        evaluated, so the view would be partial.  CM-31-003 publishes exactly
        the active participants, so a partial view is not published at all.
        """
        if all(
            isinstance(entry, CaseParticipant)
            for entry in self.case_participants
        ):
            return frozenset()
        return frozenset({"active_participants"})


def has_case_statuses(case: VulnerabilityCase) -> bool:
    """Return True when *case* has at least one CaseStatus entry.

    Use this as the single shared predicate wherever code must distinguish
    "no status history yet" from "at least one status recorded" — in both
    BT condition nodes and plain use-case guards (LST-05 / AC-5).
    """
    return bool(case.case_statuses)
