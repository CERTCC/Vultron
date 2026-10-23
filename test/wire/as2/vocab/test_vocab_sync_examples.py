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
import unittest

import vultron.wire.as2.vocab.examples.vocab_examples as examples
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import as_CaseLedgerEntry


class TestVocabSyncExamples(unittest.TestCase):
    def test_announce_case_ledger_entry(self):
        activity = examples.announce_case_ledger_entry()
        self.assertIsInstance(activity, as_Activity)
        self.assertIsInstance(activity, as_Announce)
        self.assertEqual(activity.type_, "Announce")
        self.assertIsInstance(activity.object_, as_CaseLedgerEntry)
        self.assertTrue(activity.actor)

    def test_reject_case_ledger_entry(self):
        activity = examples.reject_case_ledger_entry()
        self.assertIsInstance(activity, as_Activity)
        self.assertIsInstance(activity, as_Reject)
        self.assertEqual(activity.type_, "Reject")
        self.assertIsInstance(activity.object_, as_CaseLedgerEntry)
        self.assertTrue(activity.actor)
        self.assertTrue(activity.context)
