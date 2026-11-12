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

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict, get_args
from unittest.mock import patch

from pydantic import BaseModel

from vultron.core.models._helpers import (
    URN_UUID_PREFIX,
    SteppingClock,
    clock as helpers_clock,
    install_id_source,
)
from vultron.core.models.actor import hosted_endpoints
from vultron.wire.as2 import signing
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Organization,
    as_Person,
    as_Service,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_EXAMPLE_BASE_URL = "https://demo.vultron.local/"

#: The fixed moment the pinned example objects are stamped with.
#:
#: Tests compare an activity's embedded object against a second call to the
#: same builder, and two clock reads that straddle a tick differ — at second
#: precision for the ``published`` and ``updated`` default stamps, at minute
#: precision for an embargo ``start_time`` (#4095).  So every object a test
#: compares that way (the embargo, note, participant, participant and case
#: status, invite and vendor-profile builders) is pinned to this moment.
#: Inside :func:`_example_scope` the clock itself reads this moment, so an
#: object that was not pinned by hand is stamped with it too.  The date is
#: fixed, so it is in the past.
EXAMPLE_TIMESTAMP: datetime = datetime(2026, 6, 1, 19, 12, tzinfo=UTC)

#: The name every derived example id is drawn under, so no example id can
#: collide with an id derived anywhere else in the codebase (#5776).
_EXAMPLE_ID_SCOPE = "vultron-docs-example"

#: The case number every example that names the shared case shows.  Fixed, not
#: drawn: a regeneration must change only what the generator changed, and a
#: fresh number per run rewrote all 92 committed examples (#5776).
case_number = 20260601

#: The case number of the case the bootstrap ``Create`` example mints, kept
#: apart from :data:`case_number` so a reader can see the two are not one case.
_FRESH_CASE_NUMBER = 20260602


class _ExampleStamp(TypedDict):
    """The ``published``/``updated`` keyword pair, typed for ``**`` unpacking."""

    published: datetime
    updated: datetime


def _example_stamp() -> _ExampleStamp:
    """``published`` and ``updated`` pinned to :data:`EXAMPLE_TIMESTAMP`.

    Pass as ``**_example_stamp()`` to every example object: the times are
    required, and an example states this fixed one (ADR-0176).
    """
    return _ExampleStamp(
        published=EXAMPLE_TIMESTAMP, updated=EXAMPLE_TIMESTAMP
    )


def example_uuid(name: str) -> uuid.UUID:
    """A stable example UUID for *name*, shaped like a minted one.

    ``uuid5`` of *name* gives the stability — the same name always gives the
    same id, so regenerating the committed examples rewrites only what the
    generator changed (#5776).  ``version=4`` is then set on the result
    because what these ids stand in for is a *minted* id (``new_object_id``,
    OID-01-004), and a reader copying an example has to see the shape this
    protocol mints, not the version-5 shape that marks an id derived from
    what an activity answers (``derived_object_id``).
    ``vultron.demo.determinism.SeededUuid4`` keeps its ids version-4 for the
    same reason.
    """
    stable = uuid.uuid5(uuid.NAMESPACE_URL, f"{_EXAMPLE_ID_SCOPE}/{name}")
    return uuid.UUID(int=stable.int, version=4)


def _make_id(object_type: str) -> str:
    """The example id of *object_type* under the example base URL."""
    return f"{_EXAMPLE_BASE_URL}{object_type}/{example_uuid(object_type)}"


class _ScopedIds:
    """An id source that derives each draw from the example asking for it.

    The id source :func:`_example_scope` installs for the minter
    (``install_id_source``, OID-01-011), so an object built without an
    explicit ``id_`` still gets a stable one.  Each draw is
    :func:`example_uuid` of the scope name and the draw's position within that
    scope, so the ids one example carries depend on that example alone:
    entering another scope before or after it moves none of them.  That is the
    property a seeded sequence does not have, and the reason this is not
    ``vultron.demo.determinism.SeededUuid4`` — under one shared sequence,
    adding an example would shift every id drawn after it, which is the
    88-files-changed-to-alter-18 problem #5776 was filed for.

    Not thread-safe, and the install is process-wide: the generator builds one
    example at a time, in one thread.
    """

    def __init__(self, scope: str) -> None:
        self._scope = scope
        self._drawn = 0

    def __call__(self) -> uuid.UUID:
        self._drawn += 1
        return example_uuid(f"{self._scope}/{self._drawn}")


