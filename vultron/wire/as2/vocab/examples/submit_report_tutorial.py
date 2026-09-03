#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""Single source of truth for the "Submit a report" tutorial.

The tutorial page ``docs/tutorials/submit-a-report.md`` does not hard-code its
commands or its ``Create(VulnerabilityReport)`` payload.  Instead it imports the
renderers here through ``markdown-exec`` and displays their output, so the
examples the reader copies are the same values this module builds — and the same
values the end-to-end test exercises.  When the wire format or the API changes,
the test in ``test/demo/test_submit_report_tutorial.py`` fails and the rendered
page changes with the code, rather than drifting silently.

Three kinds of thing live here:

- **Canonical values** — the base URL, actor slug, and report identifiers the
  tutorial uses throughout.
- **Builders** — :func:`vendor_create_body` and :func:`create_report_activity`
  construct the two request bodies from the same vocabulary classes the server
  parses, so they track schema changes.
- **Renderers** — the ``render_*`` functions return fenced Markdown blocks for
  the tutorial to display, and :func:`run_end_to_end` drives the whole flow
  against any client exposing ``post``/``get`` (the FastAPI ``TestClient`` in
  tests).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlparse

from vultron.wire.as2.factories import rm_create_report_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.examples._base import (
    _strip_published_udpated,
    json2md,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# --- Canonical values shared by the docs, the commands, and the test ---------

#: Base URL the reference server serves when started with the documented
#: ``uv run uvicorn`` command (the default ``VULTRON_SERVER__BASE_URL``).  Every
#: rendered URL and path below derives from this one value.
API_BASE_URL = "http://localhost:7999/api/v2"

#: Scheme + host (e.g. ``http://localhost:7999``) and API prefix (``/api/v2``)
#: split out of :data:`API_BASE_URL` so the commands and the path helpers cannot
#: disagree about where the server lives.
_SERVER_ORIGIN = (
    f"{urlparse(API_BASE_URL).scheme}://{urlparse(API_BASE_URL).netloc}"
)
_API_PREFIX = urlparse(API_BASE_URL).path

#: Short id of the actor that receives the report (a stand-in vendor).
VENDOR_SLUG = "vendorco"
VENDOR_NAME = "VendorCo"
VENDOR_ACTOR_TYPE = "Organization"

#: The reporter and the report they submit.
FINDER_ID = "https://finder.example/users/finn"
REPORT_ID = "https://finder.example/reports/report-001"
REPORT_NAME = "FDR-0001"
REPORT_CONTENT = "I found a vulnerability!"
ACTIVITY_ID = "urn:uuid:11111111-1111-1111-1111-111111111111"

#: Fixed timestamp for the report we send.  Because we set the report's
#: ``published``/``updated`` explicitly, the store echoes them back unchanged, so
#: both the rendered payload and the rendered store response stay deterministic
#: across docs builds.  (The activity's own top-level timestamps default to build
#: time and are stripped in :func:`create_report_activity_body`.)
_FIXED_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)

#: Command the reader runs to start the reference implementation.
SERVER_COMMAND = (
    "uv run uvicorn vultron.adapters.driving.fastapi.main:app "
    "--host 127.0.0.1 --port 7999"
)

#: The record the vendor's store returns from ``GET .../datalayer/Reports/``
#: after the report is accepted, keyed by the report id.  The timestamps are the
#: ones we send (:data:`_FIXED_TS`), so the whole record is deterministic — the
#: tutorial renders it and ``test/demo/test_submit_report_tutorial.py`` asserts
#: the live response equals it, so this cannot drift from the datalayer silently.
STORED_REPORT_RESPONSE: dict[str, dict[str, Any]] = {
    REPORT_ID: {
        "id": REPORT_ID,
        "type": "VulnerabilityReport",
        "name": REPORT_NAME,
        "published": _FIXED_TS.isoformat(),
        "updated": _FIXED_TS.isoformat(),
        "content": REPORT_CONTENT,
        "attributedTo": FINDER_ID,
        "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
    }
}


class _HttpClient(Protocol):
    """Minimal client contract satisfied by ``requests`` and ``TestClient``."""

    def post(self, url: str, *args: Any, **kwargs: Any) -> Any: ...

    def get(self, url: str, *args: Any, **kwargs: Any) -> Any: ...


# --- Endpoint paths ----------------------------------------------------------


def actors_path() -> str:
    """Return the ``POST`` path that creates an actor."""
    return f"{_API_PREFIX}/actors/"


