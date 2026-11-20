"""A move's shade and a band's legend, read from its colour map
(#6603, #6673).
"""

import pytest

from vultron.measure.advice import ColourMap
from vultron.shadow.dashboard import view


def test_a_shade_runs_from_the_dark_end_to_the_light_end():
    for colour_map, stops in view.COLOUR_STOPS.items():
        assert view.shade(colour_map, 1, 1).background == stops[0]
        assert view.shade(colour_map, 1, 3).background == stops[0]
        assert view.shade(colour_map, 2, 3).background == stops[4]
        assert view.shade(colour_map, 3, 3).background == stops[-1]
        assert view.shade(colour_map, 1, 3).text == "#ffffff"
        assert view.shade(colour_map, 3, 3).text == "#000000"
    assert view.shade(ColourMap.VIRIDIS, 2, 9).background == "#472d7b"


def test_a_shade_between_two_stops_mixes_them():
    """Layer 2 of 33 sits a quarter of the way from viridis's first stop,
    ``#440154``, to its second, ``#472d7b``."""
    assert view.shade(ColourMap.VIRIDIS, 2, 33).background == "#450c5e"


@pytest.mark.parametrize("layer, deepest", [(0, 2), (3, 2), (-1, 1)])
def test_a_layer_outside_the_advice_has_no_shade(layer, deepest):
    with pytest.raises(ValueError, match=f"layer {layer} is not from 1"):
        view.shade(ColourMap.CIVIDIS, layer, deepest)


def test_a_shade_reads_as_a_cells_css():
    assert view.Shade(background="#440154", text="#ffffff").css == (
        "background-color: #440154; color: #ffffff"
    )


@pytest.mark.parametrize("deepest", [1, 2, 4])
def test_a_legend_is_each_layers_shade_from_better_to_dominated(deepest):
    """#6673 AC-1: one cell per layer, each the shade that layer's rows
    take, layer 1 at the dark end."""
    for colour_map in ColourMap:
        legend = view.band_legend_shades(colour_map, deepest)
        assert legend == tuple(
            view.shade(colour_map, layer, deepest)
            for layer in range(1, deepest + 1)
        )
        assert legend[0].background == view.COLOUR_STOPS[colour_map][0]
        if deepest > 1:
            assert legend[-1].background == view.COLOUR_STOPS[colour_map][-1]


def test_a_legend_needs_a_layer():
    with pytest.raises(ValueError):
        view.band_legend_shades(ColourMap.VIRIDIS, 0)
