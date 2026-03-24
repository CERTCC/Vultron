"""Reusable property mixins for per-semantic event subclasses.

Each mixin exposes domain-specific property names for generic base-class
fields, making use-case code self-documenting without duplicating the mapping
across multiple event classes.

Each ``_ObjectIs*Mixin`` provides:
  - ``foo_id`` — the ID string of ``self.object_``
  - ``foo``    — the rich domain object (``self.object_``), typed as a hint

The same pattern applies to ``_TargetIs*``, ``_ContextIs*``, etc.
All properties use ``type: ignore`` because the mixin does not know the
concrete ``VultronEvent`` base that carries the actual field.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vultron.core.models.activity import VultronActivity
    from vultron.core.models.base import VultronObject
    from vultron.core.models.case import VultronCase
    from vultron.core.models.case_status import VultronCaseStatus
    from vultron.core.models.embargo_event import VultronEmbargoEvent
    from vultron.core.models.note import VultronNote
    from vultron.core.models.participant import VultronParticipant
    from vultron.core.models.participant_status import VultronParticipantStatus
    from vultron.core.models.report import VultronReport


class _ObjectIsReportMixin:
    @property
    def report_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]

    @property
    def report(self) -> VultronReport | None:
        return self.object_  # type: ignore[attr-defined,return-value]


class _ObjectIsOfferMixin:
    @property
    def offer_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]

    @property
    def offer(self) -> VultronActivity | None:
        return self.object_  # type: ignore[attr-defined,return-value]


class _ObjectIsEmbargoMixin:
    @property
    def embargo_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]

    @property
    def embargo(self) -> VultronEmbargoEvent | None:
        return self.object_  # type: ignore[attr-defined,return-value]


class _ObjectIsParticipantMixin:
    @property
    def participant_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]

    @property
    def participant(self) -> VultronParticipant | None:
        return self.object_  # type: ignore[attr-defined,return-value]


class _ObjectIsNoteMixin:
    @property
    def note_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]

    @property
    def note(self) -> VultronNote | None:
        return self.object_  # type: ignore[attr-defined,return-value]


class _ObjectIsStatusMixin:
    @property
    def status_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]

    @property
    def status(self) -> VultronCaseStatus | VultronParticipantStatus | None:
        return self.object_  # type: ignore[attr-defined,return-value]


class _ObjectIsInviteMixin:
    @property
    def invite_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]

    @property
    def invite(self) -> VultronActivity | None:
        return self.object_  # type: ignore[attr-defined,return-value]


class _InnerObjectIsReportMixin:
    @property
    def report_id(self) -> str | None:
        return self.inner_object_id  # type: ignore[attr-defined]

    @property
    def report(self) -> VultronReport | None:
        return self.inner_object  # type: ignore[attr-defined,return-value]


class _InnerObjectIsEmbargoMixin:
    @property
    def embargo_id(self) -> str | None:
        return self.inner_object_id  # type: ignore[attr-defined]

    @property
    def embargo(self) -> VultronEmbargoEvent | None:
        return self.inner_object  # type: ignore[attr-defined,return-value]


class _InnerObjectIsInviteeMixin:
    @property
    def invitee_id(self) -> str | None:
        return self.inner_object_id  # type: ignore[attr-defined]

    @property
    def invitee(self) -> VultronObject | None:
        return self.inner_object  # type: ignore[attr-defined,return-value]


class _InnerObjectIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.inner_object_id  # type: ignore[attr-defined]

    @property
    def case(self) -> VultronCase | None:
        return self.inner_object  # type: ignore[attr-defined,return-value]


class _TargetIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.target_id  # type: ignore[attr-defined]

    @property
    def case(self) -> VultronCase | None:
        return self.target  # type: ignore[attr-defined,return-value]


class _TargetIsParticipantMixin:
    @property
    def participant_id(self) -> str | None:
        return self.target_id  # type: ignore[attr-defined]

    @property
    def participant(self) -> VultronParticipant | None:
        return self.target  # type: ignore[attr-defined,return-value]


class _ContextIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.context_id  # type: ignore[attr-defined]

    @property
    def case(self) -> VultronCase | None:
        return self.context  # type: ignore[attr-defined,return-value]


class _OriginIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.origin_id  # type: ignore[attr-defined]

    @property
    def case(self) -> VultronCase | None:
        return self.origin  # type: ignore[attr-defined,return-value]


class _InnerTargetIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.inner_target_id  # type: ignore[attr-defined]

    @property
    def case(self) -> VultronCase | None:
        return self.inner_target  # type: ignore[attr-defined,return-value]


class _InnerContextIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.inner_context_id  # type: ignore[attr-defined]

    @property
    def case(self) -> VultronCase | None:
        return self.inner_context  # type: ignore[attr-defined,return-value]


class _ObjectIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]

    @property
    def case(self) -> VultronCase | None:
        return self.object_  # type: ignore[attr-defined,return-value]


class _ObjectIsSuggestedActorMixin:
    @property
    def suggested_actor_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]

    @property
    def suggested_actor(self) -> VultronObject | None:
        return self.object_  # type: ignore[attr-defined,return-value]
