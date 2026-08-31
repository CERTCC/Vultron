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
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import Engine, event
from sqlalchemy.pool import NullPool, StaticPool
from sqlmodel import create_engine

logger = logging.getLogger(__name__)

#: Characters permitted in a per-actor filename slug.  Everything else is
#: collapsed to ``_`` so that an actor URI can never escape the configured
#: database directory or collide with a shell metacharacter.
_SLUG_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")

#: Slugs that would be ambiguous or dangerous as a path component.
_RESERVED_SLUGS = frozenset({"", ".", ".."})


#: Matches the ``file:NAME`` portion of a named in-memory SQLite URL.
_MEMORY_NAME_RE = re.compile(r"file:([^?]+)")

#: Default base name for in-memory stores when the template does not supply one.
_DEFAULT_MEMORY_BASE = "vultron"


def _is_memory_url(db_url: str) -> bool:
    """Return ``True`` when *db_url* names an in-memory SQLite database.

    Covers both the anonymous form (``sqlite:///:memory:``) and the named
    shared-cache form this module derives from it (``mode=memory``).
    """
    return ":memory:" in db_url or "mode=memory" in db_url


def _memory_base_name(db_url: str) -> str:
    """Return the base name a named in-memory URL is built around.

    A caller that needs several independent in-memory deployments in one
    process (notably ``create_app()``, which gives each application its own
    isolated storage per issue #534) distinguishes them by passing a *named*
    template such as ``sqlite:///file:app7?mode=memory&cache=shared&uri=true``.
    The name is carried through to each per-actor store, so two applications
    never collide even when they host the same actor.

    Note that :func:`actor_db_url` is **not** idempotent: applying it to an
    already-resolved URL appends a second slug.  Stripping one cannot be done
    unambiguously — base ``app7-vendor`` is indistinguishable from base
    ``app7`` plus slug ``vendor`` — so callers must pass the configured
    *template*, which is what ``SqliteDataLayer`` stores and what
    ``clone_for_actor`` forwards.

    Args:
        db_url: An in-memory SQLAlchemy URL, named or anonymous.

    Returns:
        The base name, or ``"vultron"`` for the anonymous form.
    """
    match = _MEMORY_NAME_RE.search(db_url)
    if match is None:
        return _DEFAULT_MEMORY_BASE
    return match.group(1)


def actor_slug(actor_id: str) -> str:
    """Return a filesystem-safe slug identifying *actor_id*.

    The slug is the final path segment of the actor's canonical URI, so it is
    reversible: given the node's configured base URL, ``slug`` maps back to
    ``{base_url}actors/{slug}``.  That reversibility is what lets the node
    enumerate the actors it hosts from the set of per-actor database files
    without a separate registry (ADR-0073).

    Two actors **under one authority** cannot share a slug, because under
    ADR-0073 the URL path segment *is* the actor's identity within that node —
    same segment means same actor.  The guarantee stops at the authority
    boundary: the scheme and netloc are dropped, so ``http://vendor/…/case-actor``
    and ``http://case-actor:7999/…/case-actor`` produce the same slug and hence
    the same store.  After ADR-0081 no legitimate path opens a store for a
    foreign-authority id, so the cross-authority collision is structurally
    unreachable; :func:`get_actor_engine` raises if it ever occurs.

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
    # string for a bare name, which yields no path.  Note that an opaque URI
    # *does* parse — ``urn:uuid:abc`` has path ``uuid:abc`` — so the fallback
    # is narrower than "not an http URL".
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

    Under ADR-0073 every actor gets its own store, so the configured
    ``db_url`` is a **template** rather than a location:

    - ``sqlite:////app/data/mydb.sqlite`` becomes
      ``sqlite:////app/data/mydb-vendor.sqlite``
    - ``sqlite:///:memory:`` becomes a **named** shared-cache in-memory
      database, ``sqlite:///file:vultron-vendor?mode=memory&cache=shared&uri=true``

    Naming the in-memory database matters: it makes the URL the single source
    of store identity in *both* modes.  Returning ``:memory:`` unchanged left
    identity carried by the Python :class:`~sqlalchemy.engine.Engine` object
    instead, recovered via a cache — which meant two independent applications
    in one process, both hosting the same actor, silently shared one store.

    Args:
        db_url: The configured SQLAlchemy URL template.
        actor_id: The actor's canonical URI.

    Returns:
        A SQLAlchemy URL naming that actor's own store.
    """
    slug = actor_slug(actor_id)

    if _is_memory_url(db_url):
        base = _memory_base_name(db_url)
        return (
            f"sqlite:///file:{base}-{slug}"
            "?mode=memory&cache=shared&uri=true"
        )

    scheme, _, location = db_url.partition("///")
    if not location:
        # Not a shape we can rewrite (e.g. a non-SQLite URL).  Returning it
        # unchanged would silently put two actors in one store, so refuse.
        raise ValueError(
            f"cannot derive a per-actor database URL from {db_url!r}; "
            "expected a sqlite:/// URL or an in-memory URL"
        )

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


