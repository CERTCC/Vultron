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

"""Tests for correlation ids on log records (SL-02-003, SL-02-004).

Every assertion reads record attributes or the formatter's output, never the
message text: an id named in the message does not satisfy SL-02 (SL-02-004).
Each test logs through its own logger with ``propagate=False`` and its own
handler, so nothing reaches or changes the root logger.
"""

import asyncio
import logging
import sys
import uuid
from collections.abc import Iterator

import pytest

from vultron.logging_correlation import (
    CORRELATION_FIELDS,
    DEFAULT_LOG_FORMAT,
    CorrelationFilter,
    CorrelationFormatter,
    correlation_context,
    current_correlation,
    install_correlation_logging,
)

ACTIVITY = "https://example.org/activities/a1"
ACTOR = "https://example.org/actors/vendor"


class _ListHandler(logging.Handler):
    """Keep every record it handles, after its filters have run."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def handler() -> _ListHandler:
    return _ListHandler()


@pytest.fixture
def logger(handler: _ListHandler) -> Iterator[logging.Logger]:
    log = logging.getLogger(f"test.logging_correlation.{uuid.uuid4().hex}")
    log.propagate = False
    log.setLevel(logging.DEBUG)
    log.addHandler(handler)
    yield log
    log.removeHandler(handler)


def _ids(record: logging.LogRecord) -> dict[str, object]:
    return {
        name: getattr(record, name)
        for name in CORRELATION_FIELDS
        if hasattr(record, name)
    }


# --- AC-1: context and filter ------------------------------------------------


@pytest.mark.spec("SL-02-003", "SL-02-004")
def test_filter_copies_both_ids_onto_the_record(handler, logger):
    """Inside the boundary, a record carries both ids as attributes."""
    handler.addFilter(CorrelationFilter())
    with correlation_context(activity_id=ACTIVITY, actor_id=ACTOR):
        logger.info("processing")
    (record,) = handler.records
    assert _ids(record) == {"activity_id": ACTIVITY, "actor_id": ACTOR}


@pytest.mark.spec("SL-02-003")
def test_unset_ids_are_absent_not_empty(handler, logger):
    """Outside any context, neither attribute exists on the record."""
    handler.addFilter(CorrelationFilter())
    logger.info("no boundary")
    (record,) = handler.records
    assert not hasattr(record, "activity_id")
    assert not hasattr(record, "actor_id")


@pytest.mark.spec("SL-02-003")
def test_only_the_id_that_is_set_is_copied(handler, logger):
    handler.addFilter(CorrelationFilter())
    with correlation_context(actor_id=ACTOR):
        logger.info("actor only")
    (record,) = handler.records
    assert _ids(record) == {"actor_id": ACTOR}


@pytest.mark.spec("SL-02-003")
def test_record_from_code_unaware_of_correlation_carries_the_ids(handler):
    """A child logger's record, propagated to the handler, is filtered too."""
    parent = logging.getLogger(f"test.logging_correlation.{uuid.uuid4().hex}")
    parent.propagate = False
    parent.setLevel(logging.DEBUG)
    parent.addHandler(handler)
    handler.addFilter(CorrelationFilter())
    try:
        with correlation_context(activity_id=ACTIVITY):
            logging.getLogger(f"{parent.name}.child").warning("deep")
    finally:
        parent.removeHandler(handler)
    (record,) = handler.records
    assert _ids(record) == {"activity_id": ACTIVITY}


def test_filter_never_drops_a_record():
    record = logging.LogRecord("n", logging.INFO, __file__, 1, "m", None, None)
    assert CorrelationFilter().filter(record) is True


def test_context_restores_previous_values_on_exit():
    assert current_correlation() == {}
    with correlation_context(activity_id=ACTIVITY, actor_id=ACTOR):
        assert current_correlation() == {
            "activity_id": ACTIVITY,
            "actor_id": ACTOR,
        }
    assert current_correlation() == {}


def test_nested_context_overrides_then_restores_the_outer_ids():
    """An inner boundary keeps outer ids it does not name and restores both."""
    with correlation_context(activity_id=ACTIVITY, actor_id=ACTOR):
        with correlation_context(actor_id="https://example.org/actors/cm"):
            assert current_correlation() == {
                "activity_id": ACTIVITY,
                "actor_id": "https://example.org/actors/cm",
            }
        assert current_correlation() == {
            "activity_id": ACTIVITY,
            "actor_id": ACTOR,
        }
    assert current_correlation() == {}


