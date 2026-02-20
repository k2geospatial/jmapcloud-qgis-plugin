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

import io
import re

from qgis.core import (
    Qgis,
    QgsFillSymbol,
    QgsFillSymbolLayer,
    QgsFontMarkerSymbolLayer,
    QgsLabelLineSettings,
    QgsLabelThinningSettings,
    QgsLineSymbol,
    QgsLineSymbolLayer,
    QgsMarkerSymbol,
    QgsMarkerSymbolLayer,
    QgsPalLayerSettings,
    QgsProject,
    QgsRasterMarkerSymbolLayer,
    QgsRuleBasedLabeling,
    QgsRuleBasedRenderer,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
    QgsSymbol,
    QgsSymbolLayer,
    QgsTextBackgroundSettings,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsVectorTileBasicLabeling,
    QgsVectorTileBasicLabelingStyle,
    QgsVectorTileBasicRendererStyle,
)
from qgis.PyQt.QtCore import QPointF, QSizeF, Qt
from qgis.PyQt.QtGui import QColor, QFont, QPixmap

from ..constant import ElementTypeWrapper
from ..plugin_util import (
    convert_jmap_text_mouse_over_expression,
    convert_jmap_text_label_expression,
    convert_zoom_to_scale,
    find_value_in_dict_or_first,
)
from ..qgs_message_bar_handler import QgsMessageBarHandler
from .jmap_services_access import JMapMCS


