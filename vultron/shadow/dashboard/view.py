#!/usr/bin/env python

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

"""What the dashboard shows, as plain rows: the scoreboard's words and icons.

Every function here reads a :class:`~vultron.shadow.analysis.CaseAnalysis`
and returns strings and rows, with no Streamlit call, so what an analyst
reads is tested without a browser.  :mod:`~vultron.shadow.dashboard.page`
lays the rows out.

A state reads as an icon and a short label, so the page reads at a glance
(ADR-0192).  The open moves are read from the case's
:class:`~vultron.measure.advice.CaseAdvice` (ADR-0200): each band in its
order, each move shaded by its layer and marked as the advice marks it, and
each vendor's harm on its own.  No column combines the vendors' numbers into
one score, and nothing here reorders a move (SHD-03-002).

The case narrative reads one row per ledger entry
(:func:`narrative_rows`), each with its state changes in words, and a
case-state flag the source cannot observe shown as unknown (CRD-02-005).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from fractions import Fraction

from pydantic import BaseModel, ConfigDict, model_validator

from vultron.core.models._helpers import format_timestamp
from vultron.core.models.case_reading import CaseReading
from vultron.core.states.cs import (
    AttackObservation,
    ExploitPublication,
    PublicAwareness,
)
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.measure.advice import (
    AdvisedMove,
    Band,
    BandAdvice,
    CaseAdvice,
    ColourMap,
)
from vultron.measure.advice.case import AllowedMove
from vultron.measure.baselines import EventKind
from vultron.measure.history import (
    NarrativeLine,
    PxaName,
    StateChange,
    StateMachine,
)
from vultron.measure.ledger import (
    MISSING_SLOT,
    UNNAMED_ACTOR,
    display_label,
)
from vultron.measure.scoring import UnscoredScope
from vultron.measure.standing import (
    DesideratumStanding,
    DesideratumStatus,
    ParticipantStanding,
    StandingGap,
)

#: A row of a table the page shows, column name to cell: text, or a number
#: that sorts as one, such as a move's layer.
Row = dict[str, str | int]

#: Each case-state event's name, as the CS model pages spell it.
EVENT_LABELS: Mapping[CSEvent, str] = {
    CSEvent.V: "Vendor Awareness",
    CSEvent.F: "Fix Ready",
    CSEvent.D: "Fix Deployed",
    CSEvent.P: "Public Awareness",
    CSEvent.X: "Exploit Public",
    CSEvent.A: "Attacks Observed",
}

#: Each event a desideratum can order, by name: the six case-state events
#: as :data:`EVENT_LABELS` spells them, the report and embargo events as
#: ``_case_events.md`` and ``process_model_desiderata.md`` name them where
#: they do, and the rest as :class:`~vultron.measure.baselines.EventKind`
#: describes them.  Every kind has a name, so a desideratum added to the
#: catalog reads in words with no change here.
DESIDERATUM_EVENT_LABELS: Mapping[EventKind, str] = {
    **{EventKind(e.value): label for e, label in EVENT_LABELS.items()},
    EventKind.INVALIDATED: "Report Invalidation",
    EventKind.VALIDATED: "Report Validation",
    EventKind.DEFERRED: "Report Deferral",
    EventKind.ACCEPTED: "Report Acceptance",
    EventKind.CLOSED: "Report Closure",
    EventKind.EMBARGO_PROPOSED: "Embargo Proposal",
    EventKind.EMBARGO_REJECTED: "Embargo Rejection",
    EventKind.EMBARGO_CANCELLED: "Embargo Proposal Cancelled",
    EventKind.EMBARGO_START: "Embargo Start",
    EventKind.REVISION_PROPOSED: "Embargo Revision Proposal",
    EventKind.REVISION_SETTLED: "Embargo Revision Settled",
    EventKind.EXIT: "Embargo Exit",
    EventKind.EXIT_OWN_TERMS: "Embargo Exit on Its Own Terms",
    EventKind.EXIT_THREAT: "Embargo Exit on a Threat Signal",
    EventKind.EXIT_OTHER: "Other Early Embargo Exit",
}

#: A desideratum's status as an icon and a word.
DESIDERATUM_BADGES: Mapping[DesideratumStatus, str] = {
    DesideratumStatus.MET: "✅ met",
    DesideratumStatus.BROKEN: "❌ broken",
    DesideratumStatus.OPEN: "⏳ open",
    DesideratumStatus.UNKNOWN: "❔ unknown",
    DesideratumStatus.UNSCORED: "▫️ not scored",
}

#: The statuses a tally counts only when a desideratum has one: a source
#: that observes every event, and a vendor its walk reads, show no empty
#: count for them.
_COUNTED_WHEN_SEEN = frozenset(
    {DesideratumStatus.UNKNOWN, DesideratumStatus.UNSCORED}
)

#: Why the Desiderata table has no row for ``V_i ≺ F_j``, which the
#: desiderata page lists.  The page's other multi-party desideratum,
#: ``F_i ≺ P``, is each vendor's ``F ≺ P`` row, so it needs no note.
DESIDERATA_NOTE = (
    "The table leaves out V_i ≺ F_j (every vendor aware before any fix is"
    " ready): move advice does not use it (ADR-0200)."
)

#: A report-management state as an icon and a word.
RM_BADGES: Mapping[RM, str] = {
    RM.START: "⚪ Start",
    RM.RECEIVED: "📥 Received",
    RM.INVALID: "🚫 Invalid",
    RM.VALID: "☑️ Valid",
    RM.DEFERRED: "⏸️ Deferred",
    RM.ACCEPTED: "▶️ Accepted",
    RM.CLOSED: "⏹️ Closed",
}

#: The case's embargo-management state as an icon and a word.
EM_BADGES: Mapping[EM, str] = {
    EM.NONE: "➖ No embargo",
    EM.PROPOSED: "📨 Embargo proposed",
    EM.ACTIVE: "🔒 Embargo active",
    EM.REVISE: "✏️ Revision proposed",
    EM.EXITED: "🔓 Embargo exited",
}

#: What an untranslated or unobservable fact means for the scores.
NOT_TRANSLATED_NOTE = (
    "The case reader could not translate these facts, so the states and"
    " scores above do not count them."
)
UNOBSERVABLE_NOTE = (
    "The source never records these facts, so the page reads each one as"
    " unknown, not as false."
)


def actor_label(actor: str, names: Mapping[str, str]) -> str:
    """*actor* by its display name, never a bare URI or UUID (DRPT-03-009).

    An actor no payload names reads by the last segment of its URI, and one
    whose id is opaque, as an outside system's ``urn:uuid:`` id is, reads
    as :data:`~vultron.measure.ledger.UNNAMED_ACTOR`.
    """
    return display_label(actor, "Actor", names) or UNNAMED_ACTOR


def desideratum_label(desideratum: DesideratumStanding) -> str:
    """The desideratum in words: ``Fix Ready before Public Awareness``."""
    return (
        f"{DESIDERATUM_EVENT_LABELS[desideratum.before]} before"
        f" {DESIDERATUM_EVENT_LABELS[desideratum.after]}"
    )


def desideratum_code(desideratum: DesideratumStanding) -> str:
    """The desideratum in event letters: ``F ≺ P``."""
    return f"{desideratum.before.value} ≺ {desideratum.after.value}"


def public_badges(pxa: PxaName) -> tuple[str, str, str]:
    """The case's public state as three badges: public, exploit, attacks."""
    state = pxa.value
    return (
        "📢 Public aware"
        if state.public_awareness is PublicAwareness.PUBLIC_AWARE
        else "🤫 Not public",
        "💥 Exploit public"
        if state.exploit_publication is ExploitPublication.EXPLOIT_PUBLIC
        else "🛡️ No public exploit",
        "🎯 Attacks observed"
        if state.attack_observation is AttackObservation.ATTACKS_OBSERVED
        else "🛡️ No attacks observed",
    )


