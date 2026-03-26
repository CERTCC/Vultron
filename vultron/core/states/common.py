#!/usr/bin/env python

# Copyright

"""
Provides common state machine components for Vultron protocol states,
including the TransitionBase model and any shared utilities or base classes
for state machines.
"""

from enum import Enum

from pydantic import BaseModel
from transitions import Machine

from vultron.core.models.base import NonEmptyString


class TransitionBase(BaseModel):
    trigger: NonEmptyString
    source: NonEmptyString | Enum
    dest: NonEmptyString | Enum


def mermaid_machine(M: Machine):
    lines = []
    lines.append("```mermaid")
    lines.append("flowchart LR")
    for trigger_name in M.events.keys():
        # Fetch transitions associated with this trigger
        transitions = M.get_transitions(trigger=trigger_name)

        for trans in transitions:
            # trans is now guaranteed to be a Transition object
            lines.append(f"{trans.source} -->|{trigger_name}| {trans.dest}")
    lines.append("```")
    return "\n".join(lines)
