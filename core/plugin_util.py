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
from typing import Union

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFontMarkerSymbolLayer,
    QgsMapSettings,
    QgsMessageLog,
    QgsProject,
    QgsRasterMarkerSymbolLayer,
    QgsRenderContext,
    QgsSVGFillSymbolLayer,
    QgsSvgMarkerSymbolLayer,
    QgsSymbol,
)
from qgis.PyQt.QtCore import QBuffer, QLocale, QMetaType, QRect, QSettings, QSize, Qt
from qgis.PyQt.QtGui import QColor, QFont, QImage, QPainter, QPainterPath
from qgis.PyQt.QtSvg import QSvgGenerator

MAX_SCALE_LIMIT = 295828763
TILE_SIZE_IN_PIXELS = 512
EARTH_CIRCUMFERENCE_IN_METERS_AT_EQUATOR = 40075016.686
METERS_PER_PX_AT_EQUATOR = EARTH_CIRCUMFERENCE_IN_METERS_AT_EQUATOR / TILE_SIZE_IN_PIXELS
METERS_PER_INCH = 0.0254
DEFAULT_OGC_WMS_DPI = 25.4 / 0.28  # 90.7142857142857 dpi

# --- JMap expression pattern constants ---
# Case-insensitive patterns: use re.IGNORECASE flag in regex operations
_PAT_EV = r"ev\(\s*(\w+)\s*\)"
_PAT_IFNOTNULL = r"ifnotnull\(\s*(\w+)\s*,\s*([^)]+)\s*\)"
_PAT_IFNULL = r"ifnull\(\s*(\w+)\s*,\s*([^)]+)\s*\)"
_PAT_LINELENGTH = r"linelength\(\s*\)"
_PAT_POLYGONAREA = r"polygonarea\(\s*\)"
_PAT_PROJECTNAME = r"projectname\(\s*\)"
_PAT_DATE = r"date\(\s*\)"
_PAT_SUBSTRING = (
    r"substring" r"\(\s*([\w]+|\{\d+\})\s*,\s*([\w]+|\{\d+\})\s*,\s*([\w]+|\{\d+\})\s*\)"
)
_PAT_FORMAT_DATE = r"format\(\s*(\w+)\s*,\s*([^)]+)\s*\)"
_PAT_FORMAT_NUMBER = r"format\(\s*(\w+)\s*,\s*[\'\"]?((?:[#0.,]+))[\'\"]?\s*\)"
_PAT_CENTROID = r"centroid\(\s*\)"
_PAT_ELEMENTID = r"elementid\(\s*\)"
_PAT_USERNAME = r"username\(\s*\)"

_REPL_MO_EV = r"[%if(attribute('\1'), attribute('\1'), '')%]"
_REPL_MO_IFNOTNULL = r"[%if(attribute('\1'), attribute('\1'), '')%]"
_REPL_MO_IFNULL = r"[%if(attribute('\1'), '', attribute('\1'))%]"
_REPL_MO_LINELENGTH = "[%if(geometry_type(@geometry)='Line', round($length, 2), '')%]"
_REPL_MO_POLYGONAREA = "[%if(geometry_type(@geometry)='Polygon', round($area, 2), '')%]"
_REPL_MO_PROJECTNAME = "[%@project_basename%]"
_REPL_MO_DATE = "[%format_date( now(),'ddd MMM dd yyyy')%]"
_REPL_MO_SUBSTRING = r"[%substr(if(attribute('\1'), attribute('\1'), ''), \2, \3 - \2)%]"
_REPL_MO_FORMAT_DATE = r"[%format_date(attribute('\1'), '\2')%]"
_REPL_MO_FORMAT_NUMBER = r"[%format_number(attribute('\1'), '\2')%]"
_REPL_MO_CENTROID = r"[%concat('X: ',x(centroid(@geometry)), ' Y: ', y(centroid(@geometry)))%]"
_REPL_MO_ELEMENTID = r"[%if(attribute('jmap_id'), attribute('jmap_id'), '')%]"
_REPL_MO_USERNAME = "[%@user_account_name%]"
# --- end JMap expression pattern constants ---

_SVG_PARAM_PATTERN = re.compile(r"param\(\s*([^)]+?)\s*\)\s*([^\"';\s>]*)")


def _convert_latitude_to_radians(latitude: float) -> float:
    """Convert latitude in degrees to radians."""
    return math.radians(latitude)


