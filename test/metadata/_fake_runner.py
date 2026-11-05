"""One stand-in for :data:`vultron.metadata.planning.gh.Runner`.

The planning scripts take a ``Runner`` so their tests never reach GitHub. This
fake records every argument list and answers from queued replies: a ``str`` is
returned as is, an exception is raised, and anything else is returned as JSON.
The last reply repeats, so a test that expects one call can pass one reply and
still see a stray second call in ``calls`` rather than an ``IndexError``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence


class FakeRunner:
    """Records ``gh`` calls and answers each with the next queued reply."""

    def __init__(self, *replies: object) -> None:
        if not replies:
            raise ValueError("FakeRunner needs at least one reply")
        self.replies = list(replies)
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> str:
        self.calls.append(list(args))
        reply = (
            self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        )
        if isinstance(reply, BaseException):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)