def test_context_restores_when_the_block_raises():
    with pytest.raises(RuntimeError):
        with correlation_context(activity_id=ACTIVITY):
            raise RuntimeError("boom")
    assert current_correlation() == {}


@pytest.mark.parametrize("blank", ["", "   "])
@pytest.mark.parametrize("field", ["activity_id", "actor_id"])
def test_blank_id_is_refused(field, blank):
    """A record never carries an empty correlation id."""
    with pytest.raises(ValueError, match=field):
        with correlation_context(**{field: blank}):
            pass  # pragma: no cover - never entered
    assert current_correlation() == {}


def test_concurrent_tasks_keep_their_own_ids():
    """contextvars isolate two interleaved boundaries from each other."""

    async def boundary(actor: str) -> dict[str, str]:
        with correlation_context(actor_id=actor):
            await asyncio.sleep(0)
            return current_correlation()

    async def main() -> list[dict[str, str]]:
        return list(await asyncio.gather(boundary("a"), boundary("b")))

    assert asyncio.run(main()) == [{"actor_id": "a"}, {"actor_id": "b"}]


# --- AC-2: install function and plain-text format ----------------------------


@pytest.mark.spec("SL-02-003")
def test_install_adds_filter_and_formatter(handler, logger):
    install_correlation_logging([handler])
    assert isinstance(handler.formatter, CorrelationFormatter)
    with correlation_context(activity_id=ACTIVITY, actor_id=ACTOR):
        logger.info("installed")
    (record,) = handler.records
    assert _ids(record) == {"activity_id": ACTIVITY, "actor_id": ACTOR}


def test_install_twice_adds_one_filter(handler):
    install_correlation_logging([handler])
    install_correlation_logging([handler])
    assert sum(isinstance(f, CorrelationFilter) for f in handler.filters) == 1


def test_install_covers_every_handler_given():
    handlers = [_ListHandler(), _ListHandler()]
    install_correlation_logging(handlers)
    for h in handlers:
        assert any(isinstance(f, CorrelationFilter) for f in h.filters)
        assert isinstance(h.formatter, CorrelationFormatter)


def _record(**ids: str) -> logging.LogRecord:
    record = logging.LogRecord(
        "vultron.x", logging.INFO, __file__, 1, "hello %s", ("world",), None
    )
    for name, value in ids.items():
        setattr(record, name, value)
    return record


@pytest.mark.spec("SL-01-003", "SL-02-003")
def test_format_prints_both_ids_beside_the_message():
    formatter = CorrelationFormatter("%(name)s: %(message)s")
    text = formatter.format(_record(activity_id=ACTIVITY, actor_id=ACTOR))
    assert text == (
        f"vultron.x: hello world [activity_id={ACTIVITY} actor_id={ACTOR}]"
    )


def test_format_prints_only_the_id_present():
    formatter = CorrelationFormatter("%(message)s")
    assert (
        formatter.format(_record(actor_id=ACTOR))
        == f"hello world [actor_id={ACTOR}]"
    )


def test_format_without_ids_matches_the_base_format():
    """With no ids the line renders exactly as a plain Formatter would."""
    record = _record()
    assert CorrelationFormatter(DEFAULT_LOG_FORMAT).format(
        record
    ) == logging.Formatter(DEFAULT_LOG_FORMAT).format(record)


def _raise_bad() -> None:
    raise ValueError("bad")


def test_ids_sit_on_the_message_line_before_a_traceback():
    try:
        _raise_bad()
    except ValueError:
        record = logging.LogRecord(
            "vultron.x",
            logging.ERROR,
            __file__,
            1,
            "failed",
            None,
            sys.exc_info(),
        )
    record.actor_id = ACTOR
    first_line, *rest = (
        CorrelationFormatter("%(message)s").format(record).splitlines()
    )
    assert first_line == f"failed [actor_id={ACTOR}]"
    assert rest[-1] == "ValueError: bad"


def test_install_uses_the_given_format(handler, logger):
    install_correlation_logging([handler], fmt="%(levelname)s %(message)s")
    with correlation_context(actor_id=ACTOR):
        logger.warning("w")
    (record,) = handler.records
    assert handler.format(record) == f"WARNING w [actor_id={ACTOR}]"
