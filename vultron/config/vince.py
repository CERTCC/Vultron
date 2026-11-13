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

"""VINCE connector configuration: the endpoint and the API credential.

Provides :class:`VinceConfig`, the ``vince:`` section of
:class:`~vultron.config.app.AppConfig`.  The shadow's VINCE connector reads its
endpoint and credential here, through :func:`~vultron.config.app.get_config`
(CFG-01-004).

The credential is a secret kept outside the code, the repository and every
configuration file: it is read only from ``VULTRON_VINCE__API_TOKEN`` in the
environment the node runs in, and a configuration file that names it is
refused at load (VSD-01-004, SHD-02-003).  It is held as a
:class:`pydantic.SecretStr`, so a log record, an exception message or a repr
renders it masked (VSD-01-005).

Per ``specs/vince-shadow-data.yaml`` VSD-01-004, VSD-01-005 and
``specs/case-shadow.yaml`` SHD-02-003.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from vultron.config.env_names import env_var_name
from vultron.errors import VultronMissingCredentialError

#: The environment variable that carries the VINCE API credential.
VINCE_API_TOKEN_ENV_VAR = env_var_name(("vince", "api_token"))


class VinceConfig(BaseModel):
    """Where the VINCE API is and the credential that reads it.

    Attributes:
        base_url: Base URL of the VINCE API the shadow reads cases from. It
            starts with ``http://`` or ``https://``.  When it is ``None`` the
            node has no VINCE endpoint.  Default ``None``.
        api_token: The VINCE API credential.  It is a secret, read only from
            the environment: a configuration file that names this key is
            refused at load, and the value is masked wherever the
            configuration is rendered.  When it is ``None`` the VINCE
            connector refuses to read a case.  Default ``None``.
    """

    # A validation error names the field but never quotes its input, so the
    # section is safe to validate on its own; inside ``AppConfig`` the
    # outermost model's matching setting governs (VSD-01-005).
    model_config = ConfigDict(hide_input_in_errors=True)

    base_url: str | None = None
    api_token: SecretStr | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        """Require an http:// or https:// scheme when a URL is set."""
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v

    @field_validator("api_token")
    @classmethod
    def reject_blank_api_token(cls, v: SecretStr | None) -> SecretStr | None:
        """Refuse a credential that is set but empty or only whitespace.

        A blank variable is a deployment mistake, not a credential, so it is
        refused where it is set rather than sent to VINCE (CS-08-002).
        """
        if v is not None and not v.get_secret_value().strip():
            raise ValueError(
                f"{VINCE_API_TOKEN_ENV_VAR} is set but empty; set the VINCE"
                " API credential or unset the variable"
            )
        return v

    def require_api_token(self) -> SecretStr:
        """Return the VINCE API credential, or refuse when there is none.

        The VINCE connector calls this before it reads a case, so a node with
        no credential refuses the read instead of sending an unauthenticated
        request (VSD-01-004, SHD-02-003).

        Returns:
            The credential, still masked; call ``get_secret_value()`` only
            where the request is built.

        Raises:
            VultronMissingCredentialError: ``VULTRON_VINCE__API_TOKEN`` is not
                set.
        """
        if self.api_token is None:
            raise VultronMissingCredentialError(
                "the VINCE API credential is not set, so no VINCE case can be"
                f" read; set {VINCE_API_TOKEN_ENV_VAR} in the environment the"
                " shadow runs in"
            )
        return self.api_token