def _mean_latitude_from_rect(rect, src_crs, proj: QgsProject) -> float:
    if not rect or rect.isEmpty() or not src_crs or not src_crs.isValid():
        return 0.0
    try:
        tr = QgsCoordinateTransform(
            src_crs, QgsCoordinateReferenceSystem("EPSG:4326"), proj.transformContext()
        )
        lonlat_bb = tr.transformBoundingBox(rect)
        return lonlat_bb.center().y()
    except Exception:
        QgsMessageLog.logMessage(
            "Failed to compute mean latitude from project extent."
            + " Falling back to map center latitude.",
            "JMap Cloud Plugin",
            Qgis.MessageLevel.Warning,
        )
        return 0.0


def _mean_latitude_from_layers() -> float:
    proj = QgsProject.instance()
    dst_crs = proj.crs()
    if not dst_crs or not dst_crs.isValid():
        return 0.0

    union_rect = None
    for layer in proj.mapLayers().values():
        try:
            if not layer.isValid():
                continue
            lyr_extent = layer.extent()
            if not lyr_extent or lyr_extent.isEmpty():
                continue
            lyr_crs = layer.crs() if hasattr(layer, "crs") else None
            if lyr_crs and lyr_crs.isValid() and lyr_crs != dst_crs:
                tr = QgsCoordinateTransform(lyr_crs, dst_crs, proj.transformContext())
                lyr_extent = tr.transformBoundingBox(lyr_extent)
            union_rect = (
                lyr_extent if union_rect is None else union_rect.combineExtentWith(lyr_extent)
            )
        except Exception:
            QgsMessageLog.logMessage(
                f"Failed to include layer {layer.name()} in mean latitude computation.",
                "JMap Cloud Plugin",
                Qgis.MessageLevel.Warning,
            )
            continue

    return _mean_latitude_from_rect(union_rect, dst_crs, proj) if union_rect else 0.0


def _get_mean_latitude_project() -> float:
    """Get the mean latitude of the current project extent."""
    proj = QgsProject.instance()
    project_extent = proj.viewSettings().defaultViewExtent()

    if project_extent and not project_extent.isEmpty():
        return _mean_latitude_from_rect(project_extent, proj.crs(), proj)
    else:
        return _mean_latitude_from_layers()


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
        QMetaType.Type.Int: "INTEGER",
        QMetaType.Type.LongLong: "BIGINT",
        QMetaType.Type.Double: "DECIMAL",
        QMetaType.Type.Float: "DECIMAL",
        QMetaType.Type.QString: "VARCHAR",
        QMetaType.Type.QDate: "DATE",
        QMetaType.Type.QTime: "TIME",
        QMetaType.Type.QDateTime: "DATETIME",
        QMetaType.Type.Bool: "BOOLEAN",
        QMetaType.Type.QByteArray: "BLOB",
        QMetaType.Type.QVariantList: "JSON",  # unsuported now
    }

    return QGIS_DATA_TYPE_TO_MYSQL.get(type_enum, "UNKNOWN")


def convert_crs_to_epsg(
    crs: QgsCoordinateReferenceSystem,
) -> QgsCoordinateReferenceSystem:  # TODO: convert to epsg
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


def convert_scale_to_zoom(scale: int) -> Union[int, None]:
    if scale <= 0:
        return None

    mean_latitude = _get_mean_latitude_project()
    return math.log2(
        (
            METERS_PER_PX_AT_EQUATOR
            * math.cos(_convert_latitude_to_radians(mean_latitude))
            * (1 / scale)
            * DEFAULT_OGC_WMS_DPI
        )
        / METERS_PER_INCH
    )


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
                raise ValueError(
                    "The render context does not contain a map to pixel transformation."
                )
        # elif unit == Qgis.RenderUnit.MetersInMapUnits and False:  # TODO:
        #     if render_context.mapToPixel():
        #         pass
        #     else:
        #         raise ValueError(
        #             "The render context does not contain a map to pixel transformation."
        #         )
        # elif unit == Qgis.RenderUnit.Percentage and False:  # TODO
        #     return (value / 100.0) * context.scaleFactor()
        elif unit == Qgis.RenderUnit.Unknown:
            raise ValueError("Unknown unit")
        else:
            raise ValueError("Unknown unit: {}".format(unit))


def image_to_base64(path: str, qSize: QSize = None) -> str:
    if not pathlib.Path(path).is_file():
        raise ValueError("The file {} does not exist.".format(path))
    img = QImage(str(path))

    if img.isNull():
        raise ValueError("Failed to load image: {}".format(path))
    if qSize is not None:
        img = img.scaled(
            qSize,
            aspectRatioMode=Qt.AspectRatioMode.IgnoreAspectRatio,
            transformMode=Qt.TransformationMode.SmoothTransformation,
        )

    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.ReadWrite)
    img.save(buffer, "PNG")
    base64_str = base64.b64encode(buffer.data()).decode("utf-8")
    buffer.close()
    return base64_str


