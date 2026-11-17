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

"""The CVD action rules: the actions a compound case state makes possible.

Each :class:`CSActionRule` names a set of compound case states by a
six-position ``vfdpxa`` pattern, and the CVD actions a participant in one of
those states *could* take.  The actions are a menu of possibilities, never
duties: which one a participant takes is left to its policy.

The table re-expresses the legacy pattern table of
``vultron.core.case_states.patterns.potential_actions`` against the
authoritative `CS` enum.  The legacy module stays as the test oracle
(ADR-0060); ``test_cs_actions.py`` holds :func:`cs_actions` equal to the
legacy ``action()`` over every valid compound state (CSB-17-001).

A rule matches only a `CS` member, so an invalid combination such as
``vfDpxa`` (a fix deployed that was never ready) has no reading here.  The
legacy ``action()`` reads any six-character string, that one included
(#3355).

Spec: CSB-17-001.  Decision: ADR-0060.
"""

from __future__ import annotations

from dataclasses import dataclass

from vultron.core.scoring.potential_actions import Actions
from vultron.core.states.cs import CS
from vultron.core.states.cs_invariants import (
    CS_EVENTS,
    CSEvent,
    cs_happened_events,
)


@dataclass(frozen=True)
class CSActionRule:
    """One pattern over the compound case states, and its possible actions.

    A malformed pattern, or a rule with no action, is refused at
    construction.

    Fields:
        pattern: The rule's ``vfdpxa`` pattern.  Each position holds its
            event's letter, upper-case when the event must have occurred,
            lower-case when it must not have, or ``.`` for either.
        actions: The CVD actions a participant in a matching state could
            take, in the order the rule lists them.
    """

    pattern: str
    actions: tuple[Actions, ...]

    def __post_init__(self) -> None:
        if len(self.pattern) != len(CS_EVENTS) or any(
            letter not in (".", event.value, event.value.lower())
            for event, letter in zip(CS_EVENTS, self.pattern, strict=False)
        ):
            raise ValueError(
                "an action-rule pattern holds, for each event of"
                f" {''.join(CS_EVENTS)} in turn, '.' or that event's letter"
                f" in either case; got {self.pattern!r}"
            )
        if not self.actions:
            raise ValueError(
                f"the action rule {self.pattern!r} names no action"
            )

    @property
    def occurred(self) -> frozenset[CSEvent]:
        """The events a matching state has had."""
        return frozenset(
            event
            for event, letter in zip(CS_EVENTS, self.pattern, strict=True)
            if letter == event.value
        )

    @property
    def pending(self) -> frozenset[CSEvent]:
        """The events a matching state has not yet had."""
        return frozenset(
            event
            for event, letter in zip(CS_EVENTS, self.pattern, strict=True)
            if letter == event.value.lower()
        )

    def matches(self, state: CS) -> bool:
        """Whether *state* has had every :attr:`occurred` event and none of
        the :attr:`pending` ones."""
        happened = cs_happened_events(state)
        return self.occurred <= happened and not self.pending & happened


def _rule(pattern: str, *actions: Actions) -> CSActionRule:
    """A :class:`CSActionRule` from its pattern and its actions."""
    return CSActionRule(pattern, actions)


