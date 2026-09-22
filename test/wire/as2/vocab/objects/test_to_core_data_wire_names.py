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
"""``_to_core_data`` emits wire-facing identity names (#2940 cleanup #2)."""

from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)


def test_to_core_data_uses_wire_facing_identity_names() -> None:
    """The round-trip helper rewrites id_/type_/context_ to id/type/@context.

    A core ``model_validate`` accepts those via its ``validation_alias``, so the
    dict validates under ``extra="forbid"`` instead of tripping on a Python
    field-name spelling (ARCH-23-005).
    """
    wire = as_VulnerabilityReport(
        name="CVE-2940-0001",
        content="details",
        attributed_to="https://example.org/finder",
    )

    data = wire._to_core_data()

    # Wire-facing names present; Python field-name spellings absent.
    assert "id" in data and "id_" not in data
    assert "type" in data and "type_" not in data
    assert "context_" not in data

    # And the projected dict validates cleanly against the core type.
    from vultron.core.models.report import VulnerabilityReport

    core = VulnerabilityReport.model_validate(
        {k: v for k, v in data.items() if k != "@context"}
    )
    assert core.attributed_to == "https://example.org/finder"