def resolve_polygon_svg_params(symbol_layer: QgsSVGFillSymbolLayer) -> str:
    """
    Resolves `param(...)` placeholders in an SVG used by a QgsSVGFillSymbolLayer.
    Args:
        symbol_layer: The QgsSVGFillSymbolLayer object.
    Returns:
        str: The final SVG content with placeholders replaced.
    """
    properties = symbol_layer.properties()
    svg_path = pathlib.Path(symbol_layer.svgFilePath())

    if not svg_path.exists():
        return ""

    svg_content = svg_path.read_text(encoding="utf-8").replace("\n", "")

    param_to_value = _build_svg_param_map(properties)

    # Step 4: Replace param(...) with actual values
    # Replace existing width/height or add them if missing
    final_svg = _replace_svg_params_in_text(svg_content, param_to_value)
    final_svg = _ensure_xml_declaration(final_svg)

    # Step 5: Print or save final SVG
    return final_svg


def resolve_point_svg_params(symbol_layer: QgsSvgMarkerSymbolLayer) -> str:
    """
    Resolves `param(...)` placeholders in an SVG used by a QgsSvgMarkerSymbolLayer.
    Args:
        symbol_layer: The QgsSvgMarkerSymbolLayer object.
    Returns:
        str: The final SVG content with placeholders replaced.
    """
    properties = symbol_layer.properties()
    svg_path = pathlib.Path(symbol_layer.path())

    if not svg_path.exists():
        return ""

    width = math.ceil(convert_measurement_to_pixel(symbol_layer.size(), symbol_layer.sizeUnit()))
    height = math.ceil(
        convert_measurement_to_pixel(
            calculate_height_symbol_layer(symbol_layer), symbol_layer.sizeUnit()
        )
    )
    svg_content = svg_path.read_text(encoding="utf-8").replace("\n", "")

    param_to_value = _build_svg_param_map(properties)

    # Step 4: Replace param(...) with actual values
    # Replace existing width/height or add them if missing
    svg_content = _set_svg_root_dimensions(svg_content, width, height)
    final_svg = _replace_svg_params_in_text(svg_content, param_to_value)
    final_svg = _ensure_xml_declaration(final_svg)

    # Step 5: Print or save final SVG
    return final_svg


def font_marker_to_svg(symbol_layer: QgsFontMarkerSymbolLayer) -> str:
    character = symbol_layer.character()
    font_family = symbol_layer.fontFamily()

    # Convert symbol size to pixels regardless of original unit
    size_px = math.ceil(convert_measurement_to_pixel(symbol_layer.size(), symbol_layer.sizeUnit()))

    fill = symbol_layer.color().name()
    stroke_color = symbol_layer.strokeColor().name()
    stroke_width = math.ceil(
        convert_measurement_to_pixel(symbol_layer.strokeWidth(), symbol_layer.strokeWidthUnit())
    )

    # Canvas size (in pixels)
    canvas_size = size_px * 2

    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)

    svg_gen = QSvgGenerator()
    svg_gen.setOutputDevice(buffer)

    # Set size in pixels
    svg_gen.setSize(QSize(canvas_size, canvas_size))

    # Set viewBox to match our pixel dimensions
    svg_gen.setViewBox(QRect(0, 0, canvas_size, canvas_size))

    painter = QPainter()
    if not painter.begin(svg_gen):
        raise ValueError("Failed to begin painting on SVG generator.")

    # Use a font size proportional to our pixel size
    font = QFont(font_family, size_px)
    font.setPixelSize(size_px)  # This ensures the font size is exactly in pixels

    path = QPainterPath()
    path.addText(0, 0, font, character)

    # Calculate proper centering
    rect = path.boundingRect()
    x_offset = (canvas_size - rect.width()) / 2 - rect.left()
    y_offset = (canvas_size - rect.height()) / 2 - rect.top()

    centered_path = QPainterPath()
    centered_path.addText(x_offset, y_offset, font, character)

    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(fill))

    if stroke_width > 0:
        pen = painter.pen()
        pen.setColor(QColor(stroke_color))
        pen.setWidth(stroke_width)
        painter.setPen(pen)
    else:
        painter.setPen(Qt.PenStyle.NoPen)

    painter.drawPath(centered_path)
    painter.end()

    svg_content = buffer.data().data().decode("utf-8")

    # Post-process SVG to ensure dimensions are in pixels
    svg_content = re.sub(
        r"<svg [^>]*>",
        lambda m: re.sub(r'(width|height)="[^"]*mm"', r'\1="{}px"'.format(canvas_size), m.group(0)),
        svg_content,
    )

    buffer.close()
    return svg_content


