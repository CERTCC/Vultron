"""Architecture check: committed example JSON files match generator output.

Fails when a new example function is added to ``vocab_examples.main()`` but
the generator has not been re-run (or vice-versa, when a call is removed but
the committed JSON file has not been cleaned up), and when a committed file's
*contents* differ in any byte from what the generator writes now.

The contents check is an equality, with no excluded value class.  It can be,
because the generator is deterministic: every id it writes is derived from a
fixed name and every timestamp from ``EXAMPLE_TIMESTAMP``
(``vultron.wire.as2.vocab.examples._base._example_scope``).  Before that, ids,
timestamps and the case number were drawn afresh on every run, so this module
could only compare which keys appeared where — and a changed *value* passed
unnoticed, which is the hole #5776 closed.

To regenerate from the repo root::

    uv run python vultron/wire/as2/vocab/examples/vocab_examples.py

AC-2, AC-3 of issue #3004; AC-2 of issue #5776.
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

import difflib
import json
import re
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

    assert invalid == [], (
        "Invalid JSON in committed examples:\n  " + "\n  ".join(invalid)
    )


def _reported_diff(committed: str, generated: str, filename: str) -> str:
    """A readable account of how the two texts differ.

    The comparison itself is on bytes; this only renders the result, so a
    difference that a line diff cannot show — a line ending, a missing final
    newline — is named rather than reported as an empty diff.
    """
    lines = list(
        difflib.unified_diff(
            committed.splitlines(),
            generated.splitlines(),
            fromfile=f"committed {filename}",
            tofile=f"generated {filename}",
            lineterm="",
        )
    )
    if lines:
        return "\n".join(lines)
    return (
        f"{filename}: same lines, different bytes — a line ending or a "
        "trailing newline differs"
    )


@pytest.mark.spec("CS-13-002")
def test_committed_examples_are_byte_identical_to_generated(
    generated_dir, generated_files, committed_files
):
    """Every committed example is byte-for-byte what the generator writes.

    Catches both halves of going stale: a serializer change (a renamed alias,
    a dropped or added field) that left the committed files describing the old
    wire format, and a *value* change — a different id, timestamp, hash, state
    or piece of content — that a key-shape comparison could not see (#5776).
    No value class is excluded: the generator derives every id and stamps
    every timestamp from a fixed moment, so a difference here is always a
    committed file that has not been regenerated.

    The comparison reads bytes, not ``Path.read_text``, which decodes with the
    locale's preferred encoding and folds ``\r\n`` into ``\n`` — so a CRLF or
    differently-encoded copy of an example would compare equal and pass, the
    hazard ``vultron.metadata.generated_files`` records for every other
    generated artifact in this repository.

    Fix: re-run the generator and commit ``docs/reference/examples/``.
    """
    drifted: list[str] = []
    for filename in sorted(generated_files & committed_files):
        committed = (_COMMITTED_DIR / filename).read_bytes()
        generated = (generated_dir / filename).read_bytes()
        if committed != generated:
            drifted.append(
                _reported_diff(
                    committed.decode("utf-8", "replace"),
                    generated.decode("utf-8", "replace"),
                    filename,
                )
            )
    assert not drifted, (
        "Committed examples differ from the generator's output. Re-run\n"
        "  uv run python vultron/wire/as2/vocab/examples/vocab_examples.py\n"
        "and commit docs/reference/examples/.\n\n" + "\n\n".join(drifted)
    )


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


@pytest.mark.spec("CS-13-007")
def test_committed_example_timestamps_take_the_fixed_form(committed_files):
    """Every example timestamp has six fractional digits (ADR-0167)."""
    fixed = re.compile(r"\.\d{6}[+-]\d{2}:\d{2}$")
    bad = [
        f"{filename}: {stamp}"
        for filename in sorted(committed_files)
        for stamp in _times(
            json.loads((_COMMITTED_DIR / filename).read_text())
        )
        if not fixed.search(stamp)
    ]
    assert not bad, "Timestamps not in the fixed form:\n  " + "\n  ".join(bad)
