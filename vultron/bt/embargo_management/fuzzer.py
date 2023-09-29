#!/usr/bin/env python
"""file: fuzzer
author: adh
created_at: 4/26/22 1:20 PM

Each of the following classes is a fuzzable bt tree node.
The fuzzing is done by the bt.fuzzer module.
These classes are the most likely places where one of the following is likely to apply:
1. a human might need to intervene to make a decision
2. a human might need to intervene to provide input to an automated decision process
3. an automated decision process might need to be implemented based on some site-specific logic

But for now they are just stubs that return a random result so we can exercise the tree.
"""
#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
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


import sys

import vultron.bt.base.fuzzer as btz
from vultron.bt.base.decorators import Invert


class ExitEmbargoWhenDeployed(btz.ProbablyFail):
    """Decide whether to exit the embargo when the fix has already been deployed.
    This is a special case because the fix has already been deployed, so the embargo is usually no longer necessary.
    But usually, deployment of the fix itself is not a sufficient reason to exit an active embargo.
    For example, the fix may have been deployed in error, or the fix may have been deployed to a subset of the population.
    """

    # implement as necessary, ask a human


class ExitEmbargoWhenFixReady(btz.UsuallyFail):
    """Decide whether to exit the embargo when the fix is ready.
    When the fix is ready, the embargo is usually no longer necessary,
    however there are some cases where it is.
    For example, if the vendor is able to deploy the fix directly
    to the affected population, then the embargo may still be useful.
    """

    # implement as necessary, ask a human


class ExitEmbargoForOtherReason(btz.OneInTwoHundred):
    """Decide whether to exit the embargo for some reason *other* than:
    - the fix is ready or deployed
    - the embargo timer has expired
    - the public is aware of the vulnerability
    - an exploit has been published
    - attacks have been observed
    There aren't that many extraneous reasons to exit an embargo, so this is a rare case.
    """

    # ask a human


class EmbargoTimerExpired(btz.OneInOneHundred):
    """Decide whether the embargo timer has expired.
    We are simulating that the embargo is usually not expired.
    But in reality, this would just be a check of the actual embargo timer.
    """


class OnEmbargoExit(btz.AlwaysSucceed):
    """Do whatever is necessary when the embargo is exited.
    This is a stub for now.
    It is a placeholder for site-specific logic for what to do when the embargo is exited.
    In an actual implementation, this would probably be a call to a function that does whatever is necessary.
    """

    # implement as necessary


# Negotiating
class StopProposingEmbargo(btz.UsuallyFail):
    """Decide whether to stop proposing an embargo.
    This would be a choice for the humans involved in the case to make.
    We are modeling it here as if the humans are usually willing to keep trying to negotiate an embargo.
    """

    # ask a human


class SelectEmbargoOfferTerms(btz.AlwaysSucceed):
    """Select the terms of the embargo offer.
    This is a stub for now.
    In an actual implementation, this would probably be a call out
    to either a human or a function that does whatever is necessary.
    """

    # implement as necessary, ask a human


class WantToProposeEmbargo(btz.RandomSucceedFail):
    """Decide whether to propose an embargo.
    This is a stub for now.
    In an actual implementation, this would probably be a call out
    to either a human or a function that does whatever is necessary.
    We'd suggest that the default bt is to propose an embargo.
    But the fuzzer will exercise both cases.
    """

    # implement as necessary, ask a human


class WillingToCounterEmbargoProposal(btz.UsuallyFail):
    """Decide whether to counter an embargo proposal.
    In an actual implementation, this would probably be a call out
    to either a human or a function that does whatever is necessary.
    However, we generally suggest that the default bt is not
    to counter an embargo proposal. Instead, it is better to accept
    the proposal on the table and then propose a revision to adjust
    the terms.
    """

    # implement as necessary, ask a human


class AvoidEmbargoCounterProposal(Invert):
    """This is a convenience class that inverts the result of WillingToCounterEmbargoProposal."""

    _children = (WillingToCounterEmbargoProposal,)


class ReasonToProposeEmbargoWhenDeployed(btz.AlmostCertainlyFail):
    """Decide whether there is a reason to propose an embargo when the fix has already been deployed.
    In most cases, there is no reason to propose an embargo when the fix has already been deployed.
    Therefore we are modeling this as a rare case.
    In an actual implementation, this would probably need to be a call out to a human.
    """

    # ask a human


# Evaluating
class EvaluateEmbargoProposal(btz.UsuallySucceed):
    """Decide whether to accept an embargo proposal.
    In an actual implementation, this would probably be a call out to a human.
    Or it is conceivable that this could be a call out to a function that automatically evaluates the proposal.
    We are modeling this as a case where the humans usually accept the proposal.
    """

    # success = accept
    # implement as necessary, ask a human


class OnEmbargoAccept(btz.AlwaysSucceed):
    """This is a stub for now.
    It serves as a placeholder for site-specific logic that would be triggered when an embargo is accepted.
    In an actual implementation, this would probably be a call out to a function
    that does whatever is necessary when an embargo is accepted.
    E.g., it might trigger some automated process to notify internal stakeholders.
    """

    # implement as necessary


class OnEmbargoReject(btz.AlwaysSucceed):
    """This is a stub for now.
    It serves as a placeholder for site-specific logic that would be triggered when an embargo is rejected.
    In an actual implementation, this would probably be a call out to a function
    that does whatever is necessary when an embargo is rejected.
    E.g., it might trigger some automated process to notify internal stakeholders.
    """

    pass
    # implement as necessary


class CurrentEmbargoAcceptable(btz.AlmostAlwaysSucceed):
    """Decide whether the current embargo is acceptable.
    In an actual implementation, this would probably be a call out to a human.
    We are modeling this as a case where the humans usually choose to keep the current embargo.
    """

    # implement as necessary, ask a human


def main():
    import inspect

    # get all the classes in this module
    classes = inspect.getmembers(sys.modules[__name__], inspect.isclass)

    print(sys.modules[__name__].__doc__)
    print()
    for name, cls in classes:
        print(f"class {name}")
        for k in cls.__bases__:
            print(f"    likelihood: {k.__name__}")
        print(f"    {cls.__doc__}")
        print()

    pass


if __name__ == "__main__":
    main()
