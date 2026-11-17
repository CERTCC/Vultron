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
"""An actor request survives FastAPI losing its warning suppression (#6039).

FastAPI builds a ``ModelField`` for each route and override parameter, lazily on
the first request, on the ``TestClient`` portal thread.  Its ``TypeAdapter``
makes pydantic warn (``UnsupportedFieldAttributeWarning``) about the alias
FastAPI sets on every parameter.  FastAPI hides that warning inside
``warnings.catch_warnings()``, which on this interpreter edits the
process-global filter list.  When two portal threads do this at once, one
thread's exit drops the other's ``ignore`` entry, so ``filterwarnings =
["error"]`` used to turn the warning into a failed in-process delivery.

The race cannot be scheduled, so these tests take FastAPI's suppression away,
which is the state the losing thread is in, and run under the project's own
``filterwarnings``.  The narrow ``ignore`` entry in ``pyproject.toml`` is what
lets the request succeed; without it these tests fail with the warning.
"""

import re
import tomllib
import warnings
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated

import fastapi._compat.v2 as fastapi_v2
import pytest
from fastapi.testclient import TestClient
from pydantic import Field, TypeAdapter
from pydantic.fields import FieldInfo
from pydantic.warnings import UnsupportedFieldAttributeWarning

from vultron.adapters.driving.fastapi.app import create_app
from vultron.demo.in_process import InProcessRouter, create_isolated_actor_app

_ALIAS_IGNORE_PREFIX = "ignore:"
_ALIAS_IGNORE_SUFFIX = ":pydantic.warnings.UnsupportedFieldAttributeWarning"


def _alias_ignore_message() -> str:
    """The message regex of the project's alias ``ignore`` entry."""
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    entries = config["tool"]["pytest"]["ini_options"]["filterwarnings"]
    (entry,) = [
        e
        for e in entries
        if e.startswith(_ALIAS_IGNORE_PREFIX)
        and e.endswith(_ALIAS_IGNORE_SUFFIX)
    ]
    return entry[len(_ALIAS_IGNORE_PREFIX) : -len(_ALIAS_IGNORE_SUFFIX)]


@pytest.fixture
def fastapi_suppression_lost(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make FastAPI's own ``ignore`` of the warning a no-op, as the race does."""
    monkeypatch.setattr(
        fastapi_v2,
        "warnings",
        SimpleNamespace(
            **{
                **vars(warnings),
                "catch_warnings": nullcontext,
                "simplefilter": lambda *args, **kwargs: None,
            }
        ),
    )


@contextmanager
def _isolated_actor_client() -> Iterator[TestClient]:
    iso = create_isolated_actor_app(
        "http://warning-node.test", InProcessRouter(), actor_slug="vendor"
    )
    try:
        with iso.client as client:
            yield client
    finally:
        iso.close()


@contextmanager
def _create_app_client() -> Iterator[TestClient]:
    with TestClient(create_app(docs_url=None, openapi_url=None)) as client:
        yield client


@pytest.mark.usefixtures("fastapi_suppression_lost")
def test_fixture_exposes_fastapis_alias_warning() -> None:
    """Without FastAPI's ``ignore``, building a field emits the alias warning.

    Guards the tests below: if FastAPI moves its suppression, the fixture
    stops removing it and they would pass with or without the entry.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fastapi_v2.ModelField(
            field_info=FieldInfo(annotation=str, alias="actor_id"),
            name="actor_id",
        )

    assert any(
        issubclass(w.category, UnsupportedFieldAttributeWarning)
        and re.match(_alias_ignore_message(), str(w.message), re.IGNORECASE)
        for w in caught
    )


def test_other_unsupported_field_attributes_still_raise() -> None:
    """The ``ignore`` entry covers only the alias message, not its category."""
    with pytest.raises(
        UnsupportedFieldAttributeWarning, match="validation_alias"
    ):
        TypeAdapter(Annotated[int, Field(validation_alias="b")])


@pytest.mark.usefixtures("fastapi_suppression_lost")
@pytest.mark.parametrize(
    "client_factory",
    [_isolated_actor_client, _create_app_client],
    ids=["create_isolated_actor_app", "create_app"],
)
def test_actor_route_passes_under_project_filters_without_fastapis_suppression(
    client_factory: Callable[[], AbstractContextManager[TestClient]],
) -> None:
    """An actor-scoped request succeeds though FastAPI's ``ignore`` is gone."""
    with client_factory() as client:
        resp = client.post(
            "/api/v2/actors/", json={"name": "Vendor", "id": "vendor"}
        )
        assert resp.status_code == 201

        resp = client.get("/api/v2/actors/vendor")

        assert resp.status_code == 200
