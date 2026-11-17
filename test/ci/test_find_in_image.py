"""The marker search that proves no image layer holds a credential (#6604).

``.github/scripts/find_in_image.py`` reads ``docker image save`` output. The
dev container has no Docker, so these tests build saved images by hand: a tar
archive of layer archives (plain and gzip) and a JSON config, the shapes
``docker image save`` writes (SHD-02-003).
"""

from __future__ import annotations

import gzip
import io
import json
import tarfile
from pathlib import Path

import pytest

from test.ci._scripts import load_script
from test.ci._workflows import REPO_ROOT, load_workflow, triggers

pytestmark = pytest.mark.spec("SHD-02-003")

_find = load_script("find_in_image")

MARKER = "shadow-marker-1234"
ENV = "TEST_SHADOW_MARKER"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "shadow-image.yml"


def _tar(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _image(
    tmp_path: Path,
    *,
    layer: dict[str, bytes] | None = None,
    config: dict[str, object] | None = None,
) -> Path:
    """A saved image: one gzip layer, one plain layer, a config, a manifest."""
    members = {
        "blobs/sha256/aaaa": gzip.compress(
            _tar({"usr/bin/tool": b"#!/bin/sh\n"} | (layer or {}))
        ),
        "blobs/sha256/bbbb": _tar({"app/README": b"hello\n"}),
        "blobs/sha256/cccc": json.dumps(
            config or {"config": {"Env": ["PATH=/usr/bin"]}}
        ).encode(),
        "manifest.json": b'[{"Layers": ["blobs/sha256/aaaa", "blobs/sha256/bbbb"]}]',
    }
    path = tmp_path / "image.tar"
    path.write_bytes(_tar(members))
    return path


def _run(
    image: Path, monkeypatch: pytest.MonkeyPatch, marker: str | None = MARKER
) -> int:
    if marker is None:
        monkeypatch.delenv(ENV, raising=False)
    else:
        monkeypatch.setenv(ENV, marker)
    return int(_find.main(["--marker-env", ENV, str(image)]))


def test_an_image_without_the_marker_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _run(_image(tmp_path), monkeypatch) == 0
    out = capsys.readouterr().out
    assert "Searched 2 layer(s)" in out
    assert MARKER not in out


@pytest.mark.parametrize(
    ("kwargs", "where"),
    [
        pytest.param(
            {"layer": {"app/.env": f"TOKEN={MARKER}\n".encode()}},
            "blobs/sha256/aaaa:app/.env",
            id="file-in-a-compressed-layer",
        ),
        pytest.param(
            {"layer": {f"tmp/{MARKER}": b""}},
            f"blobs/sha256/aaaa:tmp/{MARKER} (in its path or link target)",
            id="path-in-a-compressed-layer",
        ),
        pytest.param(
            {
                "config": {
                    "config": {"Env": [f"VULTRON_VINCE__API_TOKEN={MARKER}"]}
                }
            },
            "blobs/sha256/cccc",
            id="env-in-the-config",
        ),
    ],
)
def test_the_marker_anywhere_in_the_image_fails_and_is_named(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    kwargs: dict[str, dict[str, object]],
    where: str,
) -> None:
    assert _run(_image(tmp_path, **kwargs), monkeypatch) == 1  # type: ignore[arg-type]
    assert f"The marker from {ENV} is in {where}" in capsys.readouterr().out


def test_the_marker_in_a_plain_layer_is_named_inside_the_layer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layer = tmp_path / "layer.tar"
    layer.write_bytes(_tar({"etc/token": MARKER.encode()}))
    image = tmp_path / "image.tar"
    image.write_bytes(_tar({"layer.tar": layer.read_bytes()}))
    _, hits = _find.search(image, MARKER.encode())
    assert hits == ["layer.tar", "layer.tar:etc/token"]


def _symlink_layer(target: str) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo("etc/link")
        info.type = tarfile.SYMTYPE
        info.linkname = target
        archive.addfile(info)
    return buffer.getvalue()


def test_the_marker_in_a_link_target_is_named(tmp_path: Path) -> None:
    image = tmp_path / "image.tar"
    image.write_bytes(
        _tar({"blobs/sha256/eeee": gzip.compress(_symlink_layer(MARKER))})
    )
    _, hits = _find.search(image, MARKER.encode())
    assert hits == ["blobs/sha256/eeee:etc/link (in its path or link target)"]


def test_the_marker_in_a_path_of_the_saved_image_is_named(
    tmp_path: Path,
) -> None:
    image = tmp_path / "image.tar"
    image.write_bytes(
        _tar(
            {
                "layer.tar": _tar({"app/README": b"hi\n"}),
                f"{MARKER}.json": b"{}",
            }
        )
    )
    _, hits = _find.search(image, MARKER.encode())
    assert hits == [f"{MARKER}.json (in its path)"]


def test_a_member_name_that_is_not_utf8_is_searched_and_printed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """tarfile decodes such a name with surrogate escapes; the search reads
    its bytes, and the report prints it escaped instead of crashing."""
    layer = io.BytesIO()
    with tarfile.open(
        fileobj=layer, mode="w", format=tarfile.GNU_FORMAT
    ) as archive:
        name = b"tmp/\xff-" + MARKER.encode()
        info = tarfile.TarInfo(name.decode("utf-8", "surrogateescape"))
        archive.addfile(info, io.BytesIO(b""))
    image = tmp_path / "image.tar"
    image.write_bytes(_tar({"layer.tar": layer.getvalue()}))
    assert _run(image, monkeypatch) == 1
    assert f"layer.tar:tmp/\\udcff-{MARKER}" in capsys.readouterr().out


def test_a_marker_split_across_two_chunks_is_found() -> None:
    data = b"x" * 7 + MARKER.encode() + b"y" * 7
    assert _find.contains(io.BytesIO(data), MARKER.encode(), chunk_size=8)
    assert not _find.contains(
        io.BytesIO(b"x" * 40), MARKER.encode(), chunk_size=8
    )


@pytest.mark.parametrize("marker", [None, ""], ids=["unset", "empty"])
def test_a_missing_marker_cannot_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, marker: str | None
) -> None:
    assert _run(_image(tmp_path), monkeypatch, marker) == 2


