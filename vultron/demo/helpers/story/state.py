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
"""What one story run shares: its state, its props and its unseated containers.

:class:`StoryState` is what every fragment takes — the cast's sessions, the
case-actor client, the harness and the artifacts the story has made so far.
A family's own artifacts are :class:`StoryProp`\\ s kept on it, and a
character actor's container waits as an :class:`UnseatedContainer` until the
fragment that brings the actor in seeds and seats it.  :data:`Fragment` is
here because it is the type of a callable on this state
(:mod:`vultron.demo.helpers.story`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.harness import ScenarioHarness
from vultron.demo.utils import DataLayerClient
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

#: One step of a story: a callable run against the story's state.  Named
#: rather than inlined because it is also what a named prefix is made of, and
#: what a scenario reads top to bottom.
Fragment = Callable[["StoryState"], None]


@dataclass(frozen=True)
class StoryProp[PropT]:
    """One artifact a story carries from the fragment that makes it onward.

    :class:`StoryState` names the artifacts *every* story has — the case, the
    report, the Offer, the delivered Invites.  A family's own artifacts are
    declared as props beside the fragments that pass them: the embargo in
    force in the Reporter → Coordinator → Vendor embargo pair, the note a
    later poster replies to.  A prop rather than a field on the state, and
    rather than a per-family subclass, because a fragment is typed
    ``Callable[[StoryState], None]`` and a ``Callable[[Subclass], None]`` is
    not assignable to it (``notes/demo-scenario-tree.md`` § "Composition").

    Declare one at module level, where the fragments that share it can see it::

        EMBARGO_IN_FORCE: StoryProp[str] = StoryProp("embargo in force", str)

    Attributes:
        name: What the artifact is, in the words the error message uses.
        type_: What :meth:`StoryState.keep` accepts and
            :meth:`StoryState.kept` returns.  Checked on the way in, so a
            reader never has to.
    """

    name: str
    type_: type[PropT]


@dataclass(frozen=True, slots=True)
class UnseatedContainer:
    """A container whose character actor the story has not seeded yet.

    The shared opening of a family seeds only the containers every one of its
    scenarios uses: each actor and peer record it writes reads the recording
    clock, so one extra container moves the first ledger entry's timestamp
    away from the siblings whose bytes it must match (DEMOCI-11-018, #5532).
    A character actor's container is therefore reset with the rest and left
    here, for the fragment that brings the actor into the case to seed and
    seat (:meth:`StoryState.container`, :meth:`StoryState.seat`).

    Attributes:
        label: What the reset and the health check call the container.
        client: Client for it.
        actor_id: The deterministic URI its actor is to be seeded with, when
            the run was given one; ``None`` lets the container derive it.
    """

    label: str
    client: DataLayerClient
    actor_id: str | None = None


@dataclass
class StoryState:
    """What every fragment of one story run shares.

    A fragment takes the cast, not a container: each actor is an
    :class:`~vultron.demo.actor_session.ActorSession` bound to the container
    the fixed cast seats it in (DEMOCI-11-020), looked up by the name the
    story seats it under.  The artifacts a story produces — the report, the
    Offer, the case, each delivered Invite — are recorded here as the
    fragments that produce them run, and read back through accessors that
    raise rather than hand out a ``None`` a later fragment would post.
    Whatever else one family passes between its own fragments is kept as a
    :class:`StoryProp` (:meth:`keep`, :meth:`kept`).
    """

    #: Each actor the story has seated so far, by the name it seats it under.
    #: A character actor joins mid-story (:meth:`seat`), so this is the cast
    #: as of now, not the scenario's whole ``ROLES`` list.
    cast: dict[str, ActorSession]
    #: Client for the dedicated case-actor container, which holds the
    #: canonical case and ledger (DEMOMA-06-005).
    case_actor_client: DataLayerClient
    #: The harness of this run: where the step marks and the ledger dump go.
    harness: ScenarioHarness
    #: This scenario's ledger dump, armed by :meth:`open_case` as soon as
    #: there is a case to dump (DEMOMA-23-003).
    dump: Callable[[StoryState], None]
    #: The containers a character actor is still to be seeded in, by the name
    #: the story will seat it under (:class:`UnseatedContainer`).
    unseated: dict[str, UnseatedContainer] = field(default_factory=dict)
    _case: as_VulnerabilityCase | None = field(
        default=None, init=False, repr=False
    )
    _report: as_VulnerabilityReport | None = field(
        default=None, init=False, repr=False
    )
    _offer: as_Offer | None = field(default=None, init=False, repr=False)
    _invites: dict[str, str] = field(
        default_factory=dict, init=False, repr=False
    )
    _props: dict[str, object] = field(
        default_factory=dict, init=False, repr=False
    )

    def actor(self, name: str) -> ActorSession:
        """The session of the cast member this scenario calls *name*.

        Raises:
            DemoStoryError: When the scenario's cast seats no such actor —
                a fragment and the scenario's ``ROLES`` have drifted apart.
        """
        session = self.cast.get(name)
        if session is None:
            raise DemoStoryError(
                f"the story names the actor {name!r}, which this scenario's "
                f"cast does not seat yet; it seats {sorted(self.cast)}. A "
                "character actor is seated by the fragment that brings it "
                "into the case (seat), so a fragment that reads it runs "
                "after that one."
            )
        return session

    def container(self, name: str) -> UnseatedContainer:
        """The container the story is still to seed its *name* actor in.

        Read by the fragment that brings that character actor into the case:
        it seeds the actor on this client, with this deterministic id, and
        then :meth:`seat`\\ s the session.

        Raises:
            DemoStoryError: When the scenario declared no such container, or
                its actor is seated already.
        """
        pending = self.unseated.get(name)
        if pending is None:
            raise DemoStoryError(
                f"the story has no container waiting for {name!r}; it is "
                f"waiting for {sorted(self.unseated)} and already seats "
                f"{sorted(self.cast)}."
            )
        return pending

    def seat(self, name: str, session: ActorSession) -> None:
        """Seat the character actor the story has just seeded as *name*.

        The name leaves :attr:`unseated` for :attr:`cast`, so the container is
        seeded once and every later fragment reaches its actor through
        :meth:`actor`.

        Args:
            name: The name this story's fragments call the new member.
            session: Its session, bound to its own container.

        Raises:
            DemoStoryError: When the name is already seated, or no container
                was waiting for it.  Re-seating would silently redirect every
                later fragment that names it.
        """
        if name in self.cast:
            raise DemoStoryError(
                f"the story already seats an actor called {name!r}; a cast "
                "member is seated once, and the name is how every later "
                "fragment reaches it."
            )
        self.container(name)
        self.cast[name] = session
        del self.unseated[name]

    def keep[PropT](self, prop: StoryProp[PropT], value: PropT) -> None:
        """Record *value* as this story's *prop*, for a later fragment.

        Args:
            prop: The artifact being recorded.
            value: What to record.  A fragment whose act failed records
                nothing, so the dependent fragment's :meth:`kept` raises and
                the story stops there rather than acting on a stand-in
                (:func:`run_story`).

        Raises:
            DemoStoryError: When *value* is not of the prop's type — including
                a ``None`` from a helper that records its own failure.
        """
        if not isinstance(value, prop.type_):
            raise DemoStoryError(
                f"the story's {prop.name} is a {prop.type_.__name__}, and "
                f"{value!r} is not one; a fragment whose act failed keeps "
                "nothing, so the fragments that need it stop instead."
            )
        self._props[prop.name] = value

    def kept[PropT](self, prop: StoryProp[PropT]) -> PropT:
        """The *prop* an earlier fragment of this story recorded.

        Raises:
            DemoStoryError: When no fragment recorded it.  On a run that has
                already failed that is the earlier failure showing through,
                and :func:`run_story` stops the story; on a clean run the
                story is mis-assembled.
        """
        held = self._props.get(prop.name)
        if not isinstance(held, prop.type_):
            raise DemoStoryError(
                f"the story has no {prop.name} yet; the fragment that makes "
                "it runs before the fragments that read it, and keeps "
                "nothing when its own act failed."
            )
        return held

    def client(self, name: str) -> DataLayerClient:
        """The container client of the cast member called *name*."""
        return self.actor(name).client

    def actor_id(self, name: str) -> str:
        """The actor id of the cast member called *name*.

        Raises:
            DemoStoryError: When the cast seats no such actor, or its actor
                carries no id — a seeded actor always does, so an id-less one
                means the cast was built from a stand-in.
        """
        actor_id = self.actor(name).actor.id_
        if not actor_id:
            raise DemoStoryError(
                f"the cast member {name!r} has no actor id, so no step it "
                "decides can be checked against its role (DEMOCI-11-047)."
            )
        return actor_id

    @property
    def case(self) -> as_VulnerabilityCase:
        """The case this story opened.

        Raises:
            DemoStoryError: Before :meth:`open_case` — a fragment that reads
                the case must run after the one that opens it.
        """
        if self._case is None:
            raise DemoStoryError(
                "the story has not opened a case yet; a fragment that reads "
                "the case runs after the one that opens it."
            )
        return self._case

    @property
    def report(self) -> as_VulnerabilityReport:
        """The report this story's Reporter submitted.

        Raises:
            DemoStoryError: Before :meth:`open_case`.
        """
        if self._report is None:
            raise DemoStoryError(
                "the story has no report yet; the Reporter submits it in the "
                "fragment that opens the case."
            )
        return self._report

    @property
    def offer(self) -> as_Offer:
        """The Offer the submitted report arrived as.

        Raises:
            DemoStoryError: Before :meth:`open_case`.
        """
        if self._offer is None:
            raise DemoStoryError(
                "the story has no report Offer yet; the Reporter submits it "
                "in the fragment that opens the case."
            )
        return self._offer

    def open_case(
        self,
        *,
        case: as_VulnerabilityCase,
        report: as_VulnerabilityReport,
        offer: as_Offer,
    ) -> None:
        """Record the opened case, arm the ledger dump and follow the ledger.

        Called by the fragment that opens the case, which is the first point
        at which there is anything to dump: every later fragment can then fail
        without costing the ledgers (DEMOMA-23-003, ISSUE-2239).

        Args:
            case: The case as the Case Owner's container stores it.
            report: The report the Reporter submitted.
            offer: The Offer it arrived as.

        Raises:
            DemoStoryError: When the story has opened a case already.  Arming
                a second dump would export the ledgers twice and follow a
                second ledger, so a step that re-reads the case calls
                :meth:`restate_case` instead.
        """
        if self._case is not None:
            raise DemoStoryError(
                "the story has opened a case already; the dump is armed at "
                "the first instant there is anything to dump and exactly "
                "once (DEMOMA-23-003), so a step that re-reads the case "
                "calls restate_case."
            )
        self._case = case
        self._report = report
        self._offer = offer
        self.harness.dump_with(lambda: self.dump(self))
        self.harness.follow_ledger(self.case_actor_client, case.id_)

    def restate_case(self, case: as_VulnerabilityCase) -> None:
        """Replace the case this story holds, the ledger dump already armed.

        For a step that reads the case back after an act changed it: the
        opening re-reads it once the Coordinator's triage and the participant
        seating have moved on, and an ownership transfer changes who owns it
        (#5535).  Separate from :meth:`open_case` because that one also arms
        the dump and starts following the ledger, which must happen at the
        first instant there is anything to dump and exactly once
        (DEMOMA-23-003, ISSUE-2239).

        The restated case must be the one the story opened.  Nothing a
        scenario does changes a case's id — an ownership transfer moves
        ``attributed_to`` and leaves the id alone (CM-21-024) — so a different
        id means the fragment read the wrong record, and taking it would leave
        the story acting on one case while the armed dump and the followed
        ledger belong to another (#5535).

        Args:
            case: The case as its container now stores it.

        Raises:
            DemoStoryError: Before :meth:`open_case` — restating a case the
                story never opened would arm no dump and follow no ledger —
                or when *case* is not the case the story opened.
        """
        if self._case is None:
            raise DemoStoryError(
                "the story has no case to restate yet; the fragment that "
                "opens one calls open_case, which also arms the ledger dump."
            )
        if case.id_ != self._case.id_:
            raise DemoStoryError(
                f"the story opened the case {self._case.id_!r} and is being "
                f"asked to restate it as {case.id_!r}; no act of a scenario "
                "changes a case's id, so the fragment read the wrong record "
                "and the armed dump and the followed ledger would still be "
                "the first case's (DEMOMA-23-003)."
            )
        self._case = case

    def invited(self, name: str, invite_id: str | None) -> None:
        """Record the Invite delivered to the cast member called *name*.

        ``None`` records that none was — the invite trigger or the delivery
        wait failed and recorded it — which is what
        :meth:`delivered_invite` hands the answer fragment.

        Raises:
            DemoStoryError: When the cast seats no actor of that name.
        """
        self.actor(name)
        if invite_id is None:
            self._invites.pop(name, None)
            return
        self._invites[name] = invite_id

    def delivered_invite(self, name: str) -> str | None:
        """The Invite the cast member called *name* holds, or ``None``.

        The one accessor here that may hand back ``None``, because the answer
        is the step that owns the skip: a demo helper records a failure and
        skips its dependents rather than raising
        (:func:`~vultron.demo.helpers.invite_chain.answer_case_invite` refuses
        a ``None`` inside its own gate, EDF-06-005).  Everything else a story
        produces is read through an accessor that raises.

        Raises:
            DemoStoryError: When the cast seats no actor of that name.
        """
        self.actor(name)
        return self._invites.get(name)


__all__ = ["Fragment", "StoryProp", "StoryState", "UnseatedContainer"]
