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

"""Which actors does *this node* host?

This is the one legitimately node-level fact left after ADR-0073 removed the
unscoped DataLayer. It is deliberately **not** a data store and holds no
protocol state: it answers "which actors run here" and "what canonical URI does
this URL path segment mean", and nothing else. No actor can learn anything about
another actor through it.

Two representations are reconciled:

- **Canonical URI** — ``{base_url}actors/{slug}``, the actor's protocol identity.
- **Slug** — the final URL path segment, which is also the per-actor database
  filename discriminator (see
  :func:`~vultron.adapters.driven.datalayer_sqlite.engine.actor_slug`).

The mapping is a pure computation in both directions, which is why no registry
is persisted: a node can enumerate what it hosts from the per-actor stores that
exist, and resolve an inbound URL segment without consulting any store at all.
"""

import logging
import os
from pathlib import Path
from urllib.parse import urlsplit

from vultron.adapters.driven.datalayer_sqlite.engine import (
    _is_memory_url,
    actor_slug,
)
from vultron.config import get_config

logger = logging.getLogger(__name__)

#: Path component that separates a node's base URL from an actor slug.
#: Public because it is also the shape test for "does this URI name one actor?"
#: — see ``_names_an_individual_actor`` in the inbox adapter (IE-11-002).
ACTORS_SEGMENT = "actors"


def canonical_actor_uri(segment: str, base_url: str | None = None) -> str:
    """Return the canonical actor URI for a URL path *segment*.

    This replaces the pre-ADR-0073 approach of scanning every actor row in a
    shared store to find one whose id ended in ``/{segment}``. That scan was the
    last thing genuinely requiring a cross-actor view, and it had a
    chicken-and-egg problem under per-actor stores: choosing which store to open
    required the canonical URI that the scan was being used to discover.

    Any id that already carries a scheme is returned unchanged — including one
    under a *foreign* authority, which is therefore **not** rewritten into this
    node's namespace. That is deliberate: a peer's id is the URL outbound
    delivery posts to, so rewriting it would turn a reachable peer into a local
    phantom (ADR-0073#peer-records-in-knowers-store). The cost is that a foreign id reaching a
    store-opening call site mints a local store for an actor this node does not
    host, where :func:`~vultron.adapters.driven.datalayer_sqlite.engine.actor_slug`
    can collide it with a co-hosted actor. Tracked in issue #2549; the collision
    itself is logged by ``get_actor_engine``.

    Args:
        segment: Final path segment from the request URL (e.g. ``"vendor"``), or
            an already-absolute actor URI, which is returned unchanged.
        base_url: Node base URL. Defaults to ``ServerConfig.base_url``.

    Returns:
        The canonical actor URI.

    Raises:
        ValueError: If *segment* is empty, or names no actor once its slashes
            are stripped.
    """
    if not segment:
        raise ValueError("actor URL segment must not be empty")

    # Already canonical (or at least absolute) — do not double-prefix it.
    if urlsplit(segment).scheme:
        return segment

    # A segment of ``"/"`` is not empty but names nothing.  Left unchecked it
    # produced ``{base}/actors/``, whose final path segment is ``actors`` — so
    # ``actor_slug`` returned a usable slug and the node quietly opened a store
    # for a phantom actor named after the path component.  ``assert_hosted_slug``
    # could not catch it downstream, because by then the value looked valid.
    slug_source = segment.strip("/")
    if not slug_source:
        raise ValueError(
            f"actor URL segment {segment!r} names no actor once its slashes "
            "are stripped"
        )

    base = base_url if base_url is not None else get_config().server.base_url
    return f"{base.rstrip('/')}/{ACTORS_SEGMENT}/{slug_source}"


def hosted_actor_ids(
    db_url: str | None = None, base_url: str | None = None
) -> list[str]:
    """Return the canonical URIs of every actor this node hosts.

    Derived from the per-actor stores that exist, so it includes actors created
    at runtime (notably the CaseActors a vendor self-hosts under CP-08-003) that
    appear in no configuration file.

    For an in-memory ``db_url`` there are no files to enumerate, so the
    in-process instance registry is used instead. That is the correct source in
    that mode: an in-memory store exists only while some instance holds it open.

    Args:
        db_url: SQLAlchemy URL template. Defaults to ``DatabaseConfig.db_url``.
        base_url: Node base URL. Defaults to ``ServerConfig.base_url``.

    Returns:
        Canonical actor URIs, sorted for stable output.
    """
    cfg = get_config()
    url = db_url if db_url is not None else cfg.database.db_url
    base = base_url if base_url is not None else cfg.server.base_url

    if _is_memory_url(url):
        from vultron.adapters.driven.datalayer_sqlite import (
            get_all_actor_datalayers,
        )

        return sorted(get_all_actor_datalayers())

    return sorted(
        canonical_actor_uri(slug, base) for slug in hosted_actor_slugs(url)
    )


