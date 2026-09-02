#  Copyright (c) 2024-2025 Carnegie Mellon University and Contributors.
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
import inspect
import json
import os
import tempfile
import unittest

import pytest

import vultron.wire.as2.vocab.examples.vocab_examples as examples
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# Rendering utilities, not vocabulary examples.
_NOT_EXAMPLES = frozenset({"main", "json2md", "obj_to_file", "print_obj"})


def _example_funcs() -> list:
    """Every zero-argument example function reachable from ``vocab_examples``.

    These are exactly the callables the ``markdown_exec`` blocks under
    ``docs/howto/activitypub/`` invoke, so this list is what keeps the docs
    build from being the only place a broken example is detected.
    """
    funcs = []
    for name, obj in vars(examples).items():
        if name.startswith("_") or name in _NOT_EXAMPLES:
            continue
        if not inspect.isfunction(obj):
            continue
        if not obj.__module__.startswith("vultron.wire.as2.vocab.examples"):
            continue
        required = [
            p
            for p in inspect.signature(obj).parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind
            in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
        ]
        if required:
            continue
        funcs.append(obj)
    return sorted(funcs, key=lambda f: f.__name__)


class Foo(as_Base):
    bar: str = "baz"


def _frozen_report() -> as_VulnerabilityReport:
    """A wire report, which is frozen and carries both timestamps."""
    return as_VulnerabilityReport(
        name="FDR-0000001",
        id_="https://vultron.example/reports/FDR-0000001",
        content="I found a vulnerability!",
        attributed_to=["https://vultron.example/users/finndervul"],
    )


class TestStripPublishedUpdated(unittest.TestCase):
    """Regression tests for issue #2904.

    ``Foo`` above is not frozen and declares neither ``published`` nor
    ``updated``, so ``TestVocabUtils`` never reaches the timestamp-stripping
    branch. These tests use a real wire object, which is frozen by design
    (ADR-0074) and does carry both timestamps.
    """

    def test_frozen_wire_object_carries_both_timestamps(self):
        report = _frozen_report()
        self.assertIsNotNone(report.published)
        self.assertIsNotNone(report.updated)
        self.assertTrue(type(report).model_config.get("frozen"))

    def test_json2md_strips_timestamps_from_frozen_model(self):
        report = _frozen_report()

        rendered = examples.json2md(report)
        payload = json.loads(
            rendered.removeprefix("```json").removesuffix("```")
        )

        self.assertNotIn("published", payload)
        self.assertNotIn("updated", payload)
        self.assertEqual(payload["name"], "FDR-0000001")

    def test_json2md_does_not_mutate_the_object_it_renders(self):
        """The examples are shared singletons served live by the example API.

        Stripping in place would strip them for every other consumer too
        (the shared-singleton hazard of issue #1328), so rendering MUST
        leave its argument alone.
        """
        report = _frozen_report()
        published, updated = report.published, report.updated

        examples.json2md(report)

        self.assertEqual(report.published, published)
        self.assertEqual(report.updated, updated)

    def test_obj_to_file_strips_timestamps_from_frozen_model(self):
        report = _frozen_report()
        with tempfile.TemporaryDirectory() as tmpdirname:
            filename = os.path.join(tmpdirname, "report.json")
            examples.obj_to_file(report, filename)

            with open(filename, "r") as f:
                payload = json.load(f)

        self.assertNotIn("published", payload)
        self.assertNotIn("updated", payload)
        self.assertEqual(payload["name"], "FDR-0000001")
        self.assertIsNotNone(report.published)


@pytest.mark.parametrize("func", _example_funcs(), ids=lambda f: f.__name__)
def test_every_example_renders_as_json(func):
    """Every documented example must render to parseable JSON.

    The ``markdown_exec`` blocks in ``docs/`` are `print(json2md(func()))`,
    so a failure here is a broken page on the published site.
    """
    rendered = examples.json2md(func())

    assert rendered.startswith("```json")
    assert rendered.endswith("```")
    payload = json.loads(rendered.removeprefix("```json").removesuffix("```"))
    assert payload.get("type"), f"{func.__name__} rendered no AS2 type"
    assert "published" not in payload
    assert "updated" not in payload


def test_example_func_discovery_is_not_vacuous():
    """Guard the ratchet above against silently collecting nothing."""
    names = {f.__name__ for f in _example_funcs()}

    assert len(names) > 50, f"only found {len(names)} example functions"
    for expected in ("gen_report", "case", "create_case", "propose_embargo"):
        assert expected in names


class TestVocabUtils(unittest.TestCase):
    def test_json2md(self):
        foo = Foo(bar="baz")

        txt = examples.json2md(foo)
        self.assertTrue(txt.startswith("```json"))
        self.assertTrue(txt.endswith("```"))
        self.assertTrue("bar" in txt)
        self.assertTrue("baz" in txt)

    def test_obj_to_file(self):
        foo = Foo(bar="baz")
        with tempfile.TemporaryDirectory() as tmpdirname:
            filename = tmpdirname + "/test.md"
            self.assertFalse(os.path.exists(filename))
            examples.obj_to_file(foo, filename)
            self.assertTrue(os.path.exists(filename))

            with open(filename, "r") as f:
                obj = json.load(f)
            self.assertEqual(obj["bar"], "baz")


if __name__ == "__main__":
    unittest.main()
