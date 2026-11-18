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

"""The VINCE case reader: fetch one VINCE case, return its case reading.

:class:`VinceCaseReader` implements the core
:class:`~vultron.core.ports.case_reader.CaseReader` port and nothing else
(ARCH-05-004, ARCH-05-005).  Given a VINCE case id, it sends one ``GET``
for each per-case read the translation takes (:data:`~.records.READS`),
below ``case/<vuid>/`` of the VINCE Comm API, and hands the answers to
:func:`~.translate.translate_case`.  It builds every URL from that list, so
no request it sends can reach a VINCE write endpoint, and it sends nothing
but ``GET``.

The reader reads the clock once per request, before its first read, and
passes that time to the translation as the time of reading: the translation
itself reads no clock (CRD-02-006).

The endpoint and the credential come from the ``vince:`` configuration
section (:class:`~vultron.config.vince.VinceConfig`), read when a case is
requested, never when the reader is built: the connector loader builds
every installed plugin with no arguments (ARCH-05-003), and a node with no
VINCE settings must still load.  The credential travels only in the
``Authorization`` header, only over ``https`` or to a loopback host, and
appears in no log, error or repr (VSD-01-005).

Each read gets one attempt, with a timeout, and no retry.  A refused
credential, a rate limit, an unreachable or failing VINCE and an unknown
case each raise their own :class:`~vultron.errors.VinceReadError`, so the
analyst sees why at once.  A 404 on any read but the case itself is a read
VINCE has nothing for, which the translation reads as absent.

The answers are held in memory for the one request and dropped once
translated (ADR-0190).  The reader logs the case's VINCE id, each read's
status, and counts, never case content (VSD-01-003).
"""

from __future__ import annotations

import ipaddress
import logging
import re
from collections.abc import Callable
from datetime import datetime
from urllib.parse import urlsplit

import httpx2 as httpx
from pydantic import JsonValue

from vultron.adapters.connectors.vince.crosswalk import VINCE_UNOBSERVABLE
from vultron.adapters.connectors.vince.records import READS
from vultron.adapters.connectors.vince.translate import translate_case
from vultron.config import get_config
from vultron.config.vince import VINCE_BASE_URL_ENV_VAR, VinceConfig
from vultron.core.models._helpers.clock import now_utc
from vultron.core.models.case_reading import CaseReading, UnobservableFact
from vultron.errors import (
    VinceAuthError,
    VinceCaseNotFoundError,
    VinceRateLimitedError,
    VinceReadError,
    VinceUnavailableError,
    VultronConfigError,
    VultronValidationError,
)

logger = logging.getLogger(__name__)

#: Seconds each network step of a read may take: connecting, sending, the
#: wait for each chunk of the answer, and taking a pooled connection.  It
#: bounds no read as a whole.
DEFAULT_READ_TIMEOUT: float = 30.0

#: A VINCE case id: its number, as VINCE's API names it, or ``VU#`` and
#: its number, as VINCE shows it to a person.
_CASE_ID = re.compile(r"(?:VU#)?([0-9]+)")

#: A ``Retry-After`` value in its delay-seconds form: ASCII digits only.
_DELAY_SECONDS = re.compile(r"[0-9]+")


def _vuid(case_id: str) -> str:
    """The VINCE id *case_id* names, its digits only.

    Raises:
        VultronValidationError: *case_id* is not a VINCE case id.  Only
            digits reach a URL, so no case id can name another endpoint.
    """
    match = _CASE_ID.fullmatch(case_id.strip())
    if match is None:
        raise VultronValidationError(
            "A VINCE case id is a number, such as 123456 or VU#123456;"
            f" {case_id!r} is not one"
        )
    return match.group(1)


def _is_loopback(host: str | None) -> bool:
    """Whether *host* is ``localhost`` or a loopback address."""
    if host is None:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _api_url(config: VinceConfig) -> str:
    """The VINCE Comm API base URL, without a trailing slash.

    A plain ``http`` URL is accepted only for a loopback host, so the
    credential never crosses a network in cleartext (maintainer decision,
    Epic run #5954).

    Raises:
        VultronConfigError: No base URL is set; it is ``http`` to a host
            that is not loopback; or it does not end in ``/api``, so the
            VINCE Comm root cannot be derived from it.
    """
    if config.base_url is None:
        raise VultronConfigError(
            "the VINCE API base URL is not set, so no VINCE case can be"
            f" read; set {VINCE_BASE_URL_ENV_VAR}"
        )
    api_url = config.base_url.rstrip("/")
    parts = urlsplit(api_url)
    if parts.scheme.lower() == "http" and not _is_loopback(parts.hostname):
        raise VultronConfigError(
            f"{VINCE_BASE_URL_ENV_VAR} uses the http scheme for the host"
            f" {parts.hostname!r}, which is not loopback; the VINCE API"
            " credential is sent only over https, or over http to"
            " localhost, 127.0.0.0/8 or ::1"
        )
    if not api_url.endswith("/api"):
        raise VultronConfigError(
            f"{VINCE_BASE_URL_ENV_VAR} must be the VINCE Comm API root, ending in"
            " /api, such as https://kb.cert.org/vince/comm/api"
        )
    return api_url


