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
"""An action rule: a pattern over one vendor's position, roles, an action and
the desiderata it serves (ADR-0216).

* :class:`Position` is one vendor's position: its RM state, its compound case
  state, the case's EM state, and its consent to the embargo in force and to
  each open proposal.  A reading that holds no consent state says so
  (:attr:`Position.consent` is ``None``).
* :class:`RulePattern` names a set of states for each part, or any state.
  :meth:`RulePattern.match` gives *matched*, *unmatched* or *undecided*: a
  part the reading does not hold is unknown, never false (SHD-05-003).
* :class:`AuthoredRule` holds one pattern, its roles, one action, its reason,
  and the desiderata from the move-advice list that its reason is, if any
  (SHD-05-004).  A carried-over rule
  records the ``CS_ACTION_RULES`` pair it came from and stays inside it
  (SHD-05-022, SHD-05-023).

A move is named as move advice names it: its machine and its trigger
(``rm.close``, ``cs.fix_is_ready``, ``em.propose``; SHD-05-005).  PEC moves
(``pec.agree``) are named the same way, but move advice does not score them
yet (#6677).  An action that is a move at some positions only, such as a
publication, is named by its member of
:class:`~vultron.core.scoring.potential_actions.Actions`, and
:data:`ACTION_MOVES` gives the move it is where its event has not happened
(SHD-05-018, SHD-05-019).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from functools import cache
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from vultron.core.scoring.potential_actions import Actions
from vultron.core.states.cs import CS
from vultron.core.states.cs_actions import CS_ACTION_RULES, CSPattern
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM, EM_TRANSITIONS, EM_Trigger
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
    consent_trigger_is_legal,
)
from vultron.core.states.rm import (
    RM,
    RM_Trigger,
    is_valid_rm_transition,
    rm_transition_trigger,
)
from vultron.enums.roles import CVDRole
from vultron.measure.baselines import Desideratum, scope_desiderata
from vultron.measure.standing.model import ActionName
from vultron.measure.standing.moves import CS_TRIGGERS, CSName
from vultron.primitives import NonEmptyString

ANY_ROLE: Literal["any"] = "any"
"""The roles of a rule that constrains no role, as the ``None`` entry of
:data:`~vultron.core.states.em.EM_TRIGGER_ROLES` does."""

type Roles = frozenset[CVDRole] | Literal["any"]
"""A rule's roles: a non-empty set of CVD roles, or :data:`ANY_ROLE`."""


class Machine(StrEnum):
    """The state machine a move belongs to, the prefix of its name."""

    RM = "rm"
    CS = "cs"
    EM = "em"
    PEC = "pec"


SCORED_MACHINES: frozenset[Machine] = frozenset(
    {Machine.RM, Machine.CS, Machine.EM}
)
"""The machines whose moves move advice scores; PEC moves wait for #6677."""


@cache
def move_names() -> Mapping[str, Machine]:
    """Every move name and its machine: each RM, CS, EM and PEC trigger,
    named ``<machine>.<trigger>`` as move advice names it."""
    triggers: list[tuple[Machine, Iterable[StrEnum]]] = [
        (Machine.RM, RM_Trigger),
        (Machine.CS, CS_TRIGGERS.values()),
        (Machine.EM, EM_Trigger),
        (Machine.PEC, PEC_Trigger),
    ]
    return MappingProxyType(
        {
            f"{machine}.{trigger}": machine
            for machine, members in triggers
            for trigger in members
        }
    )


def machine_of(move: str) -> Machine:
    """The machine of the move named *move*.

    Raises:
        ValueError: *move* names no move.
    """
    try:
        return move_names()[move]
    except KeyError:
        raise ValueError(
            f"{move!r} names no move; a move is named <machine>.<trigger>,"
            " as move advice names it"
        ) from None


def trigger_of(move: str) -> str:
    """The trigger of the move named *move*, its name less the machine.

    Raises:
        ValueError: *move* names no move.
    """
    machine = machine_of(move)
    return move.removeprefix(f"{machine}.")


def _a_move_name(move: str) -> str:
    machine_of(move)
    return move


MoveName = Annotated[str, AfterValidator(_a_move_name)]
"""A move's name, refused unless it names an RM, CS, EM or PEC trigger."""


