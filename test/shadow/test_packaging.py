"""The case shadow tool's packaging: its Compose service, image and imports.

The ``shadow`` service publishes its page on loopback only and names the
outside system's settings without a value; its image runs ``vultron-shadow``,
which turns Streamlit's usage statistics off; Streamlit stays inside the
shadow package; and nothing the tool imports can deliver an activity.

The service and its image declare no volume, so the container has nowhere
persistent to write a case.

Spec: SHD-01-001, SHD-02-001, SHD-02-002, SHD-02-003, SHD-02-004.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner
from streamlit import config as st_config, net_util
from streamlit.web import bootstrap

from test.support.child_env import child_env
from vultron.config.shadow import (
    SHADOW_NODE_ACTOR_ID_ENV_VAR,
    SHADOW_NODE_URL_ENV_VAR,
)
from vultron.config.vince import VINCE_API_TOKEN_ENV_VAR
from vultron.metadata.base import repo_root
from vultron.shadow.dashboard import cli
from vultron.shadow.dashboard.cli import DEFAULT_PORT, streamlit_args

_REPO = repo_root()
_COMPOSE = _REPO / "docker" / "docker-compose.yml"
_DEMO_COMPOSE = _REPO / "docker" / "docker-compose-multi-actor.yml"
_DOCKERFILE = _REPO / "docker" / "Dockerfile"
_SHADOW = _REPO / "vultron" / "shadow"

#: Every interface inside the container.  The host side of the port is
#: loopback only (SHD-02-002), so this binding reaches no other machine.
_IN_CONTAINER = "0.0.0.0"  # noqa: S104


def _service() -> dict[str, Any]:
    services = yaml.safe_load(_COMPOSE.read_text())["services"]
    service: dict[str, Any] = services["shadow"]
    return service


def _ports() -> list[str]:
    return [str(port) for port in _service().get("ports", [])]


@pytest.mark.spec("SHD-02-002")
def test_the_service_publishes_its_port_on_loopback_only():
    ports = _ports()
    assert ports
    for port in ports:
        host_ip, _, rest = port.partition(":")
        assert host_ip == "127.0.0.1", port
        assert rest
    assert "network_mode" not in _service()


def test_the_service_publishes_the_port_the_page_listens_on():
    (port,) = _ports()
    assert port.endswith(f":{DEFAULT_PORT}")
    assert _service()["build"]["target"] == "shadow"


@pytest.mark.spec("SHD-02-003")
def test_the_service_names_the_credential_with_no_value():
    """The credential is passed through by name, never written here."""
    environment = _service()["environment"]
    assert VINCE_API_TOKEN_ENV_VAR in environment
    for item in environment:
        name, sep, value = str(item).partition("=")
        if name == VINCE_API_TOKEN_ENV_VAR:
            assert not sep and not value, item
    assert not re.search(
        rf"{VINCE_API_TOKEN_ENV_VAR}\s*[:=]", _COMPOSE.read_text()
    )


def test_the_service_names_the_demo_node_settings_with_no_value():
    """The node to follow is the shell's to set, by name (#6531)."""
    environment = [str(item) for item in _service()["environment"]]
    for name in (SHADOW_NODE_URL_ENV_VAR, SHADOW_NODE_ACTOR_ID_ENV_VAR):
        assert name in environment


def test_the_service_is_on_the_demo_nodes_network():
    """It reaches a demo node by service name, on the nodes' own network."""
    demo = yaml.safe_load(_DEMO_COMPOSE.read_text())
    assert demo["services"]["case-actor"]["networks"] == ["vultron-network"]
    assert _service()["networks"] == ["vultron-network"]
    assert "vultron-network" in demo["networks"]


def _shadow_stage() -> list[str]:
    lines = _DOCKERFILE.read_text().splitlines()
    start = lines.index("FROM dependencies AS shadow")
    stage = []
    for line in lines[start + 1 :]:
        if line.startswith("FROM "):
            break
        stage.append(line)
    return stage


@pytest.mark.spec("SHD-02-001")
def test_the_service_declares_no_volume():
    assert "volumes" not in _service()
    assert "volumes_from" not in _service()


def test_the_volume_check_reads_a_service_that_has_volumes():
    """The check above reads a key Compose uses: another service has it."""
    services = yaml.safe_load(_COMPOSE.read_text())["services"]
    assert any("volumes" in service for service in services.values())


