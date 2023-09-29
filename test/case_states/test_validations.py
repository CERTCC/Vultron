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


import random
import string
import unittest
from itertools import permutations, product

import vultron.case_states.errors as err
import vultron.case_states.validations as v
from vultron.case_states.hypercube import CVDmodel

alpha = string.ascii_lowercase

ok_pfx = [
    "vfd",
    "Vfd",
    "VFd",
    "VFD",
]

bogus_pfx = [
    "vFd",
    "vfD",
    "vFD",
    "VfD",
]

ok_states = ["".join(parts) for parts in product(ok_pfx, "pP", "xX", "aA")]
# note these aren't all possible bad states, just the ones closest to the ok states
bad_states = ["".join(parts) for parts in product(bogus_pfx, "pP", "xX", "aA")]


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.sg = CVDmodel()

    def tearDown(self):
        pass

    def test_ok_states(self):
        self.assertEqual(32, len(ok_states))
        for state in ok_states:
            self.assertIn(state, self.sg.states)

    def test_bad_states(self):
        for state in bad_states:
            self.assertNotIn(state, self.sg.states)

        self.assertEqual(32, len(bad_states))

    def test_is_valid_pattern_bad_length(self):
        """
        Fuzz the is_valid_pattern function with strings of various lengths
        :return:
        """
        # wrong length
        for length in range(1, 10):
            if length == 6:
                continue
            for i in range(100):
                test_str = "".join(
                    (random.choice(alpha) for _ in range(length))
                )
                self.assertEqual(length, len(test_str))
                with self.assertRaises(err.PatternValidationError):
                    v.is_valid_pattern(test_str)

    def test_is_valid_pattern_bad_chars(self):
        """
        Fuzz the is_valid_pattern function with strings of invalid chars
        :return:
        """
        # wrong chars
        for i in range(1000):
            ch = [a for a in alpha if a not in "vfdpxa"]
            test_str = "".join((random.choice(ch) for _ in range(6)))
            self.assertEqual(6, len(test_str))
            with self.assertRaises(err.PatternValidationError):
                v.is_valid_pattern(test_str)

    def test_is_valid_pattern_bad_order(self):
        # exhaustive test
        # chars out of place
        for letters in permutations("vfdpxa"):
            test_str = "".join(letters)
            if test_str == "vfdpxa":
                continue
            with self.assertRaises(err.PatternValidationError):
                v.is_valid_pattern(test_str)

    def test_is_valid_pattern_ok(self):
        # exhaustive test
        # ok patterns
        # dots or random case are ok
        for parts in product("vV.", "fF.", "dD.", "pP.", "xX.", "aA."):
            test_str = "".join(parts)
            self.assertIsNone(v.is_valid_pattern(test_str))

    def test_is_valid_state_bad_length(self):
        """
        Fuzz the is_valid_state function with strings of various lengths
        :return:
        """
        # wrong length
        for length in range(1, 10):
            if length == 6:
                continue
            for i in range(100):
                test_str = "".join(
                    (random.choice(alpha) for _ in range(length))
                )
                self.assertEqual(length, len(test_str))
                with self.assertRaises(err.StateValidationError):
                    v.is_valid_state(test_str)

    def test_is_valid_state_bad_chars(self):
        """
        Fuzz the is_valid_state function with strings of invalid chars
        :return:
        """
        # wrong chars
        for i in range(1000):
            ch = [a for a in alpha if a not in "vfdpxa"]
            test_str = "".join((random.choice(ch) for _ in range(6)))
            self.assertEqual(6, len(test_str))
            with self.assertRaises(err.StateValidationError):
                v.is_valid_state(test_str)

    def test_is_valid_state_bad_pattern(self):
        for parts in product(bogus_pfx, "pP", "xX", "aA"):
            state = "".join(parts)
            with self.assertRaises(err.StateValidationError):
                v.is_valid_state(state)

    def test_is_valid_state_ok(self):
        for parts in product(ok_pfx, "pP", "xX", "aA"):
            state = "".join(parts)
            self.assertIsNone(v.is_valid_state(state))

    def test_is_valid_transition_PV_causality(self):
        # validation semantics
        # none = ok
        # raises error = not ok

        # v -> V
        self.assertIsNone(v.is_valid_transition("vfdpxa", "Vfdpxa"))

        # vp -> vP
        self.assertIsNone(v.is_valid_transition("vfdpxa", "vfdPxa"))

        # vP -> VP
        self.assertIsNone(v.is_valid_transition("vfdPxa", "VfdPxa"))

        # vPx -> vPX
        with self.assertRaises(err.TransitionValidationError):
            v.is_valid_transition("vfdPxa", "vfdPXa")

        # vPa -> vPA
        with self.assertRaises(err.TransitionValidationError):
            v.is_valid_transition("vfdPxa", "vfdPxA")

    def test_is_valid_transition_XP_causality(self):
        # pX -> PX
        for pfx in ok_pfx:
            self.assertIsNone(v.is_valid_transition(f"{pfx}pXa", f"{pfx}PXa"))
            # pXa -> pXA
            with self.assertRaises(err.TransitionValidationError):
                v.is_valid_transition(f"{pfx}pXa", f"{pfx}pXA")

    def test_is_valid_transition_bad_states(self):
        for a, b in product(ok_states, bad_states):
            with self.assertRaises(err.TransitionValidationError):
                v.is_valid_transition(a, b)

            with self.assertRaises(err.TransitionValidationError):
                v.is_valid_transition(b, a)

    def test_is_valid_transition_ok_states(self):
        # all single char changes from valid state to valid state are ok
        for a, b in product(ok_states, ok_states):
            diff = []
            for c1, c2 in zip(a, b):
                if c1 != c2:
                    diff.append((c1, c2))
            if len(diff) == 1:
                x, y = diff[0]
                if not x.islower():
                    with self.assertRaises(err.TransitionValidationError):
                        v.is_valid_transition(a, b)

                if not y.isupper():
                    with self.assertRaises(err.TransitionValidationError):
                        v.is_valid_transition(a, b)

            elif len(diff) == 0:
                self.assertIsNone(v.is_valid_transition(a, b, allow_null=True))

                with self.assertRaises(err.TransitionValidationError):
                    v.is_valid_transition(a, b, allow_null=False)
            else:
                with self.assertRaises(err.TransitionValidationError):
                    v.is_valid_transition(a, b)

    def test_is_valid_history_bad(self):
        invalid = [
            "vfdpxa",
            "FVDPXA",
            "AXVDFP",
            "aaa",
            "aaaaaaa",
            "VFFDPX",
            "XAPVFD",
        ]

        for h in invalid:
            with self.assertRaises(err.HistoryValidationError):
                v.is_valid_history(h)

    def test_is_valid_history_ok(self):
        valid = self.sg.histories
        self.assertEqual(70, len(valid))
        for h in valid:
            self.assertIsNone(v.is_valid_history(h))


if __name__ == "__main__":
    unittest.main()
