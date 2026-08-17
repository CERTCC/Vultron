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

"""Tests for vultron.demo.helpers.ledger_dump."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _pytest.outcomes import Failed

from test.ci.invariants import common
from vultron.demo.helpers.ledger_dump import (
    DUMP_MANIFEST_FILENAME,
    _PRERUN_SENTINEL_REASON,
    write_prerun_sentinel,
)


def _read_sentinel(manifest_path: Path) -> dict:
    """Parse the manifest written at *manifest_path*."""
    return json.loads(manifest_path.read_text(encoding="utf-8"))


class TestWritePrerunSentinel:
    """``write_prerun_sentinel`` writes a valid DEMOCI-10-002 manifest.

    Verifies AC-1, AC-3, and AC-4 of ISSUE-2312:

    - The sentinel manifest is created at the expected path.
    - Its JSON conforms to the DEMOCI-10-002 schema.
    - ``load_devlogs()`` reports a failure — not a skip — when the sentinel is
      the only artifact present (manifest-without-ledgers path, DEMOCI-10-003).
    """

    DEMO_NAME = "fv"

    def test_creates_manifest_file(self, tmp_path):
        manifest_path = write_prerun_sentinel(
            self.DEMO_NAME, output_root=tmp_path
        )
        assert (
            manifest_path.is_file()
        ), f"Expected sentinel manifest at {manifest_path}"
        assert (
            manifest_path == tmp_path / self.DEMO_NAME / DUMP_MANIFEST_FILENAME
        )

    def test_manifest_conforms_to_democi_10_002_schema(self, tmp_path):
        """Manifest has all required DEMOCI-10-002 fields with correct values."""
        manifest_path = write_prerun_sentinel(
            self.DEMO_NAME, output_root=tmp_path
        )
        data = _read_sentinel(manifest_path)
        assert data["demoName"] == self.DEMO_NAME
        assert data["caseId"] is None
        assert data["ledgerFileCount"] == 0
        assert data["targetCount"] == 0
        assert isinstance(data["reason"], str) and data["reason"]
        assert data["actors"] == []

    def test_sentinel_reason_string_matches_spec(self, tmp_path):
        """Reason string indicates the demo-runner had not yet started."""
        manifest_path = write_prerun_sentinel(
            self.DEMO_NAME, output_root=tmp_path
        )
        data = _read_sentinel(manifest_path)
        assert data["reason"] == _PRERUN_SENTINEL_REASON
        assert "sentinel" in data["reason"].lower()
        assert "not yet started" in data["reason"].lower()

    def test_overwrites_existing_manifest(self, tmp_path):
        """Sentinel overwrites any manifest already present at the path."""
        demo_dir = tmp_path / self.DEMO_NAME
        demo_dir.mkdir(parents=True, exist_ok=True)
        existing = demo_dir / DUMP_MANIFEST_FILENAME
        existing.write_text('{"old": true}', encoding="utf-8")

        manifest_path = write_prerun_sentinel(
            self.DEMO_NAME, output_root=tmp_path
        )

        data = _read_sentinel(manifest_path)
        assert "demoName" in data, "Sentinel must overwrite the prior manifest"
        assert "old" not in data

    def test_load_devlogs_fails_not_skips_on_sentinel(
        self, tmp_path, monkeypatch
    ):
        """load_devlogs() reports failure — not skip — when sentinel is present.

        Verifies the DEMOCI-10-003 fail-vs-skip rule for the pre-harness path
        (AC-4 of ISSUE-2312): when the sentinel is the only artifact, the
        invariant-harness job reports a real failure instead of silently
        skipping.
        """
        write_prerun_sentinel(self.DEMO_NAME, output_root=tmp_path)
        monkeypatch.setattr(common, "_DEVLOGS_DIR", tmp_path)

        with pytest.raises(Failed) as excinfo:
            common.load_devlogs(self.DEMO_NAME)

        message = excinfo.value.msg or ""
        assert "no case-ledger" in message.lower(), (
            f"Expected failure message to mention missing ledger files; "
            f"got: {message!r}"
        )
