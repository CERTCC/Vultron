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
"""Enforce the publication axis: a withheld artifact produces no ``site/`` files.

An artifact is *withheld* when the project has decided not to publish it. That
decision is a claim, and a claim with nothing comparing it to the output is how
``docs/ns/`` came to be live: its page carried ``draft: true``, which is a
Material *blog-plugin* key and not an MkDocs one, so the frontmatter suppressed
nothing while reading as though it had. Whoever wrote it believed the page was
withheld. A build produced ``site/ns/index.html`` and ``site/ns/context.jsonld``
anyway, and nothing noticed for as long as the site went unpublished.

This module is the comparison. :data:`WITHHELD_ARTIFACTS` declares what is
withheld and which built paths each artifact must not produce;
:func:`published_violations` checks a built ``site/`` against that declaration.

The mechanism that does the withholding is ``mkdocs.yml`` — ``draft_docs`` for
``ns/``, deletion for the ontology detail pages. This check does not duplicate
that mechanism: it verifies the *outcome*, so a withholding pattern that is
mis-anchored (as ``docs/developer/`` once was), silently dropped, or defeated by
a plugin fails here instead of shipping.

Two rules keep the check honest:

* A missing or empty ``site/`` is a hard failure, not a pass. A check that
  resolves no targets and reports success is worse than no check, because the
  clean signal suppresses the review it replaced (DF-09-009).
* A declared artifact whose paths no longer exist anywhere in the source tree is
  a hard failure too. Otherwise a withheld artifact could be renamed and its
  declaration would keep passing while describing nothing.

The declaration here is the interim home for the publication axis. #3555 builds
the maturity manifest, which carries publication and maturity for every artifact
the project ships; when it lands, this module reads the manifest instead of
:data:`WITHHELD_ARTIFACTS` and the tier-monotonicity checks join it. The check
itself does not change shape.

CLI (``uv run docs-withheld``)::

    uv run mkdocs build
    uv run docs-withheld          # exit 1 if a withheld artifact is in site/
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.base import repo_root


@dataclass(frozen=True)
class WithheldArtifact:
    """One artifact the project has decided not to publish.

    Attributes:
        name: The artifact's name, as the maturity manifest will key it (#3555).
        site_prefixes: Paths, relative to ``site/``, that MUST NOT be built —
            each covering itself and everything under it. Write them against the
            built layout, not the source layout: under ``use_directory_urls`` a
            page ``docs/x/y.md`` builds to ``site/x/y/index.html``, so the prefix
            is ``x/y``. :meth:`site_globs` derives the match patterns.
        source_globs: Globs, relative to the repo root, that locate the artifact
            itself in the source tree. At least one MUST match, so an artifact
            that was deleted or moved fails the check rather than leaving a
            declaration that describes nothing and passes forever. This guards
            the artifact's existence, not ``site_prefixes`` — those name paths
            that must *not* exist, so nothing can assert them into being.
        reason: Why the artifact is withheld, in one sentence.
        gate: What has to be true before it may be published.
    """

    name: str
    site_prefixes: tuple[str, ...]
    source_globs: tuple[str, ...]
    reason: str
    gate: str

    def covers(self, site_path: str) -> bool:
        """Return whether *site_path*, relative to ``site/``, is this artifact's.

        A path is covered when it equals a prefix or sits beneath one, so
        ``reference/ontology/dfa`` covers ``reference/ontology/dfa/index.html``
        but not ``reference/ontology/dfa2``.
        """
        return any(
            site_path == prefix or site_path.startswith(f"{prefix}/")
            for prefix in self.site_prefixes
        )

    def site_globs(self) -> tuple[str, ...]:
        """Return the glob patterns matching every built path this artifact owns.

        Each prefix yields two patterns: the prefix itself, which matches the
        built directory or file, and ``<prefix>/**/*``, which matches everything
        beneath it.

        ``<prefix>/**`` is deliberately **not** used. Before Python 3.13 a
        pattern ending in ``**`` matched directories only, so ``ns/**`` would
        skip ``site/ns/context.jsonld`` — and the whole point of this artifact is
        the JSON-LD file, not the page beside it. The project supports Python
        3.12+ (CI runs 3.13), so the pattern has to mean the same thing on both.
        """
        return tuple(
            pattern
            for prefix in self.site_prefixes
            for pattern in (prefix, f"{prefix}/**/*")
        )


