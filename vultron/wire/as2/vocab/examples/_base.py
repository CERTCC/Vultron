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

import random
from uuid import uuid4

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


def _make_id(object_type: str) -> str:
    return f"{_EXAMPLE_BASE_URL}{object_type}/{uuid4()}"


base_url = "https://vultron.example"
user_base_url = f"{base_url}/users"
case_base_url = f"{base_url}/cases"
organization_base_url = f"{base_url}/organizations"
report_base_url = f"{base_url}/reports"

# generated once per run so all examples in a single run share the same case number
case_number = random.randint(10000000, 99999999)

_FINDER = as_Person(name="Finn der Vul", id_=f"{user_base_url}/finndervul")
_VENDOR = as_Organization(
    name="VendorCo", id_=f"{organization_base_url}/vendorco"
)
_COORDINATOR = as_Organization(
    name="Coordinator LLC", id_=f"{organization_base_url}/coordinator"
)

case_actor_base_url = f"{base_url}/case-actors"
_CASE_ACTOR = as_Service(
    name="VendorCo Case Actor",
    id_=f"{case_actor_base_url}/vendorco-case-actor",
)

_REPORT = as_VulnerabilityReport(
    name="FDR-8675309",
    id_=_make_id("VulnerabilityReport"),
    content="I found a vulnerability!",
    attributed_to=[
        _FINDER.id_,
    ],
)
_CASE = as_VulnerabilityCase(
    name=f"{_VENDOR.name} Case #{case_number}",
    attributed_to=_VENDOR.id_,
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


def case(random_id=False, **kwargs) -> as_VulnerabilityCase:
    """The example case, optionally with extra fields populated.

    With no arguments this returns the shared `_CASE` singleton, whose id every
    other case-related example refers to. Any ``kwargs`` are applied on top of
    that same identity — id, name and attributor are preserved, so a populated
    case and the participants built against `case()` still agree on which case
    they belong to. Pass ``random_id=True`` for a case with a fresh id instead.
    """
    if random_id:
        _case_number = random.randint(10000000, 99999999)
        _case = as_VulnerabilityCase(
            name=f"{_VENDOR.name} Case #{_case_number}",
            id_=_make_id("VulnerabilityCase"),
            attributed_to=_VENDOR.id_,
            **kwargs,
        )
        return _case
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


def _strip_published_udpated(obj: as_Base) -> as_Base:
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
    """
    fields = type(obj).model_fields
    updates: dict[str, None] = {
        name: None for name in ("published", "updated") if name in fields
    }
    if not updates:
        return obj
    return obj.model_copy(update=updates)


def json2md(obj: as_Base) -> str:
    """
    Given an object with a to_json method, return a markdown-formatted string of the object's JSON.
    Args:
        obj: an object with a to_json method

    Returns:
        a markdown-formatted string of the object's JSON
    """
    obj = _strip_published_udpated(obj)

    if not hasattr(obj, "to_json"):
        raise TypeError(f"obj must have a to_json method: {obj}")

    s = f"```json\n{obj.to_json(indent=2)}\n```"
    return s


def obj_to_file(obj: as_Base, filename: str) -> None:
    """
    Given an object with a to_json method, write it to a file.
    Args:
        obj: an object with a to_json method
        filename: the file to write to

    Returns:
        None
    """
    obj = _strip_published_udpated(obj)

    if not hasattr(obj, "to_json"):
        raise TypeError(f"obj must have a to_json method: {obj}")

    with open(filename, "w") as fp:
        fp.write(obj.to_json(indent=2))


def print_obj(obj: as_Base) -> None:
    """
    Given an object with a to_json method, print it to stdout.
    Args:
        obj: an object with a to_json method

    Returns:
        None
    """
    print(obj.to_json(indent=2))


ACTOR_FUNCS = [finder, vendor, coordinator, case_actor]
