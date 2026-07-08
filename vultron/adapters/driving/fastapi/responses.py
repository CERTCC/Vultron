#!/usr/bin/env python
"""
Canonical FastAPI response class for Vultron AS2 endpoints.

HTTP-09-002: Route handlers returning AS2 objects MUST use AS2JSONResponse.
HTTP-09-003: Serializes with model_dump(mode="json", by_alias=True,
             exclude_none=True) and sets Content-Type: application/activity+json.
"""

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

from typing import Any

from fastapi.responses import JSONResponse

from vultron.wire.as2.vocab.base.base import as_Base

AS2_CONTENT_TYPE = "application/activity+json"


class AS2JSONResponse(JSONResponse):
    """FastAPI response for ActivityStreams 2.0 objects.

    Serializes an ``as_Base`` subclass instance with ``by_alias=True`` and
    ``exclude_none=True`` to produce compact camelCase AS2 JSON, and sets the
    ``Content-Type`` header to ``application/activity+json``.

    Usage::

        return AS2JSONResponse(wire_obj)

    Keep ``response_model=`` on the route decorator for OpenAPI schema
    generation — ``AS2JSONResponse`` bypasses FastAPI's response-model
    filtering so subclass fields are never stripped (HTTP-08-001 fix).
    """

    media_type = AS2_CONTENT_TYPE

    def __init__(self, content: "as_Base | Any", **kwargs: Any) -> None:
        if isinstance(content, as_Base):
            body = content.model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
        else:
            body = content
        super().__init__(content=body, **kwargs)