def _tally(desiderata: Sequence[DesideratumStanding]) -> str:
    """Each status's count; unknown or unscored only when a desideratum is
    (:data:`_COUNTED_WHEN_SEEN`)."""
    counts = Counter(d.status for d in desiderata)
    return "  ".join(
        f"{DESIDERATUM_BADGES[status].split()[0]} {counts[status]}"
        for status in DesideratumStatus
        if counts[status] or status not in _COUNTED_WHEN_SEEN
    )


def _not_scored_because(participant: ParticipantStanding) -> str:
    """Why the participant, or part of its scope, has no score; empty when
    all of it is scored.

    A participant with no case-state sequence says why it has none.  A
    vendor whose walk cannot go on from its case keeps its original
    desiderata's statuses, so the reason names the part left unscored.
    """
    if participant.unscored is not None:
        return participant.unscored.detail
    if isinstance(participant.extended, UnscoredScope):
        return (
            "report-handling and embargo desiderata:"
            f" {participant.extended.reason}"
        )
    return ""


def participant_rows(
    participants: Sequence[ParticipantStanding], names: Mapping[str, str]
) -> list[Row]:
    """One row per participant: roles, report state, case state, tally."""
    rows: list[Row] = []
    for p in participants:
        rows.append(
            {
                "Participant": actor_label(p.participant, names),
                "Roles": ", ".join(p.roles) or "—",
                "Joined": "✔️ joined" if p.joined else "✉️ invited",
                "Report": RM_BADGES[p.rm],
                "Case state": p.case_state.name
                if p.case_state is not None
                else "—",
                "Desiderata": _tally(p.desiderata) if p.desiderata else "—",
                "Not scored because": _not_scored_because(p),
                "Actor": p.participant,
            }
        )
    return rows