def _path(vuid: str, read: str) -> str:
    """The URL of *read*, relative to the API root."""
    return f"case/{vuid}/" if read == "case" else f"case/{vuid}/{read}/"


def _retry_after(response: httpx.Response) -> float | None:
    """The seconds a 429 answer's ``Retry-After`` header asks for.

    ``None`` when the header is missing or is not HTTP's delay-seconds
    form, a whole number of seconds in ASCII digits: the HTTP-date form
    would need a clock read to turn into a wait.
    """
    value = response.headers.get("Retry-After")
    if value is None or not _DELAY_SECONDS.fullmatch(value.strip()):
        return None
    return float(value.strip())


def _answer(vuid: str, read: str, response: httpx.Response) -> JsonValue:
    """*response*'s JSON, ``None`` for a 404, or the named failure.

    Raises:
        VinceCaseNotFoundError: The case read answered 404.
        VinceAuthError: VINCE refused the credential (401, 403).
        VinceRateLimitedError: VINCE answered 429.
        VinceUnavailableError: VINCE answered with a server error (5xx).
        VinceReadError: Any other answer but 200, or a 200 whose body is
            not JSON.
    """
    status = response.status_code
    if status == 200:
        try:
            body: JsonValue = response.json()
        except ValueError:
            raise VinceReadError(
                vuid, read, "answered with a body that is not JSON", status
            ) from None
        return body
    if status == 404:
        if read == "case":
            raise VinceCaseNotFoundError(
                vuid,
                read,
                "found no such case, or none the credential's account sees",
                status,
            )
        return None
    if status in (401, 403):
        raise VinceAuthError(
            vuid, read, "was refused the API credential", status
        )
    if status == 429:
        raise VinceRateLimitedError(
            vuid,
            read,
            "was rate-limited; ask again later",
            status,
            retry_after=_retry_after(response),
        )
    if status >= 500:
        raise VinceUnavailableError(
            vuid, read, "failed on the VINCE side", status
        )
    raise VinceReadError(vuid, read, "had an unexpected answer", status)


class VinceCaseReader:
    """A ``CaseReader`` over the VINCE Comm API (#5963).

    It keeps nothing between requests (ADR-0190).

    Args:
        config: The VINCE endpoint and credential; by default the ``vince:``
            section of the node's configuration, read on each request.
        transport: The HTTP transport requests go through; by default the
            network.  A test passes one that serves recorded answers.
        clock: Returns the time of reading, an aware datetime; read once
            per request.  By default the current UTC time.
        timeout: Seconds each network step of a read may take.
    """

    name = "vince"
    #: What the VINCE API never exposes (CRD-02-004).
    unobservable: tuple[UnobservableFact, ...] = VINCE_UNOBSERVABLE

    def __init__(
        self,
        config: VinceConfig | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = now_utc,
        timeout: float = DEFAULT_READ_TIMEOUT,
    ) -> None:
        self._config = config
        self._transport = transport
        self._clock = clock
        self._timeout = timeout

    def read_case(self, case_id: str) -> CaseReading:
        """Read the VINCE case *case_id* and return its case reading.

        Args:
            case_id: The case's VINCE id, such as ``123456`` or
                ``VU#123456``.

        Raises:
            VultronValidationError: *case_id* is not a VINCE case id.
            VultronConfigError: The VINCE base URL is not set, is
                ``http`` to a host that is not loopback, or does not end in
                ``/api``.
            VultronMissingCredentialError: The VINCE API credential is not
                set.
            VinceReadError: A read failed; its subclass names why.
            VinceCaseRecordsError: The case record VINCE served cannot be
                translated at all.
        """
        vuid = _vuid(case_id)
        config = self._config
        if config is None:
            config = get_config().vince
        api_url = _api_url(config)
        token = config.require_api_token()
        as_of = self._clock()

        with httpx.Client(
            base_url=api_url,
            transport=self._transport,
            timeout=self._timeout,
            follow_redirects=False,
            # A proxy named in the environment would carry a plain-http
            # loopback read, credential included, across the network.
            trust_env=not api_url.startswith("http://"),
            headers={
                "Accept": "application/json",
                "Authorization": f"Token {token.get_secret_value()}",
            },
        ) as client:
            reads = {read: self._fetch(client, vuid, read) for read in READS}
        reading = translate_case(
            reads, comm_url=api_url.removesuffix("/api"), as_of=as_of
        )
        logger.info(
            "Read VINCE case %s: %d reads translated into %d entries and %d"
            " untranslated facts",
            vuid,
            len(reads),
            len(reading.ledger),
            len(reading.untranslated),
        )
        return reading

    @staticmethod
    def _fetch(client: httpx.Client, vuid: str, read: str) -> JsonValue:
        """Send the one ``GET`` for *read* and return its answer."""
        try:
            response = client.get(_path(vuid, read))
        except httpx.TimeoutException as exc:
            raise VinceUnavailableError(vuid, read, "timed out") from exc
        except httpx.HTTPError as exc:
            raise VinceUnavailableError(
                vuid, read, f"could not reach VINCE ({type(exc).__name__})"
            ) from exc
        logger.debug(
            "VINCE case %s: %r read answered %d",
            vuid,
            read,
            response.status_code,
        )
        return _answer(vuid, read, response)


__all__ = ["DEFAULT_READ_TIMEOUT", "VinceCaseReader"]
