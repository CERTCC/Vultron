"""The ``Occasion`` value object: one situation a sender conveys with an
entry's wire activity (ADR-0128, MSM-08-005, MSM-08-007)."""

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

from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from vultron.core.behaviors.sender_entitlement import (
    AddresseeSide,
)
from vultron.enums.roles import CVDRole
from vultron.primitives import NonEmptyString
from vultron.semantic_registry._occasion.distinguisher import (
    _FROZEN,
    Distinguisher,
)
from vultron.semantic_registry._occasion.vocabulary import (
    HowToGuide,
    ProtocolShorthand,
)

#: An occasion anchor: lowercase words joined by hyphens.
ANCHOR_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_EXAMPLE_NAME_PATTERN = r"^[a-z_][a-z0-9_]*$"


class Occasion(BaseModel):
    """One situation a sender conveys with an entry's wire activity.

    Holds what only a human can supply (ADR-0128).  The prose fields render
    on reference pages and in how-to guides, so they follow the docs style
    guide and address no reader (MSM-08-007).  The model is strict, so a
    usual sender must be a ``CVDRole`` member, not a string (MSM-08-005).

    Attributes:
        when: The sender's situation, worded to complete "When…", e.g.
            "a Vendor has a fix ready".
        anchor: Stable section anchor, lowercase words joined by hyphens.
        addressee: Whom the activity is sent to, as a side of a sender rule:
            the CASE_MANAGER, a participant, or an actor outside any case.
            It picks the side of the use case's declared rule that gives
            "Sent by", and renders as "Send to"; ``SemanticEntry`` refuses an
            addressee its use case's rule states no side for (MSM-08-009).
        heading: The plain-English heading of the occasion's section, in
            sentence case, e.g. "Add note to case".  Required when the
            occasion has no shorthand.  An occasion whose shorthand is
            carried by another entry too (an expansion such as ``GI``) needs
            one as well, and one whose shorthand is its own must not declare
            one, because its section is headed by the formal name
            (MSM-08-008); both depend on the whole registry, so
            ``vultron.metadata.msm`` checks them, not this model.
        description: One or two sentences on what the activity does.
        example: Name of the committed vocab example this occasion shows:
            the stem of ``docs/reference/examples/<example>.json``, which
            ``vocab_examples.render_example`` renders and
            ``vocab_examples.build_example`` builds (MSM-08-003, #5893).
        distinguisher: What tells this occasion apart from the entry's other
            occasions, when it has any.  It is required when another
            occasion of the entry has the same addressee, which
            ``SemanticEntry`` checks (MSM-08-011).
        howto: The how-to guide whose steps send it.  The guide must embed
            the occasion where a step sends it, or ``msm-occasions`` fails;
            the section's "Seen in" lists that guide and every other page
            that embeds the occasion (#4432).
        shorthand: The formal protocol message it carries, if any.
        usual_senders: The CVD roles that usually send it, beside the rule a
            receiver applies (MSM-08-005).
        notes: Further prose for the occasion's section.
        evolved: ``True`` when the activity serves a formal message's purpose
            on a different axis (MSM-05).  Such an occasion has no shorthand
            to count, which is what leaves ``evolved`` the one declared
            mapping status (MSM-08-006).
    """

    model_config = _FROZEN

    when: NonEmptyString
    anchor: Annotated[str, Field(pattern=ANCHOR_PATTERN)]
    addressee: AddresseeSide
    description: NonEmptyString
    heading: NonEmptyString | None = None
    example: Annotated[str, Field(pattern=_EXAMPLE_NAME_PATTERN)]
    distinguisher: Distinguisher | None = None
    howto: HowToGuide | None = None
    shorthand: ProtocolShorthand | None = None
    usual_senders: tuple[CVDRole, ...] = ()
    notes: NonEmptyString | None = None
    evolved: bool = False

    @model_validator(mode="after")
    def _evolved_has_no_shorthand(self) -> Occasion:
        if self.evolved and self.shorthand is not None:
            raise ValueError(
                "an evolved occasion has no shorthand of its own (MSM-08-006)"
            )
        return self

    @model_validator(mode="after")
    def _no_shorthand_needs_a_heading(self) -> Occasion:
        if self.shorthand is None and self.heading is None:
            raise ValueError(
                f"occasion {self.anchor!r} has no shorthand, so its section"
                " needs a plain-English heading (MSM-08-008)"
            )
        return self
