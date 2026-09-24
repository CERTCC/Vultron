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
"""Deterministic backstop for an agent's spec selection (``spec-backstop``).

From the changes on a branch, compute which spec groups plausibly govern the
changed code, and check them against the agent's Spec manifest::

    spec-backstop                                  # diff vs origin/main
    spec-backstop --base main --manifest manifest.txt
    spec-backstop --paths vultron/core/foo.py --json

Exit codes: 0 = no manifest given or every MUST-tier group resolved;
1 = unresolved MUST-tier groups; 2 = setup error.

Requirements: specs/spec-registry.yaml SR-12.
"""

from vultron.metadata.specs.backstop._analysis import (
    analyze,
    load_requirements,
    mentions,
)
from vultron.metadata.specs.backstop._cli import (
    main,
)
from vultron.metadata.specs.backstop._diff import (
    changes_from_paths,
    collect_git_changes,
    git_toplevel,
    parse_diff_hunks,
)
from vultron.metadata.specs.backstop._manifest import (
    is_resolved,
    parse_manifest,
    unresolved_groups,
)
from vultron.metadata.specs.backstop._model import (
    HUB_THRESHOLD,
    MAX_EVIDENCE,
    MONOLITH_GROUP_SPAN,
    SOURCE_PREFIX,
    TEST_PREFIX,
    BackstopError,
    BackstopReport,
    FileChange,
    GitRunner,
    GroupHit,
    Manifest,
    Requirement,
    TestFile,
)
from vultron.metadata.specs.backstop._render import (
    render_json,
    render_text,
)
from vultron.metadata.specs.backstop._symbols import (
    BOILERPLATE_SYMBOLS,
    build_test_index,
    changed_nodes,
    changed_symbols,
    imported_symbols,
    index_test_file,
    mirror_tests,
    module_name,
    spec_ids_in,
)

__all__ = [
    "BOILERPLATE_SYMBOLS",
    "BackstopError",
    "BackstopReport",
    "FileChange",
    "GitRunner",
    "GroupHit",
    "HUB_THRESHOLD",
    "MAX_EVIDENCE",
    "MONOLITH_GROUP_SPAN",
    "Manifest",
    "Requirement",
    "SOURCE_PREFIX",
    "TEST_PREFIX",
    "TestFile",
    "analyze",
    "build_test_index",
    "changed_nodes",
    "changed_symbols",
    "changes_from_paths",
    "collect_git_changes",
    "git_toplevel",
    "imported_symbols",
    "index_test_file",
    "is_resolved",
    "load_requirements",
    "main",
    "mentions",
    "mirror_tests",
    "module_name",
    "parse_diff_hunks",
    "parse_manifest",
    "render_json",
    "render_text",
    "spec_ids_in",
    "unresolved_groups",
]
