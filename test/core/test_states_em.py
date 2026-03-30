from vultron.core.states.em import EM, EM_NEGOTIATING


def test_em_negotiating_constant_present():
    """EM_NEGOTIATING should exist and contain the negotiating states."""
    assert isinstance(EM_NEGOTIATING, tuple)
    assert EM.PROPOSED in EM_NEGOTIATING
    assert EM.REVISE in EM_NEGOTIATING
    # Ensure the tuple contains exactly the intended members
    assert set(EM_NEGOTIATING) == {EM.PROPOSED, EM.REVISE}