class StyleManager:

    class QGISExpression:
        # to identify mapbox expression from normal value
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return str(self.value)

        def __repr__(self):
            return str({"__class__": self.__class__.__name__, "value": self.value})

        def convert_expression_variable_to_qgis_variable(self, convert_dict: dict) -> str:
            for key, value in convert_dict.items():
                if key in self.value:
                    self.value = self.value.replace(key, value)
            return self.value

    def __init__(self, jmap_mcs: JMapMCS):
        self.jmap_mcs = jmap_mcs

    def _get_project_icons_from_sprite_sheet(self, url) -> dict:
        """
        Extracts icons from a sprite sheet and saves them without resizing.

        :return: Dictionary containing the paths and dimensions of the extracted icons.
        """
        icons_data, sprite_sheet_data = self.jmap_mcs.get_project_sprites(url)
        if not sprite_sheet_data or not icons_data:
            return None

        sprite_sheet = QPixmap()
        sprite_sheet.loadFromData(io.BytesIO(sprite_sheet_data).read())

        icons = {}
        project = QgsProject.instance()
        for icon_id, icon_data in icons_data.items():
            if "selection" in icon_id:
                continue

            x, y, width, height = icon_data["x"], icon_data["y"], icon_data["width"], icon_data["height"]

            icon_image = sprite_sheet.copy(x, y, width, height)

            path = project.createAttachedFile("{}.png".format(icon_id))
            icon_image.save(path, "PNG")

            icons[icon_id] = {
                "path": path,
                "width": width,
                "height": height,
                "pixelRatio": icon_data["pixelRatio"],
            }

        return icons

    def format_layer_label_config(self, layer_data: dict, default_language: str = "en") -> dict:
        """
        Formats JMap label configurations for a list of layer data.
        """
        if "labellingConfiguration" not in layer_data:
            return {}
        if "text" in layer_data["labellingConfiguration"]:
            text = find_value_in_dict_or_first(layer_data["labellingConfiguration"]["text"], [default_language], "")
            layer_data["labellingConfiguration"]["text"] = convert_jmap_text_label_expression(text)
        return layer_data["labellingConfiguration"]

    def format_layer_mouse_over_configs(self, layer_data: dict, default_language: str = "en") -> str:

        if "mouseOverConfiguration" not in layer_data or "text" not in layer_data["mouseOverConfiguration"]:
            return None
        text = find_value_in_dict_or_first(layer_data["mouseOverConfiguration"]["text"], [default_language], "")

        text_label = convert_jmap_text_mouse_over_expression(text)
        text_label = text_label.replace("\n", "<br>\n")
        text_label = "<div style='background-c  olor:white; color:black; padding:5px;'>{}</div>".format(text_label)
        
        return text_label

    
    def format_properties(self, mapbox_styles: dict, graphql_style_data: dict = {}, layers_data: list = []) -> dict:
        """
        Formats a mapbox styles with graphql style name data to make it easier to use for a QGIS project.
        :param mapbox_styles: mapbox styles file
        :param graphql_style_data: dict of style names
        :param labels_config: dict of layer labels
        """
        icons = {}
        if "sprite" in mapbox_styles and mapbox_styles["sprite"] != "":
            icons = self._get_project_icons_from_sprite_sheet(mapbox_styles["sprite"])
        filtered_styles = []
        for index, style in enumerate(mapbox_styles["layers"]):
            matches = ["selection", "background", "hillshade", "label"]
            if not any(x in style["id"] for x in matches):
                filtered_styles.append(mapbox_styles["layers"][index])
        layer_styles = {}

        for mapbox_style in filtered_styles:
            layer_id = mapbox_style["metadata"]["layer-id"]

            # symbology of layer
            if layer_id not in layer_styles:
                layer_styles[layer_id] = {
                    "styleRules": {},
                    "label": {},
                    "mouseOver": None,
                    "elementType": None,
                }
            layer = layer_styles[layer_id]

            if "source" in mapbox_style and "tiles" in mapbox_styles["sources"][mapbox_style["source"]]:
                layer["sources"] = mapbox_styles["sources"][mapbox_style["source"]]

            # styleRules are symbol groups
            # elif "style-rule-id" in mapbox_style["metadata"]:
            if "style-rule-id" in mapbox_style["metadata"]:
                style_rule_id = mapbox_style["metadata"]["style-rule-id"]
                if style_rule_id not in layer["styleRules"]:
                    layer["styleRules"][style_rule_id] = {}
                style_rule = layer["styleRules"][style_rule_id]

                # styleConditions are symbols with filters
                if "rule-condition-id" in mapbox_style["metadata"]:
                    rule_condition_id = mapbox_style["metadata"]["rule-condition-id"]
                    if rule_condition_id not in style_rule:
                        style_rule[rule_condition_id] = {
                            "conditionExpressions": None,
                            "styleMapScales": {},
                        }
                    rule_condition = style_rule[rule_condition_id]

                    # Should be the same for each style_scale and fill border-line styles
                    if "filter" in mapbox_style:
                        filter_expression = mapbox_style["filter"]
                    else:
                        filter_expression = None
                    if rule_condition["conditionExpressions"] is None:
                        rule_condition["conditionExpressions"] = filter_expression

                    # styleMapScales are symbols with zoom condition
                    if "style-map-scale-id" in mapbox_style["metadata"]:
                        style_map_scale_id = mapbox_style["metadata"]["style-map-scale-id"]
                        if style_map_scale_id not in rule_condition["styleMapScales"]:
                            rule_condition["styleMapScales"][style_map_scale_id] = {
                                "styles": {},
                                "maximumZoom": mapbox_style["maxzoom"],
                                "minimumZoom": mapbox_style["minzoom"],
                                "type": ("fill" if "border" in mapbox_style["id"] else mapbox_style["type"]),
                            }
                        # styles are symbol_layer
                        style_map_scale = rule_condition["styleMapScales"][style_map_scale_id]
                        if "style-id" in mapbox_style["metadata"]:
                            style_id = mapbox_style["metadata"]["style-id"]
                            if style_id not in style_map_scale["styles"]:
                                style_map_scale["styles"][style_id] = {}

                            # convert every mapbox expression
                            properties = {**mapbox_style["paint"], **mapbox_style["layout"]}

                            for key, value in properties.items():
                                # ALL JMAP HARDCODE IS HERE--------------------------
                                if "opacity" in key and not isinstance(value, float) and "case" in value:
                                    properties[key] = value[-1]
                                elif "text-opacity" in key and "interpolate" in value:
                                    properties[key] = 1.0
                                elif "text-size" in key and "interpolate" in value:
                                    properties[key] = self.QGISExpression(
                                        "{}/2^(23-  @vector_tile_zoom )".format(
                                            self._convert_mapbox_expression(value[4][2][1])
                                        )
                                    )
                                # END OF JMAP HARDCODE-------------------------------
                                elif isinstance(value, list):
                                    if "literal" in value and all(
                                        isinstance(x, int) or isinstance(x, float) for x in value[1]
                                    ):
                                        properties[key] = value[1]
                                    else:
                                        properties[key] = self._convert_mapbox_expression(value)
                                elif "icon-image" in key:
                                    properties[key] = icons[value]

                            # merge style. Should only appen for fill border-line styles
                            style_map_scale["styles"][style_id] = {**style_map_scale["styles"][style_id], **properties}
        # rename data
        if bool(graphql_style_data):
            for style_rule in graphql_style_data["data"]["getStyleRules"]:
                for condition in style_rule["conditions"]:
                    c = layer_styles[style_rule["layerId"]]["styleRules"][style_rule["id"]][condition["id"]]
                    c["name"] = condition["name"]
                    # the style rule name cannot be in style rule because there  is only condition id that can be here for now
                    c["styleRuleName"] = style_rule["name"]

        # format layer data properties
        for layer_data in layers_data:
            labeling_config = self.format_layer_label_config(layer_data)
            mouse_over_config = self.format_layer_mouse_over_configs(layer_data)

            layer_styles[layer_data["id"]]["label"] = labeling_config
            layer_styles[layer_data["id"]]["mouseOver"] = mouse_over_config
            if layer_data["elementType"] in ElementTypeWrapper.__members__:
                layer_styles[layer_data["id"]]["elementType"] = ElementTypeWrapper[
                    layer_data["elementType"]
                ].to_qgis_geometry_type()
            else:
                layer_styles[layer_data["id"]]["elementType"] = Qgis.GeometryType.Unknown

        return layer_styles

    def get_layer_labels(self, labeling_data: dict, element_type: Qgis.GeometryType) -> QgsRuleBasedLabeling:
        if not bool(labeling_data):
            return QgsRuleBasedLabeling(QgsRuleBasedLabeling.Rule(None))

        rule_settings = self._get_pal_layer_settings(labeling_data, element_type)

        # set rule settings
        rule = QgsRuleBasedLabeling.Rule(rule_settings)
        if "maximumZoom" in labeling_data:
            maxScale = round(convert_zoom_to_scale(labeling_data["maximumZoom"]))
            rule.setMaximumScale(maxScale)
        if "minimumZoom" in labeling_data:
            minScale = round(convert_zoom_to_scale(labeling_data["minimumZoom"]))
            rule.setMinimumScale(minScale)
        if "active" in labeling_data:
            rule.setActive(labeling_data["active"])

        root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())
        root_rule.appendChild(rule)

        return QgsRuleBasedLabeling(root_rule)

    def get_layer_styles(self, style_rules: dict) -> QgsRuleBasedRenderer:
        """
        Convert JMap style rules from specific layer to QGIS RuleBasedRenderer

        :param layer_id: JMap layer id
        :return: QGIS RuleBasedRenderer
        """
        renderer = QgsRuleBasedRenderer(QgsRuleBasedRenderer.Rule(None))
        root_rule = renderer.rootRule()

        for style_rule in style_rules.values():
            # one group foreach style_rule

            # create empty symbol to adjust the height of the rule group in MacOS
            rule_group = QgsRuleBasedRenderer.Rule(QgsMarkerSymbol.createSimple({
                'name': 'circle',
                'color': '0,0,0,0',     # fully transparent fill
                'outline_color': '0,0,0,0',  # fully transparent border
                'size': '0'             # zero size, or use very small size like '0.1'
            }))

            # conditions are filters
            for condition in style_rule.values():
                rule_group.setLabel(condition["styleRuleName"])
                
                filter_expression = self._convert_mapbox_expression(condition["conditionExpressions"])
                # style by zoom level
                for style_map_scale in condition["styleMapScales"].values():
                    symbol = self._convert_formatted_style_map_scale_to_symbol(style_map_scale)
                    if symbol is None:
                        continue

                    rule_name = condition["name"] + (
                        " {}-{}".format(int(style_map_scale["minimumZoom"]), int(style_map_scale["maximumZoom"]))
                        if len(condition["styleMapScales"]) > 1
                        else ""
                    )
                    min_scale = round(convert_zoom_to_scale(style_map_scale["minimumZoom"]))
                    max_scale = round(convert_zoom_to_scale(style_map_scale["maximumZoom"]))
                    rule = QgsRuleBasedRenderer.Rule(
                        symbol,
                        max_scale,
                        min_scale,
                        str(filter_expression),
                        label=rule_name,
                    )
                    rule_group.appendChild(rule)
            root_rule.appendChild(rule_group)

        return renderer

    def get_mvt_layer_labels(self, labeling_data: dict, element_type: Qgis.GeometryType) -> QgsVectorTileBasicLabeling:
        if not bool(labeling_data):
            return QgsVectorTileBasicLabeling()

        label_settings = self._get_pal_layer_settings(labeling_data, element_type)

        rule = QgsVectorTileBasicLabelingStyle()

        if element_type == Qgis.GeometryType.Point:
            rule.setGeometryType(Qgis.GeometryType.Point)
        elif element_type == Qgis.GeometryType.Line:
            rule.setGeometryType(Qgis.GeometryType.Line)
        elif element_type == Qgis.GeometryType.Polygon:
            rule.setGeometryType(Qgis.GeometryType.Polygon)

        rule.setLabelSettings(label_settings)
        if "maximumZoom" in labeling_data:
            maxZoom = int(labeling_data["maximumZoom"])
            rule.setMaxZoomLevel(maxZoom)
        if "minimumZoom" in labeling_data:
            minZoom = int(labeling_data["minimumZoom"])
            rule.setMinZoomLevel(minZoom)
        if "active" in labeling_data:
            rule.setEnabled(labeling_data["active"])

        labeling = QgsVectorTileBasicLabeling()
        labeling.setStyles([rule])
        return labeling

    def get_mvt_layer_styles(
        self, style_rules: dict, element_type: Qgis.GeometryType
    ) -> list[dict[str, list[QgsVectorTileBasicRendererStyle]]]:

        # MVT layer are in a group of layer because of impossibility to handle multiple styles in one layer
        style_groups = []
        # a style_rule is a visualization of a data
        for i, style_rule in style_rules.items():
            # one group foreach style_rule
            styles = {"name": None, "style_list": []}
            # conditions are filters
            for condition in style_rule.values():
                styles["name"] = condition["styleRuleName"]
                filter_expression = self._convert_mapbox_expression(condition["conditionExpressions"])
                # style by zoom level
                for h, style_map_scale in condition["styleMapScales"].items():
                    symbol = self._convert_formatted_style_map_scale_to_symbol(style_map_scale)
                    if element_type == Qgis.GeometryType.Point:
                        style = QgsVectorTileBasicRendererStyle(i, "", Qgis.GeometryType.Point)

                    elif element_type == Qgis.GeometryType.Line:
                        style = QgsVectorTileBasicRendererStyle(i, "", Qgis.GeometryType.Line)

                    elif element_type == Qgis.GeometryType.Polygon:
                        style = QgsVectorTileBasicRendererStyle(i, "", Qgis.GeometryType.Polygon)
                    else:
                        continue
                    style.setFilterExpression(str(filter_expression))
                    max_zoom = int(style_map_scale["maximumZoom"])
                    min_zoom = int(style_map_scale["minimumZoom"])
                    style.setMaxZoomLevel(max_zoom)
                    style.setMinZoomLevel(min_zoom)
                    style.setSymbol(symbol)
                    styleName = condition["name"] + (
                        " {}-{}".format(min_zoom, max_zoom) if len(condition["styleMapScales"]) > 1 else ""
                    )
                    style.setStyleName(styleName)
                    styles["style_list"].append(style)
            style_groups.append(styles)
        return style_groups

    def _convert_formatted_style_map_scale_to_symbol(self, formatted_style_map_scale: dict) -> QgsSymbol:
        """
        Converts a formatted_style_map_scale style to QGIS Symbol.

        :param jmap_style: JMAP style dictionary
        :return: QGIS symbol
        """

        # define the symbol type
        # POINT
        symbol = None
        if formatted_style_map_scale["type"].lower() == "symbol":
            symbol = QgsMarkerSymbol()
            symbol.deleteSymbolLayer(0)
            for style in formatted_style_map_scale["styles"].values():
                symbol_layer = symbol_layer = self.handle_marker_symbol_layer(style)
                symbol.appendSymbolLayer(symbol_layer)
        # LINE
        elif formatted_style_map_scale["type"].lower() == "line":
            symbol = QgsLineSymbol()
            symbol.deleteSymbolLayer(0)
            for style in formatted_style_map_scale["styles"].values():
                symbol_layer = self.handle_line_symbol_layer(style)
                symbol.appendSymbolLayer(symbol_layer)
        # POLYGON
        elif formatted_style_map_scale["type"].lower() == "fill":
            symbol = QgsFillSymbol()
            symbol.deleteSymbolLayer(0)
            for style in formatted_style_map_scale["styles"].values():
                symbol_layer = self.handle_polygon_symbol_layer(style)
                symbol.appendSymbolLayer(symbol_layer)
                if "line-color" in style:
                    symbol_layer_border = self.handle_line_symbol_layer(style)
                    symbol.appendSymbolLayer(symbol_layer_border)
        # IMAGE
        elif formatted_style_map_scale["type"].lower() == "image":
            QgsMessageBarHandler.send_message_to_message_bar(
                "IMAGE style type not yet supported",
                prefix="Error loading style",
                level=Qgis.MessageLevel.Warning,
            )
            return None
        # other
        else:
            QgsMessageBarHandler.send_message_to_message_bar(
                "Style type not supported", prefix="Error loading style", level=Qgis.MessageLevel.Critical
            )
            return None
        return symbol

    def handle_marker_symbol_layer(self, style: dict) -> QgsMarkerSymbolLayer:
        if "icon-image" in style:
            # set icon
            icons = style["icon-image"]
            symbol_layer = QgsRasterMarkerSymbolLayer(
                icons["path"],
                size=(icons["width"] + icons["height"]) / 2 / icons["pixelRatio"],
            )
            symbol_layer.setFixedAspectRatio(icons["height"] / icons["width"])
            symbol_layer.setSizeUnit(Qgis.RenderUnit.Pixels)
            # set icon properties
            if "icon-opacity" in style:
                if isinstance(style["icon-opacity"], self.QGISExpression):
                    expression = "({}) * 100".format(style["icon-opacity"].value)
                    symbol_layer = self._set_object_data_define_property_expression(
                        symbol_layer, QgsSymbolLayer.Property.PropertyOpacity, expression
                    )
                else:
                    symbol_layer.setOpacity(style["icon-opacity"])
                if "icon-translate" in style:
                    icon_offset = style["icon-translate"]
                    # mapbox style offset is array and convert to mapbox expression by default
                    if isinstance(icon_offset, self.QGISExpression):
                        symbol_layer = self._set_object_data_define_property_expression(
                            symbol_layer, QgsSymbolLayer.Property.PropertyOffset, icon_offset.value
                        )
                    else:
                        symbol_layer.setOffset(QPointF(icon_offset[0], icon_offset[1]))
                    symbol_layer.setOffsetUnit(Qgis.RenderUnit.Pixels)
                if "icon-rotate" in style:
                    if isinstance(style["icon-rotate"], self.QGISExpression):
                        symbol_layer = self._set_object_data_define_property_expression(
                            symbol_layer, QgsSymbolLayer.Property.PropertyAngle, style["icon-rotate"].value
                        )
                    else:
                        symbol_layer.setAngle(style["icon-rotate"])

        elif "text-field" in style:
            symbol_layer = QgsFontMarkerSymbolLayer()
            if isinstance(style["text-field"], self.QGISExpression):
                symbol_layer = self._set_object_data_define_property_expression(
                    symbol_layer, QgsSymbolLayer.Property.PropertyCharacter, style["text-field"].value
                )
            else:
                symbol_layer.setCharacter(style["text-field"])

            # set font properties
            if "text-font" in style:
                font_family, font_style = self._convert_mapbox_font(style["text-font"])
                symbol_layer.setFontFamily(font_family)
                symbol_layer.setFontStyle(font_style)

            if "text-rotate" in style:
                if isinstance(style["text-rotate"], self.QGISExpression):
                    symbol_layer = self._set_object_data_define_property_expression(
                        symbol_layer, QgsSymbolLayer.Property.PropertyAngle, style["text-rotate"].value
                    )
                else:
                    symbol_layer.setAngle(style["text-rotate"])

            if "text-size" in style:
                if isinstance(style["text-size"], self.QGISExpression):
                    symbol_layer = self._set_object_data_define_property_expression(
                        symbol_layer, QgsSymbolLayer.Property.PropertySize, style["text-size"].value
                    )
                else:
                    symbol_layer.setSize(style["text-size"])
                symbol_layer.setSizeUnit(Qgis.RenderUnit.Pixels)

            text_color = style["text-color"] if "text-color" in style else symbol_layer.color().name()
            text_opacity = style["text-opacity"] if "text-opacity" in style else None
            text_color = self._merge_color_and_opacity_if_exist(text_color, text_opacity)

            if isinstance(text_color, self.QGISExpression):
                symbol_layer = self._set_object_data_define_property_expression(
                    symbol_layer, QgsSymbolLayer.PropertyColor, text_color.value
                )
            else:
                symbol_layer.setColor(text_color)

            # maplibre text anchor is inverse of qgis
            if "textAnchor" in style:
                text_anchor = style["textAnchor"].lower()
                if "top" in text_anchor:
                    symbol_layer.setVerticalAnchorPoint(QgsMarkerSymbolLayer.VerticalAnchorPoint.Bottom)
                elif "bottom" in text_anchor:
                    symbol_layer.setVerticalAnchorPoint(QgsMarkerSymbolLayer.VerticalAnchorPoint.Top)
                else:
                    symbol_layer.setVerticalAnchorPoint(QgsMarkerSymbolLayer.VerticalAnchorPoint.VCenter)
                if "left" in text_anchor:
                    symbol_layer.setHorizontalAnchorPoint(QgsMarkerSymbolLayer.HorizontalAnchorPoint.Right)
                elif "right" in text_anchor:
                    symbol_layer.setHorizontalAnchorPoint(QgsMarkerSymbolLayer.HorizontalAnchorPoint.Left)
                else:
                    symbol_layer.setHorizontalAnchorPoint(QgsMarkerSymbolLayer.HorizontalAnchorPoint.HCenter)
        else:
            return QgsSimpleMarkerSymbolLayer()
        return symbol_layer


    def handle_line_symbol_layer(self, style: dict) -> QgsLineSymbolLayer:
        symbol_layer = QgsSimpleLineSymbolLayer()
        # set line properties
        # set color
        line_color = style["line-color"] if "line-color" in style else symbol_layer.color().name()
        line_opacity = style["line-opacity"] if "line-opacity" in style else None
        line_color = self._merge_color_and_opacity_if_exist(line_color, line_opacity)
        if isinstance(line_color, self.QGISExpression):
            symbol_layer = self._set_object_data_define_property_expression(
                symbol_layer, QgsSymbolLayer.Property.PropertyFillColor, line_color.value
            )
        else:
            symbol_layer.setColor(line_color)
        # ----------------
        line_width = 1
        if "line-width" in style:
            line_width = style["line-width"]
            if isinstance(line_width, self.QGISExpression):
                symbol_layer = self._set_object_data_define_property_expression(
                    symbol_layer, QgsSymbolLayer.Property.PropertyWidth, line_width.value
                )
            else:
                symbol_layer.setWidth(line_width)
            symbol_layer.setWidthUnit(Qgis.RenderUnit.Pixels)

        if "line-dasharray" in style:
            if isinstance(style["line-dasharray"], self.QGISExpression) or isinstance(line_width, self.QGISExpression):
                expression = "array_to_string( array_foreach({},@element*{} ),';')".format(
                    style["line-dasharray"].value, style["line-width"]
                )
                symbol_layer = self._set_object_data_define_property_expression(
                    symbol_layer, QgsSymbolLayer.PropertyDashVector, expression
                )
            else:
                symbol_layer.setUseCustomDashPattern(True)
                symbol_layer.setCustomDashPatternUnit(Qgis.RenderUnit.Pixels)
                symbol_layer.setCustomDashVector([v * line_width for v in style["line-dasharray"]])

        if "line-cap" in style:
            if style["line-cap"].upper() == "FLAT":
                symbol_layer.setPenCapStyle(Qt.PenCapStyle.FlatCap)
            elif style["line-cap"].upper() == "SQUARE":
                symbol_layer.setPenCapStyle(Qt.PenCapStyle.SquareCap)
            elif style["line-cap"].upper() == "ROUND":
                symbol_layer.setPenCapStyle(Qt.PenCapStyle.RoundCap)

        if "line-join" in style:
            if style["line-join"].upper() == "MITER":
                symbol_layer.setPenJoinStyle(Qt.PenJoinStyle.MiterJoin)
            elif style["line-join"].upper() == "BEVEL":
                symbol_layer.setPenJoinStyle(Qt.PenJoinStyle.BevelJoin)
            elif style["line-join"].upper() == "ROUND":
                symbol_layer.setPenJoinStyle(Qt.PenJoinStyle.RoundJoin)

        return symbol_layer

    def handle_polygon_symbol_layer(self, style: dict) -> QgsFillSymbolLayer:
        symbol_layer = QgsSimpleFillSymbolLayer()
        # set fill color
        fill_color = style["fill-color"] if "fill-color" in style else symbol_layer.color().name()
        fill_opacity = style["fill-opacity"] if "fill-opacity" in style else None
        fill_color = self._merge_color_and_opacity_if_exist(fill_color, fill_opacity)
        if isinstance(fill_color, self.QGISExpression):
            symbol_layer = self._set_object_data_define_property_expression(
                symbol_layer, QgsSymbolLayer.Property.PropertyFillColor, fill_color.value
            )
        else:
            symbol_layer.setColor(fill_color)

        if "fill-outline-color" in style:
            border_color = style["fill-outline-color"]

            symbol_layer.setStrokeColor(QColor(border_color))
            symbol_layer.setStrokeWidth(1)
            symbol_layer.setStrokeWidthUnit(Qgis.RenderUnit.Pixels)
        else:
            symbol_layer.setStrokeStyle(Qt.PenStyle.NoPen)

        return symbol_layer

    def _convert_mapbox_expression(self, condition_expressions) -> any:
        if condition_expressions is None:
            return ""
        if not isinstance(condition_expressions, list):
            if isinstance(condition_expressions, str):
                condition_expressions = condition_expressions.replace("'", r"\'")
                condition_expressions = "'{}'".format(condition_expressions)
            # elif isinstance(condition_expressions, float):
            #    condition_expressions = condition_expressions * 100
            return condition_expressions

        # https://maplibre.org/maplibre-style-spec/expressions
        try:
            if condition_expressions[0] == "literal":
                exp = self._convert_mapbox_expression(condition_expressions[1])
                exp = str(exp).replace("[", "").replace("]", "")
                return self.QGISExpression("array({})".format(exp))

            elif condition_expressions[0] in ["string", "number", "boolean", "object"]:
                exp = self._convert_mapbox_expression(condition_expressions[1])
                return self.QGISExpression(exp)

            elif condition_expressions[0] == "to-string":
                exp = self._convert_mapbox_expression(condition_expressions[1])
                return self.QGISExpression("to_string({})".format(exp))

            elif condition_expressions[0] == "to-number":
                exp = self._convert_mapbox_expression(condition_expressions[1])
                return self.QGISExpression("to_real({})".format(exp))

            elif condition_expressions[0] == "to-object":
                exp = self._convert_mapbox_expression(condition_expressions[1])
                return self.QGISExpression("to_object({})".format(exp))

            elif condition_expressions[0] == "at":
                exp1 = self._convert_mapbox_expression(condition_expressions[1])
                exp2 = self._convert_mapbox_expression(condition_expressions[2])
                return self.QGISExpression("{}[{}]".format(exp2, exp1))

            elif condition_expressions[0] == "index-of":
                exp1 = self._convert_mapbox_expression(condition_expressions[1])
                exp2 = self._convert_mapbox_expression(condition_expressions[2])
                return self.QGISExpression("array_find({}, {})".format(exp1, exp2))

            elif condition_expressions[0] == "slice":
                exp1 = self._convert_mapbox_expression(condition_expressions[1])
                exp2 = self._convert_mapbox_expression(condition_expressions[2])
                converted_string = "array_slice({}, {})".format(exp1, exp2)
                if len(condition_expressions) > 3:
                    exp3 = self._convert_mapbox_expression(condition_expressions[3])
                    converted_string += ", {}".format(exp3)
                return self.QGISExpression(converted_string)

            elif condition_expressions[0] == "get":
                return self.QGISExpression(condition_expressions[1])

            elif condition_expressions[0] == "has":
                exp1 = self._convert_mapbox_expression(condition_expressions[1])
                return self.QGISExpression("attribute({}) is not null".format(exp1))

            elif condition_expressions[0] == "length":
                exp1 = self._convert_mapbox_expression(condition_expressions[1])
                return self.QGISExpression("array_length({})".format(exp1))

            elif condition_expressions[0] == "case":
                converted_expression = "CASE"
                for i in range(1, len(condition_expressions) - 1, 2):
                    exp_x = self._convert_mapbox_expression(condition_expressions[i])
                    exp_y = self._convert_mapbox_expression(condition_expressions[i + 1])
                    converted_expression += " WHEN {} THEN {}".format(exp_x, exp_y)
                if len(condition_expressions) % 2 == 0:
                    exp1 = self._convert_mapbox_expression(condition_expressions[-1])
                    converted_expression += " ELSE {}".format(exp1)
                converted_expression += " END"
                return self.QGISExpression(converted_expression)

            elif condition_expressions[0] == "match":
                converted_expression = "CASE"
                exp1 = self._convert_mapbox_expression(condition_expressions[1])
                for i in range(2, len(condition_expressions), 2):
                    exp_x = self._convert_mapbox_expression(condition_expressions[i])
                    exp_y = self._convert_mapbox_expression(condition_expressions[i + 1])
                    converted_expression += " WHEN {} in {} THEN {}".format(exp1, exp_x, exp_y)
                if len(condition_expressions) % 2 == 0:
                    exp2 = self._convert_mapbox_expression(condition_expressions[-1])
                    converted_expression += " ELSE {}".format(exp2)
                converted_expression += " END"
                return self.QGISExpression(converted_expression)

            elif condition_expressions[0] in ["==", ">", "<", ">=", "<=", "!=", "in", "/", "%", "^"]:
                exp1 = self._convert_mapbox_expression(condition_expressions[1])
                exp2 = self._convert_mapbox_expression(condition_expressions[2])
                return "{} {} {}".format(
                    exp1, condition_expressions[0] if condition_expressions[0] != "==" else "=", exp2
                )

            elif condition_expressions[0] in ["+", "*"]:
                exp1 = self._convert_mapbox_expression(condition_expressions[1])
                converted_expression = "{}".format(exp1)
                for i in range(2, len(condition_expressions)):
                    exp_x = self._convert_mapbox_expression(condition_expressions[i])
                    converted_expression += " {} {}".format(condition_expressions[0], exp_x)
                return self.QGISExpression(converted_expression)

            elif condition_expressions[0] == "-":
                exp1 = self._convert_mapbox_expression(condition_expressions[1])
                if len(condition_expressions) == 3:
                    exp2 = self._convert_mapbox_expression(condition_expressions[2])
                    return "{} - {}".format(exp1, exp2)
                else:
                    return self.QGISExpression("-({})".format(exp1))

            elif condition_expressions[0] in ["all", "any"]:
                exp1 = self._convert_mapbox_expression(condition_expressions[1])
                converted_expression = "({}".format(exp1)
                for i in range(2, len(condition_expressions)):
                    exp_x = self._convert_mapbox_expression(condition_expressions[i])
                    converted_expression += "{} {}".format(
                        " and" if condition_expressions[0] == "all" else " or", exp_x
                    )
                converted_expression += ")"
                return self.QGISExpression(converted_expression)

            elif condition_expressions[0] == "!":
                exp1 = self._convert_mapbox_expression(condition_expressions[1])
                return self.QGISExpression("not {}".format(exp1))

            elif condition_expressions[0] == "within":
                message = "Within expression not supported"
                QgsMessageBarHandler.send_message_to_message_bar(message, prefix="Expression error", level=Qgis.MessageLevel.Warning)
                return ""

            elif condition_expressions[0] == "feature-state":
                message = "Feature state expression not supported"
                QgsMessageBarHandler.send_message_to_message_bar(message, prefix="Expression error", level=Qgis.MessageLevel.Warning)
                return "false"

            elif condition_expressions[0] == "format":
                exp = "{}".format(self._convert_mapbox_expression(condition_expressions[1]))
                for i in range(3, len(condition_expressions), 2):
                    exp += "+{}".format(self._convert_mapbox_expression(condition_expressions[i]))
                return self.QGISExpression(exp)

            else:
                return condition_expressions

        except Exception as e:
            QgsMessageBarHandler.send_message_to_message_bar(str(e), prefix="Expression error", level=Qgis.MessageLevel.Warning)
            return "false"

    def _convert_mapbox_font(self, fonts: list) -> tuple[str, str]:
        qgis_font_styles = [
            "Regular",
            "Bold Italic",
            "Bold",
            "Italic",
        ]
        for font in fonts:
            for qgis_font_style in qgis_font_styles:
                if qgis_font_style in font:
                    font_family = font.replace(qgis_font_style, "").strip()
                    return font_family, qgis_font_style
        QgsMessageBarHandler.send_message_to_message_bar(
            "Font {} not supported".format(font), prefix="Expression error", level=Qgis.MessageLevel.Warning
        )
        return "", ""

    def _convert_jmap_offset(self,offset: str):
        match = re.search(r"POINT\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)", offset)

        if match:
            x, y = map(int, match.groups())
            return x, y

    def _get_pal_layer_settings(self, labeling_data: dict, element_type: Qgis.GeometryType) -> QgsPalLayerSettings:

        # set label settings
        rule_settings = QgsPalLayerSettings()
        rule_settings.centroidInside = True
        rule_settings.centroidWhole = True
        rule_settings.isExpression = True
        rule_settings.layerType = element_type

        if "text" in labeling_data:
            rule_settings.fieldName = labeling_data["text"]

        # set position settings
        offset_y = 0
        if "offset" in labeling_data:
            text_translate = labeling_data["offset"]
            # if isinstance(text_translate, str):
            #    rule_settings.xOffset = cls._set_object_data_define_property_expression(
            #        rule_settings, QgsPalLayerSettings.OffsetXY, text_translate
            #    )
            # else:
            offset_x, offset_y = self._convert_jmap_offset(text_translate)

        # line label are not handled by point on map but rather by line itself
        if element_type == Qgis.GeometryType.Line:
            line_settings = QgsLabelLineSettings()
            line_settings.setAnchorClipping(QgsLabelLineSettings.AnchorClipping.UseEntireLine)
            # line render settings
            if "labelSpacing" in labeling_data:
                rule_settings.repeatDistance = labeling_data["labelSpacing"]
                rule_settings.repeatDistanceUnit = Qgis.RenderUnit.Pixels
            # --------------------

            if "followMapRotation" in labeling_data and labeling_data["followMapRotation"]:
                rule_settings.placement = Qgis.LabelPlacement.Line
                if "anchor" in labeling_data:
                    if "top" in labeling_data["anchor"].lower():  # Maplibre top is bottom in qgis and vice versa
                        offset_y = -offset_y
                        line_settings.setPlacementFlags(
                            Qgis.LabelLinePlacementFlags(
                                Qgis.LabelLinePlacementFlag.BelowLine | Qgis.LabelLinePlacementFlag.MapOrientation
                            )
                        )
                    else:
                        if "bottom" not in labeling_data["anchor"].lower():
                            offset_y -= 6
                        line_settings.setPlacementFlags(
                            Qgis.LabelLinePlacementFlags(
                                Qgis.LabelLinePlacementFlag.AboveLine | Qgis.LabelLinePlacementFlag.MapOrientation
                            )
                        )

                    rule_settings.dist = offset_y
                    rule_settings.distUnits = Qgis.RenderUnit.Pixels
            else:
                rule_settings.placement = Qgis.LabelPlacement.Horizontal

            rule_settings.setLineSettings(line_settings)

        # label is handled as point
        else:
            rule_settings.placement = Qgis.LabelPlacement.OverPoint
            rule_settings.xOffset = offset_x
            rule_settings.yOffset = -offset_y
            rule_settings.offsetUnits = Qgis.RenderUnit.Pixels
            # maplibre text anchor is inverse of qgis
            if "anchor" in labeling_data:
                text_anchor = labeling_data["anchor"].lower()

                if text_anchor == "left":
                    rule_settings.quadOffset = QgsPalLayerSettings.QuadrantPosition.QuadrantRight
                elif text_anchor == "right":
                    rule_settings.quadOffset = QgsPalLayerSettings.QuadrantPosition.QuadrantLeft
                elif text_anchor == "top":
                    rule_settings.quadOffset = QgsPalLayerSettings.QuadrantPosition.QuadrantBelow
                elif text_anchor == "bottom":
                    rule_settings.quadOffset = QgsPalLayerSettings.QuadrantPosition.QuadrantAbove
                elif text_anchor == "top-left":
                    rule_settings.quadOffset = QgsPalLayerSettings.QuadrantPosition.QuadrantBelowRight
                elif text_anchor == "top-right":
                    rule_settings.quadOffset = QgsPalLayerSettings.QuadrantPosition.QuadrantBelowLeft
                elif text_anchor == "bottom-left":
                    rule_settings.quadOffset = QgsPalLayerSettings.QuadrantPosition.QuadrantAboveRight
                elif text_anchor == "bottom-right":
                    rule_settings.quadOffset = QgsPalLayerSettings.QuadrantPosition.QuadrantAboveLeft
                else:
                    rule_settings.quadOffset = QgsPalLayerSettings.QuadrantPosition.QuadrantOver

        # set render settings
        thinning_settings = QgsLabelThinningSettings()
        thinning_settings.setMinimumFeatureSize(15)
        rule_settings.setThinningSettings(thinning_settings)
        if "allowOverlapping" in labeling_data:
            text_allow_overlap = labeling_data["allowOverlapping"]
            # if isinstance(text_allow_overlap, cls.QGISExpression):
            #    convert_dict = {
            #        "true": int(Qgis.LabelOverlapHandling.AllowOverlapAtNoCost),
            #        "false": int(Qgis.LabelOverlapHandling.PreventOverlap),
            #    }
            #    text_allow_overlap = text_allow_overlap.convert_expression_variable_to_qgis_variable(convert_dict)
            #    rule_settings.allowOverlap = cls._set_object_data_define_property_expression(
            #        rule_settings, Qgis.LabelOverlapHandling, text_allow_overlap
            #    )
            # else:
            if text_allow_overlap == True:
                rule_settings.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.AllowOverlapAtNoCost)
            else:
                rule_settings.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.PreventOverlap)

        # set label setting text format
        text_format = QgsTextFormat()
        # if "text-font" in labeling_data:
        #    text_font = labeling_data["text-font"].value
        #    font_family, font_style = cls._convert_mapbox_font(text_font)
        #    font = QFont()
        #    font.setFamily(font_family)
        #    if "Regular" in font_style:
        #        font.setStyle(QFont.StyleNormal)
        #    elif "Bold" in font_style:
        #        font.setBold(True)
        #    elif "Italic" in font_style:
        #        font.setItalic(True)
        #    text_format.setFont(font)
        font = QFont()
        if "textBold" in labeling_data:
            font.setBold(labeling_data["textBold"])
        if "textItalic" in labeling_data:
            font.setItalic(labeling_data["textItalic"])
        text_format.setFont(font)

        if "textSize" in labeling_data:
            text_size = labeling_data["textSize"]
            # if isinstance(text_size, cls.QGISExpression):
            #    text_format = cls._set_object_data_define_property_expression(
            #        rule_settings, QgsPalLayerSettings.Size, text_size.value
            #    )
            # else:
            text_format.setSize(text_size)
            text_format.setSizeUnit(Qgis.RenderUnit.Pixels)

        # set text format color
        color = labeling_data["textColor"] if "textColor" in labeling_data else text_format.color().name()
        opacity = 1.0 - labeling_data["transparency"] if "transparency" in labeling_data else None
        color = self._merge_color_and_opacity_if_exist(color, opacity)
        # if isinstance(color, cls.QGISExpression):
        #    rule_settings = cls._set_object_data_define_property_expression(
        #        rule_settings, QgsPalLayerSettings.Color, color.value
        #    )
        # else:
        text_format.setColor(color)
        # ----------------------

        # set text format buffer
        buffer = QgsTextBufferSettings()
        if "outlined" in labeling_data:
            buffer.setEnabled(labeling_data["outlined"])

        text_halo_color = labeling_data["outlineColor"] if "outlineColor" in labeling_data else buffer.color().name()
        opacity = 1.0 - labeling_data["transparency"] if "transparency" in labeling_data else None
        text_halo_color = self._merge_color_and_opacity_if_exist(text_halo_color, opacity)
        # if isinstance(text_halo_color, cls.QGISExpression):
        #    rule_settings = cls._set_object_data_define_property_expression(
        #        rule_settings, QgsPalLayerSettings.BufferColor, text_halo_color.value
        #    )
        # else:
        buffer.setColor(text_halo_color)
        # if "text-halo-width" in labeling_data:
        # if isinstance(labeling_data["text-halo-width"], cls.QGISExpression):
        #    buffer = cls._set_object_data_define_property_expression(
        #        rule_settings, QgsPalLayerSettings.BufferSize, labeling_data["text-halo-width"].value
        #    )
        # else:
        buffer.setSize(1)
        buffer.setSizeUnit(Qgis.RenderUnit.Pixels)
        text_format.setBuffer(buffer)

        # set background text format
        background = QgsTextBackgroundSettings()
        background.setType(QgsTextBackgroundSettings.ShapeType.ShapeRectangle)
        if "frameActive" in labeling_data:
            background.setEnabled(labeling_data["frameActive"])

        background_symbol = background.fillSymbol()
        background_color = (
            labeling_data["frameFillColor"] if "frameFillColor" in labeling_data else background.color().name()
        )
        background_opacity = 1.0 - labeling_data["frameTransparency"] if "frameTransparency" in labeling_data else None
        background_color = self._merge_color_and_opacity_if_exist(background_color, background_opacity)
        background_symbol.setColor(background_color)
        background_symbol_layer = background_symbol.symbolLayer(0)
        background_border_color = (
            labeling_data["frameBorderColor"] if "frameBorderColor" in labeling_data else background.color().name()
        )
        background_border_opacity = (
            1.0 - labeling_data["frameTransparency"] if "frameTransparency" in labeling_data else None
        )
        background_border_color = self._merge_color_and_opacity_if_exist(
            background_border_color, background_border_opacity
        )
        background_symbol_layer.setStrokeColor(background_border_color)

        background_symbol_layer.setStrokeWidth(2)
        background_symbol_layer.setStrokeWidthUnit(Qgis.RenderUnit.Pixels)
        background_symbol_layer.setStrokeStyle(Qt.PenStyle.SolidLine)
        background_symbol_layer.setPenJoinStyle(Qt.PenJoinStyle.MiterJoin)

        if "backgroundSymbolOffset" in labeling_data:
            x, y = self._convert_jmap_offset(labeling_data["backgroundSymbolOffset"])
            background.setOffset(QPointF(x, y))
        background.setOffsetUnit(Qgis.RenderUnit.Pixels)
        background.setSize(QSizeF(5, 5))
        background.setSizeUnit(Qgis.RenderUnit.Pixels)

        text_format.setBackground(background)

        rule_settings.setFormat(text_format)
        return rule_settings

    def _merge_color_and_opacity_if_exist(
        self,
        color: any,
        opacity: any = None,
    ) -> any:
        color_is_expression = isinstance(color, self.QGISExpression)
        opacity_is_expression = opacity and isinstance(opacity, self.QGISExpression)

        if opacity:
            if color_is_expression or opacity_is_expression:
                color = color.value if color_is_expression else "'{}'".format(color)
                opacity = opacity.value if opacity_is_expression else opacity
                expressionString = "set_color_part(({}),'alpha',to_int(255*({})))".format(color, opacity)
                return self.QGISExpression(expressionString)
            else:
                color = QColor(color)
                color.setAlphaF(opacity)
                return color
        else:
            if color_is_expression:
                return color
            else:
                return QColor(color)


    def _set_object_data_define_property_expression(self, object: any, property_name: str, expressionString: str) -> any:
        properties_collection = object.dataDefinedProperties()
        property = properties_collection.property(property_name)
        property.setExpressionString(expressionString)
        properties_collection.setProperty(property_name, property)
        object.setDataDefinedProperties(properties_collection)
        return object
    
    def get_raster_opacity(self, layer_properties: dict, default: float = 1.0) -> float:
        try:
            for style_rule in layer_properties["styleRules"].values():
                for condition in style_rule.values():
                    for style_map_scale in condition["styleMapScales"].values():
                        for style in style_map_scale["styles"].values():
                            return float(style.get("raster-opacity", default))
        except Exception:
            QgsMessageBarHandler.send_message_to_message_bar(
                "Error getting raster opacity from layer properties", prefix="Warning", level=Qgis.MessageLevel.Warning
            )
        return default