def _vendor_columns(
    scored: Sequence[ParticipantStanding], names: Mapping[str, str]
) -> list[str]:
    """One column name per scored vendor, never one another's or a fixed one.

    A vendor's short label names its column.  A label two vendors share, or
    that a fixed column already uses, takes the vendor's actor id as well,
    so no vendor's column overwrites another's.
    """
    labels = [actor_label(p.participant, names) for p in scored]
    taken = Counter(labels) + Counter(_DESIDERATA_COLUMNS)
    return [
        label if taken[label] == 1 else f"{label} ({p.participant})"
        for label, p in zip(labels, scored, strict=True)
    ]


#: The desiderata table's own columns, before one column per vendor.
_DESIDERATA_COLUMNS = ("Desideratum", "Events")


def desiderata_rows(
    participants: Sequence[ParticipantStanding], names: Mapping[str, str]
) -> list[Row]:
    """One row per desideratum of a vendor's scope, one status column per
    scored vendor.

    The rows are the desiderata move advice sums, in catalog order, each
    group of equivalent ones once under its first
    (:func:`~vultron.measure.baselines.scope_desiderata`), so a desideratum
    added to that list gets a row with no change here.
    """
    scored = [p for p in participants if p.desiderata]
    if not scored:
        return []
    columns = _vendor_columns(scored, names)
    rows: list[Row] = []
    for position, desideratum in enumerate(scored[0].desiderata):
        row: Row = dict(
            zip(
                _DESIDERATA_COLUMNS,
                (
                    desideratum_label(desideratum),
                    desideratum_code(desideratum),
                ),
                strict=True,
            )
        )
        for column, p in zip(columns, scored, strict=True):
            row[column] = DESIDERATUM_BADGES[p.desiderata[position].status]
        rows.append(row)
    return rows


def _move_label(move: AllowedMove) -> tuple[str, str]:
    machine, _, trigger = move.name.partition(".")
    return machine.upper(), trigger.replace("_", " ").capitalize()


def _move_cells(move: AllowedMove, names: Mapping[str, str]) -> Row:
    """Who makes *move*, in which machine, and from which state to which."""
    machine, label = _move_label(move)
    return {
        "Who": actor_label(move.participant, names),
        "Machine": machine,
        "Move": label,
        "From → to": f"{move.source.name} → {move.destination.name}",
    }


#: Each band's heading on the page.
BAND_TITLES: Mapping[Band, str] = {
    Band.HARM_FREE: "Harm-free",
    Band.TRADE_OFF: "Trade-off",
    Band.UNHELPFUL: "Unhelpful",
}

#: Each band's caption when no open move falls in it.
BAND_EMPTY: Mapping[Band, str] = {
    Band.HARM_FREE: "No open move helps a vendor and harms none.",
    Band.TRADE_OFF: "No open move helps one vendor at another's cost.",
    Band.UNHELPFUL: "No open move is unhelpful.",
}

