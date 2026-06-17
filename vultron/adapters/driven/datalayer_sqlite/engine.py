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

"""SQLAlchemy engine setup and JSON serialization for SQLite."""

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy.pool import NullPool, StaticPool
from sqlmodel import create_engine


def json_default(obj: Any) -> Any:
    """JSON encoder fallback that serializes ``datetime`` / ``date`` objects."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(
        f"Object of type {type(obj).__name__} is not JSON serializable"
    )


def json_serializer(value: Any) -> str:
    """Serialize *value* to a JSON string, handling datetime objects."""
    return json.dumps(value, default=json_default)


def make_engine(db_url: str) -> Engine:
    """Create a SQLAlchemy engine for the given URL.

    For in-memory databases uses ``StaticPool`` so every connection
    shares the same in-memory database instead of creating a fresh one.
    For file-backed SQLite uses ``NullPool`` (one fresh connection per
    ``Session``) and enables WAL mode so that concurrent readers always
    observe the most recently committed writes. Together these prevent
    read-after-write staleness in the asyncio + ``BackgroundTasks`` +
    SQLite combination used by the FastAPI driving adapter, which
    otherwise can return stale rows for tens of seconds under CI load
    (see issue #659).

    A custom ``json_serializer`` ensures that ``datetime`` values stored in
    JSON columns are serialised as ISO-8601 strings instead of raising
    ``TypeError``.

    Args:
        db_url: SQLAlchemy connection URL.

    Returns:
        Configured :class:`sqlalchemy.engine.Engine`.
    """
    kwargs: dict[str, Any] = {
        "connect_args": {"check_same_thread": False},
        "json_serializer": json_serializer,
    }
    is_memory = db_url == "sqlite:///:memory:"
    if is_memory:
        kwargs["poolclass"] = StaticPool
    else:
        # NullPool gives a fresh DB-API connection per Session. This avoids
        # the SingletonThreadPool default in which a BackgroundTask and a
        # concurrent GET handler can share one SQLite connection and observe
        # stale data across transactions.
        kwargs["poolclass"] = NullPool
    engine = create_engine(db_url, **kwargs)
    if not is_memory:
        # Enable WAL + NORMAL synchronous on every new connection so that
        # committed writes are immediately visible to subsequent readers.
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
            finally:
                cursor.close()

    return engine