#: A ``FROM`` line: optional flags such as ``--platform``, the image or
#: stage it builds on, and an optional ``AS`` name.
_FROM = re.compile(
    r"FROM\s+(?:--\S+\s+)*(?P<parent>\S+)(?:\s+AS\s+(?P<name>\S+))?\s*$",
    re.IGNORECASE,
)


def _instructions(text: str) -> list[str]:
    """The Dockerfile's instructions, a ``\\``-continued one as one line."""
    joined = re.sub(r"\\\n", " ", text)
    return [
        line.strip()
        for line in joined.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _stage_ancestry(text: str, stage: str) -> list[list[str]]:
    """The instructions of *stage* and of every stage it is built ``FROM``.

    A stage with no ``AS`` name is kept under its index, as Docker numbers
    it, so its instructions never fall into the stage before it.
    """
    stages: dict[str, tuple[str, list[str]]] = {}
    current: list[str] = []
    for line in _instructions(text):
        match = _FROM.match(line)
        if match:
            current = []
            name = match.group("name") or str(len(stages))
            stages[name] = (match.group("parent"), current)
        else:
            current.append(line)
    chain = []
    while stage in stages:
        parent, lines = stages[stage]
        chain.append(lines)
        stage = parent
    return chain


def _volumes(text: str, stage: str) -> list[str]:
    return [
        line
        for lines in _stage_ancestry(text, stage)
        for line in lines
        if line.upper().startswith("VOLUME")
    ]


@pytest.mark.spec("SHD-02-001")
def test_the_image_declares_no_volume():
    text = _DOCKERFILE.read_text()
    chain = _stage_ancestry(text, "shadow")
    assert len(chain) > 1, "the shadow stage builds on the dependency stages"
    assert _volumes(text, "shadow") == []


def test_the_volume_scan_finds_a_volume_in_a_parent_stage():
    """The scan above would find one: in a parent, flagged, continued."""
    text = (
        "FROM --platform=linux/amd64 python:3.14-slim AS base\n"
        "# VOLUME in a comment is no volume\n"
        "VOLUME \\\n  /data\n"
        "FROM busybox\n"
        "VOLUME /unnamed\n"
        "FROM base AS shadow\n"
        'CMD ["run"]\n'
    )
    assert _volumes(text, "shadow") == ["VOLUME    /data"]


def test_the_image_runs_the_page_on_every_interface_in_the_container():
    (cmd,) = [line for line in _shadow_stage() if line.startswith("CMD ")]
    assert json.loads(cmd.removeprefix("CMD ")) == [
        "vultron-shadow",
        "--address",
        _IN_CONTAINER,
        "--port",
        str(DEFAULT_PORT),
    ]


@pytest.mark.spec("SHD-02-003")
def test_the_image_takes_no_credential_at_build():
    for line in _shadow_stage():
        assert not line.startswith(("ARG ", "ENV ")), line
    assert VINCE_API_TOKEN_ENV_VAR not in _DOCKERFILE.read_text()


@pytest.mark.spec("SHD-01-001")
def test_the_launcher_turns_streamlit_usage_statistics_off():
    """Usage statistics are a request to a host the tool does not read."""
    args = streamlit_args("127.0.0.1", DEFAULT_PORT)
    assert args[:2] == ["run", str(_SHADOW / "dashboard" / "app.py")]
    settings = dict(zip(args[2::2], args[3::2], strict=True))
    assert settings == {
        "--server.address": "127.0.0.1",
        "--server.port": str(DEFAULT_PORT),
        "--server.headless": "true",
        "--server.fileWatcherType": "none",
        "--browser.gatherUsageStats": "false",
        "--browser.serverAddress": "127.0.0.1",
        "--logger.hideWelcomeMessage": "true",
        "--logger.enableRich": "false",
        "--global.developmentMode": "false",
    }


@pytest.mark.spec("SHD-01-001")
def test_a_start_on_every_interface_looks_up_no_address(monkeypatch):
    """A headless start's welcome message looks up the host's external IP
    at checkip.amazonaws.com; the launcher's settings skip it."""
    args = streamlit_args(_IN_CONTAINER, DEFAULT_PORT)
    settings = dict(zip(args[2::2], args[3::2], strict=True))
    lookups: list[str] = []
    monkeypatch.setattr(
        net_util, "get_external_ip", lambda: lookups.append("external")
    )
    monkeypatch.setattr(
        net_util, "get_internal_ip", lambda: lookups.append("internal")
    )
    saved = {
        key: st_config.get_option(key.removeprefix("--")) for key in settings
    }
    try:
        for key, value in settings.items():
            st_config.set_option(
                key.removeprefix("--"),
                {"true": True, "false": False}.get(value, value),
            )
        bootstrap._print_url(is_running_hello=False)
    finally:
        for key, value in saved.items():
            st_config.set_option(key.removeprefix("--"), value)
    assert lookups == []


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif (
            isinstance(node, ast.ImportFrom) and node.module and not node.level
        ):
            names.add(node.module)
    return names


@pytest.mark.spec("SHD-02-004")
def test_no_module_outside_the_shadow_package_imports_streamlit():
    importers = sorted(
        str(path.relative_to(_REPO))
        for path in (_REPO / "vultron").rglob("*.py")
        if not path.is_relative_to(_SHADOW)
        and any(
            name == "streamlit" or name.startswith("streamlit.")
            for name in _imports(path)
        )
    )
    assert importers == []


def test_the_scan_sees_the_shadow_packages_own_streamlit_import():
    """The scan above would find an import: the page's own is found."""
    assert "streamlit" in _imports(_SHADOW / "dashboard" / "page" / "frame.py")


def test_no_view_module_imports_streamlit():
    """What the page shows is worked out with no Streamlit call, so it is
    tested without a browser; only the page lays it out."""
    view_modules = sorted((_SHADOW / "dashboard" / "view").glob("*.py"))
    assert view_modules
    importers = [
        path.name
        for path in view_modules
        if any(
            name == "streamlit" or name.startswith("streamlit.")
            for name in _imports(path)
        )
    ]
    assert importers == []


#: Module prefixes that can deliver an activity: every adapter but the
#: connectors (the outbox, its drain and the HTTP delivery adapters), and
#: the activity emitter port.  Core behavior-tree emit nodes only queue an
#: activity in a DataLayer's outbox; the tool builds no DataLayer, and
#: nothing it imports drains an outbox.
_DELIVERY = re.compile(
    r"^vultron\.(adapters\.(?!connectors(\.|$))|core\.ports\.emitter$)"
)

_IMPORT_DRIVER = """
import importlib, json, sys
for name in sys.argv[1:]:
    importlib.import_module(name)
print(json.dumps(sorted(m for m in sys.modules if m.startswith("vultron"))))
"""


@pytest.mark.spec("SHD-01-001")
def test_nothing_the_tool_imports_can_deliver_an_activity():
    entry_points = [
        "vultron.shadow.dashboard.app",
        "vultron.shadow.dashboard.cli",
    ]
    result = subprocess.run(
        [sys.executable, "-c", _IMPORT_DRIVER, *entry_points],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO,
        env=child_env(),
        timeout=120,
    )
    loaded = json.loads(result.stdout)
    assert "vultron.shadow.dashboard.page" in loaded
    # The live reader's HTTP client is among what the scan covers.
    assert "vultron.shadow.readers.vultron_node" in loaded
    assert [name for name in loaded if _DELIVERY.match(name)] == []


def test_the_delivery_pattern_names_the_delivery_modules():
    for name in (
        "vultron.adapters.driven.http_delivery",
        "vultron.adapters.driving.fastapi.outbox_handler.drain",
        "vultron.adapters.outbox_sealed_body",
        "vultron.core.ports.emitter",
    ):
        assert _DELIVERY.match(name), name
    for name in (
        "vultron.adapters.connectors.loader",
        "vultron.adapters.connectors",
        "vultron.core.ports.case_reader",
    ):
        assert not _DELIVERY.match(name), name


def test_the_launcher_hands_streamlit_its_command_line(monkeypatch):
    seen: list[tuple[list[str], str]] = []

    def fake_main(*, args: list[str], prog_name: str) -> None:
        seen.append((args, prog_name))

    monkeypatch.setattr(cli.streamlit_cli, "main", fake_main)
    result = CliRunner().invoke(cli.main, ["--port", "8600"])
    assert result.exit_code == 0, result.output
    assert seen == [(streamlit_args("127.0.0.1", 8600), "streamlit")]


def test_the_launcher_refuses_a_port_out_of_range():
    result = CliRunner().invoke(cli.main, ["--port", "0"])
    assert result.exit_code != 0
