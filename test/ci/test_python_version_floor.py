"""CI verification test — every declaration of the Python floor names one version.

Implements IMPLTS-01-001 from ``specs/tech-stack.yaml`` (#6052).

The floor is declared in three places that only read it (``requires-python``,
ruff's ``target-version``, pyright's ``pythonVersion``) and run in two (the CI
setup action's default interpreter and the Docker base image). When they
disagree, the declared floor is a claim nothing tests: the checks accept code
for a version CI never runs, or reject syntax the shipped runtime supports.
This module keeps all five on one version, so raising the floor is one change
that moves them together.
"""

from __future__ import annotations

import json
import re
import tomllib

import pytest

from test.ci._workflows import REPO_ROOT
from vultron.metadata.planning.ci_mirror._workflows import load_mapping

_PYPROJECT = REPO_ROOT / "pyproject.toml"
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


@pytest.mark.spec("IMPLTS-01-001")
@pytest.mark.parametrize(
    ("where", "read"),
    [
        ("ruff target-version", _ruff_target),
        ("pyright pythonVersion", _pyright_version),
        ("CI setup-python-uv default", _ci_default_python),
        ("Docker base image", _docker_base_python),
    ],
)
def test_declaration_names_the_requires_python_floor(where, read):
    floor = _requires_python_floor()
    assert read() == floor, (
        f"{where} names Python {read()}, but requires-python's floor is "
        f"{floor}; raise or lower them together."
    )


@pytest.mark.spec("IMPLTS-01-001")
def test_floor_meets_the_minimum_the_spec_names():
    major, minor = (int(part) for part in _requires_python_floor().split("."))
    assert (major, minor) >= (3, 13)
