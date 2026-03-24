"""Reusable property mixins for per-semantic event subclasses.

Each mixin exposes a domain-specific property name for a generic base-class
field, making use-case code self-documenting without duplicating the mapping
across multiple event classes.
"""


class _ObjectIsReportMixin:
    @property
    def report_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]


class _ObjectIsOfferMixin:
    @property
    def offer_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]


class _ObjectIsEmbargoMixin:
    @property
    def embargo_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]


class _ObjectIsParticipantMixin:
    @property
    def participant_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]


class _ObjectIsNoteMixin:
    @property
    def note_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]


class _ObjectIsStatusMixin:
    @property
    def status_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]


class _ObjectIsInviteMixin:
    @property
    def invite_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]


class _InnerObjectIsReportMixin:
    @property
    def report_id(self) -> str | None:
        return self.inner_object_id  # type: ignore[attr-defined]


class _InnerObjectIsEmbargoMixin:
    @property
    def embargo_id(self) -> str | None:
        return self.inner_object_id  # type: ignore[attr-defined]


class _InnerObjectIsInviteeMixin:
    @property
    def invitee_id(self) -> str | None:
        return self.inner_object_id  # type: ignore[attr-defined]


class _InnerObjectIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.inner_object_id  # type: ignore[attr-defined]


class _TargetIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.target_id  # type: ignore[attr-defined]


class _TargetIsParticipantMixin:
    @property
    def participant_id(self) -> str | None:
        return self.target_id  # type: ignore[attr-defined]


class _ContextIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.context_id  # type: ignore[attr-defined]


class _OriginIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.origin_id  # type: ignore[attr-defined]


class _InnerTargetIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.inner_target_id  # type: ignore[attr-defined]


class _InnerContextIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.inner_context_id  # type: ignore[attr-defined]


class _ObjectIsCaseMixin:
    @property
    def case_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]


class _ObjectIsSuggestedActorMixin:
    @property
    def suggested_actor_id(self) -> str | None:
        return self.object_id  # type: ignore[attr-defined]
