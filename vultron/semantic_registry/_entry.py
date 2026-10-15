"""Shared ``SemanticEntry`` dataclass used by all domain sub-modules."""

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

from dataclasses import dataclass, field

from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.semantic_registry._occasion import MessagePage, Occasion
from vultron.wire.as2.extractor import ActivityPattern
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

#: Dispatcher fallbacks: entries that route unrecognised activities and are
#: not protocol messages, so they declare no occasion and own no page
#: (MSM-06-002, MSM-08-001).
DISPATCHER_FALLBACKS: frozenset[MessageSemantics] = frozenset(
    {
        MessageSemantics.UNKNOWN,
        MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT,
    }
)


@dataclass(frozen=True)
class SemanticEntry:
    """All dispatch components for a single ``MessageSemantics`` value.

    Attributes:
        semantics: The semantic intent this entry describes.
        pattern: Wire-layer pattern for matching the incoming activity.
            ``None`` for the ``UNKNOWN`` fallback entry.
        event_class: Domain event class to construct from the matched activity.
        use_case_class: Use-case class to execute for this semantic type.
        phrase: Active-voice format-string template for human-readable event
            summaries (SE-07-001).  Named slots drawn from
            ``{actor}``, ``{object}``, ``{target}``, ``{context}``,
            ``{origin}``, ``{inner_object}`` (SE-07-002).  No default — omitting
            it is a ``TypeError`` at construction time (SE-07-003).
        wire_activity_class: Specific wire ``as_Activity`` subclass for
            DataLayer coercion. ``None`` when no specific wire class exists.
        include_activity: When ``True``, ``extract_intent()`` populates
            ``VultronEvent.activity`` for this semantic type.
        occasions: The situations a sender conveys with this entry's wire
            activity (ADR-0128).  At least one is required, except on a
            dispatcher fallback, which has none (MSM-08-001).
        page: The ``docs/reference/messages/`` page that owns the entry
            (MSM-06-002).  Required, except on a dispatcher fallback, which
            has none.

    Raises:
        TypeError: At construction, when ``occasions`` is not a tuple or
            ``page`` is not a ``MessagePage``.
        ValueError: At construction, when a non-fallback entry declares no
            occasion or no page, or a fallback declares either, or an
            occasion's addressee is a side the use case's declared sender
            rule states no kinds for (MSM-08-009).
    """

    semantics: MessageSemantics
    pattern: ActivityPattern | None
    event_class: type[VultronEvent]
    use_case_class: type
    phrase: str
    wire_activity_class: type[as_Activity] | None = field(default=None)
    include_activity: bool = field(default=False)
    occasions: tuple[Occasion, ...] = field(default=())
    page: MessagePage | None = field(default=None)

    def __post_init__(self) -> None:
        if not isinstance(self.occasions, tuple):
            raise TypeError(
                f"{self.semantics.name}: occasions must be a tuple"
            )
        if self.page is not None and not isinstance(self.page, MessagePage):
            raise TypeError(
                f"{self.semantics.name}: page must be a MessagePage, not"
                f" {type(self.page).__name__}"
            )
        if self.semantics in DISPATCHER_FALLBACKS:
            if self.occasions or self.page is not None:
                raise ValueError(
                    f"{self.semantics.name} is a dispatcher fallback, not a"
                    " protocol message, so it declares no occasion and no"
                    " page (MSM-06-002)"
                )
            return
        if not self.occasions:
            raise ValueError(
                f"{self.semantics.name} declares no occasion; every entry"
                " outside the dispatcher fallbacks needs at least one"
                " (MSM-08-001)"
            )
        if self.page is None:
            raise ValueError(
                f"{self.semantics.name} names no message page (MSM-06-002)"
            )
        self._addressees_are_sides_of_the_rule()

    def _addressees_are_sides_of_the_rule(self) -> None:
        """Refuse an occasion sent to a side the declared rule leaves empty.

        Only a declared :class:`SenderRule` has sides: an exemption is not
        yet checked, and a missing declaration is the HP-01-007 ratchet's to
        report.
        """
        rule: object = getattr(self.use_case_class, "sender_entitlement", None)
        if not isinstance(rule, SenderRule):
            return
        unmatched = [
            f"{o.anchor!r} ({o.addressee.name})"
            for o in self.occasions
            if not rule.side(o.addressee)
        ]
        if unmatched:
            raise ValueError(
                f"{self.semantics.name}: {self.use_case_class.__name__}'s"
                " sender rule states no side for the addressee of occasion"
                f" {', '.join(unmatched)} (MSM-08-009)"
            )