def _cs_move(event: CSEvent) -> str:
    return f"{Machine.CS}.{CS_TRIGGERS[event]}"


#: The CS event each CS move causes, by move name.
CS_MOVE_EVENTS: Mapping[str, CSEvent] = MappingProxyType(
    {_cs_move(event): event for event in CS_TRIGGERS}
)

_PUBLICATIONS = (
    Actions.PUBLISH_VULNERABILITY,
    Actions.PUBLISH_FIX,
    Actions.PUBLISH_MITIGATION,
    Actions.PUBLISH_DETECTION_FOR_EXPLOITS,
    Actions.PUBLISH_DETECTION_FOR_ATTACKS,
    Actions.PUBLICIZE_PUBLISHED_EXPLOITS,
    Actions.PUBLICIZE_MITIGATION,
)

ACTION_MOVES: Mapping[Actions, str] = MappingProxyType(
    {
        Actions.NOTIFY_VENDOR: _cs_move(CSEvent.V),
        Actions.PAY_ATTENTION_TO_PUBLIC_REPORTS: _cs_move(CSEvent.V),
        Actions.CREATE_FIX: _cs_move(CSEvent.F),
        Actions.DEPLOY_FIX: _cs_move(CSEvent.D),
        **dict.fromkeys(_PUBLICATIONS, _cs_move(CSEvent.P)),
        Actions.PUBLISH_EXPLOIT_CODE: _cs_move(CSEvent.X),
        Actions.TERMINATE_ANY_EXISTING_EMBARGO: f"{Machine.EM}.terminate",
        Actions.CLOSE_CASE: f"{Machine.RM}.close",
    }
)
"""The move each member of ``Actions`` that changes state is (SHD-05-019).

A publication is any publication; only the first causes P, so where P has
happened a publication is an action that changes no state (ADR-0216,
SHD-05-024).  The same holds for an action that causes V, F, D or X.
``INITIATE_EMBARGO_TERMINATION`` is in :data:`NO_STATE_ACTIONS`: the case
owner's own termination is a rule that names ``em.terminate``, and anyone
else's is a request that changes no state."""

NO_STATE_ACTIONS: frozenset[Actions] = frozenset(
    {
        Actions.SCRUTINIZE_APPROPRIATENESS_OF_EMBARGO_INITIATION,
        Actions.INITIATE_EMBARGO_TERMINATION,
        Actions.MAINTAIN_VIGILANCE_FOR_EMBARGO_EXIT_CRITERIA,
        Actions.MAINTAIN_ANY_EXISTING_EMBARGO,
        Actions.MOTIVATE_VENDOR_TO_FIX,
        Actions.ENCOURAGE_VENDOR_TO_CREATE_FIX,
        Actions.ENCOURAGE_VENDOR_TO_DEPLOY_FIX,
        Actions.DISCOURAGE_EXPLOIT_PUBLICATION,
        Actions.PROMOTE_FIX_DEPLOYMENT,
        Actions.MONITOR_FOR_EXPLOIT_PUBLICATION,
        Actions.MONITOR_FOR_EXPLOIT_REFINEMENT,
        Actions.MONITOR_FOR_ATTACKS,
        Actions.MONITOR_FOR_ADDITIONAL_ATTACKS,
        Actions.ESCALATE_RESPONSE_PRIORITY,
        Actions.ESCALATE_VENDOR_NOTIFICATION_PRIORITY,
        Actions.ESCALATE_FIX_PRIORITY,
        Actions.ESCALATE_DEPLOYMENT_PRIORITY,
        Actions.ESCALATE_VIGILANCE_FOR_EXPLOITS,
        Actions.ESCALATE_VIGILANCE_FOR_ATTACKS,
    }
)
"""The members of ``Actions`` that change no state at any position.

Two members are in neither this set nor :data:`ACTION_MOVES`:
``NEGOTIATE_OR_ESTABLISH_DISCLOSURE_EMBARGO``, which the authored rules split
into the EM and PEC moves it is (ADR-0216, SHD-05-006), and ``INITIATE_VEP_USGOV``,
which is not a move of the protocol and does not carry over."""


