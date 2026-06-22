"""Tests for vultron.demo.fuzzer.report_management.publication."""

import pytest
import py_trees

from vultron.demo.fuzzer.base import (
    AlmostAlwaysFail,
    AlmostAlwaysSucceed,
    AlwaysSucceed,
    OftenSucceed,
    UsuallyFail,
    UsuallySucceed,
)
from vultron.demo.fuzzer.report_management.publication import (
    AllPublished,
    ExploitReady,
    NoPublishExploit,
    NoPublishFix,
    NoPublishReport,
    PrepareFix,
    PrepareExploit,
    PrepareReport,
    PrioritizePublicationIntents,
    Publish,
    PublicationIntentsSet,
    ReprioritizeExploit,
    ReprioritizeFix,
    ReprioritizeReport,
)

_ALL_NODES = [
    AllPublished,
    PublicationIntentsSet,
    PrioritizePublicationIntents,
    Publish,
    NoPublishExploit,
    ExploitReady,
    PrepareExploit,
    ReprioritizeExploit,
    NoPublishFix,
    PrepareFix,
    ReprioritizeFix,
    NoPublishReport,
    PrepareReport,
    ReprioritizeReport,
]


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_node_is_behaviour(node_cls):
    """Each node must be a py_trees Behaviour."""
    node = node_cls()
    assert isinstance(node, py_trees.behaviour.Behaviour)


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_node_has_docstring(node_cls):
    """Each node must have a non-empty docstring (BT-16-003)."""
    assert node_cls.__doc__ and node_cls.__doc__.strip()


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_node_name_defaults_to_class_name(node_cls):
    """Default name must be the class name."""
    node = node_cls()
    assert node.name == node_cls.__name__


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_node_name_custom(node_cls):
    """Custom name must be respected."""
    node = node_cls(name="custom")
    assert node.name == "custom"


@pytest.mark.parametrize("node_cls", _ALL_NODES)
def test_update_returns_status(node_cls):
    """update() must return a valid py_trees Status."""
    node = node_cls()
    node.setup()
    status = node.update()
    assert status in (
        py_trees.common.Status.SUCCESS,
        py_trees.common.Status.FAILURE,
        py_trees.common.Status.RUNNING,
    )


# --- Base type assertions ---


def test_all_published_base_type():
    assert issubclass(AllPublished, AlmostAlwaysFail)


def test_publication_intents_set_base_type():
    assert issubclass(PublicationIntentsSet, UsuallyFail)


def test_prioritize_publication_intents_base_type():
    assert issubclass(PrioritizePublicationIntents, AlwaysSucceed)


def test_publish_base_type():
    assert issubclass(Publish, AlmostAlwaysSucceed)


def test_no_publish_exploit_base_type():
    assert issubclass(NoPublishExploit, UsuallySucceed)


def test_exploit_ready_base_type():
    assert issubclass(ExploitReady, OftenSucceed)


def test_prepare_exploit_base_type():
    assert issubclass(PrepareExploit, AlmostAlwaysSucceed)


def test_reprioritize_exploit_base_type():
    assert issubclass(ReprioritizeExploit, AlwaysSucceed)


def test_no_publish_fix_base_type():
    assert issubclass(NoPublishFix, AlmostAlwaysFail)


def test_prepare_fix_base_type():
    assert issubclass(PrepareFix, AlmostAlwaysSucceed)


def test_reprioritize_fix_base_type():
    assert issubclass(ReprioritizeFix, AlwaysSucceed)


def test_no_publish_report_base_type():
    assert issubclass(NoPublishReport, AlmostAlwaysFail)


def test_prepare_report_base_type():
    assert issubclass(PrepareReport, AlmostAlwaysSucceed)


def test_reprioritize_report_base_type():
    assert issubclass(ReprioritizeReport, AlwaysSucceed)


# --- Success rate assertions ---


def test_all_published_success_rate():
    assert AllPublished.success_rate == pytest.approx(0.10)


def test_publication_intents_set_success_rate():
    assert PublicationIntentsSet.success_rate == pytest.approx(0.25)


def test_prioritize_publication_intents_success_rate():
    assert PrioritizePublicationIntents.success_rate == pytest.approx(1.0)


def test_publish_success_rate():
    assert Publish.success_rate == pytest.approx(0.90)


def test_no_publish_exploit_success_rate():
    assert NoPublishExploit.success_rate == pytest.approx(0.75)


def test_exploit_ready_success_rate():
    assert ExploitReady.success_rate == pytest.approx(0.70)


def test_prepare_exploit_success_rate():
    assert PrepareExploit.success_rate == pytest.approx(0.90)


def test_reprioritize_exploit_success_rate():
    assert ReprioritizeExploit.success_rate == pytest.approx(1.0)


def test_no_publish_fix_success_rate():
    assert NoPublishFix.success_rate == pytest.approx(0.10)


def test_prepare_fix_success_rate():
    assert PrepareFix.success_rate == pytest.approx(0.90)


def test_reprioritize_fix_success_rate():
    assert ReprioritizeFix.success_rate == pytest.approx(1.0)


def test_no_publish_report_success_rate():
    assert NoPublishReport.success_rate == pytest.approx(0.10)


def test_prepare_report_success_rate():
    assert PrepareReport.success_rate == pytest.approx(0.90)


def test_reprioritize_report_success_rate():
    assert ReprioritizeReport.success_rate == pytest.approx(1.0)
