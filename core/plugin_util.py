# -----------------------------------------------------------
# JMap Cloud plugin for QGIS
# Copyright (C) 2025 K2 Geospatial
# -----------------------------------------------------------
# Licensed under the terms of GNU GPL 3
# #
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
# #
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see https://www.gnu.org/licenses/gpl-3.0.html.
# -----------------------------------------------------------

import base64
import math
import pathlib
import re
import tempfile
from datetime import datetime, timezone

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsMapSettings,
    QgsRenderContext,
    QgsSymbol,
)
from qgis.PyQt.QtCore import QMetaType, QSize, Qt

MAX_SCALE_LIMIT = 295828763


def qgis_layer_type_to_jmc(type_enum: Qgis.LayerType) -> str:
    """Convert a QgsField.typeName() string to a MySQL type."""
    QGIS_LAYER_TYPE_TO_MYSQL = {
        Qgis.LayerType.Vector: "VECTOR",
        Qgis.LayerType.Raster: "RASTER",
        Qgis.LayerType.VectorTile: "VECTORTILE",
        Qgis.LayerType.Annotation: "VECTOR",
    }

    return QGIS_LAYER_TYPE_TO_MYSQL.get(type_enum, "UNKNOWN")


def qgis_data_type_name_to_mysql(type_enum: QMetaType.Type) -> str:
    """Convert a QgsField.typeName() string to a MySQL type."""
    QGIS_DATA_TYPE_TO_MYSQL = {
        QMetaType.Int: "INTEGER",
        QMetaType.LongLong: "BIGINT",
        QMetaType.Double: "DECIMAL",
        QMetaType.Float: "DECIMAL",
        QMetaType.QString: "VARCHAR",
        QMetaType.QDate: "DATE",
        QMetaType.QTime: "TIME",
        QMetaType.QDateTime: "DATETIME",
        QMetaType.Bool: "BOOLEAN",
        QMetaType.QByteArray: "BLOB",
        QMetaType.QVariantList: "JSON",  # unsuported now
    }

    return QGIS_DATA_TYPE_TO_MYSQL.get(type_enum, "UNKNOWN")


def convert_crs_to_epsg(crs: QgsCoordinateReferenceSystem) -> QgsCoordinateReferenceSystem:  # TODO: convert to epsg

    return crs


def find_value_in_dict_or_first(dict: dict, keys: list, default_value: any = None) -> any:
    """Find the first value in a dictionary that matches one of the keys.

    If the dictionary contains one of the keys, return the value associated with it.
    Otherwise, return the first item in the dictionary, or the default value if no items are found.
    """

    for key in keys:
        if key in dict:
            return dict[key]
    return next(iter(dict.values()), default_value)


def convert_zoom_to_scale(zoom: int) -> int:
    return int(MAX_SCALE_LIMIT / (2**zoom))


def convert_scale_to_zoom(scale: int) -> int:
    if scale == 0:
        return None
    return max(min(int(math.log2(MAX_SCALE_LIMIT / scale)), 23), 1)


def convert_measurement_to_pixel(value: any, unit: Qgis.RenderUnit) -> float:
    if isinstance(value, list):
        return [convert_measurement_to_pixel(v, unit) for v in value]
    else:
        map_settings = QgsMapSettings()
        render_context = QgsRenderContext.fromMapSettings(map_settings)
        if unit == Qgis.RenderUnit.Pixels:
            return value  # Déjà en pixels
        elif unit in [Qgis.RenderUnit.Millimeters, Qgis.RenderUnit.Inches, Qgis.RenderUnit.Points]:
            return render_context.convertToPainterUnits(value, unit)
        elif unit == Qgis.RenderUnit.MapUnits:
            if render_context.mapToPixel():
                return value / render_context.mapToPixel().mapUnitsPerPixel()  # TODO TEST
            else:
                raise ValueError("The render context does not contain a map to pixel transformation.")
        elif unit == Qgis.RenderUnit.MetersInMapUnits and False:  # TODO:
            if context.mapToPixel():
                pass
            else:
                raise ValueError("The render context does not contain a map to pixel transformation.")
        elif unit == Qgis.RenderUnit.Percentage and False:  # TODO
            return (value / 100.0) * context.scaleFactor()
        elif unit == Qgis.RenderUnit.Unknown:
            raise ValueError("Unknown unit")
        else:
            raise ValueError(f"Unknown unit: {unit}")


def image_to_base64(path: str) -> str:
    if not pathlib.Path(path).is_file():
        raise ValueError(f"The file {path} does not exist.")
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def symbol_to_SVG_base64(symbol: QgsSymbol) -> str:
    temp_dir = tempfile.TemporaryDirectory(delete=True)
    temp_file = temp_dir.name + "/MarkerSymbol.svg"
    size = math.ceil(convert_measurement_to_pixel(symbol.size(), symbol.sizeUnit()))
    symbol.exportImage(temp_file, "SVG", QSize(size, size))
    base64_symbol = image_to_base64(temp_file)
    temp_dir.cleanup()
    return base64_symbol


def convert_jmap_datetime(jmap_datetime: str) -> datetime:
    return datetime.fromisoformat(jmap_datetime).astimezone(timezone.utc)


