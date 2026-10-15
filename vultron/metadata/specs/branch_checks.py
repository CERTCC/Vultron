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

from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.line_length import (
    LINE_LIMIT,
    added_overlong_lines,
    new_lines,
    overlong_spec_yaml_lines,
)
from vultron.metadata.specs.growth_guard import (
    BaseUnavailableError,
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


@dataclass(frozen=True)
class _SpecTree:
    """What the branch checks read from one tree's ``specs/``."""

    fingerprints: dict[str, str]
    overlong: frozenset[str]

    @classmethod
    def read(cls, root: Path) -> _SpecTree:
        return cls(
            requirement_fingerprints(root), overlong_spec_yaml_lines(root)
        )


@dataclass(frozen=True)
class BranchChanges:
    """What the branch changed in ``specs/`` since its merge base.

    Attributes:
        requirement_ids: Requirements added or changed (any field).
        yaml_lines: Overlong spec YAML lines added; a moved line is not.
    """

    requirement_ids: frozenset[str]
    yaml_lines: frozenset[str]


def branch_changes(repo_root: Path, base_ref: str) -> BranchChanges:
    """Read ``specs/`` once at the merge base with *base_ref* and once here.

    Raises:
        BaseUnavailableError: *base_ref* does not resolve, or shares no
            history with ``HEAD``.
    """
    seen = compare_with_base(
        _SpecTree.read,
        repo_root=repo_root,
        paths=_SPEC_PATHS,
        base_ref=base_ref,
        require_base=True,
    )
    if seen.base_value is None:  # require_base raises first; never a pass
        raise BaseUnavailableError(seen.skipped or f"{base_ref} not read")
    base, head = seen.base_value, seen.head_value
    return BranchChanges(
        changed_requirement_ids(base.fingerprints, head.fingerprints),
        new_lines(base.overlong, head.overlong),
    )


def changed_since(repo_root: Path, base_ref: str) -> frozenset[str]:
    """Requirement IDs added or changed since the merge base with *base_ref*.

    Raises:
        BaseUnavailableError: as :func:`branch_changes`.
    """
    return branch_changes(repo_root, base_ref).requirement_ids


def check_changed_markers(
    registry: SpecRegistry,
    repo_root: Path,
    changed: frozenset[str],
    index: SuiteIndex | None = None,
) -> list[str]:
    """MS-10-011 errors for the *changed* requirements of *registry*.

    *index* is the test suite of *repo_root*, when the caller built it.
    """
    if index is None:
        index = SuiteIndex.build(repo_root)
    return [
        marker_problem(spec_id)
        for spec_id in sorted(changed)
        if (spec := registry.all_specs.get(spec_id)) is not None
        and named_tests_lack_marker(spec_id, spec, index)
    ]


def _yaml_line_errors(lines: frozenset[str], base_ref: str) -> list[str]:
    return [
        f"PD-10-002: line over {LINE_LIMIT} characters added since "
        f"{base_ref}: {item}. Wrap it; YAML folds a plain or `>-` scalar's "
        f"line breaks into spaces."
        for item in sorted(lines)
    ]


def check_added_yaml_lines(repo_root: Path, base_ref: str) -> list[str]:
    """PD-10-002 errors for each overlong spec YAML line the branch adds.

    Reads the lines alone; :func:`check_branch` reads them together with the
    requirements, in one pass over the base tree.
    """
    check = added_overlong_lines(
        overlong_spec_yaml_lines,
        repo_root=repo_root,
        paths=_SPEC_PATHS,
        base_ref=base_ref,
        require_base=True,
    )
    return _yaml_line_errors(check.added, base_ref)


def check_branch(
    registry: SpecRegistry,
    repo_root: Path,
    base_ref: str,
    index: SuiteIndex | None = None,
) -> list[str]:
    """Every ``--changed-since`` hard error for the branch against *base_ref*.

    *index* is the test suite of *repo_root*, when the caller built it.
    """
    changes = branch_changes(repo_root, base_ref)
    errors = check_changed_markers(
        registry, repo_root, changes.requirement_ids, index
    )
    errors.extend(_yaml_line_errors(changes.yaml_lines, base_ref))
    return errors


__all__ = [
    "BranchChanges",
    "branch_changes",
    "changed_since",
    "check_added_yaml_lines",
    "check_branch",
    "check_changed_markers",
]