def calculate_height_symbol_layer(
    symbol_layer: Union[QgsRasterMarkerSymbolLayer, QgsSvgMarkerSymbolLayer],
) -> float:
    """
    Calculate the height of the symbol layer.
    This is a placeholder for actual height calculation logic.
    """
    size = symbol_layer.size()  # This is the marker's base size (often height)
    if symbol_layer.preservedAspectRatio():
        aspect = symbol_layer.defaultAspectRatio()  # width / height from image
    else:
        aspect = symbol_layer.fixedAspectRatio()  # custom, if set
    # If aspect ratio is 0, fallback to 1 (square)
    if aspect <= 0:
        aspect = 1.0
    # Now calculate width and height
    width = size
    height = width * aspect
    return height


def SVG_to_base64(svg_content: str) -> str:
    """Convert SVG content to a base64 encoded string."""
    if not svg_content:
        raise ValueError("SVG content is empty.")
    svg_bytes = svg_content.encode("utf-8")
    return base64.b64encode(svg_bytes).decode("utf-8")


def symbol_to_SVG_base64(symbol: QgsSymbol, qSize: QSize = None) -> str:
    temp_dir = tempfile.TemporaryDirectory()
    temp_file = temp_dir.name + "/MarkerSymbol.svg"
    dimension = math.ceil(convert_measurement_to_pixel(symbol.size(), symbol.sizeUnit()))
    size = qSize if qSize else QSize(dimension, dimension)  # Default size if not provided
    symbol.exportImage(temp_file, "SVG", size)
    base64_symbol = image_to_base64(temp_file)
    temp_dir.cleanup()
    return base64_symbol


def svg_content_to_base64(svg_content: str, qSize: QSize) -> str:
    temp_dir = tempfile.TemporaryDirectory()
    temp_file = temp_dir.name + "/temp.svg"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(svg_content)
    base64_svg = image_to_base64(temp_file, qSize)
    temp_dir.cleanup()
    return base64_svg


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


def convert_jmap_text_mouse_over_expression(text: str) -> str:
    text = text.replace("{", "{{").replace("}", "}}")
    text = text.replace("'", "\\'")

    new_text = text
    replacement_counter = 0
    replacements = {}

    patterns = {
        _PAT_EV: _REPL_MO_EV,  # non formatter group
        _PAT_IFNOTNULL: _REPL_MO_IFNOTNULL,  # formatter groups
        _PAT_IFNULL: _REPL_MO_IFNULL,  # formatter groups
        _PAT_LINELENGTH: _REPL_MO_LINELENGTH,
        _PAT_POLYGONAREA: _REPL_MO_POLYGONAREA,
        _PAT_PROJECTNAME: _REPL_MO_PROJECTNAME,
        _PAT_DATE: _REPL_MO_DATE,
        _PAT_SUBSTRING: _REPL_MO_SUBSTRING,
        _PAT_FORMAT_DATE: _REPL_MO_FORMAT_DATE,
        _PAT_FORMAT_NUMBER: _REPL_MO_FORMAT_NUMBER,
        _PAT_CENTROID: _REPL_MO_CENTROID,
        _PAT_ELEMENTID: _REPL_MO_ELEMENTID,
        _PAT_USERNAME: _REPL_MO_USERNAME,
    }
    # 🔹 **Build a regex that matches any function name in `patterns`**
    pattern_regex = "|".join(patterns.keys())

    def quote(group) -> str:
        if not re.search(r"\{\d+\}", group):
            group = "'{}'".format(group)
        return group

    # 🔹 **Step 1: Process one match at a time until no more matches are found**
    while True:
        match = re.search(pattern_regex, new_text, re.IGNORECASE)
        if not match:  # No more functions found → stop processing
            break

        formatted_group = match.group(0)
        # Apply the corresponding pattern replacement
        for pattern, replacement in patterns.items():
            sub_matches = re.search(pattern, formatted_group, re.IGNORECASE)
            if not sub_matches:
                continue
            # quote all non placeholder formatter groups
            # quoted_group = [quote(group) for grou`p in sub_matches.groups()]

            # replacement is quoted if specified in the pattern replacement
            formatted_group = re.sub(pattern, replacement, formatted_group, flags=re.IGNORECASE)

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
            formatted_parts.append("{}".format(part))

    # # 🔹 **Step 3: Join with `+`**
    # new_text = " + ".join(formatted_parts)

    # 🔹 **Step 4: Replace placeholders with actual function outputs**

    while re.search(r"\{\d+\}", new_text):
        new_text = new_text.format(*replacements.values())

    return new_text


