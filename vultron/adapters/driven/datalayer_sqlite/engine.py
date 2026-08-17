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
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import Engine, event
from sqlalchemy.pool import NullPool, StaticPool
from sqlmodel import create_engine

#: Characters permitted in a per-actor filename slug.  Everything else is
#: collapsed to ``_`` so that an actor URI can never escape the configured
#: database directory or collide with a shell metacharacter.
_SLUG_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")

#: Slugs that would be ambiguous or dangerous as a path component.
_RESERVED_SLUGS = frozenset({"", ".", ".."})


def _is_memory_url(db_url: str) -> bool:
    """Return ``True`` when *db_url* names an in-memory SQLite database."""
    return ":memory:" in db_url


def actor_slug(actor_id: str) -> str:
    """Return a filesystem-safe slug identifying *actor_id*.

    The slug is the final path segment of the actor's canonical URI, so it is
    reversible: given the node's configured base URL, ``slug`` maps back to
    ``{base_url}actors/{slug}``.  That reversibility is what lets the node
    enumerate the actors it hosts from the set of per-actor database files
    without a separate registry (ADR-0066).

    Two actors hosted by one node cannot share a slug, because under ADR-0066
    the URL path segment *is* the actor's identity within that node — same
    segment means same actor.

    Args:
        actor_id: The actor's canonical URI.

    Returns:
        A slug safe to embed in a filename.

    Raises:
        ValueError: If *actor_id* is empty or yields no usable slug.
    """
    if not actor_id:
        raise ValueError("actor_id must be a non-empty canonical actor URI")

    # Use the URL path when the id parses as a URI; fall back to the raw
    # string for opaque ids such as ``urn:uuid:...`` or bare test names.
    path = urlsplit(actor_id).path or actor_id
    segment = path.rstrip("/").rsplit("/", 1)[-1]
    slug = _SLUG_UNSAFE_RE.sub("_", segment)

    if slug in _RESERVED_SLUGS:
        # An actor id that degenerates to nothing usable (e.g. "/" or "..")
        # must fail loudly rather than silently share a store with another.
        raise ValueError(
            f"actor_id {actor_id!r} yields no usable storage slug"
        )
    return slug


def actor_db_url(db_url: str, actor_id: str) -> str:
    """Return the per-actor database URL derived from *db_url*.

    Under ADR-0066 every actor gets its own store, so the configured
    ``db_url`` is a **template** rather than a location:

    - ``sqlite:////app/data/mydb.sqlite`` becomes
      ``sqlite:////app/data/mydb-vendor.sqlite``
    - ``sqlite:///:memory:`` is returned unchanged; in-memory isolation comes
      from each actor getting its own :class:`~sqlalchemy.engine.Engine`, since
      two engines on ``:memory:`` never share a database.

    Args:
        db_url: The configured SQLAlchemy URL template.
        actor_id: The actor's canonical URI.

    Returns:
        A SQLAlchemy URL naming that actor's own store.
    """
    if _is_memory_url(db_url):
        return db_url

    scheme, _, location = db_url.partition("///")
    if not location:
        # Not a shape we can rewrite (e.g. a non-SQLite URL).  Returning it
        # unchanged would silently put two actors in one store, so refuse.
        raise ValueError(
            f"cannot derive a per-actor database URL from {db_url!r}; "
            "expected a sqlite:/// URL or an in-memory URL"
        )

    slug = actor_slug(actor_id)
    path = Path(location)
    stem = path.stem or "vultron"
    suffix = path.suffix or ".sqlite"
    return f"{scheme}///{path.with_name(f'{stem}-{slug}{suffix}')}"


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


#: Process-level engine cache keyed by ``(db_url_template, actor_id)``.
#:
#: Two DataLayer instances for the **same** actor must share one engine, or an
#: in-memory store would silently split in two: :func:`actor_db_url` returns
#: ``sqlite:///:memory:`` unchanged, and two engines on ``:memory:`` never share
#: a database.  Two *different* actors must never share an engine — that is
#: exactly the isolation ADR-0066 requires — so the actor id is part of the key.
_ENGINES: dict[tuple[str, str], Engine] = {}


def get_actor_engine(db_url: str, actor_id: str) -> Engine:
    """Return the cached engine for *actor_id*, creating it if needed.

    Args:
        db_url: The configured SQLAlchemy URL template.
        actor_id: The actor's canonical URI.

    Returns:
        The :class:`~sqlalchemy.engine.Engine` backing that actor's own store.
    """
    key = (db_url, actor_id)
    engine = _ENGINES.get(key)
    if engine is None:
        engine = make_engine(actor_db_url(db_url, actor_id))
        _ENGINES[key] = engine
    return engine


def dispose_actor_engines(
    db_url: str | None = None, actor_id: str | None = None
) -> None:
    """Dispose cached engines, releasing their SQLite connections.

    For in-memory stores disposal also *destroys* the database, since the
    database exists only as long as a connection to it is open.  That is what
    makes this the correct reset primitive for tests.

    Args:
        db_url: Restrict disposal to this URL template, or ``None`` for any.
        actor_id: Restrict disposal to this actor, or ``None`` for all actors.
    """
    for key in [
        k
        for k in _ENGINES
        if (db_url is None or k[0] == db_url)
        and (actor_id is None or k[1] == actor_id)
    ]:
        _ENGINES.pop(key).dispose()


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
    is_memory = _is_memory_url(db_url)
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
