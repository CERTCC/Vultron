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

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timezone
from typing import TypedDict, get_args
from unittest.mock import patch

from pydantic import BaseModel

from vultron.core.models._helpers import (
    URN_UUID_PREFIX,
    clock as helpers_clock,
)
from vultron.core.models.activity_ids import derived_object_id
from vultron.core.models.actor import hosted_endpoints
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

    Pass as ``**_example_stamp()`` to an object that would otherwise stamp the
    clock through its ``published``/``updated`` default factories.
    """
    return _ExampleStamp(
        published=EXAMPLE_TIMESTAMP, updated=EXAMPLE_TIMESTAMP
    )


def _make_id(object_type: str) -> str:
    """The example id of *object_type* under the example base URL.

    Derived from a fixed name, not minted (``derived_object_id``, OID-01-004):
    the same object type always carries the same id, so regenerating the
    committed examples rewrites only what the generator changed (#5776).
    """
    derived = derived_object_id(_EXAMPLE_ID_SCOPE, object_type)
    uuid_part = derived.removeprefix(URN_UUID_PREFIX)
    return f"{_EXAMPLE_BASE_URL}{object_type}/{uuid_part}"


class _PinnedClock:
    """A ``datetime`` stand-in whose ``now()`` always reads the fixed moment.

    Stands in for ``_helpers.clock.datetime`` inside :func:`_example_scope`, so
    an object whose ``published``/``updated`` default factory reads the clock
    is stamped with :data:`EXAMPLE_TIMESTAMP` without every builder having to
    pass ``**_example_stamp()``.  Only ``now`` is provided: any other
    attribute a patched path reaches for raises ``AttributeError`` rather than
    returning a wrong time.
    """

    @staticmethod
    def now(tz: timezone | None = None) -> datetime:
        if tz is None:
            return EXAMPLE_TIMESTAMP
        return EXAMPLE_TIMESTAMP.astimezone(tz)


class _ScopedIds:
    """An id source that derives each draw from the example asking for it.

    Stands in for ``uuid.uuid4`` inside :func:`_example_scope`, which is where
    ``new_object_id`` draws its bits, so an object built without an explicit
    ``id_`` still gets a stable one.  The draw is ``uuid5`` of the scope name
    and the draw's position within that scope, so the ids one example carries
    depend on that example alone: adding or regenerating another example moves
    none of them.

    Not thread-safe, and neither is the patch that installs it: the generator
    builds one example at a time, in one thread.
    """

    def __init__(self, scope: str) -> None:
        self._scope = scope
        self._drawn = 0

    def __call__(self) -> uuid.UUID:
        self._drawn += 1
        return uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{_EXAMPLE_ID_SCOPE}/{self._scope}/{self._drawn}",
        )


@contextmanager
def _example_scope(scope: str) -> Iterator[None]:
    """Build one example's objects with derived ids and the fixed clock.

    Two sources made the generator write different bytes on every run: the
    minted object ids, and the wall clock behind every ``published`` and
    ``updated`` default factory.  Inside this block both are replaced, keyed
    on *scope* — the name of the example being written — so that running the
    generator twice over an unchanged tree produces an unchanged tree, and a
    change to one example rewrites only that example's file (#5776).
    """
    with (
        patch.object(uuid, "uuid4", _ScopedIds(scope)),
        patch.object(helpers_clock, "datetime", _PinnedClock),
    ):
        yield


base_url = "https://vultron.example"
user_base_url = f"{base_url}/users"
case_base_url = f"{base_url}/cases"
organization_base_url = f"{base_url}/organizations"
report_base_url = f"{base_url}/reports"

# The shared objects every other example refers to are built once, when this
# module is imported.  The whole block runs inside an ``_example_scope`` so
# that their stamps, and the ids of the objects their constructors create
# inline, are derived rather than drawn: an activity that carries one of them
# shows the values it was built with, and a value that moved between runs
# moved in all 92 committed files at once (#5776).
#
# Each example actor's profile is the one it publishes, so it states its own
# endpoints (``hosted_endpoints``); an activity naming it carries it as held.
with _example_scope("_base"):
    _FINDER = as_Person.model_validate(
        {
            "id": f"{user_base_url}/finndervul",
            "name": "Finn der Vul",
            **hosted_endpoints(f"{user_base_url}/finndervul"),
        }
    )
    _VENDOR = as_Organization.model_validate(
        {
            "id": f"{organization_base_url}/vendorco",
            "name": "VendorCo",
            **hosted_endpoints(f"{organization_base_url}/vendorco"),
        }
    )
    _COORDINATOR = as_Organization.model_validate(
        {
            "id": f"{organization_base_url}/coordinator",
            "name": "Coordinator LLC",
            **hosted_endpoints(f"{organization_base_url}/coordinator"),
        }
    )

    case_actor_base_url = f"{base_url}/case-actors"
    _CASE_ACTOR = as_Service.model_validate(
        {
            "id": f"{case_actor_base_url}/vendorco-case-actor",
            "name": "VendorCo Case Actor",
            **hosted_endpoints(f"{case_actor_base_url}/vendorco-case-actor"),
        }
    )

    # The report and case id are derived by name rather than left to the
    # scope's draw order, so inserting another shared object above moves
    # neither of them.
    _REPORT = as_VulnerabilityReport(
        name="FDR-8675309",
        id_=_make_id("VulnerabilityReport"),
        content="I found a vulnerability!",
        attributed_to=_FINDER.id_,
        **_example_stamp(),
    )
    _CASE = as_VulnerabilityCase(
        name=f"{_VENDOR.name} Case #{case_number}",
        id_=derived_object_id(_EXAMPLE_ID_SCOPE, "shared-VulnerabilityCase"),
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


def case(fresh_id=False, **kwargs) -> as_VulnerabilityCase:
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
            **kwargs,
        )
    if kwargs:
        return as_VulnerabilityCase(
            name=_CASE.name,
            id_=_CASE.id_,
            attributed_to=_CASE.attributed_to,
            **kwargs,
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

    Both timestamps default to build time, so leaving them in would make every
    rendered example churn on each docs build.

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


def json2md(obj: as_Base | BaseModel) -> str:
    """
    Given a Pydantic model, return a markdown-formatted string of the object's JSON.
    Args:
        obj: a Pydantic model (wire or core)

    Returns:
        a markdown-formatted string of the object's JSON
    """
    obj = _strip_published_udpated(obj)
    s = f"```json\n{_to_json(obj, indent=2)}\n```"
    return s


def obj_to_file(obj: as_Base | BaseModel, filename: str) -> None:
    """
    Given a Pydantic model, write it to a file as JSON.
    Args:
        obj: a Pydantic model (wire or core)
        filename: the file to write to

    Returns:
        None
    """
    obj = _strip_published_udpated(obj)

    with open(filename, "w") as fp:
        fp.write(_to_json(obj, indent=2))


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