WITHHELD_ARTIFACTS: tuple[WithheldArtifact, ...] = (
    WithheldArtifact(
        name="JSON-LD vocabulary",
        site_prefixes=("ns",),
        source_globs=("docs/ns/index.md", "docs/ns/context.jsonld"),
        reason=(
            "Publishing the site would make the namespace URI "
            "https://certcc.github.io/Vultron/ns/context.jsonld resolve for the "
            "first time, and a namespace URI is a long-lived commitment."
        ),
        gate=(
            "The declared term set settling. #2943 landed the drift check "
            "(wire-context --check), but #3487 and #3488 delete the as_* classes "
            "the terms name, under an ADR-0099 that is accepted-provisional."
        ),
    ),
    WithheldArtifact(
        name="OWL/TTL ontology",
        # The tombstone at `reference/ontology/index.md` stays published, so the
        # prefixes name the five detail pages rather than the directory (#3551).
        site_prefixes=(
            "reference/ontology/vultron_as",
            "reference/ontology/vultron_protocol",
            "reference/ontology/vultron_process",
            "reference/ontology/dfa",
            "reference/ontology/rfc2119",
            # Protégé how-to fragments the detail pages included; each was
            # built as a page of its own and is a live URL on the old site.
            "includes/ontology_tips",
            "includes/use_protege",
        ),
        source_globs=("ontology/*.ttl",),
        reason=(
            "A translation artifact from the formal message types onto the AS2 "
            "vocabulary, unmaintained, with no dependent uses."
        ),
        gate=(
            "None; the decision is to retain it in the repository and not "
            "publish it. docs/reference/ontology/index.md is the tombstone that "
            "answers the live URL, and is deliberately still published (#3551)."
        ),
    ),
    WithheldArtifact(
        name="Ledger replication spec",
        site_prefixes=("reference/draft-vultron-replication-spec",),
        source_globs=("docs/reference/draft-vultron-replication-spec.md",),
        reason="A draft companion spec, not yet reviewed for publication.",
        gate="ADR-0077's companion spec being finished and reviewed.",
    ),
)


def site_dir(root: Path | None = None) -> Path:
    """Return the built site directory."""
    return (root or repo_root()) / "site"


def published_violations(
    root: Path | None = None,
    artifacts: tuple[WithheldArtifact, ...] = WITHHELD_ARTIFACTS,
) -> list[tuple[WithheldArtifact, Path]]:
    """Return every ``(artifact, path)`` pair where a withheld artifact is built.

    Args:
        root: Repository root. Defaults to the enclosing checkout.
        artifacts: The declaration to check. Overridden in tests.

    Returns:
        One entry per distinct built path that a withheld artifact's globs
        matched, sorted by artifact name then path so output is stable. Paths are
        deduplicated per artifact, because a prefix and its ``/**/*`` companion
        can both match when a build nests one withheld prefix inside another.

    Raises:
        FileNotFoundError: If ``site/`` is absent or empty. The caller must build
            the site first; an unbuilt site cannot evidence the claim, so it is a
            failure rather than a pass (DF-09-009).
    """
    base = root or repo_root()
    built = site_dir(base)
    if not built.is_dir() or not any(built.iterdir()):
        raise FileNotFoundError(
            f"{built} is absent or empty — run 'uv run mkdocs build' first. "
            "An unbuilt site cannot show that a withheld artifact is unpublished."
        )

    violations: list[tuple[WithheldArtifact, Path]] = []
    for artifact in artifacts:
        matched: set[Path] = set()
        for pattern in artifact.site_globs():
            matched.update(built.glob(pattern))
        violations.extend((artifact, path) for path in matched)
    return sorted(violations, key=lambda pair: (pair[0].name, str(pair[1])))


def undeclared_artifacts(
    root: Path | None = None,
    artifacts: tuple[WithheldArtifact, ...] = WITHHELD_ARTIFACTS,
) -> list[WithheldArtifact]:
    """Return declarations whose ``source_globs`` match nothing in the tree.

    A declaration that describes no file is worse than a missing one: it reports
    success forever while checking nothing, which is the failure mode this whole
    module exists to close.
    """
    base = root or repo_root()
    return [
        artifact
        for artifact in artifacts
        if not any(
            any(base.glob(pattern)) for pattern in artifact.source_globs
        )
    ]


def _report(
    violations: list[tuple[WithheldArtifact, Path]],
    stale: list[WithheldArtifact],
    base: Path,
) -> None:
    """Print every finding to stderr, grouped by artifact."""
    for artifact in stale:
        print(
            f"[ERROR] Withheld artifact '{artifact.name}' matches no source "
            f"file. Its source_globs are {list(artifact.source_globs)}. Either "
            "the artifact moved and the declaration needs updating, or it is "
            "gone and the declaration should be removed.",
            file=sys.stderr,
        )
    seen: set[str] = set()
    for artifact, path in violations:
        if artifact.name not in seen:
            seen.add(artifact.name)
            print(
                f"[ERROR] Withheld artifact '{artifact.name}' is published.\n"
                f"  Withheld because: {artifact.reason}\n"
                f"  Gate on publishing: {artifact.gate}",
                file=sys.stderr,
            )
        print(f"    built: {path.relative_to(base)}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run docs-withheld``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root holding the built site/ (default: this checkout).",
    )
    args = parser.parse_args(argv)
    base = args.root or repo_root()

    stale = undeclared_artifacts(base)
    try:
        violations = published_violations(base)
    except FileNotFoundError as exc:
        # The audience for this tool is whoever just ran it and got it wrong, so
        # a missing site/ owes them an instruction rather than a traceback. Report
        # the stale declarations already found first: they do not depend on the
        # build, and discarding them would hide real findings behind a setup error.
        _report([], stale, base)
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    if violations or stale:
        _report(violations, stale, base)
        print(
            f"\n✗ {len(violations)} published path(s) and {len(stale)} stale "
            f"declaration(s) across {len(WITHHELD_ARTIFACTS)} withheld artifacts.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"✓ All {len(WITHHELD_ARTIFACTS)} withheld artifacts are absent from "
        f"{site_dir(base).name}/."
    )


if __name__ == "__main__":
    main()