def hosted_actor_slugs(db_url: str | None = None) -> set[str]:
    """Return the slugs of every per-actor store present on disk.

    Args:
        db_url: SQLAlchemy URL template. Defaults to ``DatabaseConfig.db_url``.

    Returns:
        The set of actor slugs with a store, empty if the directory is absent.
    """
    url = db_url if db_url is not None else get_config().database.db_url
    if _is_memory_url(url):
        return set()

    _, _, location = url.partition("///")
    if not location:
        return set()

    template = Path(location)
    stem, suffix = template.stem or "vultron", template.suffix or ".sqlite"
    directory = template.parent

    if not directory.is_dir():
        # A node that has not yet written any store hosts nothing observable;
        # that is an empty answer, not an error.
        return set()

    prefix = f"{stem}-"
    return {
        path.stem[len(prefix) :]
        for path in directory.glob(f"{prefix}*{suffix}")
        if path.stem.startswith(prefix) and path.stem != prefix
    }


def storage_ready(db_url: str | None = None) -> bool:
    """Return ``True`` when the configured storage location is usable.

    Readiness is a property of the storage *location*, not of any one actor's
    store. Before ADR-0073 this was answered by ``ping()`` on the shared
    DataLayer, which selected an arbitrary actor's rows; with per-actor stores
    there is no such thing as "the" store to ping, and inventing a probe actor
    would create a stray store that :func:`hosted_actor_slugs` would then report
    as a hosted actor.

    Args:
        db_url: SQLAlchemy URL template. Defaults to ``DatabaseConfig.db_url``.

    Returns:
        ``True`` when a per-actor store could be created or opened here.
    """
    url = db_url if db_url is not None else get_config().database.db_url
    if _is_memory_url(url):
        return True

    _, _, location = url.partition("///")
    if not location:
        logger.warning(
            "storage_ready: cannot interpret database URL %r as a location",
            url,
        )
        return False

    directory = Path(location).parent
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning(
            "storage_ready: storage directory %s is unusable: %s",
            directory,
            exc,
        )
        return False
    return os.access(directory, os.W_OK)


def local_actor_id(base_url: str | None = None) -> str | None:
    """Return the configured local actor URI for this node, if any.

    A node's *primary* actor is configured via ``VULTRON_ACTOR_ID`` and is
    therefore known before any store exists, unlike the runtime-created
    CaseActors that :func:`hosted_actor_ids` discovers from stores on disk.

    The env var is read directly rather than through ``vultron.demo.seed_config``
    (which also reads it): production adapters MUST NOT import demo config
    (CFG-07-005). It belongs on ``AppConfig.actor`` per CFG-07-005..007 and
    should migrate there; this reads the environment so that the migration is a
    separate, reviewable change rather than a config-schema edit buried in
    ADR-0073's rollout. Tracked in issue #2550: the move also has to keep the
    single-underscore ``VULTRON_ACTOR_ID`` working, since every compose file sets
    it, and nested ``ActorConfig`` fields would otherwise be read as
    ``VULTRON_ACTOR__ACTOR_ID``.

    Args:
        base_url: Node base URL. Defaults to ``ServerConfig.base_url``.

    Returns:
        The canonical local actor URI, or ``None`` when unconfigured.
    """
    configured = os.environ.get("VULTRON_ACTOR_ID")
    if not configured:
        return None
    return canonical_actor_uri(configured, base_url)


def assert_hosted_slug(segment: str) -> str:
    """Return :func:`actor_slug` for *segment*, rejecting unsafe values.

    Inbound URL segments reach the storage layer as filename components, so they
    are validated here rather than at the point of file creation.

    Args:
        segment: Final path segment from the request URL.

    Returns:
        The validated slug.

    Raises:
        ValueError: If *segment* yields no usable slug.
    """
    return actor_slug(canonical_actor_uri(segment))