def desideratum_name(desideratum: Desideratum) -> str:
    """*desideratum*'s plain name, its notation without LaTeX: ``D≺P``,
    ``F_i≺ExOwn``."""
    return (
        desideratum.notation.strip("$")
        .replace(r"\ev", "")
        .replace(r" \prec ", "≺")
    )


@cache
def move_advice_desiderata() -> Mapping[str, Desideratum]:
    """The move-advice desiderata list, by plain name, in catalog order.

    The desiderata each vendor's scope sums
    (:func:`~vultron.measure.baselines.scope_desiderata`): ``E≺P``
    stands for the three ``E`` desiderata and ``ExOwn≺P`` for the three
    ``ExOwn`` ones.  Computed on first use, as that list is.
    """
    return MappingProxyType(
        {desideratum_name(d): d for d in scope_desiderata()}
    )


class MatchStatus(StrEnum):
    """Whether a rule's pattern matches a position (ADR-0216, SHD-05-003)."""

    MATCHED = "matched"
    UNMATCHED = "unmatched"
    #: A part the pattern constrains is one the reading does not hold.
    UNDECIDED = "undecided"


class ProposalConsent(BaseModel):
    """A vendor's consent to one open embargo proposal.

    Fields:
        proposal: The proposal, by its register entry.
        state: The vendor's consent to it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    proposal: NonEmptyString
    state: EmbargoConsentState


class ConsentReading(BaseModel):
    """A vendor's consent states, from a reading that holds them.

    Fields:
        in_force: Its consent to the embargo in force; ``None`` when no
            embargo is in force.
        proposals: Its consent to each open proposal, in register order.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    in_force: EmbargoConsentState | None = None
    proposals: tuple[ProposalConsent, ...] = ()


class Position(BaseModel):
    """One vendor's position: the states an action rule reads (SHD-05-001).

    Fields:
        vendor: The vendor.
        rm: Its report-management state.
        cs: Its compound case state.
        em: The case's EM state.
        consent: Its consent states; ``None`` when the reading holds no
            consent state, so a rule with a PEC part is undecided here
            (SHD-05-003).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    vendor: NonEmptyString
    rm: RM
    cs: CSName
    em: EM
    consent: ConsentReading | None = None


@cache
def cs_pattern_matches(pattern: str, state: CS) -> bool:
    """Whether the ``vfdpxa`` *pattern* matches *state*
    (:meth:`~vultron.core.states.cs_actions.CSPattern.matches`), kept: the
    comparison asks it for every rule at every position.

    Raises:
        ValueError: *pattern* is malformed.
    """
    return CSPattern(pattern).matches(state)


def _a_cs_pattern(pattern: str) -> str:
    CSPattern(pattern)
    return pattern


CSPatternText = Annotated[str, AfterValidator(_a_cs_pattern)]
"""A ``vfdpxa`` pattern (:class:`~vultron.core.states.cs_actions.CSPattern`)."""


class PatternMatch(BaseModel):
    """How a pattern matches one position.

    Fields:
        status: Matched, unmatched or undecided.
        proposals: For a matched pattern with a proposal part, each open
            proposal it matches, in register order: the rule matches once
            for each (SHD-05-020).  Empty otherwise.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: MatchStatus
    proposals: tuple[NonEmptyString, ...] = ()


