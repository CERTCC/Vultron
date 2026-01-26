#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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

import pytest

from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport


@pytest.fixture
def finder():
    return as_Actor(name="Test Finder")


@pytest.fixture
def vendor():
    return as_Actor(name="Test Vendor")


@pytest.fixture
def report(finder):
    return VulnerabilityReport(
        attributed_to=finder.as_id,
        content="This is a test vulnerability report.",
    )


@pytest.fixture
def offer_factory(finder, vendor, report):
    """
    Return a factory that produces as_Offer instances.
    Defaults mirror prior tests (actor -> finder.as_id, object -> report).
    Accepts actor and to as either actor objects or as_id strings.
    """

    def _make(actor=None, to=None, obj=None):
        kwargs = {}
        # actor may be an actor object or id
        if actor is None:
            kwargs["actor"] = finder.as_id
        else:
            kwargs["actor"] = getattr(actor, "as_id", actor)
        # optional 'to' recipient
        if to is not None:
            kwargs["to"] = getattr(to, "as_id", to)
        # object defaults to the shared report
        kwargs["object"] = obj or report
        return as_Offer(**kwargs)

    return _make


@pytest.fixture
def offer(offer_factory):
    return offer_factory()


@pytest.fixture
def dl(datalayer, finder, vendor, report):
    for obj in (finder, vendor, report):
        datalayer.create(obj)
    yield datalayer
    datalayer.clear()
