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


"""TriggerNotesPort: the notes part of
:class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`.

Note creation and attachment.
"""

from typing import Protocol


class TriggerNotesPort(Protocol):
    """Note creation and attachment."""

    def create_note(
        self,
        name: str,
        content: str,
        context_id: str,
        attributed_to: str,
        in_reply_to: str | None = None,
        note_id: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist a Note object; return ``(note_id, note_json)``.

        *note_id*, when given, is the note's id: a note that answers a
        received activity takes an id derived from it, so a re-run names the
        note its first run stored and stores no second one (ID-04-004).
        A note already stored under it is returned as stored.  Without it
        the id is minted.
        """
        ...

    def add_note_to_case(
        self,
        note_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Add(Note)[target=VulnerabilityCase]`` activity.

        The ``Add`` carries the stored note *note_id* inline as its
        ``object`` (VAM-01-015).  The id is derived from *actor* and the
        note, so a re-run names the same activity (ID-04-004).

        Returns ``(activity_id, activity_body)``, the body as sealed JSON.
        """
        ...
