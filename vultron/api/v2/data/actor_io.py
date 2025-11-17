#!/usr/bin/env python

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

# Copyright

"""
Provides TODO writeme
"""
import logging
import sys

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Mailbox(BaseModel):
    items: list[str] = Field(default_factory=list)

    def append(self, item: str) -> None:
        self.items.append(item)

    def pop(self) -> str | None:
        if self.items:
            return self.items.pop(0)
        return None

    def list_items(self) -> list[str]:
        return self.items.copy()


class ActorIO(BaseModel):
    actor_id: str
    inbox: Mailbox = Field(default_factory=Mailbox)
    outbox: Mailbox = Field(default_factory=Mailbox)


ACTOR_IO_STORE: dict[str, ActorIO] = dict()


def init_actor_io(actor_id: str, force=False) -> ActorIO:
    """
    Initialize the ActorIO for a given actor.

    Args:
        actor_id: The ID of the actor.
        force: Whether to force overwrite existing actors.
    Returns:
        The initialized ActorIO for the given actor.
    Raises:
        KeyError: If the ActorIO for the given actor already exists.
    """
    if not force and actor_id in ACTOR_IO_STORE:
        raise KeyError(
            f"ActorIO for actor_id {actor_id} already exists, set `force=True` to override."
        )

    ACTOR_IO_STORE[actor_id] = ActorIO(actor_id=actor_id)

    actor_io = ACTOR_IO_STORE[actor_id]
    return actor_io


def get_actor_io(
    actor_id: str, init=False, raise_on_missing=False
) -> ActorIO | None:
    """
    Get the ActorIO for a given actor.

    Note that `raise_on_missing` takes precedence over `init`.

    Args:
        actor_id: The ID of the actor.
        init: Whether to initialize the ActorIO for this actor if it does not exist.
        raise_on_missing: Whether to raise an exception if the ActorIO does not exist.

    Returns:
        The ActorIO for the given actor, or None if it does not exist and init is False.
    Raises:
        KeyError: If raise_on_missing is True and the ActorIO does not exist.
    """
    if actor_id not in ACTOR_IO_STORE:
        if raise_on_missing:
            raise KeyError(f"ActorIO for actor_id {actor_id} not found.")
        elif init:
            init_actor_io(actor_id)

    return ACTOR_IO_STORE.get(actor_id)


def get_actor_inbox(actor_id: str) -> Mailbox:
    """
    Get the inbox for a given actor.

    Args:
        actor_id: The ID of the actor.

    Returns:
        The inbox Mailbox for the given actor.

    Raises:
        KeyError: If the ActorIO for the given actor does not exist.
    """
    actor_io = get_actor_io(actor_id, init=False, raise_on_missing=True)
    return actor_io.inbox


def get_actor_outbox(actor_id: str) -> Mailbox:
    """
    Get the outbox for a given actor.

    Args:
        actor_id: The ID of the actor.

    Returns:
        The outbox Mailbox for the given actor.

    Raises:
        KeyError: If the ActorIO for the given actor does not exist.
    """
    actor_io = get_actor_io(actor_id, init=False, raise_on_missing=True)
    return actor_io.outbox


def reset_actor_inbox(actor_id: str) -> Mailbox:
    """
    Reset the inbox for a given actor.

    Args:
        actor_id: The ID of the actor.
    Returns:
        None

    Raises:
        KeyError: If the ActorIO for the given actor does not exist.
    """
    actor_io = get_actor_io(actor_id, init=False, raise_on_missing=True)
    actor_io.inbox = Mailbox()
    return actor_io.inbox


def reset_actor_outbox(actor_id: str) -> Mailbox:
    """
    Reset the outbox for a given actor.

    Args:
        actor_id: The ID of the actor.
    Returns:
        The new outbox Mailbox for the given actor.
    Raises:
        KeyError: If the ActorIO for the given actor does not exist.
    """
    actor_io = get_actor_io(actor_id, init=False, raise_on_missing=True)
    actor_io.outbox = Mailbox()
    return actor_io.outbox


def clear_all_actor_ios() -> None:
    """
    Clear all ActorIOs from the store.

    Returns:
        None
    """
    ACTOR_IO_STORE.clear()


def main():
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

    for actor in ["alice", "bob", "carol"]:
        io = init_actor_io(actor)
        logger.info(f"Initialized inbox for {actor}: {io.inbox}")
        logger.info(f"Initialized outbox for {actor}: {io.outbox}")

    for x in range(3):
        for actor in ["alice", "bob", "carol"]:
            inbox = get_actor_inbox(actor)
            outbox = get_actor_outbox(actor)
            inbox.append(f"message {x} to {actor} inbox")
            outbox.append(f"message {x} to {actor} outbox")

    for actor in ["alice", "bob", "carol"]:
        inbox = get_actor_inbox(actor)
        outbox = get_actor_outbox(actor)
        logger.info(f"Inbox for {actor}: {inbox}")
        logger.info(f"Outbox for {actor}: {outbox}")


if __name__ == "__main__":
    main()