def convert_jmap_text_label_expression(text: str) -> str:
    text = text.replace("{", "{{").replace("}", "}}")
    text = text.replace("'", "\\'")

    new_text = text
    replacement_counter = 0
    replacements = {}

    patterns = {
        _PAT_EV: r"\1",  # non formatter group
        _PAT_IFNOTNULL: "if(attribute({0}), {1}, '')",  # formatter groups
        _PAT_IFNULL: "if(attribute({0}), '', {1})",  # formatter groups
    }

    # 🔹 **Build a regex that matches any function name in `patterns`**
    pattern_regex = "|".join(patterns.keys())

    def quote(group) -> str:
        if not re.search(r"\{\d+\}", group):
            group = "'{}'".format(group)
        return group

    # 🔹 **Step 1: Process one match at a time until no more matches are found**
    while True:
        match = re.search(pattern_regex, new_text, re.IGNORECASE)
        if not match:  # No more functions found → stop processing
            break

        formatted_group = match.group(0)
        # Apply the corresponding pattern replacement
        for pattern, replacement in patterns.items():
            sub_matches = re.search(pattern, formatted_group, re.IGNORECASE)
            if not sub_matches:
                continue
            # quote all non placeholder formatter groups
            quoted_group = [quote(group) for group in sub_matches.groups()]

            # replacement is quoted if specified in the pattern replacement
            formatted_group = re.sub(
                pattern, replacement.format(*quoted_group), formatted_group, flags=re.IGNORECASE
            )

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
            formatted_parts.append("'{}'".format(part))

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


def get_user_locale() -> str:

    return QSettings().value("locale/userLocale", QLocale.system().name()).split("_")[0]


def _extract_rgba(qgis_color_string):
    rgba = qgis_color_string.split(",")
    if len(rgba) >= 4:
        r, g, b, a = map(int, rgba[:4])
        return f"rgb({r},{g},{b})", str(round(a / 255.0, 2))
    return "#000000", "1"


def _build_svg_param_map(properties: dict) -> dict[str, str]:
    fill_color, fill_opacity = _extract_rgba(
        find_value_in_dict_or_first(properties, ["color", "fill"], "0,0,0,255")
    )
    outline_color, outline_opacity = _extract_rgba(
        find_value_in_dict_or_first(properties, ["outline_color", "outline"], "0,0,0,255")
    )

    outline_width = find_value_in_dict_or_first(
        properties,
        ["outline_width", "outline-width", "stroke_width", "stroke-width"],
        "1",
    )

    return {
        "fill": fill_color,
        "fill-opacity": fill_opacity,
        "outline": outline_color,
        "outline-opacity": outline_opacity,
        "outline-width": str(outline_width),
    }


def _normalize_svg_param_key(key: str) -> str:
    normalized = key.strip().strip("'\"")
    normalized = re.split(r"[,\s]", normalized, maxsplit=1)[0]
    return normalized.lower()


def _replace_svg_param_match(match, param_to_value):
    key = _normalize_svg_param_key(match.group(1))
    fallback = match.group(2).strip() if match.group(2) else ""
    if key in param_to_value:
        return param_to_value[key]
    if fallback:
        return fallback
    return match.group(0)


def _replace_svg_params_in_text(svg_content: str, param_to_value: dict[str, str]) -> str:
    return _SVG_PARAM_PATTERN.sub(
        lambda m: _replace_svg_param_match(m, param_to_value),
        svg_content,
    )


def _set_svg_root_dimensions(svg_content: str, width: int, height: int) -> str:
    svg_tag_match = re.search(r"<svg\b[^>]*>", svg_content)
    if not svg_tag_match:
        return svg_content

    svg_tag = svg_tag_match.group(0)

    if re.search(r'\bwidth="[^"]*"', svg_tag):
        svg_tag = re.sub(r'\bwidth="[^"]*"', f'width="{width}"', svg_tag)
    else:
        svg_tag = svg_tag[:-1] + f' width="{width}">'

    if re.search(r'\bheight="[^"]*"', svg_tag):
        svg_tag = re.sub(r'\bheight="[^"]*"', f'height="{height}"', svg_tag)
    else:
        svg_tag = svg_tag[:-1] + f' height="{height}">'

    return svg_content[: svg_tag_match.start()] + svg_tag + svg_content[svg_tag_match.end() :]


def _ensure_xml_declaration(svg_content: str) -> str:
    return (
        svg_content
        if svg_content.lstrip().startswith("<?xml")
        else '<?xml version="1.0" encoding="UTF-8"?>' + svg_content
    )
