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
def generated_files(tmp_path_factory) -> frozenset[str]:
    """Run the generator into a temp directory and return the set of filenames."""
    tmpdir = tmp_path_factory.mktemp("vocab_examples")
    main(outdir=str(tmpdir))
    return frozenset(p.name for p in tmpdir.iterdir() if p.suffix == ".json")


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
