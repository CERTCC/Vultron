"""The case reader a run's ``shadow:`` settings name (#6366).

With no connector named, the run reads Vultron case-ledger files, confined
to ``ledger_dir``, and never runs the connector loader; a named connector
is the installed plugin of that entry-point name, refused at start when it
is missing or reads no case.

Spec: ARCH-05-003, SHD-01-002.
"""

from collections.abc import Mapping

import pytest
from pydantic import SecretStr

from test.support.case_reader import FakeCaseReader
from vultron.adapters.connectors.base import ConnectorPlugin
from vultron.config.app import AppConfig
from vultron.config.shadow import (
    SHADOW_NODE_ACTOR_ID_ENV_VAR,
    SHADOW_NODE_URL_ENV_VAR,
    ShadowConfig,
)
from vultron.config.vince import VinceConfig
from vultron.errors import (
    CaseLedgerFileError,
    ShadowConnectorError,
    VultronConfigError,
)
from vultron.shadow.readers import (
    CaseSource,
    VultronCaseReader,
    VultronNode,
    VultronNodeCaseReader,
    configured_case_reader,
    outside_connector,
    outside_source_ready,
    typed_node,
)

_OUTSIDE = CaseSource.OUTSIDE
_NODE = CaseSource.NODE
_URL = "http://case-actor:7999/api/v2"
#: A test-only VINCE credential.
_TOKEN = SecretStr("test-only-credential")


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


def test_no_ledger_dir_confines_reads_to_the_start_directory(
    tmp_path, monkeypatch
):
    (tmp_path / "inside").mkdir()
    monkeypatch.chdir(tmp_path / "inside")
    reader = configured_case_reader(ShadowConfig(), connectors=_never)
    with pytest.raises(CaseLedgerFileError, match="outside the ledger"):
        reader.read_case("../outside.jsonl")
    with pytest.raises(CaseLedgerFileError, match="outside the ledger"):
        reader.read_case("/etc/passwd")


@pytest.mark.spec("ARCH-05-003")
def test_a_named_connector_is_the_installed_plugin_of_that_name():
    fake = FakeCaseReader({})
    reader = configured_case_reader(
        ShadowConfig(connector="fake"),
        _OUTSIDE,
        connectors=lambda: {"fake": fake, "other": FakeCaseReader({})},
    )
    assert reader is fake


def test_a_connector_that_is_not_installed_is_refused_naming_both():
    with pytest.raises(ShadowConnectorError) as caught:
        configured_case_reader(
            ShadowConfig(),
            _OUTSIDE,
            connectors=lambda: {"fake": FakeCaseReader({})},
        )
    assert caught.value.connector == "vince"
    assert "'vince'" in str(caught.value)
    assert "installed: fake" in str(caught.value)


def test_a_missing_connector_with_none_installed_says_none():
    with pytest.raises(ShadowConnectorError, match=r"installed: none"):
        configured_case_reader(
            ShadowConfig(connector="vince"), _OUTSIDE, connectors=lambda: {}
        )


@pytest.mark.spec("SHD-01-002")
def test_a_connector_that_reads_no_case_is_refused():
    with pytest.raises(ShadowConnectorError, match="implements no CaseReader"):
        configured_case_reader(
            ShadowConfig(connector="named-only"),
            _OUTSIDE,
            connectors=lambda: {"named-only": _NamedOnly()},
        )


def test_a_blank_connector_name_is_refused_at_load():
    with pytest.raises(ValueError):
        ShadowConfig(connector="  ")


def test_the_node_settings_are_read_from_the_environment(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)  # no config.yaml in the working directory
    monkeypatch.delenv("VULTRON_CONFIG", raising=False)
    monkeypatch.setenv(
        SHADOW_NODE_URL_ENV_VAR, "http://case-actor:7999/api/v2"
    )
    monkeypatch.setenv(SHADOW_NODE_ACTOR_ID_ENV_VAR, "case-actor")
    assert SHADOW_NODE_URL_ENV_VAR == "VULTRON_SHADOW__NODE_URL"
    assert SHADOW_NODE_ACTOR_ID_ENV_VAR == "VULTRON_SHADOW__NODE_ACTOR_ID"
    reader = configured_case_reader(
        AppConfig().shadow, _NODE, connectors=_never
    )
    assert isinstance(reader, VultronNodeCaseReader)
    assert reader.node_url == "http://case-actor:7999/api/v2"


def test_the_chosen_source_is_read_whatever_the_others_are_set_to(
    tmp_path,
):
    fake = FakeCaseReader({})
    config = ShadowConfig(
        connector="fake",
        ledger_dir=tmp_path,
        node_url=_URL,
        node_actor_id="case-actor",
    )
    assert (
        configured_case_reader(
            config, _OUTSIDE, connectors=lambda: {"fake": fake}
        )
        is fake
    )
    assert isinstance(
        configured_case_reader(config, connectors=_never), VultronCaseReader
    )
    assert isinstance(
        configured_case_reader(config, _NODE, connectors=_never),
        VultronNodeCaseReader,
    )