#: The CVD action rules, in the legacy table's order.  Things a participant
#: COULD do, not necessarily things it SHOULD do.
CS_ACTION_RULES: tuple[CSActionRule, ...] = (
    _rule(
        "...P..",
        Actions.TERMINATE_ANY_EXISTING_EMBARGO,
        Actions.PUBLISH_VULNERABILITY,
    ),
    _rule(
        "....X.",
        Actions.TERMINATE_ANY_EXISTING_EMBARGO,
        Actions.PUBLISH_VULNERABILITY,
        Actions.PUBLICIZE_PUBLISHED_EXPLOITS,
        Actions.MONITOR_FOR_EXPLOIT_REFINEMENT,
        Actions.PUBLISH_DETECTION_FOR_EXPLOITS,
    ),
    _rule(
        ".....A",
        Actions.TERMINATE_ANY_EXISTING_EMBARGO,
        Actions.PUBLISH_VULNERABILITY,
        Actions.MONITOR_FOR_ADDITIONAL_ATTACKS,
        Actions.PUBLISH_DETECTION_FOR_ATTACKS,
    ),
    _rule("VfdpX.", Actions.INITIATE_EMBARGO_TERMINATION),
    _rule("Vfdp.A", Actions.INITIATE_EMBARGO_TERMINATION),
    _rule("....x.", Actions.MONITOR_FOR_EXPLOIT_PUBLICATION),
    _rule(".....a", Actions.MONITOR_FOR_ATTACKS),
    _rule(
        "vfdP..",
        Actions.PAY_ATTENTION_TO_PUBLIC_REPORTS,
        Actions.ESCALATE_VENDOR_NOTIFICATION_PRIORITY,
    ),
    _rule(
        "...pxa",
        Actions.MAINTAIN_VIGILANCE_FOR_EMBARGO_EXIT_CRITERIA,
        Actions.MAINTAIN_ANY_EXISTING_EMBARGO,
    ),
    _rule(
        "VfdP..",
        Actions.ESCALATE_VIGILANCE_FOR_EXPLOITS,
        Actions.ESCALATE_VIGILANCE_FOR_ATTACKS,
        Actions.PUBLISH_MITIGATION,
        Actions.PUBLICIZE_MITIGATION,
        Actions.ESCALATE_FIX_PRIORITY,
    ),
    _rule("V..p..", Actions.PUBLISH_VULNERABILITY, Actions.PUBLISH_MITIGATION),
    _rule(".fdP..", Actions.PUBLISH_MITIGATION),
    _rule("...pX.", Actions.PUBLISH_VULNERABILITY, Actions.PUBLISH_MITIGATION),
    _rule("...PX.", Actions.PUBLISH_VULNERABILITY, Actions.PUBLISH_MITIGATION),
    _rule("...p.A", Actions.PUBLISH_VULNERABILITY, Actions.PUBLISH_MITIGATION),
    _rule("vfdp..", Actions.PUBLISH_VULNERABILITY, Actions.PUBLISH_MITIGATION),
    _rule(
        "Vfd...", Actions.CREATE_FIX, Actions.ENCOURAGE_VENDOR_TO_CREATE_FIX
    ),
    _rule("VFd...", Actions.DEPLOY_FIX),
    _rule(".fdPxA", Actions.PUBLISH_EXPLOIT_CODE),
    _rule("VFdPxa", Actions.PUBLISH_EXPLOIT_CODE),
    _rule("vfd...", Actions.NOTIFY_VENDOR),
    _rule(".FdP..", Actions.ESCALATE_DEPLOYMENT_PRIORITY),
    _rule(".f..X.", Actions.ESCALATE_FIX_PRIORITY),
    _rule(".f...A", Actions.ESCALATE_FIX_PRIORITY),
    _rule(".Fd.X.", Actions.ESCALATE_DEPLOYMENT_PRIORITY),
    _rule(".Fd..A", Actions.ESCALATE_DEPLOYMENT_PRIORITY),
    _rule("..dpxa", Actions.NEGOTIATE_OR_ESTABLISH_DISCLOSURE_EMBARGO),
    _rule(
        "Vfdp..",
        Actions.MOTIVATE_VENDOR_TO_FIX,
        Actions.PUBLISH_VULNERABILITY,
    ),
    _rule("VFdpxa", Actions.SCRUTINIZE_APPROPRIATENESS_OF_EMBARGO_INITIATION),
    _rule(
        "VFdp..",
        Actions.ENCOURAGE_VENDOR_TO_DEPLOY_FIX,
        Actions.PUBLISH_VULNERABILITY,
        Actions.PUBLISH_FIX,
    ),
    _rule("VFdP..", Actions.PROMOTE_FIX_DEPLOYMENT),
    _rule("VFDp..", Actions.PUBLISH_VULNERABILITY),
    _rule(".fd.xa", Actions.DISCOURAGE_EXPLOIT_PUBLICATION),
    _rule("vfdpx.", Actions.INITIATE_VEP_USGOV),
    _rule("VFDPXA", Actions.CLOSE_CASE),
    _rule("VFDPxa", Actions.CLOSE_CASE),
    _rule("VFDPXa", Actions.CLOSE_CASE),
    _rule("VFDPxA", Actions.CLOSE_CASE),
)


def cs_actions(state: CS) -> tuple[Actions, ...]:
    """The CVD actions *state* makes possible, each once.

    The actions of every matching rule, in table order and then rule order,
    keeping each action's first place.
    """
    actions: dict[Actions, None] = {}
    for rule in CS_ACTION_RULES:
        if rule.matches(state):
            actions.update(dict.fromkeys(rule.actions))
    return tuple(actions)