class RulePattern(BaseModel):
    """A pattern over one vendor's position: a set of states for each part.

    A part left ``None`` matches any state.  An empty set is refused: it
    would match nothing.

    Fields:
        cs: The ``vfdpxa`` pattern over the vendor's compound case state.
        rm: The vendor's report-management states.
        em: The case's EM states.
        in_force: The vendor's consent states to the embargo in force; a
            position with no embargo in force does not match a set.
        proposal: The vendor's consent states to an open proposal; the
            pattern matches once for each open proposal in one of them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    cs: CSPatternText = "......"
    rm: frozenset[RM] | None = None
    em: frozenset[EM] | None = None
    in_force: frozenset[EmbargoConsentState] | None = None
    proposal: frozenset[EmbargoConsentState] | None = None

    @model_validator(mode="after")
    def _no_empty_part(self) -> RulePattern:
        empty = [
            name
            for name in ("rm", "em", "in_force", "proposal")
            if getattr(self, name) == frozenset()
        ]
        if empty:
            raise ValueError(
                f"a pattern part names at least one state: {', '.join(empty)}"
                " is empty; leave a part out to match any state"
            )
        return self

    @property
    def reads_consent(self) -> bool:
        """Whether the pattern has a PEC part."""
        return self.in_force is not None or self.proposal is not None

    def matches_cs(self, state: CS) -> bool:
        """Whether the CS part matches *state*."""
        return cs_pattern_matches(self.cs, state)

    def match(self, position: Position) -> PatternMatch:
        """How the pattern matches *position*.

        A part that fails makes the pattern unmatched, whatever the other
        parts read.  Otherwise a PEC part over a reading with no consent
        state makes it undecided, never matched or unmatched (SHD-05-003).
        """
        if not (
            self.matches_cs(position.cs)
            and (self.rm is None or position.rm in self.rm)
            and (self.em is None or position.em in self.em)
        ):
            return PatternMatch(status=MatchStatus.UNMATCHED)
        if not self.reads_consent:
            return PatternMatch(status=MatchStatus.MATCHED)
        consent = position.consent
        if consent is None:
            return PatternMatch(status=MatchStatus.UNDECIDED)
        if self.in_force is not None and consent.in_force not in self.in_force:
            return PatternMatch(status=MatchStatus.UNMATCHED)
        if self.proposal is None:
            return PatternMatch(status=MatchStatus.MATCHED)
        matched = tuple(
            p.proposal for p in consent.proposals if p.state in self.proposal
        )
        if not matched:
            return PatternMatch(status=MatchStatus.UNMATCHED)
        return PatternMatch(status=MatchStatus.MATCHED, proposals=matched)


class SourcePair(BaseModel):
    """The ``CS_ACTION_RULES`` pattern and action a rule carries over.

    Refused unless ``CS_ACTION_RULES`` holds the pair (SHD-05-022).

    Fields:
        pattern: The source rule's ``vfdpxa`` pattern.
        action: One of the source rule's actions.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern: CSPatternText
    action: ActionName

    @model_validator(mode="after")
    def _held_by_cs_action_rules(self) -> SourcePair:
        if (self.pattern, self.action) not in cs_action_pairs():
            raise ValueError(
                f"CS_ACTION_RULES holds no pair {self.pattern}"
                f" {self.action.name}"
            )
        return self


@cache
def cs_action_pairs() -> frozenset[tuple[str, Actions]]:
    """Every pattern and action pair ``CS_ACTION_RULES`` holds."""
    return frozenset(
        (rule.pattern, action)
        for rule in CS_ACTION_RULES
        for action in rule.actions
    )


def _rm_sources(trigger: str) -> frozenset[RM]:
    return frozenset(
        source
        for source in RM
        for dest in RM
        if is_valid_rm_transition(source, dest)
        and rm_transition_trigger(source, dest) == trigger
    )


def _em_sources(trigger: str) -> frozenset[EM]:
    return frozenset(
        source for source, _ in EM_TRANSITIONS[EM_Trigger(trigger)]
    )


def _pec_sources(trigger: str) -> frozenset[EmbargoConsentState]:
    return frozenset(
        state
        for state in EmbargoConsentState
        if consent_trigger_is_legal(state, PEC_Trigger(trigger))
    )


