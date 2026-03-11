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

"""
DnsResolver port — the DNS lookup interface used by the core domain layer
for actor and instance trust discovery.

Concrete implementations live in the adapter layer at
``vultron/adapters/driven/dns_resolver.py``.

No adapter-layer types appear here.
"""

from typing import Protocol


class DnsResolver(Protocol):
    """Protocol for DNS-based actor/instance trust discovery.

    Defines the minimum interface that any concrete DNS adapter must
    satisfy.  The core layer calls ``resolve_txt`` to look up TXT records
    for a given domain, which may carry Vultron instance metadata such as
    inbox URLs, public keys, or supported protocol versions following
    WebFinger / NodeInfo conventions.
    """

    def resolve_txt(self, domain: str) -> list[str]:
        """Return the DNS TXT record values for ``domain``.

        Returns an empty list when no TXT records are found or the domain
        cannot be resolved.
        """
        ...