#: The icon a top move carries: a harm-free or trade-off move in layer 1.
TOP_MARK = "⭐ top"

#: The mark on a coordinator's move none of its other moves dominates.
LEADING_MARK = "👉 leading among yours"

#: Nine evenly spaced stops of each colour map, dark end first, as
#: matplotlib draws them, so the page shades without matplotlib.
COLOUR_STOPS: Mapping[ColourMap, tuple[str, ...]] = {
    ColourMap.VIRIDIS: (
        "#440154",
        "#472d7b",
        "#3b528b",
        "#2c728e",
        "#21918c",
        "#28ae80",
        "#5ec962",
        "#addc30",
        "#fde725",
    ),
    ColourMap.CIVIDIS: (
        "#00224e",
        "#1a386f",
        "#434e6c",
        "#61656f",
        "#7d7c78",
        "#9b9476",
        "#bcae6c",
        "#dec958",
        "#fee838",
    ),
}

#: The relative luminance at which black and white text have the same
#: WCAG contrast ratio: above it, black text reads better.
_LIGHT_BACKGROUND = 0.179


class Shade(BaseModel):
    """The colours of one shaded move's row.

    Fields:
        background: The row's fill, from its band's colour map.
        text: Black or white, whichever reads on *background*.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    background: str
    text: str

    @property
    def css(self) -> str:
        """The row's style, as a table cell's CSS."""
        return f"background-color: {self.background}; color: {self.text}"


type _RGB = tuple[float, float, float]


def _rgb(hex_colour: str) -> _RGB:
    return (
        int(hex_colour[1:3], 16),
        int(hex_colour[3:5], 16),
        int(hex_colour[5:7], 16),
    )


def _luminance(rgb: _RGB) -> float:
    """WCAG relative luminance of an sRGB colour, 0 (black) to 1 (white)."""

    def linear(channel: float) -> float:
        c = channel / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def shade(colour_map: ColourMap, layer: int, deepest: int) -> Shade:
    """*layer*'s shade in *colour_map*: layer 1 at the dark end, *deepest*
    at the light end, and every layer between spaced evenly.

    Raises:
        ValueError: *layer* is not from 1 to *deepest*.
    """
    if not 1 <= layer <= deepest:
        raise ValueError(f"layer {layer} is not from 1 to {deepest}")
    stops = COLOUR_STOPS[colour_map]
    at = 0.0 if deepest == 1 else (layer - 1) / (deepest - 1)
    position = at * (len(stops) - 1)
    low = min(int(position), len(stops) - 2)
    within = position - low
    lo, hi = _rgb(stops[low]), _rgb(stops[low + 1])
    rgb: _RGB = (
        lo[0] + (hi[0] - lo[0]) * within,
        lo[1] + (hi[1] - lo[1]) * within,
        lo[2] + (hi[2] - lo[2]) * within,
    )
    return Shade(
        background="#" + "".join(f"{round(c):02x}" for c in rgb),
        text="#000000" if _luminance(rgb) > _LIGHT_BACKGROUND else "#ffffff",
    )


def _size(size: Fraction) -> str:
    return f"{float(size):.3g}".replace("-", "−")


def harm_text(move: AdvisedMove, names: Mapping[str, str]) -> str:
    """Each negative part of *move*'s shift, by vendor, with its size."""
    return (
        "; ".join(
            f"{actor_label(h.vendor, names)}: {h.part} {_size(h.size)}"
            for h in move.harms
        )
        or "none"
    )


