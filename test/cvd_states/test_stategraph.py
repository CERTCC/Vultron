#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

import unittest

import networkx as nx

import vultron.cvd_states.errors as err
import vultron.cvd_states.hypercube as sg
import vultron.cvd_states.validations as val


class TestStategraph(unittest.TestCase):
    def setUp(self):
        self.model = sg.CVDmodel()

    def tearDown(self):
        pass

    def test__create_graph(self):
        G = sg._create_graph()

        # G should have all the states as nodes
        for n in sg._create_states():
            self.assertTrue(n in G)

        # the valid graph should have 58 edges
        self.assertEqual(58, len(G.edges))

        # G should have valid edges with labels
        for a, b, t in G.edges(data="label"):
            self.assertIsNone(val.is_valid_transition(a, b))
            self.assertEqual(sg._diffstate(a, b), t)
            self.assertTrue(t in "VFDPXA")

        self.assertTrue(nx.is_directed_acyclic_graph(G))

        n_paths = len(list(nx.all_simple_paths(G, "vfdpxa", "VFDPXA")))
        self.assertEqual(70, n_paths)

    def test__create_states(self):
        states = sg._create_states()
        # enforce causality rules
        for x in states:
            self.assertNotIn("vF", x, x)
            self.assertNotIn("fD", x, x)

        # should be 32 states
        self.assertEqual(32, len(states))

    def test_H(self):
        m = self.model

        H = m.H
        self.assertEqual(70, len(H))
        for h in H:
            self.assertIsNone(val.is_valid_history(h), h)

    def test_paths_from(self):
        m = self.model

        H = m.sequences_from("VFDpxa")
        self.assertEqual(5, len(H), H)

        H = m.sequences_from("Vfdpxa")
        self.assertEqual(42, len(H), H)

        H = m.sequences_from("vfdPxa")
        self.assertEqual(12, len(H))

        H = m.sequences_from("vfdpXa")
        self.assertEqual(3, len(H), H)

        H = m.sequences_from("vfdpxA")
        self.assertEqual(13, len(H), H)

    def test_paths_to(self):
        m = self.model

        H = m.sequences_to("VFDPXa")
        self.assertEqual(13, len(H), H)

        H = m.sequences_to("VFDPxA")
        self.assertEqual(19, len(H), H)

        H = m.sequences_to("VFDpXA")
        self.assertEqual(4, len(H))

        H = m.sequences_to("VFdPXA")
        self.assertEqual(34, len(H), H)

        H = m.sequences_to("VfdPXA")
        self.assertEqual(12, len(H), H)

        H = m.sequences_to("vfdPXA")
        self.assertEqual(1, len(H), H)

    def test_walk_from(self):
        m = self.model
        start = "vfdpxa"

        path, probabilities = m.walk_from(start)
        self.assertGreaterEqual(len(path), 0)
        self.assertLessEqual(len(path), 6)
        self.assertEqual(len(path), len(probabilities))

        # check each hop probability is 0 < p <= 1
        for _p in probabilities:
            self.assertGreater(_p, 0)
            self.assertLessEqual(_p, 1)

        import math

        # check combined path probability is 0 < p <= 1
        p = math.prod(probabilities)
        self.assertGreater(p, 0)
        self.assertLessEqual(p, 1)

    def test_compute_h_probabilities(self):
        m = self.model
        H_prob = m.H_prob

        # make sure the keys match up
        self.assertEqual(len(m.H), len(H_prob))
        self.assertEqual(set(m.H), set(H_prob.keys()))

        # make sure the probabilities are sane
        for v in H_prob.values():
            self.assertGreater(v, 0)
            self.assertLessEqual(v, 1)

    def test_compute_tfidf(self):
        m = self.model
        df = m._compute_tfidf()

        self.assertIn("tfidf", df.columns)
        self.assertIn("rank", df.columns)
        tfidf = df["tfidf"]
        self.assertGreaterEqual(tfidf.min(), 0, tfidf.min())
        self.assertLessEqual(tfidf.max(), 20, tfidf.max())

    def test_compute_s_scores(self):
        m = self.model

        score = m._compute_s_scores()
        for k, v in score.items():
            self.assertIn(k, m.states)
            self.assertGreaterEqual(v, -10)
            self.assertLessEqual(v, 10)

    def test_init_df(self):
        m = self.model
        df = m._init_H_df()

        for c in ["h", "p", "D<A"]:
            self.assertIn(c, df.columns)

        # probabilities sum to 1
        self.assertAlmostEqual(1, df["p"].sum())

        # all histories are present
        for h in m.H:
            self.assertIn(h, df["h"].values)

        # nothing extra
        self.assertEqual(len(df), len(m.H))

        # d columns are all 0 or 1
        for c in m.d_cols:
            self.assertEqual({0, 1}, set(df[c].values))

        # w columns are all 0<=x<=1
        for c in m.w_cols:
            for x in df[c].values:
                self.assertGreaterEqual(x, 0)
                self.assertLessEqual(x, 1)

    def test_compute_f_d(self):
        m = self.model
        f_d = m._compute_f_d()
        self.assertIsInstance(f_d, dict)

        for k, v in f_d.items():
            # keys are d
            self.assertIn(k, m._D)

            # values are 0 < v <= 1
            self.assertGreater(v, 0)
            self.assertLessEqual(v, 1)

    def test_compute_f_d_orig(self):
        m = self.model
        f_d = m._compute_f_d_orig()

        for v in f_d.values:
            self.assertGreater(v, 0)
            self.assertLessEqual(v, 1)

    def test_build_good(self):
        m = self.model
        good = m._build_good()

        self.assertIsInstance(good, dict)

        for k, v in good.items():
            # k is a compiled re
            self.assertTrue(hasattr(k, "pattern"))
            self.assertEqual(len(k.pattern), 6)

            # patterns have letters in the right positions
            for i, c in enumerate(k.pattern):
                if c == ".":
                    continue
                else:
                    self.assertEqual(i, m.idx[c])

            # values are 0 < v <= 1
            self.assertGreater(v, 0)
            self.assertLessEqual(v, 1)

    def test_build_bad(self):
        m = self.model
        bad = m._build_bad()

        self.assertIsInstance(bad, dict)

        for k, v in bad.items():
            # k is a compiled re
            self.assertTrue(hasattr(k, "pattern"))
            self.assertEqual(len(k.pattern), 6)

            # patterns have letters in the right positions
            for i, c in enumerate(k.pattern):
                if c == ".":
                    continue
                else:
                    self.assertEqual(i, m.idx[c])

            # values are 0 < v <= 1
            self.assertGreater(v, 0)
            self.assertLessEqual(v, 1)

    def test_build_index(self):
        m = self.model

        idx = m._construct_index()

        # returns a dict
        self.assertIsInstance(idx, dict)

        for k in list("vfdpxa"):
            u = k.upper()

            # each of vfdpxa is in index
            self.assertIn(k, idx)
            # each of VFDPXA is in index
            self.assertIn(u, idx)

            # position of each letter is the same regardless of case
            self.assertEqual(idx[k], idx[u])

    def test_build_good_patterns(self):
        m = self.model

        g = m._construct_good_patterns()

        self.assertIsInstance(g, dict)

        for k, pattern in g.items():
            # k is a tuple from _D of length 2
            self.assertIsInstance(k, tuple)
            self.assertIn(k, m._D)
            self.assertEqual(len(k), 2)

            # both elements in k should be uppercase
            first, second = k
            self.assertTrue(first.isupper())
            self.assertTrue(second.isupper())

            # but in the pattern, only first is uppercase
            self.assertIn(first, pattern)
            self.assertIn(second.lower(), pattern)

            # the rest of the chars in pattern should be wildcards
            wildcards = [c for c in pattern if c == "."]
            self.assertEqual(len(wildcards), 4)

    def test_build_bad_patterns(self):
        m = self.model

        b = m._construct_bad_patterns()

        self.assertIsInstance(b, dict)

        for k, pattern in b.items():
            # k is a reversed tuple from _D of length 2
            self.assertIsInstance(k, tuple)
            self.assertIn(k[::-1], m._D)
            self.assertEqual(len(k), 2)

            # both elements in k should be uppercase
            first, second = k
            self.assertTrue(first.isupper())
            self.assertTrue(second.isupper())

            # but in the pattern, only first is uppercase
            self.assertIn(first, pattern)
            self.assertIn(second.lower(), pattern)

            # the rest of the chars in pattern should be wildcards
            wildcards = [c for c in pattern if c == "."]
            self.assertEqual(len(wildcards), 4)

    def test_state_adjacency(self):
        m = self.model
        df = m.state_adjacency_matrix()

        # every node has indegree >0 except first
        total = df.sum()
        for row in total[1:]:
            self.assertGreater(row, 0)
        self.assertEqual(total.iloc[0], 0)

        # every node has outdegree >0 except last
        total = df.sum(axis=1)
        for row in total[:-1]:
            self.assertGreater(row, 0)
        self.assertEqual(total.iloc[-1], 0)

    def test_state_transition(self):
        m = self.model
        df = m.state_transition_matrix()

        total = df.sum(axis=1)
        # all rows add to 1 except the last
        for row in total[:-1]:
            self.assertEqual(row, 1)
        self.assertEqual(total.iloc[-1], 0)

    def test_init_sdf(self):
        m = self.model
        df = m._init_sdf()

        self.assertEqual(len(df), len(m.states))
        for s in m.states:
            self.assertIn(s, df.index)

        self.assertIn("rank", df.columns)
        self.assertIn("pagerank", df.columns)
        self.assertFalse(any(df["rank"].isnull()))
        self.assertFalse(any(df["pagerank"].isnull()))

    def test_find_states(self):
        m = self.model
        pat = ".f.PxA"
        matches = m.find_states(pat)
        self.assertEqual(len(matches), 2)
        self.assertIn("vfdPxA", matches)
        self.assertIn("VfdPxA", matches)

        self.assertRaises(err.CVDmodelError, m.find_states, "abcdefg")

    def test_next_state(self):
        m = self.model

        from itertools import product

        for s1, s2 in product(m.states, m.states):
            t = sg._diffstate(s1, s2)
            # diffstate returns none on invalid transitions
            if t is not None:
                self.assertEqual(m.next_state(s1, t), s2, (s1, s2, t))

        for state in m.states:
            if state == "VFDPXA":
                continue
            self.assertGreater(len(m.next_state(state)), 0)

    def test_compute_pagerank(self):
        m = self.model

        pr = m.compute_pagerank()

        # expect VFDPXA to be max element of pr
        import operator

        max_key = max(pr.items(), key=operator.itemgetter(1))[0]
        self.assertEqual("VFDPXA", max_key)

        # self.assertFalse(True,m.compute_pagerank())

    def test_proto_states(self):
        ps = sg._proto_states()

        for e in sg.EVENTS:
            x = f"{e.lower()}{e.upper()}"
            self.assertIn(x, ps)


if __name__ == "__main__":
    unittest.main()
