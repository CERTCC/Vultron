#!/usr/bin/env python
"""
Vultron API Actors Backend
"""
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

import base64
import binascii

from pydantic import BaseModel, Field

from vultron.as_vocab.base.objects.actors import as_Actor


class ActorRegistry(BaseModel):
    """
    A simple in-memory registry for actors.
    In a real implementation, this would interface with a database.
    """

    actors: dict[str, as_Actor] = Field(default_factory=dict)

    def register_actor(self, actor: as_Actor) -> None:
        actor_id = actor.as_id

        # url encode the actor_id if necessary
        if actor_id is None:
            raise ValueError("Actor must have an id")

        key = base64.urlsafe_b64encode(actor_id.encode("utf-8")).decode(
            "ascii"
        )
        self.actors[key] = actor

    def get_actor(self, actor_id: str) -> as_Actor | None:
        try:
            # Decode the base64 encoded actor_id back to original
            original_id = base64.urlsafe_b64decode(
                actor_id.encode("ascii")
            ).decode("utf-8")
            # Re-encode to ensure consistency
            key = base64.urlsafe_b64encode(original_id.encode("utf-8")).decode(
                "ascii"
            )
            return self.actors.get(key)
        except (binascii.Error, UnicodeDecodeError):
            # If decoding fails, try direct lookup in case it's already the key
            return self.actors.get(actor_id)

    def list_actors(self) -> list[as_Actor] | None:
        # replace id with base64 encoded id
        encoded_actors = []
        for actor in self.actors.values():
            actor_copy = as_Actor.model_validate(actor.model_dump())
            if actor_copy.as_id:
                actor_copy.as_id = base64.urlsafe_b64encode(
                    actor_copy.as_id.encode("utf-8")
                ).decode("ascii")
            encoded_actors.append(actor_copy)
        return list(encoded_actors) if encoded_actors else None


ACTOR_REGISTRY = ActorRegistry()
