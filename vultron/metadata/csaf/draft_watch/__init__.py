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
"""Say whether the CSAF 2.1 draft upstream changes what the models depend on.

The scheduled ``CSAF Draft Watch`` workflow (CSAF-05-005) runs this script
over two checkouts of ``oasis-tcs/csaf``: one at the pinned commit
(``--baseline``) and one at the head of the default branch (``--upstream``).
It compares three things:

- **The generated models.** The schemas are read from the pinned local copy
  and from upstream, at the paths the pin record maps, and the models are
  generated from each. The JSON Schema meta-schemas are frozen, so both sides
  take them from the pinned local copy. Annotations (``description``,
  ``$comment``, ``examples``) are dropped from every schema first, on both
  sides, so a reworded description is no change. A ``$ref`` the pin does not
  map, or a pinned file upstream no longer has, is reported as a change, never
  raised: models cannot be generated until the pin maps it.
- **The profile text**, ``profiles.md``, line by line.
- **The list of mandatory tests** in ``testcases.json``, by test ID.

It also says which of the CSAF fields this codebase reads (:data:`READ_FIELDS`)
the change touches (CSAF-05-007): a change there needs its mapping reviewed,
and a change elsewhere needs only a regeneration.

The script never moves the pin. Exit status: 0 when nothing the models,
profiles or test list depend on changed; 3 when something did, with the issue
body written to ``--report``; anything else is a failed run.

Usage::

    uv run csaf-draft-watch --baseline <pinned checkout> \\
        --upstream <upstream checkout> [--upstream-commit <sha>] \\
        [--report <file>]
"""

from vultron.metadata.csaf.corpus import TESTCASES_FILE
from vultron.metadata.csaf.draft_watch.cli import EXIT_CHANGED, main
from vultron.metadata.csaf.draft_watch.compare import (
    MANDATORY_GROUP,
    PROFILES_FILE,
    DraftChange,
    Renderer,
    compare,
    compare_profiles,
    compare_schemas,
    compare_tests,
    mandatory_tests,
    model_diff,
)
from vultron.metadata.csaf.draft_watch.fields import (
    READ_FIELDS,
    AffectedField,
    ReadField,
    affected_fields,
)
from vultron.metadata.csaf.draft_watch.issue import BODY_LIMIT, render_issue
from vultron.metadata.csaf.draft_watch.schemas import (
    WATCHED_SCHEMA_DIRS,
    SchemaSet,
    UnresolvedReferenceError,
    is_watched,
    strip_annotations,
)

__all__ = [
    "BODY_LIMIT",
    "EXIT_CHANGED",
    "MANDATORY_GROUP",
    "PROFILES_FILE",
    "READ_FIELDS",
    "TESTCASES_FILE",
    "WATCHED_SCHEMA_DIRS",
    "AffectedField",
    "DraftChange",
    "ReadField",
    "Renderer",
    "SchemaSet",
    "UnresolvedReferenceError",
    "affected_fields",
    "compare",
    "compare_profiles",
    "compare_schemas",
    "compare_tests",
    "is_watched",
    "main",
    "mandatory_tests",
    "model_diff",
    "render_issue",
    "strip_annotations",
]
