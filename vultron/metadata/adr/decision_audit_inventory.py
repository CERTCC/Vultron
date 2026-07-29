"""Risk-ranked landmine inventory for the decision-audit skill.

Requirements: Concern #1800 (extend decision-audit to spec groups); ADR-0043.

Computes a **blast-radius × confidence-deficit** score for two artifact types
that implementers treat as ground truth:

- **ADRs** — decisions whose stale/wrong premise stalls PRs.
- **Spec groups** — requirements with the same failure mode (CM-15/ISSUE-1272,
  DEMOMA-07-003/CONCERN-1043 were spec contradictions, not ADR ones).

The signals here were validated to *discriminate*: each fires on a small
fraction of candidates. Signals that flagged nearly everything (e.g. "no
``@pytest.mark.spec`` coverage", which is absent on ~99% of spec items) are
deliberately excluded — see ``REFERENCE.md``.

CLI: ``uv run python -m vultron.metadata.adr.decision_audit_inventory``
    --top N     show only the N highest-risk candidates (default: all)
    --json      emit machine-readable JSON instead of the text table
    --kind ...  restrict to 'adr' or 'spec' (default: both)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from vultron.metadata.adr.loader import _find_repo_root, load_adr_registry
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.schema import AdrStatus

# Prose markers that mean an ADR's design is not yet validated (shared with the
# lint check). Presence while status==accepted is a confidence-deficit signal.
_PROVISIONAL_MARKERS = (
    "formed in sand",
    "not concrete",
    "provisional",
    "forward-looking",
    "will converge",
    "expected to converge",
    "should refine this adr",
    "status will advance",
)

# Words that, near a spec-group ID in learnings/history, suggest prior trouble.
_PROBLEM_WORDS = re.compile(
    r"(wrong|stale|incorrect|contradict|supersede|ambigu|mislead|"
    r"violat|rework|bad premise)",
    re.I,
)

_ADR_NUM_RE = re.compile(r"ADR-(\d{4})")

# Per-signal weights. Signals that a prior investigation already tied to real
# rework (a requirement inheriting a moved premise; an ADR whose own prose
# contradicts its status) weigh more than a bare mention. The prefix before
# ':' is matched, so parameterised signals ("status=proposed") map to a weight.
_SIGNAL_WEIGHTS: dict[str, int] = {
    "derives-from-non-accepted-adr": 3,  # rediscovers CM-15 (ISSUE-1272)
    "provisional-prose": 3,  # ADR status/prose contradiction (ADR-0025)
    "status": 2,  # ADR not plain-accepted
    "testable-false-cluster": 2,  # unverified assertions taken on faith
    "cites-superseded": 2,
    "prototype-only": 1,
    "named-in-learnings": 1,  # weakest: a mention, not a confirmed defect
}


def _signal_weight(signal: str) -> int:
    """Weight for a signal, keyed by its prefix before ':' (default 1)."""
    key = signal.split(":", 1)[0].split("=", 1)[0]
    return _SIGNAL_WEIGHTS.get(key, 1)


@dataclass
class Candidate:
    """One scored landmine candidate (an ADR or a spec group)."""

    id: str
    kind: str  # "adr" | "spec-group"
    blast_radius: int
    signals: list[str] = field(default_factory=list)

    @property
    def deficit(self) -> int:
        """Weighted confidence-deficit magnitude.

        Sum of per-signal weights rather than a raw count, so a
        high-value signal (a moved premise) outranks several weak mentions.
        """
        return sum(_signal_weight(s) for s in self.signals)

    @property
    def score(self) -> int:
        """Risk = (blast radius + 1) × weighted deficit.

        The ``+1`` floor ensures a candidate with a strong deficit signal but
        zero measured dependents still ranks above noise — a wrong requirement
        nothing yet depends on is still worth fixing before something does.
        A candidate with no deficit signal scores 0.
        """
        return (self.blast_radius + 1) * self.deficit


def _load_learnings_text(root: Path) -> str:
    parts: list[str] = []
    for rel in ("plan/history", "plan/incoming/learnings"):
        base = root / rel
        if not base.is_dir():
            continue
        for path in base.rglob("*.md"):
            try:
                parts.append(path.read_text(errors="ignore"))
            except OSError:
                continue
    return "\n".join(parts)


# Any PREFIX-NN[-NNN] identifier — used to find IDs sitting near a problem word.
_ANY_ID_RE = re.compile(r"\b([A-Z]{2,8}-\d{2}(?:-\d{3})?)\b")


def _ids_near_problem_words(text: str, window: int = 120) -> set[str]:
    """Return every spec/ADR-style identifier that appears within ``window``
    chars of a problem word.

    Computed in a single pass over ``text`` (one scan for problem-word spans,
    one scan for identifiers) rather than re-scanning per candidate — the naive
    per-candidate approach is O(candidates × len(text)) and dominates runtime.
    """
    problem_spans = [m.span() for m in _PROBLEM_WORDS.finditer(text)]
    if not problem_spans:
        return set()
    hits: set[str] = set()
    for m in _ANY_ID_RE.finditer(text):
        lo, hi = m.start() - window, m.end() + window
        # A problem word overlaps [lo, hi] iff some span starts before hi and
        # ends after lo. Linear scan is fine; spans are few relative to ids.
        for pstart, pend in problem_spans:
            if pstart <= hi and pend >= lo:
                hits.add(m.group(1))
                # Also record the two-segment group prefix (e.g. CM-15) so a
                # spec-item mention (CM-15-001) flags its group.
                parts = m.group(1).split("-")
                if len(parts) == 3:
                    hits.add(f"{parts[0]}-{parts[1]}")
                break
    return hits


def _adr_blast_radius(root: Path, reg) -> dict[str, int]:
    """Dependent count per ADR number: structured adr: edges + prose citations."""
    dep_count: dict[str, int] = defaultdict(int)
    for spec in reg.all_specs.values():
        for adr_id in spec.adr or []:
            dep_count[adr_id.split("-")[1]] += 1
    for path in (root / "specs").rglob("*.yaml"):
        for num in _ADR_NUM_RE.findall(path.read_text(errors="ignore")):
            dep_count[num] += 1
    return dep_count


def _adr_signals(fm, num: str, body: str, flagged_ids: set[str]) -> list[str]:
    """Confidence-deficit signals for one ADR."""
    signals: list[str] = []
    if fm.status is not AdrStatus.ACCEPTED:
        signals.append(f"status={fm.status.value}")
    elif _provisional_marker_hit(fm, body) is not None:
        signals.append(
            f"provisional-prose:'{_provisional_marker_hit(fm, body)}'"
        )
    if f"ADR-{num}" in flagged_ids:
        signals.append("named-in-learnings")
    return signals


def _provisional_marker_hit(fm, body: str) -> str | None:
    """First provisional prose marker in an accepted ADR not opted out, else None."""
    suppressed = fm.lint_suppress and any(
        c.value == "status_prose_contradiction" for c in fm.lint_suppress
    )
    if suppressed:
        return None
    return next((m for m in _PROVISIONAL_MARKERS if m in body), None)


def _adr_candidates(
    root: Path, flagged_ids: set[str], adr_reg: dict, reg
) -> list[Candidate]:
    dep_count = _adr_blast_radius(root, reg)
    candidates: list[Candidate] = []
    for rel_path, fm in adr_reg.items():
        num = Path(rel_path).name.split("-")[0]
        body = (root / rel_path).read_text(errors="ignore").lower()
        signals = _adr_signals(fm, num, body, flagged_ids)
        if signals:
            candidates.append(
                Candidate(
                    id=f"ADR-{num}",
                    kind="adr",
                    blast_radius=dep_count.get(num, 0),
                    signals=signals,
                )
            )
    return candidates


def _group_signals(group_id, specs, adr_by_num, reg, flagged_ids) -> list[str]:
    """Confidence-deficit signals for one spec group."""
    signals: list[str] = []

    # Derives from a non-accepted ADR (highest-value signal).
    shaky = {
        f"{adr_id}={adr_by_num[adr_id.split('-')[1]].status.value}"
        for spec in specs
        for adr_id in spec.adr or []
        if adr_by_num.get(adr_id.split("-")[1])
        and adr_by_num[adr_id.split("-")[1]].status is not AdrStatus.ACCEPTED
    }
    if shaky:
        signals.append(
            "derives-from-non-accepted-adr:" + ",".join(sorted(shaky))
        )

    # testable:false cluster with no behavioral steps.
    untestable = [
        s for s in specs if not s.testable and not getattr(s, "steps", None)
    ]
    if len(untestable) >= 2:
        signals.append(f"testable-false-cluster:{len(untestable)}")

    # Purely prototype-scoped group.
    scopes = {
        sc.value
        for spec in specs
        for sc in (reg.get_effective_scope(spec.id) or [])
    }
    if scopes == {"prototype"}:
        signals.append("prototype-only")

    if group_id in flagged_ids:
        signals.append("named-in-learnings")
    return signals


def _spec_group_candidates(
    flagged_ids: set[str], adr_by_num: dict, reg
) -> list[Candidate]:
    group_specs: dict[str, list] = defaultdict(list)
    for sid, spec in reg.all_specs.items():
        group, _ = reg._spec_context[sid]
        group_specs[group.id].append(spec)

    # Blast radius: inbound relationship edges pointing into the group.
    inbound: dict[str, int] = defaultdict(int)
    for spec in reg.all_specs.values():
        for rel in spec.relationships or []:
            inbound["-".join(rel.spec_id.split("-")[:2])] += 1

    candidates: list[Candidate] = []
    for group_id, specs in group_specs.items():
        signals = _group_signals(group_id, specs, adr_by_num, reg, flagged_ids)
        if signals:
            candidates.append(
                Candidate(
                    id=group_id,
                    kind="spec-group",
                    blast_radius=inbound.get(group_id, 0),
                    signals=signals,
                )
            )
    return candidates


def build_inventory(
    root: Path | None = None, kinds: tuple[str, ...] = ("adr", "spec")
) -> list[Candidate]:
    """Return all scored candidates, highest risk first.

    Candidates with a positive score are sorted by score desc, then blast
    radius desc; ties break on id for stable output.
    """
    root = root or _find_repo_root()
    flagged_ids = _ids_near_problem_words(_load_learnings_text(root))

    # Load each registry once and share — load_registry is ~2s, so loading it
    # per candidate-builder doubled the runtime.
    reg = load_registry(root / "specs")
    adr_reg = load_adr_registry(root)
    adr_by_num = {Path(k).name.split("-")[0]: v for k, v in adr_reg.items()}

    candidates: list[Candidate] = []
    if "adr" in kinds:
        candidates += _adr_candidates(root, flagged_ids, adr_reg, reg)
    if "spec" in kinds:
        candidates += _spec_group_candidates(flagged_ids, adr_by_num, reg)
    return sorted(
        candidates,
        key=lambda c: (-c.score, -c.blast_radius, c.id),
    )


def _format_table(candidates: list[Candidate]) -> str:
    if not candidates:
        return "No landmine candidates found."
    lines = [
        f"{'SCORE':>5}  {'BLAST':>5}  {'KIND':<10}  {'ID':<14}  SIGNALS",
        "-" * 78,
    ]
    for c in candidates:
        lines.append(
            f"{c.score:>5}  {c.blast_radius:>5}  {c.kind:<10}  {c.id:<14}  "
            + "; ".join(c.signals)
        )
    return "\n".join(lines)


def main() -> None:
    """CLI entry point for the decision-audit Phase 1 inventory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--kind", choices=["adr", "spec", "both"], default="both"
    )
    args = parser.parse_args()

    kinds = ("adr", "spec") if args.kind == "both" else (args.kind,)
    candidates = build_inventory(kinds=kinds)
    if args.top is not None:
        candidates = candidates[: args.top]

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": c.id,
                        "kind": c.kind,
                        "score": c.score,
                        "blast_radius": c.blast_radius,
                        "signals": c.signals,
                    }
                    for c in candidates
                ],
                indent=2,
            )
        )
    else:
        print(_format_table(candidates))
    sys.exit(0)


if __name__ == "__main__":
    main()
