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
"""The one minter draws from the installed id source (OID-01-011, ADR-0185)."""

import uuid

import pytest

from vultron.core.models._helpers import (
    URN_UUID_PREFIX,
    IdSource,
    install_id_source,
    new_object_id,
    system_id_source,
)
from vultron.core.models.base import CoreRecord
from vultron.errors import VultronIdSourceInstalledError, VultronWiringError
from vultron.wire.as2.vocab.base.objects.base import as_Object


class _CountingSource:
    """An id source that returns version-4 UUIDs 1, 2, 3, ... and counts."""

    def __init__(self) -> None:
        self.drawn = 0

    def __call__(self) -> uuid.UUID:
        self.drawn += 1
        return uuid.UUID(int=self.drawn, version=4)

    def id_of(self, draw: int) -> str:
        return f"{URN_UUID_PREFIX}{uuid.UUID(int=draw, version=4)}"


class _Record(CoreRecord):
    """A core record with no ``type_`` of its own, so it registers nowhere."""


class _Boom(Exception):
    pass


@pytest.fixture
def counting() -> _CountingSource:
    return _CountingSource()


@pytest.mark.spec("OID-01-011")
def test_the_counting_source_is_an_id_source(counting):
    source: IdSource = counting
    assert isinstance(source(), uuid.UUID)


@pytest.mark.spec("OID-01-011")
def test_the_system_source_draws_distinct_version_4_uuids():
    first, second = system_id_source(), system_id_source()
    assert first.version == 4 and second.version == 4
    assert first != second


@pytest.mark.spec("OID-01-011")
def test_the_minter_draws_from_the_installed_source(counting):
    with install_id_source(counting):
        assert new_object_id() == counting.id_of(1)
        assert new_object_id("https://example.org/x") == (
            f"https://example.org/x/{uuid.UUID(int=2, version=4)}"
        )
    assert counting.drawn == 2


@pytest.mark.spec("OID-01-011")
def test_both_id_default_factories_draw_from_the_installed_source(counting):
    with install_id_source(counting):
        record = _Record()
        wire = as_Object()
    assert record.id_ == counting.id_of(1)
    assert wire.id_ == counting.id_of(2)
    assert counting.drawn == 2


@pytest.mark.spec("OID-01-011")
def test_the_install_yields_its_source(counting):
    with install_id_source(counting) as installed:
        assert installed is counting


@pytest.mark.spec("OID-01-011")
def test_the_install_restores_the_previous_source_on_exit(counting):
    with install_id_source(counting):
        new_object_id()
    new_object_id()
    assert counting.drawn == 1
    # The slot is free again: a later install succeeds.
    with install_id_source(_CountingSource()):
        pass


@pytest.mark.spec("OID-01-011")
def test_the_install_restores_the_previous_source_when_the_block_raises(
    counting,
):
    with pytest.raises(_Boom), install_id_source(counting):
        raise _Boom
    new_object_id()
    assert counting.drawn == 0
    with install_id_source(_CountingSource()):
        pass


@pytest.mark.spec("OID-01-011")
def test_a_nested_install_fails_and_leaves_the_outer_install_in_place(
    counting,
):
    inner = _CountingSource()
    with install_id_source(counting):
        with pytest.raises(VultronIdSourceInstalledError):
            with install_id_source(inner):
                pass  # pragma: no cover - the install refuses to enter
        assert new_object_id() == counting.id_of(1)
    assert inner.drawn == 0
    new_object_id()
    assert counting.drawn == 1


def test_a_nested_install_is_a_composition_fault():
    assert issubclass(VultronIdSourceInstalledError, VultronWiringError)
