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

"""Driving-side port: verify the proof on a received document.

The inbox verifies a delivery as its own ingress stage, after the body is
decoded and before ``parse_activity`` (SIG-03-003).  The stage sees only the
document: it resolves the author's key itself, from the author's actor
profile (SIG-02-001), unlike ``vultron.wire.as2.signing.verify``, which is
handed the key.  The adapter is
:class:`~vultron.adapters.driving.fastapi.inbox_verification.ProfileKeyProofVerifier`.
"""

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from vultron.core.models.verified_proof import VerifiedProof


@runtime_checkable
class ProofVerificationPort(Protocol):
    """Port: refuse a received document whose proof does not verify."""

    async def verify(
        self, document: Mapping[str, Any]
    ) -> tuple[VerifiedProof, ...]:
        """Return what verified when every proof *document* needs does.

        *document* is the decoded JSON body as received.  Async because the
        author's key may have to be fetched.  Returns one
        :class:`~vultron.core.models.verified_proof.VerifiedProof` per proof
        checked, the activity's first, then a ledger snapshot's: the
        receiver keeps them on the delivery's archived record (SIG-03-004).

        Raises:
            VultronProofVerificationError: A proof is missing or does not
                verify, or its key cannot be read (SIG-03-002).
        """
        ...  # pragma: no cover


__all__ = ["ProofVerificationPort"]