def test_an_image_with_no_layer_cannot_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    image = tmp_path / "image.tar"
    image.write_bytes(_tar({"manifest.json": b"[]"}))
    assert _run(image, monkeypatch) == 2
    assert "holds no layer" in capsys.readouterr().out


def test_a_layer_it_cannot_read_stops_the_search(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A compressed member that is not a readable archive is not metadata."""
    image = tmp_path / "image.tar"
    image.write_bytes(
        _tar({"blobs/sha256/dddd": b"\x28\xb5\x2f\xfd" + b"\0" * 600})
    )
    assert _run(image, monkeypatch) == 2
    assert "cannot read this layer" in capsys.readouterr().out


def test_a_file_that_is_not_an_image_cannot_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = tmp_path / "image.tar"
    image.write_bytes(b"not a tar archive")
    assert _run(image, monkeypatch) == 2


# ── The workflow that runs the search ──────────────────────────────────────


def _job() -> dict[str, object]:
    job = load_workflow(WORKFLOW)["jobs"]["shadow-image"]
    assert isinstance(job, dict)
    return job


def test_the_job_searches_for_the_credential_it_builds_with() -> None:
    """The marker is set for the build step, and the search reads that same
    variable, so the search cannot look for a value the build never saw."""
    job = _job()
    env = job["env"]
    assert isinstance(env, dict)
    assert env["VULTRON_VINCE__API_TOKEN"]
    steps = job["steps"]
    assert isinstance(steps, list)
    names = [str(s.get("name", "")) for s in steps]
    build = names.index("Build the shadow image")
    search = next(
        i
        for i, s in enumerate(steps)
        if "find_in_image.py" in str(s.get("run", ""))
    )
    assert build < search
    assert "--marker-env VULTRON_VINCE__API_TOKEN" in str(steps[search]["run"])


def test_the_job_runs_on_a_change_to_what_it_checks() -> None:
    """AC-3: the image, the service, the tool, the lockfile and the job."""
    on = triggers(load_workflow(WORKFLOW))
    for event in ("push", "pull_request"):
        assert set(on[event]["paths"]) == {
            "docker/**",
            ".dockerignore",
            "vultron/shadow/**",
            "pyproject.toml",
            "uv.lock",
            ".github/workflows/shadow-image.yml",
            ".github/actions/build-demo-images/**",
            ".github/scripts/find_in_image.py",
        }, event
