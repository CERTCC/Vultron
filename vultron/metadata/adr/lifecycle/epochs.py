"""ADR lifecycle epochs and the status faults each epoch implies (ADR-0120)."""

from __future__ import annotations

import datetime as _dt
from enum import IntEnum

from vultron.metadata.adr.schema import AdrFrontmatter
from vultron.metadata.specs.schema import AdrStatus

#: Whole days of age at which epoch 2 and epoch 3 begin.
EPOCH_2_START_DAYS = 14


EPOCH_3_START_DAYS = 28


class AdrEpoch(IntEnum):
    """The three lifecycle epochs of ADR-0120."""

    PROPOSED = 1
    PROVISIONAL = 2
    SETTLED = 3


EPOCH_STATUS: dict[AdrEpoch, AdrStatus] = {
    AdrEpoch.PROPOSED: AdrStatus.PROPOSED,
    AdrEpoch.PROVISIONAL: AdrStatus.ACCEPTED_PROVISIONAL,
    AdrEpoch.SETTLED: AdrStatus.ACCEPTED,
}


_EPOCH_OF_STATUS: dict[AdrStatus, AdrEpoch] = {
    v: k for k, v in EPOCH_STATUS.items()
}


def today_utc() -> _dt.date:
    """Return today in UTC, the one clock the epochs are counted on."""
    return _dt.datetime.now(tz=_dt.UTC).date()


def epoch_for(
    updated: _dt.date, today: _dt.date, *, tested: bool = False
) -> AdrEpoch:
    """Return the epoch of an ADR last materially edited on ``updated``.

    ``tested`` says the ADR has a test-verified dependent, which ends epoch 1
    whatever the date (MS-14-007).
    """
    age = (today - updated).days
    if age >= EPOCH_3_START_DAYS:
        return AdrEpoch.SETTLED
    if tested or age >= EPOCH_2_START_DAYS:
        return AdrEpoch.PROVISIONAL
    return AdrEpoch.PROPOSED


def _effective_epoch(
    fm: AdrFrontmatter, today: _dt.date, *, tested: bool
) -> AdrEpoch:
    """Return the epoch an ADR is in for the edit tiers.

    The computed epoch is a floor, so a status already ahead of it stands
    (MS-14-012): this is the later of the two. A ``status_override`` is a
    human holding the status where it is, so the epoch its status names wins.
    """
    computed = epoch_for(fm.updated, today, tested=tested)
    named = _EPOCH_OF_STATUS.get(fm.status, computed)
    return named if fm.status_override else max(computed, named)


def _epoch_claim(
    name: str,
    fm: AdrFrontmatter,
    epoch: AdrEpoch,
    today: _dt.date,
    tested: bool,
) -> str:
    # Credit the dependent only when it, not the clock, ended epoch 1.
    decided = tested and epoch_for(fm.updated, today) is AdrEpoch.PROPOSED
    dependent = " and a test-verified dependent" if decided else ""
    return (
        f"{name}: status is '{fm.status.value}' but updated {fm.updated}"
        f"{dependent} put it in epoch {int(epoch)} "
        f"('{EPOCH_STATUS[epoch].value}') on {today}"
    )


def status_epoch_fault(
    name: str, fm: AdrFrontmatter, today: _dt.date, *, tested: bool = False
) -> str | None:
    """Describe a ``status`` that is not its epoch's, or return None.

    The rule for a material edit, which owns the status on its date
    (MS-14-007). Only ``proposed``, ``accepted-provisional`` and ``accepted``
    have an epoch. A ``status_override`` reason lets the disagreement stand.
    """
    if fm.status not in _EPOCH_OF_STATUS or fm.status_override:
        return None
    epoch = epoch_for(fm.updated, today, tested=tested)
    if fm.status is EPOCH_STATUS[epoch]:
        return None
    return (
        f"{_epoch_claim(name, fm, epoch, today, tested)} (MS-14-007); change "
        f"the status, or record a human's reason in 'status_override:'"
    )


def status_behind_fault(
    name: str, fm: AdrFrontmatter, today: _dt.date, *, tested: bool = False
) -> str | None:
    """Describe a ``status`` behind its epoch, or return None.

    The rule for the scheduled report. A status ahead of its epoch stands
    (MS-14-012), and a ``status_override`` reason holds one behind it.
    """
    status_epoch = _EPOCH_OF_STATUS.get(fm.status)
    if status_epoch is None or fm.status_override:
        return None
    epoch = epoch_for(fm.updated, today, tested=tested)
    if status_epoch >= epoch:
        return None
    return (
        f"{_epoch_claim(name, fm, epoch, today, tested)} (MS-14-007); flip "
        f"the status, or record a human's reason in 'status_override:'"
    )
