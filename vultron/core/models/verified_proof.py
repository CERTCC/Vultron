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


"""One proof a receiver verified, and the key it verified it with.

The inbox's verification stage checks every proof a delivery needs before
the body is parsed (SIG-03-003): the activity's own and, on an
``Announce(CaseLedgerEntry)``, its snapshot's (SIG-04-002).  For each one it
names what it verified: the author, the key the proof names, and the public
key it read from the author's profile, as fetched (SIG-02-001, SIG-02-003).

The receiver keeps these on the record of the delivery it archives
(:attr:`~vultron.core.models.received_activity_record.ReceivedActivityRecord.verified_proofs`,
SIG-03-004), so it can later say which key a past message verified against,
as key rotation needs (#1184).
"""

from pydantic import BaseModel, ConfigDict

from vultron.core.models.base import NonEmptyString, ValidatedAssignmentMixin
from vultron.primitives import NormalisedActorId


class VerifiedProof(ValidatedAssignmentMixin, BaseModel):
    """A proof that verified, by the key its author's profile published.

    Attributes:
        author_id: The actor that signed the document, its ``actor``
            (SIG-05-005).
        verification_method: The key id the proof names,
            ``<actor id>#<fragment>`` (SIG-01-002).
        public_key_multibase: The public key the author's profile listed
            for that key id when the receiver fetched it.
    """

    # A receiver's own bookkeeping, never on the wire: stored under its
    # field names, as the record that holds it is.
    model_config = ConfigDict(extra="forbid")

    author_id: NormalisedActorId
    verification_method: NonEmptyString
    public_key_multibase: NonEmptyString


__all__ = ["VerifiedProof"]
