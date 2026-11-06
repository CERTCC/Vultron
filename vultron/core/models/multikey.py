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

"""The public key an actor profile publishes for verifying its proofs.

An actor lists its signing key under ``assertionMethod`` in its profile
(ENC-01-002, ADR-0164), where a FEP-8b32 verifier looks for the key a proof's
``verificationMethod`` names.  On the wire one entry reads::

    {
      "id": "https://example.org/actors/vendorco#main-key",
      "type": "Multikey",
      "controller": "https://example.org/actors/vendorco",
      "publicKeyMultibase": "z6Mk..."
    }

The key resolver
(:func:`vultron.core.services.verification_key.resolve_verification_key`)
finds the entry whose ``id`` is the proof's ``verificationMethod``, and the
verifier passes its ``publicKeyMultibase`` to
``vultron.wire.as2.signing.verify``.  Two invariants hold for every entry a
profile carries: the key's ``id`` is a fragment of its ``controller``'s id,
and the controller is the profile's own actor
(:class:`~vultron.core.models.actor.CoreActor`).

The value is not decoded here: core holds the published text as received, and
the signing module decodes it when it verifies, refusing a value that is not a
base58btc Ed25519 key with ``VultronMultikeyError``.

A later encryption key goes under ``keyAgreement`` beside this list, not in it
(``notes/encryption.md``).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from vultron.core.models.base import NonEmptyString, ValidatedAssignmentMixin

#: The ``type`` of a published verification key (W3C Controlled Identifiers).
MULTIKEY_TYPE: Literal["Multikey"] = "Multikey"


class Multikey(ValidatedAssignmentMixin, BaseModel):
    """One public key an actor publishes under ``assertionMethod``.

    A value object, not a stored record: it has no clock stamps, so two
    stores publishing the same key publish the same bytes (SIG-05-001).
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    id_: NonEmptyString = Field(
        validation_alias="id",
        serialization_alias="id",
        description="The key id a proof's verificationMethod names.",
    )
    type_: Literal["Multikey"] = Field(
        validation_alias="type",
        serialization_alias="type",
        description="Always stated: an entry without a type is refused.",
    )
    controller: NonEmptyString = Field(
        description="The id of the actor that holds the private key."
    )
    public_key_multibase: NonEmptyString = Field(
        description="The public key as a multibase base58btc Multikey value."
    )

    @model_validator(mode="after")
    def _id_is_a_fragment_of_its_controller(self) -> "Multikey":
        """Refuse a key whose id lies outside its controller's document.

        A proof's ``verificationMethod`` is dereferenced to the document that
        lists the key, so a key id must name the controller's own profile with
        a fragment: ``<controller id>#<fragment>``.
        """
        prefix = f"{self.controller}#"
        if not self.id_.startswith(prefix) or self.id_ == prefix:
            raise ValueError(
                f"Multikey id {self.id_!r} must be a fragment of its"
                f" controller's id, {prefix}<fragment> (ENC-01-002)"
            )
        return self


__all__ = ["MULTIKEY_TYPE", "Multikey"]
