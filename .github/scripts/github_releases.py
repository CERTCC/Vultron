"""Read a GitHub Release: whether it exists, whether it is a draft, its assets.

Shared by the promote (``release.py``), the frozen-draft serving step
(``serve_frozen_drafts.py``) and the publish gate (``publish_gate.py``), which
cannot import ``release.py`` because that module imports it.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gh_cli import gh, retry_delays  # see gh_cli


@dataclass(frozen=True)
class ReleaseState:
    """A GitHub Release as the promote sees it: draft or not, and its assets."""

    is_draft: bool
    assets: tuple[str, ...]


def release_state(
    repo: str, name: str, *, retry: bool = False
) -> ReleaseState | None:
    """The GitHub Release, draft or not, for tag *name*, or ``None``.

    Only ``gh``'s "release not found" reads as no release; any other error
    raises, so a failed lookup never leads to a second draft. With *retry*,
    such an error is tried again within ``retry.sh``'s bounds, and "not
    found" is never retried: a deploy that only reads passes it, while the
    promote reads the release afresh in its own loop.
    """
    delays = retry_delays() if retry else []
    for delay in [*delays, None]:
        try:
            out = gh(
                "release", "view", name, "--repo", repo, "--json",
                "isDraft,assets", retry=False,
            )  # fmt: skip
        except subprocess.CalledProcessError as error:
            if "not found" in str(error.stderr or "").lower():
                return None
            if delay is None:
                raise
            time.sleep(delay)
            continue
        data = json.loads(out)
        return ReleaseState(
            bool(data["isDraft"]),
            tuple(str(asset["name"]) for asset in data.get("assets") or []),
        )
    raise AssertionError("unreachable: the last attempt returns or raises")
