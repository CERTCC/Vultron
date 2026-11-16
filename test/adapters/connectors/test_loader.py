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


"""The connector loader finds installed plugins and refuses bad ones (#5610).

Each test installs a fake distribution on ``sys.path``: a ``.dist-info``
directory whose ``entry_points.txt`` declares entry points in the
``vultron.connectors`` group, beside a module holding the plugins they
name.  The loader then finds them through :mod:`importlib.metadata`, as it
finds a real installed connector.

Spec: ARCH-05-003, ARCH-05-006.
"""

from __future__ import annotations

import sys
import textwrap
from collections.abc import Callable, Mapping
from importlib.metadata import EntryPoint
from pathlib import Path
from uuid import uuid4

import pytest

from vultron.adapters.connectors.base import ports_implemented_by
from vultron.adapters.connectors.example.vince import VinceCaseReader
from vultron.adapters.connectors.loader import (
    ENTRY_POINT_GROUP,
    ConnectorRefusedError,
    load_connectors,
)
from vultron.core.ports.case_reader import CaseReader
from vultron.errors import VultronConfigError

_VINCE = "vultron.adapters.connectors.example.vince:VinceCaseReader"

#: The plugins the fake distribution's module holds, good and bad.
_PLUGIN_SOURCE = textwrap.dedent(
    """
    from test.support.case_reader import FakeCaseReader


    class Reader(FakeCaseReader):
        name = "installed-reader"

        def __init__(self):
            super().__init__({})


    class NoName:
        unobservable = ()

        def read_case(self, case_id):
            raise NotImplementedError


    class BlankName(Reader):
        name = "  "


    class NameOnly:
        name = "name-only"


    class NeedsArguments(Reader):
        def __init__(self, url):
            super().__init__()
    """
)

Install = Callable[[Mapping[str, str]], str]


@pytest.fixture
def install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Install:
    """Install a fake distribution declaring *entries* (name to target).

    A target ``:Class`` names a class in the distribution's own module.
    Returns the distribution's name, which each refusal names.
    """

    def _install(entries: Mapping[str, str]) -> str:
        module = f"fake_connectors_{uuid4().hex}"
        (tmp_path / f"{module}.py").write_text(_PLUGIN_SOURCE)
        dist_info = tmp_path / f"{module}-1.0.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {module}\nVersion: 1.0\n"
        )
        lines = [f"[{ENTRY_POINT_GROUP}]"] + [
            f"{name} = {module}{target}"
            if target.startswith(":")
            else f"{name} = {target}"
            for name, target in entries.items()
        ]
        (dist_info / "entry_points.txt").write_text("\n".join(lines) + "\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        monkeypatch.delitem(sys.modules, module, raising=False)
        return module

    return _install


def _refused(
    excinfo: pytest.ExceptionInfo[ConnectorRefusedError],
) -> dict[str, str]:
    """Each refused entry point's name, mapped to its reason."""
    return {
        r.entry_point.split(" = ")[0]: r.reason for r in excinfo.value.refusals
    }


@pytest.mark.spec("ARCH-05-003")
def test_the_loader_discovers_an_installed_entry_point(install: Install):
    install({"installed": ":Reader", "vince": _VINCE})

    plugins = load_connectors()

    assert plugins["installed"].name == "installed-reader"
    assert ports_implemented_by(plugins["installed"]) == (CaseReader,)
    assert isinstance(plugins["vince"], VinceCaseReader)


@pytest.mark.spec("ARCH-05-003")
def test_the_example_connectors_declare_no_entry_point():
    assert load_connectors() == {}


def test_no_entry_points_load_no_connectors():
    assert load_connectors([]) == {}


@pytest.mark.spec("ARCH-05-006")
def test_an_entry_point_that_is_not_a_connector_plugin_is_refused_by_name(
    install: Install,
):
    dist = install({"nameless": ":NoName", "blank": ":BlankName"})

    with pytest.raises(ConnectorRefusedError) as excinfo:
        load_connectors()

    refused = _refused(excinfo)
    assert set(refused) == {"nameless", "blank"}
    assert all("not a connector plugin" in r for r in refused.values())
    message = str(excinfo.value)
    assert "nameless" in message and "blank" in message and dist in message


@pytest.mark.spec("ARCH-05-006")
def test_an_entry_point_implementing_no_core_port_is_refused_by_name(
    install: Install,
):
    dist = install({"portless": ":NameOnly"})

    with pytest.raises(ConnectorRefusedError) as excinfo:
        load_connectors()

    assert set(_refused(excinfo)) == {"portless"}
    assert "implements no core port" in _refused(excinfo)["portless"]
    assert "portless" in str(excinfo.value)
    assert dist in str(excinfo.value)


@pytest.mark.spec("ARCH-05-006")
def test_one_refusal_refuses_the_whole_load_and_names_every_bad_entry(
    install: Install,
):
    install(
        {
            "good": ":Reader",
            "portless": ":NameOnly",
            "missing": ":NoSuchClass",
            "needs-args": ":NeedsArguments",
        }
    )

    with pytest.raises(ConnectorRefusedError) as excinfo:
        load_connectors()

    refused = _refused(excinfo)
    assert set(refused) == {"portless", "missing", "needs-args"}
    assert "AttributeError" in refused["missing"]
    assert "TypeError" in refused["needs-args"]


def test_an_entry_point_whose_module_is_missing_is_refused_by_name():
    entry = EntryPoint(
        name="ghost",
        value="no_such_module_5610:Reader",
        group=ENTRY_POINT_GROUP,
    )

    with pytest.raises(ConnectorRefusedError) as excinfo:
        load_connectors([entry])

    assert set(_refused(excinfo)) == {"ghost"}
    assert "ModuleNotFoundError" in _refused(excinfo)["ghost"]


def test_two_entry_points_sharing_a_name_are_both_refused():
    entries = [
        EntryPoint(name="vince", value=_VINCE, group=ENTRY_POINT_GROUP),
        EntryPoint(name="vince", value=_VINCE, group=ENTRY_POINT_GROUP),
    ]

    with pytest.raises(ConnectorRefusedError) as excinfo:
        load_connectors(entries)

    assert [r.entry_point.split(" = ")[0] for r in excinfo.value.refusals] == [
        "vince",
        "vince",
    ]
    assert all("shares the name" in r.reason for r in excinfo.value.refusals)


def test_a_refused_load_is_a_configuration_fault():
    entry = EntryPoint(
        name="ghost",
        value="no_such_module_5610:Reader",
        group=ENTRY_POINT_GROUP,
    )

    with pytest.raises(VultronConfigError):
        load_connectors([entry])