@contextmanager
def _example_scope(scope: str) -> Iterator[None]:
    """Build one example's objects with derived ids and the fixed clock.

    Two sources made the generator write different bytes on every run: the
    minted object ids, and the wall clock.  No model reads the clock for a
    time any more (ADR-0176); every example states :data:`EXAMPLE_TIMESTAMP`,
    and the clock is still frozen here for any other read.  Inside this block
    both are replaced, keyed
    on *scope* — the name of the example being written — so that running the
    generator twice over an unchanged tree produces an unchanged tree, and a
    change to one example rewrites only that example's file (#5776).

    This is deliberately not ``vultron.demo.determinism.deterministic_run``,
    which answers the same question for a scenario recording.  The wire layer
    may not import the demo layer (ARCH-22-001 is the core allow-list; the
    demo sits above both), the id source has to be scope-derived rather than
    seeded (see :class:`_ScopedIds`), and the clock has to be frozen rather
    than stepping so that two objects in one example agree.  What the two do
    share, ``SteppingClock``, is imported rather than copied.

    The ids come through the minter's scoped install (``install_id_source``,
    ADR-0185), not a patch of the ``uuid`` module's draw, which nothing may
    replace (OID-01-012).  The install does not nest, so this block may not be
    entered inside another install, nor inside itself: that raises
    ``VultronIdSourceInstalledError`` rather than mixing two streams of ids.

    The install is process-wide for the duration of the block, so a caller
    must not enter it while another thread is minting ids: an id drawn there
    would be an example id rather than a fresh one.  Every caller is a
    single-threaded generator or test.
    """
    with (
        install_id_source(_ScopedIds(scope)),
        patch.object(
            helpers_clock,
            "datetime",
            SteppingClock(EXAMPLE_TIMESTAMP, step=timedelta(0)),
        ),
    ):
        yield


base_url = "https://vultron.example"
user_base_url = f"{base_url}/users"
case_base_url = f"{base_url}/cases"
organization_base_url = f"{base_url}/organizations"
report_base_url = f"{base_url}/reports"

# The shared objects every other example refers to are built once, when this
# module is imported, outside any per-example scope.  Each one pins the values
# it would otherwise draw: every other example carries one of them, so a value
# that moved between runs moved in all 92 committed files at once (#5776).
#
# Each example actor's profile is the one it publishes, so it states its own
# endpoints (``hosted_endpoints``); an activity naming it carries it as held.
_FINDER = as_Person.model_validate(
    {
        "id": f"{user_base_url}/finndervul",
        "name": "Finn der Vul",
        **hosted_endpoints(f"{user_base_url}/finndervul"),
        **_example_stamp(),
    }
)
_VENDOR = as_Organization.model_validate(
    {
        "id": f"{organization_base_url}/vendorco",
        "name": "VendorCo",
        **hosted_endpoints(f"{organization_base_url}/vendorco"),
        **_example_stamp(),
    }
)
_COORDINATOR = as_Organization.model_validate(
    {
        "id": f"{organization_base_url}/coordinator",
        "name": "Coordinator LLC",
        **hosted_endpoints(f"{organization_base_url}/coordinator"),
        **_example_stamp(),
    }
)

case_actor_base_url = f"{base_url}/case-actors"
_CASE_ACTOR = as_Service.model_validate(
    {
        "id": f"{case_actor_base_url}/vendorco-case-actor",
        "name": "VendorCo Case Actor",
        **hosted_endpoints(f"{case_actor_base_url}/vendorco-case-actor"),
        **_example_stamp(),
    }
)

_REPORT = as_VulnerabilityReport(
    name="FDR-8675309",
    id_=_make_id("VulnerabilityReport"),
    content="I found a vulnerability!",
    attributed_to=_FINDER.id_,
    **_example_stamp(),
)