#: Process-level engine cache keyed by the **resolved per-actor URL**.
#:
#: Because :func:`actor_db_url` names the in-memory database, the resolved URL
#: identifies a store completely in both file and memory modes — so it is the
#: whole key.  Two instances for the same actor share one engine (an actor's
#: store must not split in two); two different actors, or two differently-named
#: in-memory deployments, never do.
_ENGINES: dict[str, Engine] = {}

#: First actor id seen for each resolved store URL, used only to detect the
#: cross-authority slug collision described in :func:`actor_slug`.  Kept separate
#: from ``_ENGINES`` so disposal (a legitimate reset) does not erase the record
#: of which id claimed a store.
_STORE_CLAIMANTS: dict[str, str] = {}


def get_actor_engine(db_url: str, actor_id: str) -> Engine:
    """Return the cached engine for *actor_id*, creating it if needed.

    Warns when a *different* actor id has already claimed the same resolved
    store URL.  That only happens when two ids differ outside the final path
    segment — i.e. they are under different authorities.  After ADR-0081 no
    legitimate *production* path reaches this condition: ``POST /actors/``
    rejects foreign-authority ids, and peer knowledge is stored inside a
    hosted actor's own store via ``POST /actors/{id}/peers/``.  The guard
    stays a warning (not an exception) because the demo test harness legitimately
    runs multiple nodes in one process, and nodes that share a slug would
    otherwise fail to start.

    Args:
        db_url: The configured SQLAlchemy URL template.
        actor_id: The actor's canonical URI.

    Returns:
        The :class:`~sqlalchemy.engine.Engine` backing that actor's own store.
    """
    key = actor_db_url(db_url, actor_id)
    claimant = _STORE_CLAIMANTS.setdefault(key, actor_id)
    if claimant != actor_id:
        logger.warning(
            "Store %s is shared by two distinct actor ids (%r and %r): "
            "their slugs match but their authorities do not.  "
            "After ADR-0081 this should not occur in production.",
            key,
            claimant,
            actor_id,
        )
    engine = _ENGINES.get(key)
    if engine is None:
        engine = make_engine(key)
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
    if actor_id is not None and db_url is not None:
        targets = [actor_db_url(db_url, actor_id)]
    elif db_url is not None and _is_memory_url(db_url):
        prefix = f"sqlite:///file:{_memory_base_name(db_url)}-"
        targets = [k for k in _ENGINES if k.startswith(prefix)]
    elif db_url is not None:
        stem = Path(db_url.partition("///")[2]).stem
        targets = [k for k in _ENGINES if f"/{stem}-" in k or stem in k]
    else:
        targets = list(_ENGINES)

    for key in targets:
        engine = _ENGINES.pop(key, None)
        if engine is not None:
            engine.dispose()


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
