"""CI verification test — the Python floor is declared once and followed.

Implements IMPLTS-01-001, IMPLTS-01-009 and IMPLTS-01-010 from
``specs/tech-stack.yaml`` (#6052).

The floor is declared in ``requires-python`` and read by ruff's
``target-version``, mypy's ``python_version``, pyright's ``pythonVersion``, the
CI setup action's default interpreter and the Docker base image. When the first
four disagree with it, the declared floor is a claim nothing tests: the checks
accept code for a version CI never runs, or reject syntax the floor supports.
This module keeps them on one version, so raising the floor is one change that
moves them together. The container may run ahead of the floor, never behind it.
"""

from __future__ import annotations

import configparser
import json
import re
import tomllib
from collections.abc import Callable

import pytest

from test.ci._workflows import REPO_ROOT
from vultron.metadata.planning.ci_mirror._workflows import load_mapping

_PYPROJECT = REPO_ROOT / "pyproject.toml"
_MYPY = REPO_ROOT / ".mypy.ini"
_PYRIGHT = REPO_ROOT / "pyrightconfig.json"
_SETUP_ACTION = (
    REPO_ROOT / ".github" / "actions" / "setup-python-uv" / "action.yml"
)
_DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"


def _requires_python_floor() -> str:
    spec = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"][
        "requires-python"
    ]
    match = re.fullmatch(r">=\s*(3\.\d+)", spec)
    assert match, f"requires-python {spec!r} is not a plain `>=3.N` floor"
    return match.group(1)


def _ruff_target() -> str:
    target = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["tool"][
        "ruff"
    ]["target-version"]
    match = re.fullmatch(r"py3(\d+)", target)
    assert match, f"ruff target-version {target!r} is not `py3N`"
    return f"3.{match.group(1)}"


def _mypy_version() -> str:
    config = configparser.ConfigParser()
    config.read(_MYPY, encoding="utf-8")
    assert config.has_option("mypy", "python_version"), (
        ".mypy.ini sets no [mypy] python_version, so mypy follows the "
        "interpreter that runs it"
    )
    return config.get("mypy", "python_version")


def _pyright_version() -> str:
    return str(
        json.loads(_PYRIGHT.read_text(encoding="utf-8"))["pythonVersion"]
    )


def _ci_default_python() -> str:
    action = load_mapping(_SETUP_ACTION)
    return str(action["inputs"]["python-version"]["default"])


def _docker_base_python() -> str:
    text = _DOCKERFILE.read_text(encoding="utf-8")
    match = re.search(r"^FROM python:(3\.\d+)\S*\s+AS base$", text, re.M)
    assert match, "docker/Dockerfile has no `FROM python:3.N... AS base` stage"
    return match.group(1)


def _as_tuple(version: str) -> tuple[int, int]:
    major, minor = (int(part) for part in version.split("."))
    return major, minor


@pytest.mark.spec("IMPLTS-01-009")
@pytest.mark.parametrize(
    ("where", "read"),
    [
        ("ruff target-version", _ruff_target),
        ("mypy python_version", _mypy_version),
        ("pyright pythonVersion", _pyright_version),
        ("CI setup-python-uv default", _ci_default_python),
    ],
)
def test_declaration_names_the_requires_python_floor(
    where: str, read: Callable[[], str]
) -> None:
    floor = _requires_python_floor()
    actual = read()
    assert actual == floor, (
        f"{where} names Python {actual}, but requires-python's floor is "
        f"{floor}; raise or lower them together."
    )


@pytest.mark.spec("IMPLTS-01-010")
def test_docker_base_image_runs_the_floor_or_later() -> None:
    floor = _requires_python_floor()
    base = _docker_base_python()
    assert _as_tuple(base) >= _as_tuple(floor), (
        f"docker/Dockerfile's base image runs Python {base}, below the "
        f"requires-python floor {floor}."
    )


@pytest.mark.spec("IMPLTS-01-001")
def test_floor_meets_the_minimum_the_spec_names() -> None:
    assert _as_tuple(_requires_python_floor()) >= (3, 13)
