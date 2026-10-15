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
"""``spec-lint --changed-since REF``: checks scoped to what a branch changed.

Two spec rules have a backlog in the corpus, so ``spec-lint`` cannot fail on
them corpus-wide. Scoped to the branch, they hold for everything it touches:

- **MS-10-011** — each requirement the branch adds or changes (any field, see
  :func:`~vultron.metadata.specs.verification_refs.changed_requirement_ids`)
  whose ``verification:`` names test files has the requirement's marker in one
  of them, when its kind is ``protocol`` or ``foundation``.
- **PD-10-002** — no line the branch adds to ``specs/*.yaml`` is overlong
  (:func:`~vultron.metadata.line_length.is_overlong`).

``create-pr`` runs this before a Pull Request's first push (PAD-20-003). The
same two rules run corpus-wide as growth guards under ``test/architecture/``,
so CI holds them too. The base is required: a ref that does not resolve is an
error (exit 2), never a pass.

Requirements: specs/meta-specifications.yaml MS-10-011;
specs/project-documentation.yaml PD-10-002;
specs/parallel-development.yaml PAD-20-003.
"""

from __future__ import annotations

from pathlib import Path

from vultron.metadata.line_length import LINE_LIMIT, overlong_spec_yaml_lines
from vultron.metadata.specs.growth_guard import (
    BaseUnavailableError,
    added_since_base,
    compare_with_base,
)
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.verification_refs import (
    SuiteIndex,
    changed_requirement_ids,
    marker_problem,
    named_tests_lack_marker,
    requirement_fingerprints,
)

_SPEC_PATHS = ("specs",)


def changed_since(repo_root: Path, base_ref: str) -> frozenset[str]:
    """Requirement IDs added or changed since the merge base with *base_ref*.

    Raises:
        BaseUnavailableError: *base_ref* does not resolve, or shares no
            history with ``HEAD``.
    """
    seen = compare_with_base(
        requirement_fingerprints,
        repo_root=repo_root,
        paths=_SPEC_PATHS,
        base_ref=base_ref,
        require_base=True,
    )
    if seen.base_value is None:  # require_base raises first; never a pass
        raise BaseUnavailableError(seen.skipped or f"{base_ref} not read")
    return changed_requirement_ids(seen.base_value, seen.head_value)


def check_changed_markers(
    registry: SpecRegistry, repo_root: Path, changed: frozenset[str]
) -> list[str]:
    """MS-10-011 errors for the *changed* requirements of *registry*."""
    index = SuiteIndex.build(repo_root)
    return [
        marker_problem(spec_id)
        for spec_id in sorted(changed)
        if (spec := registry.all_specs.get(spec_id)) is not None
        and named_tests_lack_marker(spec_id, spec, index)
    ]


def check_added_yaml_lines(repo_root: Path, base_ref: str) -> list[str]:
    """PD-10-002 errors for each overlong spec YAML line the branch adds."""
    check = added_since_base(
        overlong_spec_yaml_lines,
        repo_root=repo_root,
        paths=_SPEC_PATHS,
        base_ref=base_ref,
        require_base=True,
    )
    return [
        f"PD-10-002: line over {LINE_LIMIT} characters added since "
        f"{base_ref}: {item}. Wrap it; YAML folds a plain or `>-` scalar's "
        f"line breaks into spaces."
        for item in sorted(check.added)
    ]


def check_branch(
    registry: SpecRegistry, repo_root: Path, base_ref: str
) -> list[str]:
    """Every ``--changed-since`` hard error for the branch against *base_ref*."""
    changed = changed_since(repo_root, base_ref)
    errors = check_changed_markers(registry, repo_root, changed)
    errors.extend(check_added_yaml_lines(repo_root, base_ref))
    return errors


__all__ = [
    "changed_since",
    "check_added_yaml_lines",
    "check_branch",
    "check_changed_markers",
]
