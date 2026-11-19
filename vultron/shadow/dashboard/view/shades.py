#!/usr/bin/env python

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


"""Each move's shade: its layer's colour in its band's colour map, the
text colour that reads on it, and a band's legend of one shade per layer
(SHD-03-003).  The stops are matplotlib's, so the page shades without
matplotlib.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from vultron.measure.advice import ColourMap

#: The label at the layer-1 end of a shaded band's legend (SHD-03-003).
LEGEND_BETTER = "better (layer 1) ◀"

#: The label at the deepest end of a shaded band's legend (SHD-03-003).
LEGEND_DOMINATED = "▶ dominated (deeper layers)"

#: Nine evenly spaced stops of each colour map, dark end first, as
#: matplotlib draws them, so the page shades without matplotlib.
COLOUR_STOPS: Mapping[ColourMap, tuple[str, ...]] = {
    ColourMap.VIRIDIS: (
        "#440154",
        "#472d7b",
        "#3b528b",
        "#2c728e",
        "#21918c",
        "#28ae80",
        "#5ec962",
        "#addc30",
        "#fde725",
    ),
    ColourMap.CIVIDIS: (
        "#00224e",
        "#1a386f",
        "#434e6c",
        "#61656f",
        "#7d7c78",
        "#9b9476",
        "#bcae6c",
        "#dec958",
        "#fee838",
    ),
}

#: The relative luminance at which black and white text have the same
#: WCAG contrast ratio: above it, black text reads better.
_LIGHT_BACKGROUND = 0.179


class Shade(BaseModel):
    """The colours of one shaded move's row.

    Fields:
        background: The row's fill, from its band's colour map.
        text: Black or white, whichever reads on *background*.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    background: str
    text: str

    @property
    def css(self) -> str:
        """The row's style, as a table cell's CSS."""
        return f"background-color: {self.background}; color: {self.text}"


type _RGB = tuple[float, float, float]


def _rgb(hex_colour: str) -> _RGB:
    return (
        int(hex_colour[1:3], 16),
        int(hex_colour[3:5], 16),
        int(hex_colour[5:7], 16),
    )


def _luminance(rgb: _RGB) -> float:
    """WCAG relative luminance of an sRGB colour, 0 (black) to 1 (white)."""

    def linear(channel: float) -> float:
        c = channel / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def shade(colour_map: ColourMap, layer: int, deepest: int) -> Shade:
    """*layer*'s shade in *colour_map*: layer 1 at the dark end, *deepest*
    at the light end, and every layer between spaced evenly.

    Raises:
        ValueError: *layer* is not from 1 to *deepest*.
    """
    if not 1 <= layer <= deepest:
        raise ValueError(f"layer {layer} is not from 1 to {deepest}")
    stops = COLOUR_STOPS[colour_map]
    at = 0.0 if deepest == 1 else (layer - 1) / (deepest - 1)
    position = at * (len(stops) - 1)
    low = min(int(position), len(stops) - 2)
    within = position - low
    lo, hi = _rgb(stops[low]), _rgb(stops[low + 1])
    rgb: _RGB = (
        lo[0] + (hi[0] - lo[0]) * within,
        lo[1] + (hi[1] - lo[1]) * within,
        lo[2] + (hi[2] - lo[2]) * within,
    )
    return Shade(
        background="#" + "".join(f"{round(c):02x}" for c in rgb),
        text="#000000" if _luminance(rgb) > _LIGHT_BACKGROUND else "#ffffff",
    )


def band_legend_shades(
    colour_map: ColourMap, deepest: int
) -> tuple[Shade, ...]:
    """Each layer's shade in *colour_map*, from layer 1 (better, the dark
    end) to *deepest* (dominated, the light end): one legend cell per
    layer, each the shade :func:`shade` gives that layer's rows.

    Raises:
        ValueError: *deepest* is below 1.
    """
    if deepest < 1:
        raise ValueError(f"the deepest layer {deepest} is below 1")
    return tuple(
        shade(colour_map, layer, deepest) for layer in range(1, deepest + 1)
    )


__all__ = [
    "COLOUR_STOPS",
    "LEGEND_BETTER",
    "LEGEND_DOMINATED",
    "Shade",
    "band_legend_shades",
    "shade",
]
