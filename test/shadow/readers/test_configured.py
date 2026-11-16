"""The case reader a run's ``shadow:`` settings name (#6366).

With no connector named, the run reads Vultron case-ledger files, confined
to ``ledger_dir``, and never runs the connector loader; a named connector
is the installed plugin of that entry-point name, refused at start when it
is missing or reads no case.

Spec: ARCH-05-003, SHD-01-002.
"""

from collections.abc import Mapping

import pytest

from test.support.case_reader import FakeCaseReader
from vultron.adapters.connectors.base import ConnectorPlugin
from vultron.config.shadow import ShadowConfig
from vultron.errors import CaseLedgerFileError, ShadowConnectorError
from vultron.shadow.readers import VultronCaseReader, configured_case_reader


class _NamedOnly:
    """A plugin with a name and no port."""

    name = "named-only"


def _never() -> Mapping[str, ConnectorPlugin]:
    raise AssertionError("the loader ran with no connector named")


def test_no_connector_reads_vultron_ledgers_without_the_loader(tmp_path):
    reader = configured_case_reader(
        ShadowConfig(ledger_dir=tmp_path), connectors=_never
    )
    assert isinstance(reader, VultronCaseReader)
    with pytest.raises(CaseLedgerFileError, match="outside the ledger"):
        reader.read_case("../elsewhere.jsonl")


@pytest.mark.spec("ARCH-05-003")
def test_a_named_connector_is_the_installed_plugin_of_that_name():
    fake = FakeCaseReader({})
    reader = configured_case_reader(
        ShadowConfig(connector="fake"),
        connectors=lambda: {"fake": fake, "other": FakeCaseReader({})},
    )
    assert reader is fake


def test_a_connector_that_is_not_installed_is_refused_naming_both():
    with pytest.raises(ShadowConnectorError) as caught:
        configured_case_reader(
            ShadowConfig(connector="vince"),
            connectors=lambda: {"fake": FakeCaseReader({})},
        )
    assert caught.value.connector == "vince"
    assert "'vince'" in str(caught.value)
    assert "installed: fake" in str(caught.value)


def test_a_missing_connector_with_none_installed_says_none():
    with pytest.raises(ShadowConnectorError, match=r"installed: none"):
        configured_case_reader(
            ShadowConfig(connector="vince"), connectors=lambda: {}
        )


@pytest.mark.spec("SHD-01-002")
def test_a_connector_that_reads_no_case_is_refused():
    with pytest.raises(ShadowConnectorError, match="implements no CaseReader"):
        configured_case_reader(
            ShadowConfig(connector="named-only"),
            connectors=lambda: {"named-only": _NamedOnly()},
        )


def test_a_blank_connector_name_is_refused_at_load():
    with pytest.raises(ValueError):
        ShadowConfig(connector="  ")
