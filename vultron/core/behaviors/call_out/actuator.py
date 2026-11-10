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
"""An Actuator acts on one target per call and is safe to repeat (ADR-0183).

An *error* answer leaves a received message in holding, and the re-run asks
every call-out point again.  A tree that acted on some targets before the
error acts on them again, so each Actuator call is keyed on an id the re-run
gives it again:

- :class:`ActuatorContract` is an Actuator's capability declaration: no
  outputs (BT-18-028), and every call takes one :class:`ActuationRequest`.
- :class:`ActuationRequest` is that one call's input: the one target it acts
  on, and the idempotency id derived from the act and the target
  (:func:`actuation_id`).
- :class:`ActuatorBackend` is the base class every Actuator backend
  subclasses.  It builds the request when it is ticked and hands it to
  :meth:`ActuatorBackend.act`; a backend keys its side effect on the
  request's ``idempotency_id`` so that a repeat is a no-op.
- :func:`actuator_call` is how a tree places an Actuator: it binds the call's
  one target when the tree is built.  A tree that acts on several targets
  places one call per target.

The act's id is read from the tree run when the backend is ticked.  A run
that processes a received activity carries it as ``/activity``, and its
``activity_id`` is the act's id: a re-run from holding processes the same
activity, so every call gets the id its first run used.  A trigger or sweep
run carries no received activity and is never re-run from holding (a
caller's retry is a new act, ADR-0176), so each call mints its act's id
once, as a received note does (ID-04-004).

References
----------
- ADR-0183: ``docs/adr/0183-a-call-out-backend-answers-yes-no-or-error-and-the-seam-turns-the-answer-into-tree-behaviour.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-028, BT-18-040 to
  BT-18-044
- ``notes/call-out-configuration.md`` — "An Actuator Acts on One Target and
  Is Safe to Repeat"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import ClassVar, Final

import py_trees
from py_trees.common import Access
from pydantic import BaseModel, ConfigDict

from vultron.core.behaviors.call_out.answer import (
    CallOutAnswer,
    CallOutContract,
)
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.errors import CallOutContractError
from vultron.core.behaviors.call_out.guard import (
    guard_call_out_factory,
    unwrap_call_out,
)
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory
from vultron.core.models._helpers.ids import new_object_id
from vultron.core.models.activity_ids import derived_object_id
from vultron.core.models.events.base import VultronEvent
from vultron.primitives import NonEmptyString, require_non_empty

logger = logging.getLogger(__name__)

#: Kind label of an Actuator call's idempotency id (see ``derived_object_id``).
_ACTUATION_KIND: Final[str] = "actuation"


@dataclass(frozen=True)
class ActuatorContract(CallOutContract):
    """An Actuator's capability declaration (BT-18-028, BT-18-041).

    An Actuator places no artifact on the blackboard, so it declares no
    outputs.  Every call it answers takes one :class:`ActuationRequest`: one
    target and the idempotency id the tree derives from the act and the
    target (BT-18-043).  A *no* still carries a reason, and any declared
    refusal fields.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.outputs:
            raise ValueError(
                f"an Actuator declares no outputs, not {sorted(self.outputs)};"
                " it places no artifact on the blackboard (BT-18-028)"
            )


#: The declaration of an Actuator with only a reason on *no*.
ACTUATOR_CONTRACT: Final[ActuatorContract] = ActuatorContract()


