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

from JMapCloud.core.plugin_util import (
    convert_jmap_text_expression,
    convert_zoom_to_scale,
)
from JMapCloud.core.qgs_message_bar_handler import QgsMessageBarHandler
from JMapCloud.core.services.jmap_services_access import JMapMCS


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

    @staticmethod
    def _get_project_icons_from_sprite_sheet(url) -> dict:
        """
        Extracts icons from a sprite sheet and saves them without resizing.

        :return: Dictionary containing the paths and dimensions of the extracted icons.
        """
        icons_data, sprite_sheet_data = JMapMCS.get_project_sprites(url)
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

            path = project.createAttachedFile(f"{icon_id}.png")
            icon_image.save(path, "PNG")

            icons[icon_id] = {
                "path": path,
                "width": width,
                "height": height,
                "pixelRatio": icon_data["pixelRatio"],
            }

        return icons

    @staticmethod
    def format_JMap_label_configs(layers_data: list, default_language: str = "en") -> dict:
        """
        Formats JMap label configurations for a list of layer data.
        """

        layer_label_configs = {}
        for layer_data in layers_data:
            if "labellingConfiguration" not in layer_data or "text" not in layer_data["labellingConfiguration"]:
                continue
            if default_language in layer_data["labellingConfiguration"]["text"]:
                labeling_config = layer_data["labellingConfiguration"]["text"][default_language]
            else:
                labeling_config = next(iter(layer_data["labellingConfiguration"]["text"]))
            layer_data["labellingConfiguration"]["text"] = convert_jmap_text_expression(labeling_config)
            layer_label_configs[layer_data["id"]] = layer_data["labellingConfiguration"]

        return layer_label_configs

    @classmethod
    def format_properties(cls, mapbox_styles: dict, graphql_style_data: dict = {}, labels_config: dict = {}) -> dict:
        """
        Formats a mapbox styles with graphql style name data to make it easier to use for a QGIS project.
        :param mapbox_styles: mapbox styles file
        :param graphql_style_data: dict of style names
        :param labels_config: dict of layer labels
        """
        icons = {}
        if "sprite" in mapbox_styles and mapbox_styles["sprite"] != "":
            icons = cls._get_project_icons_from_sprite_sheet(mapbox_styles["sprite"])
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
                }
            layer = layer_styles[layer_id]

            if "source" in mapbox_style and "tiles" in mapbox_styles["sources"][mapbox_style["source"]]:
                layer["sources"] = mapbox_styles["sources"][mapbox_style["source"]]["tiles"]

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
                                    properties[key] = cls.QGISExpression(
                                        f"{cls._convert_mapbox_expression(value[4][2][1])}/2^(23-  @vector_tile_zoom )"
                                    )
                                # END OF JMAP HARDCODE-------------------------------
                                elif isinstance(value, list):
                                    if "literal" in value and all(
                                        isinstance(x, int) or isinstance(x, float) for x in value[1]
                                    ):
                                        properties[key] = value[1]
                                    else:
                                        properties[key] = cls._convert_mapbox_expression(value)
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
        if bool(labels_config):
            for layer_id, label_config in labels_config.items():
                layer_styles[layer_id]["label"] = label_config
        return layer_styles

    @classmethod
    def get_layer_labels(cls, labeling_data: dict) -> QgsRuleBasedLabeling:

        if not bool(labeling_data):
            return QgsRuleBasedLabeling(QgsRuleBasedLabeling.Rule(None))

        rule_settings = cls._get_pal_layer_settings(labeling_data)

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

    @classmethod
    def get_layer_styles(cls, style_rules: dict) -> QgsRuleBasedRenderer:
        """
        Convert JMap style rules from specific layer to QGIS RuleBasedRenderer

        :param layer_id: JMap layer id
        :return: QGIS RuleBasedRenderer
        """
        renderer = QgsRuleBasedRenderer(QgsRuleBasedRenderer.Rule(None))
        root_rule = renderer.rootRule()

        for style_rule in style_rules.values():
            # one group foreach style_rule
            rule_group = QgsRuleBasedRenderer.Rule(None)
            # conditions are filters
            for condition in style_rule.values():
                rule_group.setLabel(condition["styleRuleName"])
                filter_expression = cls._convert_mapbox_expression(condition["conditionExpressions"])
                # style by zoom level
                for style_map_scale in condition["styleMapScales"].values():

                    symbol = cls._convert_formatted_style_map_scale_to_symbol(style_map_scale)
                    if symbol is None:
                        continue

                    rule_name = condition["name"] + (
                        f' {int(style_map_scale["minimumZoom"])}-{int(style_map_scale["maximumZoom"])}'
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

    @classmethod
    def get_mvt_layer_labels(cls, labeling_data: dict, element_type: str) -> QgsVectorTileBasicLabeling:

        if not bool(labeling_data):
            return QgsVectorTileBasicLabeling()

        label_settings = cls._get_pal_layer_settings(labeling_data)

        rule = QgsVectorTileBasicLabelingStyle()

        if element_type in ["POINT", "TEXT"]:
            rule.setGeometryType(Qgis.GeometryType.Point)
        elif element_type == "LINE":
            rule.setGeometryType(Qgis.GeometryType.Line)
        elif element_type == "POLYGON":
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

    @classmethod
    def get_mvt_layer_styles(
        cls, style_rules: dict, element_type: str
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
                filter_expression = cls._convert_mapbox_expression(condition["conditionExpressions"])
                # style by zoom level
                for h, style_map_scale in condition["styleMapScales"].items():
                    symbol = cls._convert_formatted_style_map_scale_to_symbol(style_map_scale)
                    if element_type in ["POINT", "TEXT"]:
                        style = QgsVectorTileBasicRendererStyle(i, "", Qgis.GeometryType.Point)

                    elif element_type == "LINE":
                        style = QgsVectorTileBasicRendererStyle(i, "", Qgis.GeometryType.Line)

                    elif element_type == "POLYGON":
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
                        f" {min_zoom}-{max_zoom}" if len(condition["styleMapScales"]) > 1 else ""
                    )
                    style.setStyleName(styleName)
                    styles["style_list"].append(style)
            style_groups.append(styles)
        return style_groups

    @classmethod
    def _convert_formatted_style_map_scale_to_symbol(cls, formatted_style_map_scale: dict) -> QgsSymbol:
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
                symbol_layer = symbol_layer = cls.handle_marker_symbol_layer(style)
                symbol.appendSymbolLayer(symbol_layer)
        # LINE
        elif formatted_style_map_scale["type"].lower() == "line":
            symbol = QgsLineSymbol()
            symbol.deleteSymbolLayer(0)
            for style in formatted_style_map_scale["styles"].values():
                symbol_layer = cls.handle_line_symbol_layer(style)
                symbol.appendSymbolLayer(symbol_layer)
        # POLYGON
        elif formatted_style_map_scale["type"].lower() == "fill":
            symbol = QgsFillSymbol()
            symbol.deleteSymbolLayer(0)
            for style in formatted_style_map_scale["styles"].values():
                symbol_layer = cls.handle_polygon_symbol_layer(style)
                symbol.appendSymbolLayer(symbol_layer)
                if "line-color" in style:
                    symbol_layer_border = cls.handle_line_symbol_layer(style)
                    symbol.appendSymbolLayer(symbol_layer_border)

        # IMAGE
        elif formatted_style_map_scale["type"].lower() == "image":
            QgsMessageBarHandler.send_message_to_message_bar(
                "IMAGE style type not yet supported",
                prefix="Error loading style",
                level=Qgis.Warning,
            )
            return None
        # other
        else:
            QgsMessageBarHandler.send_message_to_message_bar(
                "Style type not supported", prefix="Error loading style", level=Qgis.Critical
            )
            return None
        return symbol

    @classmethod
    def handle_marker_symbol_layer(cls, style: dict) -> QgsMarkerSymbolLayer:
        if "icon-image" in style:
            # set icon
            icons = style["icon-image"]
            symbol_layer = QgsRasterMarkerSymbolLayer(
                icons["path"],
                size=(icons["width"] + icons["height"]) / 2 / icons["pixelRatio"],
            )
            symbol_layer.setFixedAspectRatio(icons["width"] / icons["height"])
            symbol_layer.setSizeUnit(Qgis.RenderUnit.Pixels)
            # set icon properties
            if "icon-opacity" in style:
                if isinstance(style["icon-opacity"], cls.QGISExpression):
                    expression = f"({style['icon-opacity'].value}) * 100"
                    symbol_layer = cls._set_object_data_define_property_expression(
                        symbol_layer, QgsSymbolLayer.PropertyOpacity, expression
                    )
                else:
                    symbol_layer.setOpacity(style["icon-opacity"])
                if "icon-translate" in style:
                    icon_offset = style["icon-translate"]
                    # mapbox style offset is array and convert to mapbox expression by default
                    if isinstance(icon_offset, cls.QGISExpression):
                        symbol_layer = cls._set_object_data_define_property_expression(
                            symbol_layer, QgsSymbolLayer.PropertyOffset, icon_offset.value
                        )
                    else:
                        symbol_layer.setOffset(QPointF(icon_offset[0], icon_offset[1]))
                    symbol_layer.setOffsetUnit(Qgis.RenderUnit.Pixels)
                if "icon-rotate" in style:
                    if isinstance(style["icon-rotate"], cls.QGISExpression):
                        symbol_layer = cls._set_object_data_define_property_expression(
                            symbol_layer, QgsSymbolLayer.PropertyAngle, style["icon-rotate"].value
                        )
                    else:
                        symbol_layer.setAngle(style["icon-rotate"])

        elif "text-field" in style:
            symbol_layer = QgsFontMarkerSymbolLayer()

            if isinstance(style["text-field"], cls.QGISExpression):
                symbol_layer = cls._set_object_data_define_property_expression(
                    symbol_layer, QgsSymbolLayer.PropertyCharacter, style["text-field"].value
                )
            else:
                symbol_layer.setCharacter(style["text-field"])

            # set font properties
            if "text-font" in style:
                font_family, font_style = cls._convert_mapbox_font(style["text-font"])
                symbol_layer.setFontFamily(font_family)
                symbol_layer.setFontStyle(font_style)

            if "text-rotate" in style:
                if isinstance(style["text-rotate"], cls.QGISExpression):
                    symbol_layer = cls._set_object_data_define_property_expression(
                        symbol_layer, QgsSymbolLayer.PropertyAngle, style["text-rotate"].value
                    )
                else:
                    symbol_layer.setAngle(style["text-rotate"])

            if "text-size" in style:
                if isinstance(style["text-size"], cls.QGISExpression):
                    symbol_layer = cls._set_object_data_define_property_expression(
                        symbol_layer, QgsSymbolLayer.PropertySize, style["text-size"].value
                    )
                else:
                    symbol_layer.setSize(style["text-size"])
                symbol_layer.setSizeUnit(Qgis.RenderUnit.Pixels)

            text_color = style["text-color"] if "text-color" in style else symbol_layer.color().name()
            text_opacity = style["text-opacity"] if "text-opacity" in style else None
            text_color = cls._merge_color_and_opacity_if_exist(text_color, text_opacity)
            if isinstance(text_color, cls.QGISExpression):
                symbol_layer = cls._set_object_data_define_property_expression(
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

    @classmethod
    def handle_line_symbol_layer(cls, style: dict) -> QgsLineSymbolLayer:
        symbol_layer = QgsSimpleLineSymbolLayer()
        # set line properties
        # set color
        line_color = style["line-color"] if "line-color" in style else symbol_layer.color().name()
        line_opacity = style["line-opacity"] if "line-opacity" in style else None
        line_color = cls._merge_color_and_opacity_if_exist(line_color, line_opacity)
        if isinstance(line_color, cls.QGISExpression):
            symbol_layer = cls._set_object_data_define_property_expression(
                symbol_layer, QgsSymbolLayer.PropertyFillColor, line_color.value
            )
        else:
            symbol_layer.setColor(line_color)
        # ----------------
        line_width = 1
        if "line-width" in style:
            line_width = style["line-width"]
            if isinstance(line_width, cls.QGISExpression):
                symbol_layer = cls._set_object_data_define_property_expression(
                    symbol_layer, QgsSymbolLayer.PropertyWidth, line_width.value
                )
            else:
                symbol_layer.setWidth(line_width)
            symbol_layer.setWidthUnit(Qgis.RenderUnit.Pixels)

        if "line-dasharray" in style:
            if isinstance(style["line-dasharray"], cls.QGISExpression) or isinstance(line_width, cls.QGISExpression):
                expression = f"array_to_string( array_foreach({style['line-dasharray'].value},@element*{style['line-width']} ),';')"
                symbol_layer = cls._set_object_data_define_property_expression(
                    symbol_layer, QgsSymbolLayer.PropertyDashVector, expression
                )
            else:
                symbol_layer.setUseCustomDashPattern(True)
                symbol_layer.setCustomDashPatternUnit(Qgis.RenderUnit.Pixels)
                symbol_layer.setCustomDashVector([v * line_width for v in style["line-dasharray"]])

        if "line-cap" in style:
            if style["line-cap"].upper() == "FLAT":
                symbol_layer.setPenCapStyle(Qt.FlatCap)
            elif style["line-cap"].upper() == "SQUARE":
                symbol_layer.setPenCapStyle(Qt.SquareCap)
            elif style["line-cap"].upper() == "ROUND":
                symbol_layer.setPenCapStyle(Qt.RoundCap)

        if "line-join" in style:
            if style["line-join"].upper() == "MITER":
                symbol_layer.setPenJoinStyle(Qt.MiterJoin)
            elif style["line-join"].upper() == "BEVEL":
                symbol_layer.setPenJoinStyle(Qt.BevelJoin)
            elif style["line-join"].upper() == "ROUND":
                symbol_layer.setPenJoinStyle(Qt.RoundJoin)

        return symbol_layer

    @classmethod
    def handle_polygon_symbol_layer(cls, style: dict) -> QgsFillSymbolLayer:
        symbol_layer = QgsSimpleFillSymbolLayer()
        # set fill color
        fill_color = style["fill-color"] if "fill-color" in style else symbol_layer.color().name()
        fill_opacity = style["fill-opacity"] if "fill-opacity" in style else None
        fill_color = cls._merge_color_and_opacity_if_exist(fill_color, fill_opacity)
        if isinstance(fill_color, cls.QGISExpression):
            symbol_layer = cls._set_object_data_define_property_expression(
                symbol_layer, QgsSymbolLayer.PropertyFillColor, fill_color.value
            )
        else:
            symbol_layer.setColor(fill_color)
        # ----------------

        if "fill-outline-color" in style:
            border_color = style["fill-outline-color"]

            symbol_layer.setStrokeColor(QColor(border_color))
            symbol_layer.setStrokeWidth(1)
            symbol_layer.setStrokeWidthUnit(Qgis.RenderUnit.Pixels)
        else:
            symbol_layer.setStrokeStyle(Qt.PenStyle.NoPen)

        return symbol_layer

    @classmethod
    def _convert_mapbox_expression(cls, condition_expressions) -> any:
        if condition_expressions is None:
            return ""
        if not isinstance(condition_expressions, list):
            if isinstance(condition_expressions, str):
                condition_expressions = condition_expressions.replace("'", r"\'")
                condition_expressions = f"'{condition_expressions}'"
            # elif isinstance(condition_expressions, float):
            #    condition_expressions = condition_expressions * 100
            return condition_expressions

        # https://maplibre.org/maplibre-style-spec/expressions
        try:
            if condition_expressions[0] == "literal":
                exp = cls._convert_mapbox_expression(condition_expressions[1])
                exp = str(exp).replace("[", "").replace("]", "")
                return cls.QGISExpression(f"array({exp})")

            elif condition_expressions[0] in ["string", "number", "boolean", "object"]:
                exp = cls._convert_mapbox_expression(condition_expressions[1])
                return cls.QGISExpression(exp)

            elif condition_expressions[0] == "to-string":
                exp = cls._convert_mapbox_expression(condition_expressions[1])
                return cls.QGISExpression(f"to_string({exp})")

            elif condition_expressions[0] == "to-number":
                exp = cls._convert_mapbox_expression(condition_expressions[1])
                return cls.QGISExpression(f"to_real({exp})")

            elif condition_expressions[0] == "to-object":
                exp = cls._convert_mapbox_expression(condition_expressions[1])
                return cls.QGISExpression(f"to_object({exp})")

            elif condition_expressions[0] == "at":
                exp1 = cls._convert_mapbox_expression(condition_expressions[1])
                exp2 = cls._convert_mapbox_expression(condition_expressions[2])
                return cls.QGISExpression(f"{exp2}[{exp1}]")

            elif condition_expressions[0] == "index-of":
                exp1 = cls._convert_mapbox_expression(condition_expressions[1])
                exp2 = cls._convert_mapbox_expression(condition_expressions[2])
                return cls.QGISExpression(f"array_find({exp1}, {exp2})")

            elif condition_expressions[0] == "slice":
                exp1 = cls._convert_mapbox_expression(condition_expressions[1])
                exp2 = cls._convert_mapbox_expression(condition_expressions[2])
                converted_string = f"array_slice({exp1}, {exp2})"
                if len(condition_expressions) > 3:
                    exp3 = cls._convert_mapbox_expression(condition_expressions[3])
                    converted_string += f", {exp3}"
                return cls.QGISExpression(converted_string)

            elif condition_expressions[0] == "get":
                return cls.QGISExpression(condition_expressions[1])

            elif condition_expressions[0] == "has":
                exp1 = cls._convert_mapbox_expression(condition_expressions[1])
                return cls.QGISExpression(f"attribute({exp1}) is not null")

            elif condition_expressions[0] == "length":
                exp1 = cls._convert_mapbox_expression(condition_expressions[1])
                return cls.QGISExpression(f"array_length({exp1})")

            elif condition_expressions[0] == "case":
                converted_expression = "CASE"
                for i in range(1, len(condition_expressions) - 1, 2):
                    exp_x = cls._convert_mapbox_expression(condition_expressions[i])
                    exp_y = cls._convert_mapbox_expression(condition_expressions[i + 1])
                    converted_expression += f" WHEN {exp_x} THEN {exp_y}"
                if len(condition_expressions) % 2 == 0:
                    exp1 = cls._convert_mapbox_expression(condition_expressions[-1])
                    converted_expression += f" ELSE {exp1}"
                converted_expression += " END"
                return cls.QGISExpression(converted_expression)

            elif condition_expressions[0] == "match":
                converted_expression = "CASE"
                exp1 = cls._convert_mapbox_expression(condition_expressions[1])
                for i in range(2, len(condition_expressions), 2):
                    exp_x = cls._convert_mapbox_expression(condition_expressions[i])
                    exp_y = cls._convert_mapbox_expression(condition_expressions[i + 1])
                    converted_expression += f" WHEN {exp1} in {exp_x} THEN {exp_y}"
                if len(condition_expressions) % 2 == 0:
                    exp2 = cls._convert_mapbox_expression(condition_expressions[-1])
                    converted_expression += f" ELSE {exp2}"
                converted_expression += " END"
                return cls.QGISExpression(converted_expression)

            elif condition_expressions[0] in ["==", ">", "<", ">=", "<=", "!=", "in", "/", "%", "^"]:
                exp1 = cls._convert_mapbox_expression(condition_expressions[1])
                exp2 = cls._convert_mapbox_expression(condition_expressions[2])
                return f'{exp1} {condition_expressions[0] if condition_expressions[0] != "==" else "="} {exp2}'

            elif condition_expressions[0] in ["+", "*"]:
                exp1 = cls._convert_mapbox_expression(condition_expressions[1])
                converted_expression = f"{exp1}"
                for i in range(2, len(condition_expressions)):
                    exp_x = cls._convert_mapbox_expression(condition_expressions[i])
                    converted_expression += f" {condition_expressions[0]} {exp_x}"
                return cls.QGISExpression(converted_expression)

            elif condition_expressions[0] == "-":
                exp1 = cls._convert_mapbox_expression(condition_expressions[1])
                if len(condition_expressions) == 3:
                    exp2 = cls._convert_mapbox_expression(condition_expressions[2])
                    return f"{exp1} - {exp2}"
                else:
                    return cls.QGISExpression(f"-({exp1})")

            elif condition_expressions[0] in ["all", "any"]:
                exp1 = cls._convert_mapbox_expression(condition_expressions[1])
                converted_expression = f"({exp1}"
                for i in range(2, len(condition_expressions)):
                    exp_x = cls._convert_mapbox_expression(condition_expressions[i])
                    converted_expression += f'{" and" if condition_expressions[0] == "all" else " or"} {exp_x}'
                converted_expression += ")"
                return cls.QGISExpression(converted_expression)

            elif condition_expressions[0] == "!":
                exp1 = cls._convert_mapbox_expression(condition_expressions[1])
                return cls.QGISExpression(f"not {exp1}")

            elif condition_expressions[0] == "within":
                message = "Within expression not supported"
                QgsMessageBarHandler.send_message_to_message_bar(message, prefix="Expression error", level=Qgis.Warning)
                return ""

            elif condition_expressions[0] == "feature-state":
                message = "Feature state expression not supported"
                QgsMessageBarHandler.send_message_to_message_bar(message, prefix="Expression error", level=Qgis.Warning)
                return "false"

            elif condition_expressions[0] == "format":
                exp = f"{cls._convert_mapbox_expression(condition_expressions[1])}"
                for i in range(3, len(condition_expressions), 2):
                    exp += f"+{cls._convert_mapbox_expression(condition_expressions[i])}"
                return cls.QGISExpression(exp)

            else:
                return condition_expressions

        except Exception as e:
            QgsMessageBarHandler.send_message_to_message_bar(str(e), prefix="Expression error", level=Qgis.Warning)
            return "false"

    @staticmethod
    def _convert_mapbox_font(fonts: list) -> tuple[str, str]:
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
            f"Font {font} not supported", prefix="Expression error", level=Qgis.Warning
        )
        return "", ""

    @staticmethod
    def _convert_jmap_offset(offset: str):

        match = re.search(r"POINT\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)", offset)

        if match:
            x, y = map(int, match.groups())
            return x, y

    @classmethod
    def _get_pal_layer_settings(cls, labeling_data: dict) -> QgsPalLayerSettings:

        # set label settings
        rule_settings = QgsPalLayerSettings()
        rule_settings.centroidInside = True
        rule_settings.centroidWhole = True
        rule_settings.isExpression = True

        if "text" in labeling_data:
            rule_settings.fieldName = labeling_data["text"]

        if "symbolPlacement" in labeling_data:
            symbol_placement = labeling_data["symbolPlacement"]
            if symbol_placement == "point":
                rule_settings.placement = Qgis.LabelPlacement.OverPoint
            elif symbol_placement in ["line", "line-center"]:
                rule_settings.placement = Qgis.LabelPlacement.Line
        else:  # mapbox default value
            rule_settings.placement = Qgis.LabelPlacement.OverPoint

        # maplibre text anchor is inverse of qgis
        if "anchor" in labeling_data:
            text_anchor = labeling_data["anchor"].lower()
            # if isinstance(text_anchor, cls.QGISExpression):
            #    convert_dict = {
            #        "'center'": int(QgsPalLayerSettings.QuadrantOver),
            #        "'left'": int(QgsPalLayerSettings.QuadrantLeft),
            #        "'right'": int(QgsPalLayerSettings.QuadrantRight),
            #        "'top'": int(QgsPalLayerSettings.QuadrantAbove),
            #        "'bottom'": int(QgsPalLayerSettings.QuadrantBelow),
            #        "'top-left'": int(QgsPalLayerSettings.QuadrantAboveLeft),
            #        "'top-right'": int(QgsPalLayerSettings.QuadrantAboveRight),
            #        "'bottom-left'": int(QgsPalLayerSettings.QuadrantBelowLeft),
            #        "'bottom-right'": int(QgsPalLayerSettings.QuadrantBelowRight),
            #    }
            #    text_anchor = text_anchor.convert_expression_variable_to_qgis_variable(convert_dict)
            #    rule_settings = cls._set_object_data_define_property_expression(
            #        rule_settings, Qgis.LabelQuadrantPosition, text_anchor
            #    )
            # else:
            if text_anchor == "left":
                rule_settings.quadOffset = QgsPalLayerSettings.QuadrantRight
            elif text_anchor == "right":
                rule_settings.quadOffset = QgsPalLayerSettings.QuadrantLeft
            elif text_anchor == "top":
                rule_settings.quadOffset = QgsPalLayerSettings.QuadrantBelow
            elif text_anchor == "bottom":
                rule_settings.quadOffset = QgsPalLayerSettings.QuadrantAbove
            elif text_anchor == "top-left":
                rule_settings.quadOffset = QgsPalLayerSettings.QuadrantBelowRight
            elif text_anchor == "top-right":
                rule_settings.quadOffset = QgsPalLayerSettings.QuadrantBelowLeft
            elif text_anchor == "bottom-left":
                rule_settings.quadOffset = QgsPalLayerSettings.QuadrantAboveRight
            elif text_anchor == "bottom-right":
                rule_settings.quadOffset = QgsPalLayerSettings.QuadrantAboveLeft
            else:
                # mapbox default value
                rule_settings.quadOffset = QgsPalLayerSettings.QuadrantOver

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

        if "offset" in labeling_data:
            text_translate = labeling_data["offset"]
            # if isinstance(text_translate, str):
            #    rule_settings.xOffset = cls._set_object_data_define_property_expression(
            #        rule_settings, QgsPalLayerSettings.OffsetXY, text_translate
            #    )
            # else:
            x, y = cls._convert_jmap_offset(text_translate)
            rule_settings.xOffset = x
            rule_settings.yOffset = -y
            rule_settings.offsetUnits = Qgis.RenderUnit.Pixels

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
        color = cls._merge_color_and_opacity_if_exist(color, opacity)
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
        text_halo_color = cls._merge_color_and_opacity_if_exist(text_halo_color, opacity)
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
        background.setType(QgsTextBackgroundSettings.ShapeRectangle)
        if "frameActive" in labeling_data:
            background.setEnabled(labeling_data["frameActive"])

        background_symbol = background.fillSymbol()
        background_color = (
            labeling_data["frameFillColor"] if "frameFillColor" in labeling_data else background.color().name()
        )
        background_opacity = 1.0 - labeling_data["frameTransparency"] if "frameTransparency" in labeling_data else None
        background_color = cls._merge_color_and_opacity_if_exist(background_color, background_opacity)
        background_symbol.setColor(background_color)
        background_symbol_layer = background_symbol.symbolLayer(0)
        background_border_color = (
            labeling_data["frameBorderColor"] if "frameBorderColor" in labeling_data else background.color().name()
        )
        background_border_opacity = (
            1.0 - labeling_data["frameTransparency"] if "frameTransparency" in labeling_data else None
        )
        background_border_color = cls._merge_color_and_opacity_if_exist(
            background_border_color, background_border_opacity
        )
        background_symbol_layer.setStrokeColor(background_border_color)

        background_symbol_layer.setStrokeWidth(2)
        background_symbol_layer.setStrokeWidthUnit(Qgis.RenderUnit.Pixels)
        background_symbol_layer.setStrokeStyle(Qt.SolidLine)
        background_symbol_layer.setPenJoinStyle(Qt.MiterJoin)

        if "backgroundSymbolOffset" in labeling_data:
            x, y = cls._convert_jmap_offset(labeling_data["backgroundSymbolOffset"])
            background.setOffset(QPointF(x, y))
        background.setOffsetUnit(Qgis.RenderUnit.Pixels)
        background.setSize(QSizeF(5, 5))
        background.setSizeUnit(Qgis.RenderUnit.Pixels)

        text_format.setBackground(background)

        rule_settings.setFormat(text_format)
        return rule_settings

    @classmethod
    def _merge_color_and_opacity_if_exist(
        cls,
        color: any,
        opacity: any = None,
    ) -> any:
        color_is_expression = isinstance(color, cls.QGISExpression)
        opacity_is_expression = opacity and isinstance(opacity, cls.QGISExpression)

        if opacity:
            if color_is_expression or opacity_is_expression:
                color = color.value if color_is_expression else f"'{color}'"
                opacity = opacity.value if opacity_is_expression else opacity
                expressionString = f"set_color_part(({color}),'alpha',to_int(255*({opacity})))"
                return cls.QGISExpression(expressionString)
            else:
                color = QColor(color)
                color.setAlphaF(opacity)
                return color
        else:
            if color_is_expression:
                return color
            else:
                return QColor(color)

    @staticmethod
    def _set_object_data_define_property_expression(object: any, property_name: str, expressionString: str) -> any:
        properties_collection = object.dataDefinedProperties()
        property = properties_collection.property(property_name)
        property.setExpressionString(expressionString)
        properties_collection.setProperty(property_name, property)
        object.setDataDefinedProperties(properties_collection)
        return object