def inbox_path(slug: str = VENDOR_SLUG) -> str:
    """Return the ``POST`` path of *slug*'s inbox."""
    return f"{_API_PREFIX}/actors/{slug}/inbox/"


def reports_path(slug: str = VENDOR_SLUG) -> str:
    """Return the ``GET`` path listing the reports in *slug*'s store."""
    return f"{_API_PREFIX}/actors/{slug}/datalayer/Reports/"


def health_path() -> str:
    """Return the liveness-probe path."""
    return f"{_API_PREFIX}/health/live"


# --- Request-body builders ---------------------------------------------------


def vendor_create_body() -> dict[str, str]:
    """Return the JSON body for ``POST /actors/`` that creates the vendor."""
    return {
        "name": VENDOR_NAME,
        "actor_type": VENDOR_ACTOR_TYPE,
        "id": VENDOR_SLUG,
    }


def create_report_activity() -> as_Create:
    """Build the ``Create(VulnerabilityReport)`` the reporter submits.

    Built from the same vocabulary classes the server parses, addressed to the
    vendor by its short id so the inbox addressing gate accepts it.
    """
    report = as_VulnerabilityReport(
        id_=REPORT_ID,
        name=REPORT_NAME,
        content=REPORT_CONTENT,
        attributed_to=[FINDER_ID],
        published=_FIXED_TS,
        updated=_FIXED_TS,
    )
    return rm_create_report_activity(
        report,
        id_=ACTIVITY_ID,
        actor=FINDER_ID,
        to=[VENDOR_SLUG],
    )


def create_report_activity_body() -> dict[str, Any]:
    """Return the ``Create(VulnerabilityReport)`` as a JSON-ready dict.

    The activity's own ``published``/``updated`` default to build time, so they
    are stripped (exactly as :func:`json2md` does for the displayed payload).
    This keeps the posted body deterministic across docs builds and identical to
    what :func:`render_payload` shows the reader; the server assigns its own
    receipt timestamps regardless.  The report's fixed timestamps, being nested,
    are preserved.
    """
    activity = _strip_published_udpated(create_report_activity())
    body: dict[str, Any] = json.loads(activity.to_json())
    return body


# --- Markdown renderers consumed by the tutorial via markdown-exec -----------


def _bash_block(command: str) -> str:
    return f"```bash\n{command}\n```"


def _curl(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    url = f"{_SERVER_ORIGIN}{path}"
    if body is None:
        return f"curl {url}"
    payload = json.dumps(body, indent=2)
    return (
        f"curl -i -X {method} {url} \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -d '{payload}'"
    )


def render_server_command() -> str:
    """Render the command that starts the reference server."""
    return _bash_block(SERVER_COMMAND)


def render_health_check() -> str:
    """Render the liveness-probe command."""
    return _bash_block(_curl("GET", health_path()))


def render_create_actor() -> str:
    """Render the command that creates the vendor actor."""
    return _bash_block(_curl("POST", actors_path(), vendor_create_body()))


def render_submit_report() -> str:
    """Render the command that submits the report to the vendor's inbox."""
    return _bash_block(
        _curl("POST", inbox_path(), create_report_activity_body())
    )


def render_payload() -> str:
    """Render the ``Create(VulnerabilityReport)`` payload as JSON."""
    return json2md(create_report_activity())


def render_verify() -> str:
    """Render the command that reads the report back out of the store."""
    return _bash_block(_curl("GET", reports_path()))


def render_stored_report() -> str:
    """Render the report record the vendor's store returns after acceptance."""
    return f"```json\n{json.dumps(STORED_REPORT_RESPONSE, indent=2)}\n```"


# --- End-to-end runner, exercised by the test --------------------------------


def run_end_to_end(client: _HttpClient) -> dict[str, Any]:
    """Run the tutorial flow against *client* and return the three responses.

    Mirrors the tutorial exactly: create the vendor actor, submit the report to
    its inbox, then read the vendor's report store back.  The FastAPI
    ``TestClient`` runs the inbox background task before ``post`` returns, so the
    stored report is visible to the subsequent ``get``.

    Returns:
        A dict with ``create``, ``submit``, and ``reports`` response objects.
    """
    create = client.post(actors_path(), json=vendor_create_body())
    submit = client.post(inbox_path(), json=create_report_activity_body())
    reports = client.get(reports_path())
    return {"create": create, "submit": submit, "reports": reports}