class ActuationRequest(BaseModel):
    """The input of one Actuator call: one target and its idempotency id.

    Attributes:
        target: The one thing this call acts on, as the tree names it.
        idempotency_id: The id the side effect is keyed on.  The same act
            and target always give the same id, so a backend that has
            already acted under it acts no more (BT-18-043, BT-18-044).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    target: NonEmptyString
    idempotency_id: NonEmptyString


def actuation_id(
    *, capability: str, actor_id: str, act_id: str, target: str
) -> str:
    """The idempotency id of one Actuator call (BT-18-043).

    Derived from the call-out point's *capability* name, the executing
    *actor_id*, the *act_id* and the *target*, so two Actuators, two actors,
    two acts or two targets never share an id, and the same four always give
    the same one.  The capability is the node name the tree gives the call;
    renaming it changes the id, so a rename is a change to held messages.
    """
    return derived_object_id(
        _ACTUATION_KIND, capability, actor_id, act_id, target
    )


class ActuatorBackend(CallOutBackend):
    """An Actuator backend: acts on one target per call, safe to repeat.

    Subclasses override :meth:`act`, never :meth:`answer`; a subclass that
    defines ``answer`` is refused when it is created, so every Actuator
    answers through its request.  ``contract`` must be an
    :class:`ActuatorContract`.

    *Yes* means the side effect happened and is confirmed, or had already
    happened under the request's idempotency id.  *No* means the backend
    decided not to act.  A side effect it cannot confirm, or a rejected
    credential, is *error* (BT-18-040).
    """

    contract: ClassVar[CallOutContract] = ACTUATOR_CONTRACT

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Resolved, not only declared here: a base listed before
        # ActuatorBackend could supply an answer() that skips the request.
        if cls.answer is not ActuatorBackend.answer:
            raise TypeError(
                f"Actuator {cls.__name__} overrides answer(); an Actuator "
                "implements act(request), so every call takes its one "
                "target and idempotency id (BT-18-041, BT-18-043)."
            )
        if not isinstance(cls.contract, ActuatorContract):
            raise TypeError(
                f"Actuator {cls.__name__} declares {cls.contract!r}, not an "
                "ActuatorContract; an Actuator places no artifact on the "
                "blackboard (BT-18-028)."
            )

    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self._target: str | None = None
        self._minted_act_id: str | None = None
        self._run = self.attach_blackboard_client(
            name=f"{type(self).__name__}_{self.name}_run"
        )
        for key in ("activity", "actor_id"):
            self._run.register_key(key, Access.READ)

    @property
    def target(self) -> str | None:
        """The one target this call acts on, once :func:`actuator_call` binds it."""
        return self._target

    def bind_target(self, target: str) -> None:
        """Bind the one target this call acts on; called by :func:`actuator_call`.

        A backend is bound once: one placement is one call, and a tree that
        acts on several targets places one backend per target.

        Raises:
            CallOutContractError: The call is already bound; one call acts on
                one target (BT-18-041, BT-18-042).
        """
        require_non_empty(target, "target")
        if self._target is not None:
            raise CallOutContractError(
                f"Actuator {self.name!r} is bound to {self._target!r} and "
                f"cannot be bound again to {target!r}; a tree that acts on "
                "several targets makes one call per target (BT-18-042)."
            )
        self._target = target

    def request(self) -> ActuationRequest:
        """This call's request, built from the tree run (BT-18-043).

        Raises:
            CallOutContractError: No target is bound: the Actuator was placed
                without :func:`actuator_call` (BT-18-041).
        """
        if self._target is None:
            raise CallOutContractError(
                f"Actuator {self.name!r} ({type(self).__name__}) was ticked "
                "with no target; a tree places an Actuator with "
                "actuator_call(), which binds the one target it acts on "
                "(BT-18-041)."
            )
        return ActuationRequest(
            target=self._target,
            idempotency_id=actuation_id(
                capability=self.name,
                actor_id=self._actor_id(),
                act_id=self._act_id(),
                target=self._target,
            ),
        )

    def answer(self) -> CallOutAnswer:
        """Answer this call through :meth:`act`, with its request."""
        return self.act(self.request())

    def act(self, request: ActuationRequest) -> CallOutAnswer:
        """Act on ``request.target``, keyed on ``request.idempotency_id``.

        Subclasses override this.  The default gives the verdict of the next
        ``answer()`` in the method resolution order, so an Actuator composed
        with a constant or probabilistic backend (``NoOpActuator``, a fuzzer
        node) takes that backend's verdict.
        """
        following = super().answer
        if getattr(following, "__func__", None) is CallOutBackend.answer:
            raise NotImplementedError(
                f"{type(self).__name__}.act() must be implemented"
            )
        return following()

    def _actor_id(self) -> str:
        """The executing actor, required when the run carries a received act.

        A received act's id is shared by every actor that receives it, so the
        actor tells their calls apart.  A run with no received activity mints
        its act id, which no other call shares, so a run outside a bridge
        (a unit test ticking a lone backend) may carry no actor.

        Raises:
            CallOutContractError: A received activity is on the run and no
                ``/actor_id`` is.
        """
        actor_id = self._read_run("actor_id")
        if isinstance(actor_id, str) and actor_id:
            return actor_id
        if isinstance(self._read_run("activity"), VultronEvent):
            raise CallOutContractError(
                f"Actuator {self.name!r} runs in a received act with no "
                "/actor_id, so its idempotency id cannot name the actor "
                "(BT-18-043)."
            )
        return ""

    def _act_id(self) -> str:
        """The act's id: the received activity's, else minted once (ID-04-004).

        The minted id is held by this backend, which one tree built for one
        act places once (:meth:`bind_target`), so it is minted once per call
        and never shared: a trigger act is never re-run from holding.
        """
        event = self._read_run("activity")
        if isinstance(event, VultronEvent):
            return event.activity_id
        if self._minted_act_id is None:
            self._minted_act_id = new_object_id()
            # Traceable, not silent: a received act that reached here without
            # /activity would repeat its side effects on a re-run (BT-18-043).
            logger.debug(
                "Actuator %r minted act id %s for target %s (no received"
                " activity on the run; actor_id=%s)",
                self.name,
                self._minted_act_id,
                self._target,
                self._read_run("actor_id"),
            )
        return self._minted_act_id

    def _read_run(self, key: str) -> object | None:
        try:
            value: object = self._run.get(key)
        except KeyError:
            return None
        return value


def actuator_call(
    factory: CallOutBackendFactory, name: str, *, target: str
) -> py_trees.behaviour.Behaviour:
    """Place one Actuator call on one *target*, behind the call-out seam.

    The tree's one way to place an Actuator (BT-18-041): the backend
    *factory* builds is guarded, then bound to *target*.  A tree that acts on
    several targets calls this once per target (BT-18-042).

    Raises:
        CallOutContractError: The factory's backend is not an
            :class:`ActuatorBackend`, so it cannot take a target and an
            idempotency id.
    """
    node = guard_call_out_factory(factory)(name)
    backend = unwrap_call_out(node)
    if not isinstance(backend, ActuatorBackend):
        raise CallOutContractError(
            f"Call-out backend {backend.name!r} ({type(backend).__name__}) "
            "is placed as an Actuator but is not an ActuatorBackend; an "
            "Actuator takes one target and an idempotency id per call "
            "(BT-18-041, BT-18-043)."
        )
    backend.bind_target(target)
    return node


__all__ = [
    "ACTUATOR_CONTRACT",
    "ActuationRequest",
    "ActuatorBackend",
    "ActuatorContract",
    "actuation_id",
    "actuator_call",
]