class BandView(BaseModel):
    """One band of the move advice, as the page lays it out.

    Fields:
        band: The band.
        title: Its heading.
        collapsed: Whether the page shows it as a closed group.
        rows: One row per move, in the advice's order.
        shades: Each row's shade, in row order: one per row in the
            harm-free and trade-off bands, none in the unhelpful band.
        empty: What the page says when *rows* is empty.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    band: Band
    title: str
    collapsed: bool
    rows: tuple[Row, ...]
    shades: tuple[Shade, ...] = ()
    empty: str

    @property
    def shaded(self) -> bool:
        """Whether its rows are shaded by layer: all but the unhelpful band."""
        return self.band is not Band.UNHELPFUL

    @model_validator(mode="after")
    def _a_shade_for_every_row_or_none(self) -> BandView:
        """A shaded band has one shade per row; the unhelpful band none."""
        if not self.shaded:
            if self.shades:
                raise ValueError("the unhelpful band is not shaded")
        elif len(self.shades) != len(self.rows):
            raise ValueError(
                f"{len(self.shades)} shades for {len(self.rows)} rows"
            )
        return self


def _layer(move: AdvisedMove) -> int:
    assert move.layer is not None, "a move in a shaded band has a layer"
    return move.layer


def _deepest(advice: CaseAdvice) -> int:
    return max(
        (m.layer for m in advice.moves if m.layer is not None), default=1
    )


def _advised_row(
    move: AdvisedMove, band: BandAdvice, names: Mapping[str, str]
) -> Row:
    shaded = band.colour_map is not None
    row: Row = {"Layer": _layer(move)} if shaded else {}
    if shaded:
        row["Mark"] = TOP_MARK if move.top else ""
    row.update(_move_cells(move.move, names))
    if shaded:
        row["Yours"] = LEADING_MARK if move.leading_among_yours else ""
    row["Harms by vendor"] = harm_text(move, names)
    if band.band is Band.TRADE_OFF:
        row["Dominated by"] = move.dominated_by_harm_free or ""
    return row


def band_views(advice: CaseAdvice, names: Mapping[str, str]) -> list[BandView]:
    """Each band of *advice*, in its order: harm-free, trade-off, unhelpful.

    A harm-free or trade-off move is shaded by its layer in its band's
    colour map, with a mark when it is top or leading among yours; an
    unhelpful move has neither.  Nothing here orders or scores a move: the
    moves keep the advice's order (SHD-03-002).
    """
    deepest = _deepest(advice)
    views = []
    for band in advice.bands:
        colour_map = band.colour_map
        views.append(
            BandView(
                band=band.band,
                title=BAND_TITLES[band.band],
                collapsed=band.collapsed,
                rows=tuple(_advised_row(m, band, names) for m in band.moves),
                shades=()
                if colour_map is None
                else tuple(
                    shade(colour_map, _layer(m), deepest) for m in band.moves
                ),
                empty=BAND_EMPTY[band.band],
            )
        )
    return views


def unbanded_rows(advice: CaseAdvice, names: Mapping[str, str]) -> list[Row]:
    """One row per allowed move with no band, with the reason it has none."""
    return [
        {**_move_cells(u.move, names), "Why no band": u.reason}
        for u in advice.unbanded
    ]


def gap_lines(gap: StandingGap) -> list[str]:
    """Each hole that keeps the ledger from a standing, in words."""
    lines = []
    if gap.missing_log_indices:
        lines.append(f"Missing log indices: {gap.missing_log_indices}")
    if gap.conflicting_log_indices:
        lines.append(f"Conflicting log indices: {gap.conflicting_log_indices}")
    lines.extend(row.describe() for row in gap.unusable_rows)
    lines.extend(
        f"Unreadable entry at log index {entry.log_index}: {entry.reason}"
        for entry in gap.unreadable_entries
    )
    if gap.register_problem is not None:
        # Already worded as an embargo register problem (derive_em).
        lines.append(gap.register_problem)
    return lines


#: The case-state event each letter of a ``vfd`` or ``pxa`` spelling
#: stands for, by its lower-case letter.
_CS_LETTERS: Mapping[str, CSEvent] = {
    event.value.lower(): event for event in CSEvent
}

#: What the page shows for a case-state flag its source cannot observe.
UNKNOWN_FLAG = "?"


def cs_spelling(state: str, unobservable: frozenset[CSEvent]) -> str:
    """A ``vfd`` or ``pxa`` spelling, each flag the source cannot observe
    shown as ``?``.

    A lower-case letter says its event has not happened, which a source
    that never records the event cannot say (CRD-02-005).
    """
    return "".join(
        UNKNOWN_FLAG
        if letter.islower() and _CS_LETTERS.get(letter) in unobservable
        else letter
        for letter in state
    )


def _state_label(
    machine: StateMachine, state: str, unobservable: frozenset[CSEvent]
) -> str:
    if machine is StateMachine.RM:
        return RM_BADGES[RM[state]]
    if machine is StateMachine.EM:
        return EM_BADGES[EM[state]]
    return cs_spelling(state, unobservable)


def change_text(
    change: StateChange,
    names: Mapping[str, str],
    unobservable: frozenset[CSEvent] = frozenset(),
) -> str:
    """One state change in words: ``Vendor RM: 📥 Received → ☑️ Valid``.

    The participant reads by its display name, never a bare URI or UUID
    (DRPT-03-009).
    """
    who = (
        f"{actor_label(change.participant, names)} "
        if change.participant is not None
        else ""
    )
    before, after = (
        _state_label(change.machine, state, unobservable)
        for state in (change.before, change.after)
    )
    return f"{who}{change.machine}: {before} → {after}"


def narrative_rows(
    lines: Sequence[NarrativeLine],
    names: Mapping[str, str],
    unobservable: frozenset[CSEvent] = frozenset(),
) -> list[Row]:
    """One row per line of the case narrative, in log-index order.

    The time is the one the entry's activity claims; the commit stamp shows
    only where it differs, each in its own column, so neither stands in for
    the other (CEH-03-008).  The ``#`` column is the entry's log index.
    A line that could not read its entry in full says why, in a notes column
    the table has only when some line needs it.
    """
    noted = any(line.notes for line in lines)
    rows: list[Row] = []
    for line in lines:
        row: Row = {
            "#": line.log_index,
            "Time": format_timestamp(line.claimed_at)
            if line.claimed_at is not None
            else MISSING_SLOT,
            "Committed": format_timestamp(line.committed_at)
            if line.committed_at is not None and line.commit_differs
            else "",
            "Actor": line.actor or MISSING_SLOT,
            "Activity": line.phrase,
            "Object": line.object or MISSING_SLOT,
            "State changes": "; ".join(
                change_text(change, names, unobservable)
                for change in line.changes
            ),
        }
        if noted:
            row["Notes"] = "; ".join(line.notes)
        rows.append(row)
    return rows


def untranslated_rows(reading: CaseReading) -> list[Row]:
    """One row per fact the case reader could not translate (SHD-01-004)."""
    return [
        {
            "Source record": fact.source_record,
            "Fact": fact.fact,
            "Why": fact.reason.value.replace("_", " "),
        }
        for fact in reading.untranslated
    ]


def inference_rows(reading: CaseReading) -> list[Row]:
    """One row per state or time the source implied (CRD-02-002)."""
    return [
        {
            "Entry": inference.entry_id,
            "Rule": inference.rule_id,
            "Caveat": inference.caveat,
        }
        for inference in reading.inferences
    ]


def unobservable_rows(reading: CaseReading) -> list[Row]:
    """One row per fact the source never records, with the case-state
    events it makes the page read as unknown (CRD-02-005)."""
    return [
        {
            "Fact": fact.fact,
            "Why": fact.why,
            "Reads as unknown": ", ".join(
                EVENT_LABELS[event]
                for event in CSEvent
                if event in fact.events
            )
            or "—",
        }
        for fact in reading.unobservable
    ]


__all__ = [
    "BAND_EMPTY",
    "BAND_TITLES",
    "COLOUR_STOPS",
    "DESIDERATA_NOTE",
    "DESIDERATUM_BADGES",
    "DESIDERATUM_EVENT_LABELS",
    "LEADING_MARK",
    "TOP_MARK",
    "UNKNOWN_FLAG",
    "BandView",
    "Shade",
    "EM_BADGES",
    "EVENT_LABELS",
    "NOT_TRANSLATED_NOTE",
    "RM_BADGES",
    "UNOBSERVABLE_NOTE",
    "actor_label",
    "Row",
    "desiderata_rows",
    "desideratum_code",
    "desideratum_label",
    "gap_lines",
    "inference_rows",
    "band_views",
    "change_text",
    "cs_spelling",
    "narrative_rows",
    "harm_text",
    "shade",
    "unbanded_rows",
    "participant_rows",
    "public_badges",
    "unobservable_rows",
    "untranslated_rows",
]