def test_a_typed_node_is_read_in_place_of_the_configured_one():
    config = ShadowConfig(node_url=_URL, node_actor_id="case-actor")
    typed = VultronNode("http://other:7999/api/v2", "other-actor")
    reader = configured_case_reader(
        config, _NODE, node=typed, connectors=_never
    )
    assert isinstance(reader, VultronNodeCaseReader)
    assert reader.node_url == typed.url


def test_the_node_source_with_no_node_is_refused():
    with pytest.raises(VultronConfigError, match="name a Vultron node"):
        configured_case_reader(ShadowConfig(), _NODE, connectors=_never)


@pytest.mark.parametrize(
    "fields",
    [
        {"node_url": "http://case-actor:7999/api/v2"},
        {"node_actor_id": "case-actor"},
    ],
    ids=["url-only", "actor-only"],
)
def test_a_half_set_node_is_refused_before_any_read(fields):
    with pytest.raises(VultronConfigError, match="set both") as caught:
        configured_case_reader(
            ShadowConfig(**fields), _NODE, connectors=_never
        )
    assert SHADOW_NODE_URL_ENV_VAR in str(caught.value)
    assert SHADOW_NODE_ACTOR_ID_ENV_VAR in str(caught.value)


def test_a_node_url_without_an_http_scheme_is_refused_at_load():
    with pytest.raises(ValueError, match="http:// or https://"):
        ShadowConfig(node_url="case-actor:7999", node_actor_id="case-actor")


@pytest.mark.parametrize("actor_id", ["/", "urn:uuid:", ".", "a?b"])
def test_an_actor_id_that_names_no_actor_is_refused_as_configuration(actor_id):
    """The page shows a configuration error, never a traceback."""
    with pytest.raises(VultronConfigError) as caught:
        configured_case_reader(
            ShadowConfig(
                node_url="http://case-actor:7999/api/v2",
                node_actor_id=actor_id,
            ),
            _NODE,
            connectors=_never,
        )
    assert SHADOW_NODE_ACTOR_ID_ENV_VAR in str(caught.value)


@pytest.mark.parametrize(
    "url",
    [
        "http://user:secret@case-actor:7999/api/v2",
        "http://case-actor:7999/api/v2?token=x",
        "http://case-actor:7999/api/v2#frag",
        "http://case-actor:7999/api/v2?",
        "http://case-actor:7999/api/v2#",
    ],
    ids=[
        "userinfo",
        "query",
        "fragment",
        "bare-query-mark",
        "bare-fragment-mark",
    ],
)
def test_a_node_url_with_more_than_its_api_root_is_refused_at_load(url):
    with pytest.raises(ValueError, match="only the node's API root") as caught:
        ShadowConfig(node_url=url, node_actor_id="case-actor")
    assert "secret" not in str(caught.value)


def test_the_outside_source_is_vince_unless_a_connector_is_named():
    assert outside_connector(ShadowConfig()) == "vince"
    assert outside_connector(ShadowConfig(connector="fake")) == "fake"


def test_the_vince_default_is_the_installed_vince_entry_point():
    from importlib.metadata import entry_points

    names = {ep.name for ep in entry_points(group="vultron.connectors")}
    assert outside_connector(ShadowConfig()) in names


@pytest.mark.spec("SHD-02-003")
@pytest.mark.parametrize(
    ("vince", "ready"),
    [
        (VinceConfig(), False),
        (VinceConfig(base_url="https://vince.test/api"), False),
        (VinceConfig(api_token=_TOKEN), False),
        (
            VinceConfig(base_url="https://vince.test/api", api_token=_TOKEN),
            True,
        ),
    ],
    ids=["neither", "url-only", "token-only", "both"],
)
def test_vince_can_be_chosen_only_with_its_url_and_credential(vince, ready):
    assert outside_source_ready(ShadowConfig(), vince) is ready


def test_another_connector_can_always_be_chosen():
    assert outside_source_ready(ShadowConfig(connector="fake"), VinceConfig())


def test_a_typed_node_is_checked_and_trimmed():
    assert typed_node(f"  {_URL} ", " case-actor ") == VultronNode(
        _URL, "case-actor"
    )


@pytest.mark.parametrize(
    ("url", "actor_id", "reason"),
    [
        ("", "", "enter both"),
        (_URL, "  ", "enter both"),
        ("", "case-actor", "enter both"),
        ("case-actor:7999", "case-actor", "http:// or https://"),
        ("http://user:secret@case-actor/api", "case-actor", "API root"),
        (_URL + "?token=secret", "case-actor", "API root"),
        (_URL, "acct?token=secret", "names no actor"),
    ],
    ids=[
        "blank",
        "blank-actor",
        "blank-url",
        "no-scheme",
        "userinfo",
        "query",
        "bad-actor",
    ],
)
def test_a_typed_node_the_settings_rules_refuse_is_refused(
    url, actor_id, reason
):
    """AC-4: the same rules as ``ShadowConfig.node_url``, never echoed."""
    with pytest.raises(VultronConfigError, match=reason) as caught:
        typed_node(url, actor_id)
    assert "secret" not in str(caught.value)
