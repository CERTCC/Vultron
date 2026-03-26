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

from typing import TYPE_CHECKING, Protocol, cast

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
else:
    VultronActivity = object
    VultronObject = object
    VultronCase = object
    VultronCaseStatus = object
    VultronEmbargoEvent = object
    VultronNote = object
    VultronParticipant = object
    VultronParticipantStatus = object
    VultronReport = object


class _SupportsObjectFields(Protocol):
    object_id: str | None
    object_: object | None


class _SupportsInnerObjectFields(Protocol):
    inner_object_id: str | None
    inner_object: object | None


class _SupportsTargetFields(Protocol):
    target_id: str | None
    target: object | None


class _SupportsContextFields(Protocol):
    context_id: str | None
    context: object | None


class _SupportsOriginFields(Protocol):
    origin_id: str | None
    origin: object | None


class _SupportsInnerTargetFields(Protocol):
    inner_target_id: str | None
    inner_target: object | None


class _SupportsInnerContextFields(Protocol):
    inner_context_id: str | None
    inner_context: object | None


class _ObjectIsReportMixin:
    @property
    def report_id(self) -> str | None:
        return cast(_SupportsObjectFields, self).object_id

    @property
    def report(self) -> VultronReport | None:
        return cast(
            VultronReport | None, cast(_SupportsObjectFields, self).object_
        )


class _ObjectIsOfferMixin:
    @property
    def offer_id(self) -> str | None:
        return cast(_SupportsObjectFields, self).object_id

    @property
    def offer(self) -> VultronActivity | None:
        return cast(
            VultronActivity | None, cast(_SupportsObjectFields, self).object_
        )


class _ObjectIsEmbargoMixin:
    @property
    def embargo_id(self) -> str | None:
        return cast(_SupportsObjectFields, self).object_id

    @property
    def embargo(self) -> VultronEmbargoEvent | None:
        return cast(
            VultronEmbargoEvent | None,
            cast(_SupportsObjectFields, self).object_,
        )


class _ObjectIsParticipantMixin:
    @property
    def participant_id(self) -> str | None:
        return cast(_SupportsObjectFields, self).object_id

    @property
    def participant(self) -> VultronParticipant | None:
        return cast(
            VultronParticipant | None,
            cast(_SupportsObjectFields, self).object_,
        )


class _ObjectIsNoteMixin:
    @property
    def note_id(self) -> str | None:
        return cast(_SupportsObjectFields, self).object_id

    @property
    def note(self) -> VultronNote | None:
        return cast(
            VultronNote | None, cast(_SupportsObjectFields, self).object_
        )


class _ObjectIsStatusMixin:
    @property
    def status_id(self) -> str | None:
        return cast(_SupportsObjectFields, self).object_id

    @property
    def status(self) -> VultronCaseStatus | VultronParticipantStatus | None:
        return cast(
            VultronCaseStatus | VultronParticipantStatus | None,
            cast(_SupportsObjectFields, self).object_,
        )


class _ObjectIsInviteMixin:
    @property
    def invite_id(self) -> str | None:
        return cast(_SupportsObjectFields, self).object_id

    @property
    def invite(self) -> VultronActivity | None:
        return cast(
            VultronActivity | None, cast(_SupportsObjectFields, self).object_
        )


class _InnerObjectIsReportMixin:
    @property
    def report_id(self) -> str | None:
        return cast(_SupportsInnerObjectFields, self).inner_object_id

    @property
    def report(self) -> VultronReport | None:
        return cast(
            VultronReport | None,
            cast(_SupportsInnerObjectFields, self).inner_object,
        )


class _InnerObjectIsEmbargoMixin:
    @property
    def embargo_id(self) -> str | None:
        return cast(_SupportsInnerObjectFields, self).inner_object_id

    @property
    def embargo(self) -> VultronEmbargoEvent | None:
        return cast(
            VultronEmbargoEvent | None,
            cast(_SupportsInnerObjectFields, self).inner_object,
        )


class _InnerObjectIsInviteeMixin:
    @property
    def invitee_id(self) -> str | None:
        return cast(_SupportsInnerObjectFields, self).inner_object_id

    @property
    def invitee(self) -> VultronObject | None:
        return cast(
            VultronObject | None,
            cast(_SupportsInnerObjectFields, self).inner_object,
        )


class _InnerObjectIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return cast(_SupportsInnerObjectFields, self).inner_object_id

    @property
    def case(self) -> VultronCase | None:
        return cast(
            VultronCase | None,
            cast(_SupportsInnerObjectFields, self).inner_object,
        )


class _TargetIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return cast(_SupportsTargetFields, self).target_id

    @property
    def case(self) -> VultronCase | None:
        return cast(
            VultronCase | None, cast(_SupportsTargetFields, self).target
        )


class _TargetIsParticipantMixin:
    @property
    def participant_id(self) -> str | None:
        return cast(_SupportsTargetFields, self).target_id

    @property
    def participant(self) -> VultronParticipant | None:
        return cast(
            VultronParticipant | None, cast(_SupportsTargetFields, self).target
        )


class _ContextIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return cast(_SupportsContextFields, self).context_id

    @property
    def case(self) -> VultronCase | None:
        return cast(
            VultronCase | None, cast(_SupportsContextFields, self).context
        )


class _OriginIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return cast(_SupportsOriginFields, self).origin_id

    @property
    def case(self) -> VultronCase | None:
        return cast(
            VultronCase | None, cast(_SupportsOriginFields, self).origin
        )


class _InnerTargetIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return cast(_SupportsInnerTargetFields, self).inner_target_id

    @property
    def case(self) -> VultronCase | None:
        return cast(
            VultronCase | None,
            cast(_SupportsInnerTargetFields, self).inner_target,
        )


class _InnerContextIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return cast(_SupportsInnerContextFields, self).inner_context_id

    @property
    def case(self) -> VultronCase | None:
        return cast(
            VultronCase | None,
            cast(_SupportsInnerContextFields, self).inner_context,
        )


class _ObjectIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return cast(_SupportsObjectFields, self).object_id

    @property
    def case(self) -> VultronCase | None:
        return cast(
            VultronCase | None, cast(_SupportsObjectFields, self).object_
        )


class _ObjectIsSuggestedActorMixin:
    @property
    def suggested_actor_id(self) -> str | None:
        return cast(_SupportsObjectFields, self).object_id

    @property
    def suggested_actor(self) -> VultronObject | None:
        return cast(
            VultronObject | None, cast(_SupportsObjectFields, self).object_
        )