def time_now() -> str:
    return datetime.now(timezone.utc)


def convert_QGIS_text_expression_to_JMap(expression):  # TODO upgrade

    parts = re.split(r"\B\s*\+\s*\B", expression)
    new_parts = []
    for part in parts:
        if re.match(r"^'(.*?)'$", part.strip()):
            part = re.sub(r"^'(.*?)'$", r"\1", part)
        elif re.match(r'^"\s*\w+\s*"$', part):
            part = re.sub(r'^"\s*(\w+)\s*"$', r"ev(\1)", part)
        elif re.match(r"^\s*\w+\s*$", part):
            part = re.sub(r"^\s*(\w+)\s*$", r"ev(\1)", part)
        else:
            part = "unsupported"

        new_parts.append(part)

    return "".join(new_parts)


def convert_jmap_text_expression(text: str) -> str:
    text = text.replace("{", "{{").replace("}", "}}")
    text = text.replace("'", "\\'")

    new_text = text
    replacement_counter = 0
    replacements = {}

    # backreference are not quoted while {num} are quoted if they do not refer to a placeholder
    patterns = {
        r"[eE][vV]\(\s*(\w+)\s*\)": r"\1",  # non formatter group
        r"[iI][fF][nN][oO][tT][nN][uU][lL][lL]\(\s*([\w]+|\{\d+\})\s*,\s*([\w]+|\{\d+\})\s*\)": "if(attribute({0}), {1}, '')",  # formatter groups
        r"[iI][fF][nN][uU][lL][lL]\(\s*([\w]+|\{\d+\})\s*,\s*([\w]+|\{\d+\})\s*\)": "if(attribute({0}), '', {1})",  # formatter groups
        r"[Ll][Ii][Nn][Ee][lL][Ee][Nn][Gg][Tt][Hh]\(\s*\)": 'to_string(round( "jmap_length",2))',
        r"[Pp][Oo][Ll][Yy][Gg][Oo][Nn][Aa][Rr][Ee][Aa]\(\s*\)": 'to_string(round("jmap_area", 2))',
        r"[Pp][Rr][Oo][Jj][Ee][Cc][Tt][nN][Aa][Mm][Ee]\(\s*\)": "@project_basename",
        r"[Dd][Aa][Tt][Ee]\(\s*\)": " format_date( now(),'ddd MMM dd yyyy')",
        r"[Ss][Uu][Bb][Ss][Tt][Rr][Ii][Nn][Gg]\(\s*([\w]+|\{\d+\})\s*,\s*([\w]+|\{\d+\})\s*,\s*([\w]+|\{\d+\})\s*\)": "substr({0}, {1}, {2} - {1})",
    }

    # 🔹 **Build a regex that matches any function name in `patterns`**
    pattern_regex = "|".join(patterns.keys())

    def quote(group) -> str:
        if not re.search(r"\{\d+\}", group):
            group = f"'{group}'"
        return group

    # 🔹 **Step 1: Process one match at a time until no more matches are found**
    while True:
        match = re.search(pattern_regex, new_text)
        if not match:  # No more functions found → stop processing
            break

        formatted_group = match.group(0)
        # Apply the corresponding pattern replacement
        for pattern, replacement in patterns.items():
            sub_matches = re.search(pattern, formatted_group)
            if not sub_matches:
                continue
            # quote all non placeholder formatter groups
            quoted_group = [quote(group) for group in sub_matches.groups()]

            # replacement is quoted if specified in the pattern replacement
            formatted_group = re.sub(pattern, replacement.format(*quoted_group), formatted_group)

        replacements[replacement_counter] = formatted_group
        key = f"{{{replacement_counter}}}"
        new_text = new_text.replace(match.group(0), key, 1)  # Replace only the first occurrence
        replacement_counter += 1

    # 🔹 **Step 2: Split the text while keeping placeholders**
    parts = re.split(r"(\{\d+\})", new_text)

    formatted_parts = []
    for part in parts:
        if not bool(part):
            continue
        if re.match(r"\{\d+\}", part):
            formatted_parts.append(part)
        else:
            formatted_parts.append(f"'{part}'")

    # 🔹 **Step 3: Join with `+`**
    new_text = " + ".join(formatted_parts)

    # 🔹 **Step 4: Replace placeholders with actual function outputs**

    while re.search(r"\{\d+\}", new_text):
        new_text = new_text.format(*replacements.values())

    return new_text


def convert_pen_style_to_dash_array(pen_style, width) -> list[int]:
    dashPattern = None

    if pen_style == Qt.PenStyle.SolidLine:
        dashPattern = []
    elif pen_style == Qt.PenStyle.DotLine:
        return [1, 2]
    elif pen_style == Qt.PenStyle.DashLine:
        return [4, 2]
    elif pen_style == Qt.PenStyle.DashDotLine:
        return [4, 2, 1, 2]
    elif pen_style == Qt.PenStyle.DashDotDotLine:
        return [4, 2, 1, 2, 1, 2]

    return dashPattern


def opacity_to_transparency(opacity) -> float:

    return (1 - min(1.0, opacity)) * 100


def transparency_to_opacity(transparency) -> float:
    return 1 - transparency / 100
