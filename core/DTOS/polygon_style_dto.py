# -----------------------------------------------------------
# 2025-04-29
# Copyright (C) 2025 K2 Geospatial
# -----------------------------------------------------------
# Licensed under the terms of GNU GPL 3
# #
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
# -----------------------------------------------------------
from qgis.core import (
    QgsFillSymbol,
    QgsFillSymbolLayer,
    QgsImageFillSymbolLayer,
    QgsLinePatternFillSymbolLayer,
    QgsLineSymbolLayer,
    QgsRasterFillSymbolLayer,
    QgsRasterLineSymbolLayer,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsSVGFillSymbolLayer,
    QgsSymbolLayer,
)
from qgis.PyQt.QtCore import Qt

from ..plugin_util import (
    SVG_to_base64,
    convert_measurement_to_pixel,
    convert_pen_style_to_dash_array,
    image_to_base64,
    opacity_to_transparency,
    qimage_to_base64,
    resolve_fill_pattern_tile,
    resolve_line_pattern_fill_svg,
    resolve_line_symbol_strip_svg,
    resolve_polygon_svg_params,
    resolve_raster_fill_size,
    transparency_to_opacity,
)
from .style_dto import StyleDTO


class PolygonStyleDTO(StyleDTO):
    fillColor: str
    """value in hexadecimal: #00FF00"""
    borderThickness: int
    borderColor: str
    """value in hexadecimal: #00FF00"""
    borderTransparency: int
    """value between: 0 and 100"""
    patternData: str
    """value in base64"""
    borderDashPattern: list[int]
    """value in pair of int ex: [1, 1], [1,3,5,4]"""
    borderPatternData: str
    """value in base64"""
    showPatternBackgroundColor: bool
    """paints fillColor behind patternData; without it the pattern sits on nothing"""

    FILL_PROPERTIES = ("fillColor", "transparency", "patternData")
    BORDER_PROPERTIES = (
        "borderColor",
        "borderThickness",
        "borderTransparency",
        "borderDashPattern",
        "borderPatternData",
    )

    def __init__(self):
        super().__init__(self.StyleDTOType.POLYGON)
        self.borderTransparency = 0

    @classmethod
    def from_symbol(cls, symbol: QgsFillSymbol) -> list["PolygonStyleDTO"]:
        """
        A JMap Cloud polygon style carries both the fill and the border, so the whole
        fill symbol becomes a single style instead of one style per symbol layer.
        Exporting one style per symbol layer would create one style rule condition per
        symbol layer, duplicating every value of a categorized or graduated symbology.

        Symbol layers are merged bottom-up, so the topmost definition of each property
        wins, the same way QGIS draws them.
        """
        merged = None
        unsupported_symbol_layers = 0

        outline_layers = cls._border_pattern_layers(symbol)
        border_pattern = resolve_line_symbol_strip_svg(outline_layers) if outline_layers else None
        if border_pattern is None:
            # no strip to draw them into, so they go through the border properties
            # one by one rather than being dropped
            outline_layers = []

        for symbol_layer in cls.rendered_symbol_layers(symbol):
            if symbol_layer in outline_layers:
                # drawn as a whole into borderPatternData, below
                continue
            dto = cls.from_symbol_layer(symbol_layer)
            if dto is None:
                unsupported_symbol_layers += 1
                continue
            dto.transparency = opacity_to_transparency(
                transparency_to_opacity(dto.transparency) * symbol.opacity()
            )
            dto.borderTransparency = opacity_to_transparency(
                transparency_to_opacity(dto.borderTransparency) * symbol.opacity()
            )
            if merged is None:
                merged = dto
                continue
            merged._merge(dto, symbol_layer)

        if outline_layers:
            merged = cls._apply_border_pattern(
                merged, outline_layers, border_pattern, symbol.opacity()
            )

        if merged is not None and hasattr(merged, "patternData") and hasattr(merged, "fillColor"):
            merged.showPatternBackgroundColor = True

        dtos = [merged] if merged is not None else []
        # kept in the list so the caller can report the unsupported symbol layers
        # instead of dropping them silently
        dtos.extend([None] * unsupported_symbol_layers)

        return dtos

    @classmethod
    def _border_pattern_layers(cls, symbol: QgsFillSymbol) -> list:
        """
        The outline symbol layers that only a border pattern can describe.

        One plain outline maps onto the border properties exactly, so it is left
        alone. Several of them, or one that draws symbols along the line, would lose
        everything but the topmost layer that way.
        """
        outline_layers = [
            symbol_layer
            for symbol_layer in cls.rendered_symbol_layers(symbol)
            if isinstance(symbol_layer, QgsLineSymbolLayer)
        ]
        if len(outline_layers) < 2 and all(
            isinstance(symbol_layer, QgsSimpleLineSymbolLayer) for symbol_layer in outline_layers
        ):
            return []
        return outline_layers

    @classmethod
    def _apply_border_pattern(
        cls,
        merged: "PolygonStyleDTO",
        outline_layers: list,
        border_pattern: tuple,
        opacity: float,
    ) -> "PolygonStyleDTO":
        """
        Put the outline into borderPatternData, at the scale JMap repeats it.

        The strip is drawn at the border's own thickness so it can be sent with a
        thickness of 1; JMap scales the strip by that thickness, and anything else
        would need the fractional value it cannot express.
        """
        svg, _ = border_pattern
        if merged is None:
            merged = cls()
        merged.borderPatternData = SVG_to_base64(svg)
        # JMap scales the strip by the thickness, so the strip's own height is the border
        merged.borderThickness = 1
        merged.borderTransparency = opacity_to_transparency(opacity)

        widest = max(outline_layers, key=lambda symbol_layer: symbol_layer.width())
        merged.borderColor = widest.color().name()
        return merged

    def _merge(self, other: "PolygonStyleDTO", symbol_layer: QgsSymbolLayer):
        """Overwrite with the properties `symbol_layer` is responsible for."""
        properties = ()
        if isinstance(symbol_layer, (QgsSimpleLineSymbolLayer, QgsRasterLineSymbolLayer)):
            if (
                isinstance(symbol_layer, QgsSimpleLineSymbolLayer)
                and symbol_layer.penStyle() == Qt.PenStyle.NoPen
            ):
                # draws nothing, so it must not hide the border it is merged into
                return
            # an outline symbol layer only describes the border
            properties = self.BORDER_PROPERTIES
        elif isinstance(symbol_layer, QgsSimpleFillSymbolLayer):
            # a simple fill carries its own stroke
            properties = self.FILL_PROPERTIES + self.BORDER_PROPERTIES
        else:
            properties = self.FILL_PROPERTIES

        for property_name in properties:
            if hasattr(other, property_name):
                setattr(self, property_name, getattr(other, property_name))

    @classmethod
    def from_symbol_layer(cls, symbol_layer: QgsSymbolLayer) -> "PolygonStyleDTO":
        dto = cls()
        if isinstance(symbol_layer, QgsSimpleFillSymbolLayer):
            dto.fillColor = symbol_layer.color().name()
            dto.transparency = opacity_to_transparency(symbol_layer.color().alphaF())
            dto.borderColor = symbol_layer.strokeColor().name()
            dto.borderTransparency = opacity_to_transparency(symbol_layer.strokeColor().alphaF())
            width = symbol_layer.strokeWidth()
            if width == 0:
                dto.borderThickness = 0
            else:
                dto.borderThickness = max(
                    1, round(convert_measurement_to_pixel(width, symbol_layer.strokeWidthUnit()))
                )

            border_pen_style = symbol_layer.strokeStyle()
            if border_pen_style == Qt.PenStyle.NoPen:
                dto.borderTransparency = 100
            dto.borderDashPattern = convert_pen_style_to_dash_array(
                border_pen_style, dto.borderThickness
            )

        elif isinstance(symbol_layer, QgsImageFillSymbolLayer):
            if isinstance(symbol_layer, QgsSVGFillSymbolLayer):
                svg_parsed = resolve_polygon_svg_params(symbol_layer)

                if len(svg_parsed) == 0:
                    return None

                dto.patternData = SVG_to_base64(svg_parsed)
            elif isinstance(symbol_layer, QgsRasterFillSymbolLayer):
                size = resolve_raster_fill_size(symbol_layer)
                if size is None:
                    return None

                dto.patternData = image_to_base64(symbol_layer.imageFilePath(), size)
                dto.transparency = opacity_to_transparency(symbol_layer.opacity())
            elif isinstance(symbol_layer, QgsLinePatternFillSymbolLayer):
                svg_hatch, _ = resolve_line_pattern_fill_svg(symbol_layer)

                if len(svg_hatch) == 0:
                    return None

                dto.patternData = SVG_to_base64(svg_hatch)
            else:
                return cls._from_rendered_fill(symbol_layer)

        elif isinstance(symbol_layer, QgsSimpleLineSymbolLayer):
            width = symbol_layer.width()
            if width == 0:
                dto.borderThickness = 0
            else:
                dto.borderThickness = max(
                    1, round(convert_measurement_to_pixel(width, symbol_layer.widthUnit()))
                )
            dto.borderColor = symbol_layer.color().name()
            dto.borderTransparency = opacity_to_transparency(symbol_layer.color().alphaF())
            dto.fillColor = symbol_layer.color().name()
            dto.transparency = 100  # only border, no fill
            if symbol_layer.useCustomDashPattern():
                dash_pattern = convert_measurement_to_pixel(
                    symbol_layer.customDashVector(), symbol_layer.customDashPatternUnit()
                )
                dto.borderDashPattern = [
                    v / dto.borderThickness for v in dash_pattern
                ]  # because Mapbox dash-array is value * lineWidth
            else:
                dto.borderDashPattern = convert_pen_style_to_dash_array(
                    symbol_layer.penStyle(), dto.borderThickness
                )

        elif isinstance(symbol_layer, QgsRasterLineSymbolLayer):
            width = symbol_layer.width()
            if width == 0:
                dto.borderThickness = 0
            else:
                dto.borderThickness = max(
                    1, round(convert_measurement_to_pixel(width, symbol_layer.widthUnit()))
                )
            dto.borderTransparency = opacity_to_transparency(symbol_layer.color().alphaF())
            dto.patternData = image_to_base64(symbol_layer.path())
            dto.transparency = 100  # only border, no fill
            dto.fillColor = symbol_layer.color().name()
        elif isinstance(symbol_layer, QgsFillSymbolLayer):
            return cls._from_rendered_fill(symbol_layer)
        else:
            return None

        return dto

    @classmethod
    def _from_rendered_fill(cls, symbol_layer: QgsFillSymbolLayer) -> "PolygonStyleDTO":
        """
        Fills with no converter of their own, exported as the tile they repeat.

        Only the pattern is set, so the colours of the symbol layers underneath keep
        showing through once merged.
        """
        tile = resolve_fill_pattern_tile(symbol_layer)
        if tile is None:
            return None

        dto = cls()
        dto.patternData = qimage_to_base64(tile)
        return dto