class AuthoredRule(BaseModel):
    """One authored action rule: a suggested action, and why (ADR-0216,
    SHD-05-004).

    Every rule has a reason.  Where the reason is a desideratum, the rule
    names it, and the rule claims that its action serves it; a reason such
    as situation awareness, detection, defense or housekeeping orders no
    events, so a rule with that reason names no desideratum, and the
    comparison shows it with its reason and no number (SHD-05-028).

    Fields:
        pattern: The positions it matches.
        roles: The CVD roles that may take the action, or :data:`ANY_ROLE`.
        action: A move name, for an action that is a move at every position
            the rule matches (SHD-05-005), or a member of ``Actions``
            (SHD-05-018).
        reason: Why a participant would take the action, in words, with any
            condition that is not a pattern part, such as "unless monitoring
            for X".
        desiderata: The desiderata the action serves, by plain name, from
            the move-advice list (:func:`move_advice_desiderata`); empty when
            the reason is not a desideratum.
        source: The ``CS_ACTION_RULES`` pair it carries over; ``None`` for a
            new rule.
        blind_spot: The issue that tracks a chance-model blind spot the rule
            stands on, so a rule disagreement it gives carries it
            (SHD-05-014).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern: RulePattern
    roles: Roles
    action: ActionName | MoveName
    reason: NonEmptyString
    desiderata: tuple[NonEmptyString, ...] = ()
    source: SourcePair | None
    blind_spot: int | None = Field(default=None, gt=0)

    @field_validator("roles", mode="after")
    @classmethod
    def _some_role(cls, roles: Roles) -> Roles:
        if roles != ANY_ROLE and not roles:
            raise ValueError(
                "a rule names at least one role, or any role; the role set"
                " is empty"
            )
        return roles

    @field_validator("desiderata", mode="after")
    @classmethod
    def _from_the_move_advice_list(
        cls, desiderata: tuple[str, ...]
    ) -> tuple[str, ...]:
        listed = move_advice_desiderata()
        unknown = [d for d in desiderata if d not in listed]
        if unknown:
            raise ValueError(
                f"{', '.join(unknown)} is not in the move-advice desiderata"
                f" list ({', '.join(listed)})"
            )
        if len(set(desiderata)) != len(desiderata):
            raise ValueError("a desideratum is named more than once")
        return desiderata

    @model_validator(mode="after")
    def _fits_its_source_and_its_move(self) -> AuthoredRule:
        problems = self._outside_source()
        if isinstance(self.action, str):
            problems.extend(self._outside_move(self.action))
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def _outside_source(self) -> list[str]:
        """Where the rule's CS part leaves its source pattern
        (SHD-05-023)."""
        if self.source is None:
            return []
        source = self.source.pattern
        wider = [
            state.name
            for state in CS
            if self.pattern.matches_cs(state)
            and not cs_pattern_matches(source, state)
        ]
        if wider:
            return [
                f"{self.pattern.cs} matches {', '.join(wider)}, which its"
                f" source {self.source.pattern} does not: a carried-over rule"
                " is narrowed, never widened"
            ]
        return []

    def _outside_move(self, move: str) -> list[str]:
        """The parts that match states from which *move* does not exist
        (SHD-05-026, SHD-05-027)."""
        machine = machine_of(move)
        trigger = trigger_of(move)
        if machine is Machine.RM:
            return _within("RM", self.pattern.rm, _rm_sources(trigger), move)
        if machine is Machine.EM:
            return _within("EM", self.pattern.em, _em_sources(trigger), move)
        if machine is Machine.PEC:
            sources = _pec_sources(trigger)
            parts = [
                ("in-force PEC", self.pattern.in_force),
                ("proposal PEC", self.pattern.proposal),
            ]
            named = [(label, part) for label, part in parts if part]
            if not named:
                return [f"a rule naming {move} needs a PEC part"]
            return [
                problem
                for label, part in named
                for problem in _within(label, part, sources, move)
            ]
        return []

    @property
    def measured(self) -> bool:
        """Whether the rule names a desideratum, so a band can check it."""
        return bool(self.desiderata)

    @property
    def move(self) -> str | None:
        """The move the rule names, or ``None`` when it names an action of
        ``Actions``."""
        return self.action if isinstance(self.action, str) else None

    @property
    def roles_label(self) -> str:
        """Its roles as text: ``any``, or the roles in ``CVDRole`` order."""
        if self.roles == ANY_ROLE:
            return ANY_ROLE
        return ", ".join(r.name for r in CVDRole if r in self.roles)

    def may_take(self, role: CVDRole | None) -> bool:
        """Whether the rule's roles include *role*; ``None`` is any role,
        which every rule's roles include."""
        return role is None or self.roles == ANY_ROLE or role in self.roles


def _within[S: StrEnum](
    label: str, part: frozenset[S] | None, sources: frozenset[S], move: str
) -> list[str]:
    if part is None:
        return [
            f"a rule naming {move} names its {label} states; {move} exists"
            f" only from {', '.join(sorted(sources))}"
        ]
    outside = sorted(part - sources)
    if outside:
        return [f"{move} does not exist from {label} {', '.join(outside)}"]
    return []
