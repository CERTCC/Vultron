"""ADR status and ADR reference checks for the spec linter (SR-04)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from vultron.metadata.adr.lifecycle import (
    unflipped_adrs,
    verified_dependents,
)
from vultron.metadata.adr.loader import load_adr_registry
from vultron.metadata.adr.schema import AdrFrontmatter
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import (
    AdrStatus,
    LintWarningCode,
)

_ADR_REF_RE = re.compile(r"\bADR-(\d{4})\b")

# MS-14: prose markers that mean the design is not yet validated. An ADR
# whose body contains any of these MUST NOT declare status: accepted.
_ADR_PROVISIONAL_MARKERS = (
    "formed in sand",
    "not concrete",
    "provisional",
    "forward-looking",
    "will converge",
    "expected to converge",
    "should refine this adr",
    "status will advance",
)


def _unflipped_adr_warnings(
    adr_registry: Mapping[str, AdrFrontmatter],
    registry: SpecRegistry,
    root: Path,
) -> list[str]:
    """Warn on a ``proposed`` ADR that has tested dependents (MS-14-010).

    The status is clock-free here: the dependency alone ends epoch 1, so the
    change that added the first dependent should have flipped it.
    """
    unflipped = unflipped_adrs(
        adr_registry,
        verified_dependents(
            registry.all_specs, lambda rel: (root / rel).is_file()
        ),
    )
    return [
        f"[WARN] {Path(rel_path).name}: status is 'proposed' but tested "
        f"dependents {', '.join(sorted(spec_ids))} end its epoch 1; the "
        f"change that adds the first one sets it to 'accepted-provisional' "
        f"(MS-14-010)"
        for rel_path, spec_ids in sorted(unflipped.items())
    ]


def _check_adr_status(
    adr_dir: Path | None,
    registry: SpecRegistry | None = None,
) -> tuple[list[str], list[str]]:
    """Validate ADR frontmatter (MS-14-001 hard, MS-14-013 advisory).

    Returns ``(hard_errors, warnings)``:

    - **Hard (MS-14-001, MS-14-016)**: every ADR frontmatter MUST satisfy the
      :class:`~vultron.metadata.adr.schema.AdrFrontmatter` schema — a valid
      ``AdrStatus`` value, and a ``superseded_by`` link when retired. This
      delegates to :func:`~vultron.metadata.adr.loader.load_adr_registry`, so
      the schema is the single source of truth (no duplicated parsing).
    - **Advisory (MS-14-013)**: an ADR whose prose carries a provisional marker
      SHOULD NOT be ``status: accepted``. This is a heuristic body scan and can
      false-positive (e.g. an ADR that *discusses* provisional-ness), so it
      surfaces ``decision-audit`` candidates rather than blocking CI; an ADR may
      opt out with ``lint_suppress: [status_prose_contradiction]``.

    - **Not here (MS-14-007)**: a ``status`` behind the epoch computed from
      ``updated`` and today is never a lint failure, because the answer
      changes with the clock and no commit. The diff-based
      ``adr-lifecycle-check`` fails the change that leaves it wrong, and the
      scheduled ``adr-status-drift`` workflow reports the rest.
    - **Advisory (MS-14-010)**: with a spec ``registry``, a ``proposed`` ADR
      that a tested spec requirement depends on is warned about. That needs
      no clock: the dependency alone ends epoch 1.

    Degrades to empty lists when ``adr_dir`` is missing so the check is a no-op
    in environments without a docs/ tree.
    """
    if adr_dir is None or not adr_dir.is_dir():
        return [], []
    errors: list[str] = []
    warnings: list[str] = []

    try:
        adr_registry = load_adr_registry(adr_dir.parent.parent)
    except ValueError as exc:
        # A single malformed ADR aborts registry load; surface it as the error.
        return [f"ADR frontmatter invalid (MS-14-001): {exc}"], []
    except FileNotFoundError:
        return [], []

    for rel_path, fm in adr_registry.items():
        name = Path(rel_path).name
        if fm.status is not AdrStatus.ACCEPTED:
            continue
        if fm.lint_suppress and any(
            c.value == "status_prose_contradiction" for c in fm.lint_suppress
        ):
            continue

        body = (
            (adr_dir.parent.parent / rel_path)
            .read_text(encoding="utf-8")
            .lower()
        )
        hit = next((m for m in _ADR_PROVISIONAL_MARKERS if m in body), None)
        if hit is not None:
            warnings.append(
                f"[WARN] {name}: status is 'accepted' but prose contains "
                f"provisional marker '{hit}' (MS-14-013); if the design is "
                f"genuinely unvalidated use 'accepted-provisional' — else "
                f"this is a decision-audit candidate (see ADR-0043). "
                f"Suppress on an ADR that legitimately discusses "
                f"provisional-ness with "
                f"'lint_suppress: [status_prose_contradiction]'."
            )

    if registry is not None:
        warnings.extend(
            _unflipped_adr_warnings(
                adr_registry, registry, adr_dir.parent.parent
            )
        )
    return errors, warnings


def _adr_numbers(adr_dir: Path) -> frozenset[str]:
    """Return the number of every ADR file in ``adr_dir`` or its ``archived/``.

    ADR files follow the naming convention ``NNNN-<slug>.md``, so
    ``ADR-0009`` resolves to any file matching ``0009-*.md``. Listed once per
    run: a glob per reference cost a second on the real corpus.
    """
    return frozenset(
        path.name.split("-", 1)[0]
        for directory in (adr_dir, adr_dir / "archived")
        for path in directory.glob("*-*.md")
    )


def _check_adr_references(
    registry: SpecRegistry, adr_dir: Path | None
) -> tuple[list[str], list[str]]:
    """Validate spec → ADR references (MS-11-004, SR-03-004).

    Returns ``(hard_errors, warnings)``:

    - **Hard**: a structured ``adr:`` field target with no matching ADR file
      (in ``adr_dir`` or ``adr_dir/archived``). The structured field is part of
      the traceability edges graph, so a dangling target silently breaks
      "dependents of ADR-NNNN" queries.
    - **Advisory**: a free-text ``rationale`` citation of an ADR that does not
      exist (legacy prose form; suppressible via ``lint_suppress``).

    Returns two empty lists when ``adr_dir`` is None or does not exist so the
    check degrades gracefully in environments without a docs/ tree.
    """
    if adr_dir is None or not adr_dir.is_dir():
        return [], []

    warnings: list[str] = []
    errors: list[str] = []
    known = _adr_numbers(adr_dir)
    for spec_id, spec in registry.all_specs.items():
        # Structured adr: references are validated as HARD errors — the field is
        # part of the traceability graph, so a dangling target breaks
        # "dependents of ADR-NNNN" queries (MS-11-004, SR-03-004). Also search
        # both docs/adr/ and docs/adr/archived/ so pointing at a retired ADR is
        # still valid.
        for adr_id in spec.adr or []:
            adr_number = adr_id.split("-", 1)[1]
            if adr_number not in known:
                errors.append(
                    f"{spec_id}: adr reference '{adr_id}' has no matching "
                    f"ADR file in '{adr_dir}' or '{adr_dir / 'archived'}'"
                )

        # Free-text rationale ADR citations remain advisory (legacy prose form).
        suppressed = set(spec.lint_suppress or [])
        if LintWarningCode.DANGLING_ADR_REF in suppressed:
            continue
        seen = set(_ADR_REF_RE.findall(spec.rationale))
        for adr_number in seen:
            if adr_number not in known:
                warnings.append(
                    f"[WARN] {spec_id}: rationale references "
                    f"ADR-{adr_number} but no matching file found in "
                    f"'{adr_dir}' "
                    f"(suppress with lint_suppress: [dangling_adr_ref])"
                )
    return errors, warnings
