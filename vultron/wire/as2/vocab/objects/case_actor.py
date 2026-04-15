#!/usr/bin/env python
"""
Defines a CaseActor class for the Vultron ActivityStreams Vocabulary.
"""

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from vultron.core.models.case_actor import VultronCaseActor
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.base import _scalar_ref_id_or_value


class CaseActor(as_Service):
    """
    A CaseActor is a software service wrapper around a VulnerabilityCase object.
    It provides an inbox/outbox for the case to manage communications related to the case.
    """

    # note: CaseActor doesn't need its own type_, the value inherited from as_Service is sufficient

    # attributed_to: (Actor) Case Owner
    # context: (VulnerabilityCase) The case this actor is associated with

    @classmethod
    def from_core(cls, core_obj: VultronCaseActor) -> "CaseActor":
        return cls(
            id_=core_obj.id_,
            name=core_obj.name,
            attributed_to=core_obj.attributed_to,
            context=core_obj.context,
        )

    def to_core(self) -> VultronCaseActor:
        return VultronCaseActor.model_validate(
            {
                "id_": self.id_,
                "type_": self.type_,
                "name": self.name,
                "attributed_to": _scalar_ref_id_or_value(self.attributed_to),
                "context": _scalar_ref_id_or_value(self.context),
            }
        )


if __name__ == "__main__":
    print("This module is intended to be imported, not run directly.")

    print(CaseActor().model_dump_json(indent=2))
