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
"""Regenerating the CSAF models from the pinned local copy (CSAF-05-002, CSAF-05-003)."""

import json
import shutil
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest

from vultron.metadata.csaf import regenerate
from vultron.metadata.csaf.regenerate import (
    UnpinnedReferenceError,
    render_models,
    stage_pinned_copy,
    stale_models,
    write_models,
)
from vultron.wire.csaf.pin import (
    MODELS_DIR,
    PINNED_COPY_DIR,
    CsafPin,
    load_pin,
)


class _NetworkUsedError(AssertionError):
    """Regeneration tried to open a network connection."""


def _refuse(*_args: object, **_kwargs: object) -> None:
    raise _NetworkUsedError(
        "regeneration must read the pinned local copy only"
    )


@pytest.fixture(scope="module")
def offline_models() -> Iterator[dict[str, str]]:
    """Render the models once with every way to open a connection refused."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(socket, "getaddrinfo", _refuse)
        mp.setattr(socket, "create_connection", _refuse)
        mp.setattr(socket.socket, "connect", _refuse)
        mp.setattr(socket.socket, "connect_ex", _refuse)
        with pytest.raises(_NetworkUsedError):
            socket.create_connection(("example.org", 443))
        yield render_models()


@pytest.mark.spec("CSAF-05-002")
def test_models_generate_from_the_pinned_local_copy_offline(
    offline_models: dict[str, str],
) -> None:
    assert "__init__.py" in offline_models
    assert "class CommonSecurityAdvisoryFramework(" in "".join(
        offline_models.values()
    )


@pytest.mark.spec("CSAF-05-003")
def test_regeneration_reproduces_the_committed_models(
    offline_models: dict[str, str],
) -> None:
    stale = stale_models(offline_models, MODELS_DIR)

    assert stale == [], (
        f"CSAF-05-003: the committed models differ from a regeneration: "
        f"{stale}. Run `uv run csaf-models`."
    )


@pytest.mark.spec("CSAF-05-003")
def test_the_models_name_the_pin_they_came_from(
    offline_models: dict[str, str],
) -> None:
    pin = load_pin()

    for path, text in offline_models.items():
        assert pin.short_commit in text.splitlines()[1], path
        assert pin.draft_stage in text.splitlines()[1], path


@pytest.fixture
def copy_with_pin(tmp_path: Path) -> tuple[Path, CsafPin]:
    source = tmp_path / "source"
    shutil.copytree(PINNED_COPY_DIR, source)
    return source, load_pin()


def _add_ref(source: Path, pin: CsafPin, ref: str) -> None:
    root = source / pin.root
    schema = json.loads(root.read_bytes())
    schema["$defs"]["added_t"] = {"$ref": ref}
    root.write_text(json.dumps(schema), encoding="utf-8")


@pytest.mark.spec("CSAF-05-002")
def test_an_unpinned_remote_reference_is_refused_not_fetched(
    copy_with_pin: tuple[Path, CsafPin], tmp_path: Path
) -> None:
    source, pin = copy_with_pin
    _add_ref(source, pin, "https://schemas.example.org/unpinned.json#/x")

    with pytest.raises(UnpinnedReferenceError, match=r"unpinned\.json"):
        stage_pinned_copy(source, tmp_path / "staging", pin)


def test_staging_rewrites_remote_references_to_staged_files(
    copy_with_pin: tuple[Path, CsafPin], tmp_path: Path
) -> None:
    source, pin = copy_with_pin
    staging = tmp_path / "staging"

    root = stage_pinned_copy(source, staging, pin)

    assert root == staging / "csaf.json"
    text = root.read_text(encoding="utf-8")
    assert '"$ref": "https://' not in text
    assert '"$ref": "csaf_2.1/referenced_schema/first/cvss-v3.1.json"' in text
    assert "$id" not in json.loads(text)
    nested = json.loads(
        (staging / "csaf_2.1/json_schema/extension-content.json").read_bytes()
    )
    assert nested["properties"]["$schema"]["$ref"] == (
        "extension-metaschema.json#/$defs/content_schema_t"
    )


def test_staging_rewrites_a_relative_reference_from_the_moved_root(
    copy_with_pin: tuple[Path, CsafPin], tmp_path: Path
) -> None:
    source, pin = copy_with_pin
    _add_ref(source, pin, "extension-content.json")

    root = stage_pinned_copy(source, tmp_path / "staging", pin)

    schema = json.loads(root.read_bytes())
    assert schema["$defs"]["added_t"]["$ref"] == (
        "csaf_2.1/json_schema/extension-content.json"
    )


def test_staging_needs_every_pinned_file(
    copy_with_pin: tuple[Path, CsafPin], tmp_path: Path
) -> None:
    source, pin = copy_with_pin
    (source / "csaf_2.1/referenced_schema/first/cvss-v4.0.json").unlink()

    with pytest.raises(FileNotFoundError):
        stage_pinned_copy(source, tmp_path / "staging", pin)


def test_a_hand_edit_and_a_stray_module_are_stale(tmp_path: Path) -> None:
    models = {"__init__.py": "a\n", "_internal.py": "b\n"}
    write_models(models, tmp_path)
    (tmp_path / "_internal.py").write_text("edited\n", encoding="utf-8")
    (tmp_path / "stray.py").write_text("x\n", encoding="utf-8")

    assert stale_models(models, tmp_path) == ["_internal.py", "stray.py"]


def test_writing_makes_the_package_hold_exactly_the_models(
    tmp_path: Path,
) -> None:
    (tmp_path / "stray.py").write_text("x\n", encoding="utf-8")
    models = {"__init__.py": "a\n"}

    changed = write_models(models, tmp_path)

    assert changed == ["__init__.py", "stray.py"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["__init__.py"]
    assert write_models(models, tmp_path) == []


@pytest.fixture
def small_render(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    models = {"__init__.py": "a\n"}
    monkeypatch.setattr(regenerate, "render_models", lambda *_: models)
    return models


@pytest.mark.usefixtures("small_render")
def test_check_exits_nonzero_on_stale_models_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert regenerate.main(["--check", "--output", str(tmp_path)]) == 1
    assert list(tmp_path.iterdir()) == []
    assert "__init__.py" in capsys.readouterr().err


@pytest.mark.usefixtures("small_render")
def test_regenerating_then_checking_passes(tmp_path: Path) -> None:
    assert regenerate.main(["--output", str(tmp_path)]) == 0
    assert regenerate.main(["--check", "--output", str(tmp_path)]) == 0