# The one shared object a hand-pinned id and stamp are not enough for: the
# ``as_VulnerabilityCase`` constructor builds an initial ``CaseStatus``
# inline, whose own id it draws (its ``published`` is the case's).  So this single
# construction runs inside a scope.  It is the only import-time use of
# ``_example_scope``; see that function on why the id source it installs must
# not be entered while another thread is minting ids.
with _example_scope("shared-case"):
    _CASE = as_VulnerabilityCase(
        name=f"{_VENDOR.name} Case #{case_number}",
        id_=f"{URN_UUID_PREFIX}{example_uuid('shared-VulnerabilityCase')}",
        attributed_to=_VENDOR.id_,
        **_example_stamp(),
    )


def finder() -> as_Person:
    """
    Create a finder (Person) object
    Returns:
        an as_Person object
    """
    return _FINDER


def vendor() -> as_Organization:
    """
    Create a vendor (Organization) object
    Returns:
        an as_Organization object
    """
    return _VENDOR


def coordinator() -> as_Organization:
    """
    Create a coordinator (Organization) object
    Returns:
        an as_Organization object
    """
    return _COORDINATOR


def case_actor() -> as_Service:
    """
    Create a CaseActor (Service) object representing the automated case-management service actor.
    Returns:
        an as_Service object
    """
    return _CASE_ACTOR


_IDENTITY_KEYS = frozenset({"name", "id_", "attributed_to"})


def case(fresh_id: bool = False, **kwargs: Any) -> as_VulnerabilityCase:
    """The example case, optionally with extra fields populated.

    With no arguments this returns the shared `_CASE` singleton, whose id every
    other case-related example refers to. Any ``kwargs`` are applied on top of
    that same identity — id, name and attributor are preserved, so a populated
    case and the participants built against `case()` still agree on which case
    they belong to. Pass ``fresh_id=True`` for a second case, under an id and
    case number of its own, as the bootstrap ``Create`` example needs.

    ``kwargs`` must not include ``name``, ``id_``, or ``attributed_to`` — those
    identity fields are always supplied by this helper and cannot be overridden.
    Passing any of them raises ``ValueError``.

    ``kwargs`` is typed ``Any`` rather than ``object`` because it is unpacked
    into the ``as_VulnerabilityCase`` constructor, whose fields each have their
    own type; ``object`` is not assignable to any of them (CS-11-001 asks for
    the determinable type, and here there is none).
    """
    overlap = _IDENTITY_KEYS & kwargs.keys()
    if overlap:
        raise ValueError(
            f"kwargs must not override identity fields: {sorted(overlap)!r}"
        )
    if fresh_id:
        return as_VulnerabilityCase(
            name=f"{_VENDOR.name} Case #{_FRESH_CASE_NUMBER}",
            id_=_make_id("VulnerabilityCase"),
            attributed_to=_VENDOR.id_,
            **{**_example_stamp(), **kwargs},
        )
    if kwargs:
        return as_VulnerabilityCase(
            name=_CASE.name,
            id_=_CASE.id_,
            attributed_to=_CASE.attributed_to,
            **{**_example_stamp(), **kwargs},
        )
    return _CASE


def gen_report() -> as_VulnerabilityReport:
    """
    Create a vulnerability report
    Returns:
        a as_VulnerabilityReport object
    """
    return _REPORT


def _admits_none(annotation: object) -> bool:
    """Whether a field typed *annotation* may hold ``None``."""
    return annotation is None or type(None) in get_args(annotation)


def _strip_published_udpated(obj: as_Base | BaseModel) -> as_Base | BaseModel:
    """Return a copy of *obj* with its ``published``/``updated`` timestamps cleared.

    For a body built outside :func:`_example_scope`, whose timestamps default
    to build time and would churn on each docs build (the submit-report
    tutorial's posted body).  A docs example keeps both: it is built inside
    that scope, so they read :data:`EXAMPLE_TIMESTAMP`, and its proof's
    ``created`` is its ``published`` (:func:`_example_json`).

    This returns a copy rather than clearing the timestamps in place, for two
    independent reasons:

    - Wire objects are frozen by design (`as_Object` sets ``frozen=True``,
      ADR-0074): a wire artifact is evidence of what was sent or received, so
      assignment raises rather than silently rewriting it.
    - The examples are shared module-level singletons (`_REPORT`, `_CASE`,
      the actors), and the example API router serves those same instances.
      Clearing timestamps in place would strip them for every other consumer
      too — the shared-singleton hazard of issue #1328.

    Only the top-level object is stripped; timestamps on inline sub-objects are
    left as they are, and so are fields *derived* from the timestamps —
    `as_VulnerabilityCase.genesis_hash` is computed from ``published``
    (CLP-08-003), so a stripped case renders a hash the reader cannot recompute.

    A timestamp the class requires is kept: ``CaseStatus.published`` cannot
    be ``None`` (CLP-15-010), and ``model_copy`` runs no validation, so
    clearing it would render an example every receiver refuses.
    """
    fields = type(obj).model_fields
    updates: dict[str, None] = {
        name: None
        for name in ("published", "updated")
        if name in fields and _admits_none(fields[name].annotation)
    }
    if not updates:
        return obj
    return obj.model_copy(update=updates)


