"""Architecture check: committed example JSON files match generator output.

Fails when a new example function is added to ``vocab_examples.main()`` but
the generator has not been re-run (or vice-versa, when a call is removed but
the committed JSON file has not been cleaned up).

To regenerate from the repo root::

    uv run python vultron/wire/as2/vocab/examples/vocab_examples.py

AC-2, AC-3 of issue #3004.
"""

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

import json
from pathlib import Path

import pytest

from vultron.wire.as2.vocab.examples.vocab_examples import main

_REPO_ROOT = Path(__file__).parents[2]
_COMMITTED_DIR = _REPO_ROOT / "docs" / "reference" / "examples"


@pytest.fixture(scope="module")
def generated_dir(tmp_path_factory) -> Path:
    """Run the generator into a temp directory and return that directory."""
    tmpdir: Path = tmp_path_factory.mktemp("vocab_examples")
    main(outdir=str(tmpdir))
    return tmpdir


@pytest.fixture(scope="module")
def generated_files(generated_dir) -> frozenset[str]:
    """Return the set of filenames the generator produced."""
    return frozenset(
        p.name for p in generated_dir.iterdir() if p.suffix == ".json"
    )


@pytest.fixture(scope="module")
def committed_files() -> frozenset[str]:
    """Return the set of JSON filenames currently committed to the examples dir."""
    return frozenset(
        p.name for p in _COMMITTED_DIR.iterdir() if p.suffix == ".json"
    )


def test_committed_examples_match_generator_output(
    generated_files, committed_files
):
    """The set of committed JSON files must equal the set the generator produces.

    Failure means either:
    - A new call was added to ``vocab_examples.main()`` but the generator was
      not re-run (committed dir is missing files), or
    - A committed JSON file was not removed after its generator call was
      deleted (generator dir is missing files).

    Fix: run ``uv run python vultron/wire/as2/vocab/examples/vocab_examples.py``
    from the repo root and commit the updated ``docs/reference/examples/`` directory.
    """
    missing_from_committed = sorted(generated_files - committed_files)
    extra_in_committed = sorted(committed_files - generated_files)

    messages = []
    if missing_from_committed:
        messages.append(
            "Generated but not committed (run the generator and commit):\n  "
            + "\n  ".join(missing_from_committed)
        )
    if extra_in_committed:
        messages.append(
            "Committed but no longer generated (remove from docs/reference/examples/):\n  "
            + "\n  ".join(extra_in_committed)
        )

    assert not messages, "\n\n".join(messages)


def test_all_committed_examples_are_valid_json(committed_files):
    """Every committed JSON example file must parse as valid JSON."""
    invalid = []
    for filename in sorted(committed_files):
        path = _COMMITTED_DIR / filename
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            invalid.append(f"{filename}: {exc}")

    assert (
        invalid == []
    ), "Invalid JSON in committed examples:\n  " + "\n  ".join(invalid)


def _key_paths(value: object, prefix: str = "") -> set[str]:
    """Return every dotted key path in *value*, merging list elements.

    Ids, timestamps and case numbers are random on each generator run, so the
    examples cannot be compared value-for-value; their *shape* — which keys
    appear where — is deterministic, and that is what a wire-format change
    moves.  Keys that are themselves URIs (map entries keyed by an id) are
    collapsed to ``<uri>`` so random ids do not register as new keys.
    """
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            name = "<uri>" if ":" in key and key != "@context" else key
            path = f"{prefix}.{name}" if prefix else name
            paths.add(path)
            paths |= _key_paths(child, path)
    elif isinstance(value, list):
        for child in value:
            paths |= _key_paths(child, f"{prefix}[]")
    return paths


def test_committed_examples_have_the_same_wire_keys_as_generated(
    generated_dir, generated_files, committed_files
):
    """Every committed example has the key shape the generator now emits.

    Catches a serializer change (a renamed alias, a dropped or added field)
    that left the committed examples describing the old wire format.  AC-3 of
    issue #3487.

    Fix: re-run the generator and commit ``docs/reference/examples/``.
    """
    drifted = []
    for filename in sorted(generated_files & committed_files):
        committed = _key_paths(
            json.loads((_COMMITTED_DIR / filename).read_text())
        )
        generated = _key_paths(
            json.loads((generated_dir / filename).read_text())
        )
        if committed != generated:
            drifted.append(
                f"{filename}: only committed {sorted(committed - generated)};"
                f" only generated {sorted(generated - committed)}"
            )
    assert not drifted, "Examples out of date:\n  " + "\n  ".join(drifted)


_TIME_KEYS = frozenset({"published", "updated", "startTime", "endTime"})


def _times(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _TIME_KEYS and isinstance(child, str):
                found.append(child)
            found.extend(_times(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_times(child))
    return found


def test_committed_example_timestamps_are_utc_offset(committed_files):
    """Wire timestamps carry an explicit ``+00:00`` UTC offset (ADR-0103)."""
    bad = [
        f"{filename}: {stamp}"
        for filename in sorted(committed_files)
        for stamp in _times(
            json.loads((_COMMITTED_DIR / filename).read_text())
        )
        if not stamp.endswith("+00:00")
    ]
    assert not bad, "Non-UTC-offset timestamps:\n  " + "\n  ".join(bad)
