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

import unittest
from itertools import product

import vultron.cvd_states.hypercube as hc
from vultron.cvd_states.errors import TransitionValidationError
from vultron.cvd_states.validations import is_valid_transition


class MyTestCase(unittest.TestCase):
    def test_proto_states(self):
        ps = hc._proto_states()
        self.assertEqual(len(ps), 6)
        for x in "vfdpxa":
            s = f"{x.lower()}{x.upper()}"
            self.assertIn(s, ps)

    def test_create_states(self):
        states = hc._create_states()
        self.assertEqual(len(states), 32)
        count = 0
        for p, x, a in product("pP", "xX", "aA"):
            s = "".join([p, x, a])
            for allowed in ["vfd", "Vfd", "VFd", "VFD"]:
                a = f"{allowed}{s}"
                self.assertIn(a, states)
                count += 1
            for disallowed in ["vFd", "vfD", "vFD", "VfD"]:
                d = f"{disallowed}{s}"
                self.assertNotIn(d, states)
        self.assertEqual(count, len(states))

    def test_create_graph(self):
        G = hc._create_graph()
        states = hc._create_states()
        self.assertEqual(len(G.nodes), len(states))
        for state in hc._create_states():
            self.assertIn(state, G.nodes)

    def test_diffstate(self):
        states = hc._create_states()
        for s1, s2 in product(states, states):
            try:
                is_valid_transition(s1, s2)
            except TransitionValidationError:
                continue

            # only one character should be different
            self.assertNotEqual(s1, s2)
            diff = [x for x in zip(s1, s2) if x[0] != x[1]]
            self.assertEqual(len(diff), 1)

            # and it should be a lower to upper case transition
            self.assertTrue(diff[0][0].islower())
            self.assertTrue(diff[0][1].isupper())
            self.assertEqual(diff[0][0].upper(), diff[0][1])

    def test_model_states(self):
        states = hc._create_states()
        m = hc.CVDmodel()
        self.assertEqual(len(m.states), len(states))
        for state in states:
            self.assertIn(state, m.states)

    def test_model_graph(self):
        m = hc.CVDmodel()
        self.assertEqual(len(m.G.nodes), len(m.states))
        for state in m.states:
            self.assertIn(state, m.G.nodes)

    def test_model_previous_state(self):
        m = hc.CVDmodel()
        for state in m.states:
            previous = m.previous_state(state)
            for pred in m.G.predecessors(state):
                self.assertIn(pred, previous)

    def test_model_next_state(self):
        m = hc.CVDmodel()
        for state in m.states:
            next = m.next_state(state)
            for succ in m.G.successors(state):
                self.assertIn(succ, next)

    def test_paths_between(self):
        m = hc.CVDmodel()
        paths = list(m.paths_between("vfdpxa", "VFDPXA"))
        self.assertEqual(len(paths), 70)

    def test_paths_from(self):
        m = hc.CVDmodel()
        paths = list(m.paths_from("vfdpxa"))
        self.assertEqual(len(paths), 70)

    def test_paths_to(self):
        m = hc.CVDmodel()
        paths = list(m.paths_to("VFDPXA"))
        self.assertEqual(len(paths), 70)


if __name__ == "__main__":
    unittest.main()