def _to_json(obj: object, **kwargs: object) -> str:
    """Serialize *obj* to a JSON string, excluding None values and using aliases.

    Serialized as a sender delivers it (``outbox_delivery``): a field typed as a
    parent class dumps its value's *own* fields, so an inline subclass such as a
    ``CaseProposal`` under ``object`` keeps the ``object``/``target`` a receiver
    requires instead of being cut down to the parent's shape.
    """
    kwargs.setdefault("serialize_as_any", True)
    if hasattr(obj, "to_json"):
        return obj.to_json(**kwargs)  # type: ignore[union-attr,no-any-return]
    if isinstance(obj, BaseModel):
        return obj.model_dump_json(
            exclude_none=True,
            by_alias=True,
            **kwargs,  # type: ignore[arg-type]
        )
    raise TypeError(f"obj must be serializable to JSON: {obj}")


def _example_json(obj: as_Base | BaseModel) -> str:
    """*obj* as a docs example shows it: indented JSON, signed if it is sent.

    The object's ``published``/``updated`` are shown as built: inside
    :func:`_example_scope` they read :data:`EXAMPLE_TIMESTAMP`.  An object
    that names an ``actor`` is an activity that actor sends, so it is shown
    as that actor's outbox would seal it: with a proof made by the example's
    own ``actor`` (:func:`vultron.wire.as2.signing.sign_docs_example`,
    SIG-01-001).  The proof's ``created`` is the activity's ``published``,
    the rule the outbox follows (``signing.authored_time``), so the proof
    asserts the time the example says it was sent and the signed bytes are
    the same on every regeneration.  The proof covers the body as shown, so
    a reader can check it against the key the actor's seed gives.  Anything
    else, such as an actor profile or a report, is shown unsigned.
    """
    text = _to_json(obj, indent=2)
    document = json.loads(text)
    if not isinstance(document, dict) or "actor" not in document:
        return text
    signed = signing.sign_docs_example(document)
    return json.dumps(signed, indent=2, ensure_ascii=False)


def json2md(obj: as_Base | BaseModel) -> str:
    """
    Given a Pydantic model, return a markdown-formatted string of the object's JSON.

    The JSON is :func:`_example_json`'s, so an activity carries its actor's
    proof.

    Args:
        obj: a Pydantic model (wire or core)

    Returns:
        a markdown-formatted string of the object's JSON
    """
    return f"```json\n{_example_json(obj)}\n```"


def obj_to_file(obj: as_Base | BaseModel, filename: str) -> None:
    """Write *obj* to *filename* as JSON, in one fixed on-disk form.

    The encoding and the line endings are stated rather than left to the
    locale, so the committed artifact has one on-disk form and the currency
    check's byte comparison means what it says: the examples carry ``—`` and
    ``®``, and a CRLF copy would compare equal through ``Path.read_text`` and
    pass.  ``vultron.metadata.generated_files`` records the same hazard for
    the generate-and-check subpackages; it is not imported here because
    nothing outside ``vultron/metadata/`` depends on that tooling and this
    package is imported by the running app.

    The text is :func:`_example_json`'s, so an activity carries its actor's
    proof.

    Args:
        obj: a Pydantic model (wire or core)
        filename: the file to write to
    """
    text = _example_json(obj)
    with open(filename, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(text)


def print_obj(obj: as_Base | BaseModel) -> None:
    """
    Given an object with a to_json method, print it to stdout.
    Args:
        obj: an object with a to_json method

    Returns:
        None
    """
    print(_to_json(obj, indent=2))


ACTOR_FUNCS = [finder, vendor, coordinator, case_actor]
