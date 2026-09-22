"""Turning a ``Bundle`` into the report a human reads.

PAD-15-006 requires every excluded candidate to carry a reason, and requires the
two exclusion stages to stay distinguishable: a candidate held back for size or
tier is a different finding from one that is blocked or already claimed, and a
human acts on them differently.
"""

from __future__ import annotations

from vultron.metadata.planning.bundle_fit.model import Bundle


def _render(bundle: Bundle) -> str:
    """Human-readable proposal, including the reasoning behind each choice."""
    lines: list[str] = []
    epic = f"#{bundle.epic}" if bundle.epic else "(unknown Epic)"
    tier = bundle.epic_schedule or "unset"
    if bundle.members:
        lines.append(
            f"Proposed /{bundle.workflow} bundle for Epic {epic} "
            f"(Epic Schedule={tier}) — size {bundle.weight}/{bundle.budget}:"
        )
        for i, c in enumerate(bundle.members, 1):
            sched = c.schedule or f"inherits {tier}"
            lines.append(
                f"  {i}. #{c.number} [{c.issue_type} {c.size_label} "
                f"Schedule={sched} weight={c.weight}] {c.title}"
            )
        lines.append("")
        lines.append(f"Run: {bundle.command}")
    else:
        lines.append(f"No bundle for Epic {epic} — no candidate cleared fit.")

    if bundle.hints:
        lines.append("")
        lines.append("Coherence hints (evidence, not a verdict):")
        lines.extend(f"  - {h}" for h in bundle.hints)

    # PAD-15-007: the grain call is the agent's, so the report asks for it
    # rather than scoring it.
    lines.append("")
    lines.append(
        "State the single design idea these members share in one sentence. "
        "If a member needs a different sentence, drop it from the bundle."
    )

    for stage, heading in (
        ("fit", "Held back by fit (workable, but not in this bundle)"),
        ("eligibility", "Not workable yet"),
    ):
        rows = [r for r in bundle.rejected if r.stage == stage]
        # Closed sub-issues stay in `rejected` so the API accounts for every
        # candidate, but a long Epic has dozens of them and listing finished
        # work under "not workable" buries the rows a human can act on.
        rows = [r for r in rows if not r.reason.startswith("closed")]
        if rows:
            lines.append("")
            lines.append(f"{heading}:")
            lines.extend(f"  - #{r.number}: {r.reason}" for r in rows)
    return "\n".join(lines)
