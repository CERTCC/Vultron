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
from typing import Any, cast
from uuid import uuid4

from vultron.adapters.driven.db_record import object_to_record
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import DataLayer
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Organization,
    as_Person,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
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

_REPORT = VulnerabilityReport(
    name="FDR-8675309",
    id_=_make_id("VulnerabilityReport"),
    content="I found a vulnerability!",
    attributed_to=[
        _FINDER.id_,
    ],
)
_CASE = VulnerabilityCase(
    name=f"{_VENDOR.name} Case #{case_number}",
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


def case(random_id=False) -> VulnerabilityCase:
    if random_id:
        _case_number = random.randint(10000000, 99999999)
        _case = VulnerabilityCase(
            name=f"{_VENDOR.name} Case #{_case_number}",
            id_=_make_id("VulnerabilityCase"),
        )
        return _case
    return _CASE


def gen_report() -> VulnerabilityReport:
    """
    Create a vulnerability report
    Returns:
        a VulnerabilityReport object
    """
    return _REPORT


def initialize_examples(datalayer: DataLayer) -> None:
    for obj in [_FINDER, _VENDOR, _COORDINATOR, _REPORT]:
        if obj.type_ is None:
            raise ValueError(f"Example object missing type_: {obj}")
        datalayer.create(object_to_record(cast(PersistableModel, obj)))


def _strip_published_udpated(obj: as_Base) -> as_Base:
    # strip out published and updated timestamps if they are present
    if hasattr(obj, "published"):
        cast(Any, obj).published = None
    if hasattr(obj, "updated"):
        cast(Any, obj).updated = None
    return obj


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


ACTOR_FUNCS = [finder, vendor, coordinator]
