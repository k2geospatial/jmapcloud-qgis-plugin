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
    QgsMapSettings,
    QgsRenderContext,
    QgsSymbol,
    QgsFontMarkerSymbolLayer,
    QgsSvgMarkerSymbolLayer,
    QgsRasterMarkerSymbolLayer,
    QgsSVGFillSymbolLayer,
    QgsCoordinateTransform,
    QgsProject,
)

from qgis.PyQt.QtCore import QMetaType, QSize, Qt, QBuffer, QRect
from qgis.PyQt.QtGui import QImage, QPainter, QFont, QPainterPath, QColor
from PyQt5.QtSvg import QSvgGenerator

MAX_SCALE_LIMIT = 295828763
TILE_SIZE_IN_PIXELS = 512
EARTH_CIRCUMFERENCE_IN_METERS_AT_EQUATOR = 40075016.686
METERS_PER_PX_AT_EQUATOR = EARTH_CIRCUMFERENCE_IN_METERS_AT_EQUATOR / TILE_SIZE_IN_PIXELS
METERS_PER_INCH = 0.0254
DEFAULT_OGC_WMS_DPI = 25.4 / 0.28  # 90.7142857142857 dpi

def _convert_latitude_to_radians(latitude: float) -> float:
    """Convert latitude in degrees to radians."""
    return math.radians(latitude)

def map_center_position() -> tuple[float, float]:
    """Get the map center position in latitude and longitude."""
    proj = QgsProject.instance()
    rect = proj.viewSettings().defaultViewExtent()
    tr = QgsCoordinateTransform(proj.crs(), QgsCoordinateReferenceSystem("EPSG:4326"), proj.transformContext())
    center = tr.transform(rect.center())
    lat, lon = center.y(), center.x()
    return lat, lon

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


def convert_scale_to_zoom(scale: int) -> Union[int, None]:
    if scale <= 0:
        return None
    
    lat, _ = map_center_position()
    return math.log2(
        (METERS_PER_PX_AT_EQUATOR * math.cos(_convert_latitude_to_radians(lat)) * (1 / scale) * DEFAULT_OGC_WMS_DPI) / 
         METERS_PER_INCH
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
            raise ValueError("Unknown unit: {}".format(unit))


def image_to_base64(path: str, qSize: QSize = None) -> str:
    if not pathlib.Path(path).is_file():
        raise ValueError("The file {} does not exist.".format(path))
    img = QImage(str(path))

    if img.isNull():
        raise ValueError("Failed to load image: {}".format(path))
    if qSize is not None:
        img = img.scaled(qSize, aspectRatioMode=Qt.IgnoreAspectRatio, transformMode=Qt.SmoothTransformation)
   
    buffer = QBuffer()
    buffer.open(QBuffer.ReadWrite)
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
    
    svg_content = svg_path.read_text(encoding='utf-8').replace("\n", "")

    param_to_value = {
        "fill": properties.get("color", "#000000").split(',')[0],  # fallback to black
        "fill-opacity": "1",  # can extract alpha if needed
        "outline": properties.get("outline_color", "#000000").split(',')[0],
        "outline-opacity": "1",  # can extract alpha if needed
        "outline-width": properties.get("outline_width", "1")
    }

    # Replace values with accurate RGBA
    if "color" in properties:
        fill_color, fill_opacity = _extract_rgba(properties["color"])
        param_to_value["fill"] = fill_color
        param_to_value["fill-opacity"] = fill_opacity

    if "outline_color" in properties:
        outline_color, outline_opacity = _extract_rgba(properties["outline_color"])
        param_to_value["outline"] = outline_color
        param_to_value["outline-opacity"] = outline_opacity

    # Step 4: Replace param(...) with actual values
    # Replace existing width/height or add them if missing
    final_svg = re.sub(r'param\((.*?)\)', lambda m: _replace_param(m, param_to_value), svg_content)
     
    final_svg = '<?xml version="1.0" encoding="UTF-8"?>' + final_svg  # Ensure the SVG starts with the XML declaration

    # Step 5: Print or save final SVG
    return final_svg

def resolve_point_svg_params(symbol_layer:  QgsSvgMarkerSymbolLayer) -> str:
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
    height = math.ceil(convert_measurement_to_pixel(calculate_height_symbol_layer(symbol_layer), symbol_layer.sizeUnit()))
    svg_content = svg_path.read_text(encoding='utf-8').replace("\n", "")

    param_to_value = {
        "fill": properties.get("color", "#000000").split(',')[0],  # fallback to black
        "fill-opacity": "1",  # can extract alpha if needed
        "outline": properties.get("outline_color", "#000000").split(',')[0],
        "outline-opacity": "1",  # can extract alpha if needed
        "outline-width": properties.get("outline_width", "1")
    }

    # Replace values with accurate RGBA
    if "color" in properties:
        fill_color, fill_opacity = _extract_rgba(properties["color"])
        param_to_value["fill"] = fill_color
        param_to_value["fill-opacity"] = fill_opacity

    if "outline_color" in properties:
        outline_color, outline_opacity = _extract_rgba(properties["outline_color"])
        param_to_value["outline"] = outline_color
        param_to_value["outline-opacity"] = outline_opacity

    # Step 4: Replace param(...) with actual values
    # Replace existing width/height or add them if missing
    svg_content = re.sub(r'width="[^"]*"', f'width="{width}"', svg_content)
    svg_content = re.sub(r'height="[^"]*"', f'height="{height}"', svg_content)
    final_svg = re.sub(r'param\((.*?)\)', lambda m: _replace_param(m, param_to_value), svg_content)
     
    final_svg = '<?xml version="1.0" encoding="UTF-8"?>' + final_svg  # Ensure the SVG starts with the XML declaration

    # Step 5: Print or save final SVG
    return final_svg

def font_marker_to_svg(symbol_layer: QgsFontMarkerSymbolLayer) -> str:
    character = symbol_layer.character()
    font_family = symbol_layer.fontFamily()
    
    # Convert symbol size to pixels regardless of original unit
    size_px = math.ceil(convert_measurement_to_pixel(symbol_layer.size(), symbol_layer.sizeUnit()))
    
    fill = symbol_layer.color().name()
    stroke_color = symbol_layer.strokeColor().name()
    stroke_width = math.ceil(convert_measurement_to_pixel(symbol_layer.strokeWidth(), symbol_layer.strokeWidthUnit()))

    # Canvas size (in pixels)
    canvas_size = size_px * 2

    buffer = QBuffer()
    buffer.open(QBuffer.WriteOnly)
    
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

    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(fill))

    if stroke_width > 0:
        pen = painter.pen()
        pen.setColor(QColor(stroke_color))
        pen.setWidth(stroke_width)
        painter.setPen(pen)
    else:
        painter.setPen(Qt.NoPen)

    painter.drawPath(centered_path)
    painter.end()
    
    svg_content = buffer.data().data().decode('utf-8')
    
    # Post-process SVG to ensure dimensions are in pixels
    svg_content = re.sub(r'<svg [^>]*>', lambda m: re.sub(r'(width|height)="[^"]*mm"', r'\1="{}px"'.format(canvas_size), m.group(0)), svg_content)
    
    buffer.close()
    return svg_content

def calculate_height_symbol_layer(symbol_layer: Union[QgsRasterMarkerSymbolLayer, QgsSvgMarkerSymbolLayer]) -> float:
     """
     Calculate the height of the symbol layer.
     This is a placeholder for actual height calculation logic.
     """
     size = symbol_layer.size()  # This is the marker's base size (often height)
     if symbol_layer.preservedAspectRatio():
         aspect = symbol_layer.defaultAspectRatio()  # width / height from image
     else:
         aspect = symbol_layer.fixedAspectRatio()    # custom, if set
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
    svg_bytes = svg_content.encode('utf-8')
    return base64.b64encode(svg_bytes).decode('utf-8')

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
    with open(temp_file, 'w', encoding='utf-8') as f:
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

    # backreference are not quoted while {num} are quoted if they do not refer to a placeholder
    patterns = {
        r"[eE][vV]\(\s*(\w+)\s*\)": r"[%if(attribute('\1'), attribute('\1'), '')%]",  # non formatter group
        r"[iI][fF][nN][oO][tT][nN][uU][lL][lL]\(\s*(\w+)\s*,\s*([^)]+)\s*\)": r"[%if(attribute('\1'), attribute('\1'), '')%]",  # formatter groups
        r"[iI][fF][nN][uU][lL][lL]\(\s*(\w+)\s*,\s*([^)]+)\s*\)": r"[%if(attribute('\1'), '', attribute('\1'))%]",  # formatter groups
        r"[Ll][Ii][Nn][Ee][lL][Ee][Nn][Gg][Tt][Hh]\(\s*\)": "[%if(geometry_type(@geometry)='Line', round($length, 2), '')%]",
        r"[Pp][Oo][Ll][Yy][Gg][Oo][Nn][Aa][Rr][Ee][Aa]\(\s*\)": "[%if(geometry_type(@geometry)='Polygon', round($area, 2), '')%]",
        r"[Pp][Rr][Oo][Jj][Ee][Cc][Tt][nN][Aa][Mm][Ee]\(\s*\)": "[%@project_basename%]",
        r"[Dd][Aa][Tt][Ee]\(\s*\)": "[%format_date( now(),'ddd MMM dd yyyy')%]",
        r"[Ss][Uu][Bb][Ss][Tt][Rr][Ii][Nn][Gg]\(\s*([\w]+|\{\d+\})\s*,\s*([\w]+|\{\d+\})\s*,\s*([\w]+|\{\d+\})\s*\)": r"[%substr(if(attribute('\1'), attribute('\1'), ''), \2, \3 - \2)%]",
        r"[fF][oO][rR][mM][aA][tT]\(\s*(\w+)\s*,\s*([^)]+)\s*\)": r"[%format_date(attribute('\1'), '\2')%]",
        r"[fF][oO][rR][mM][aA][tT]\(\s*(\w+)\s*,\s*[\'\"]?((?:[#0.,]+))[\'\"]?\s*\)": r"[%format_number(attribute('\1'), '\2')%]",
        r"[cC][eE][nN][tT][rR][oO][iI][dD]\(\s*\)": r"[%concat('X: ',x(centroid(@geometry)), ' Y: ', y(centroid(@geometry)))%]",
        r"[eE][lL][eE][mM][eE][nN][tT][iI][dD]\(\s*\)": r"[%if(attribute('jmap_id'), attribute('jmap_id'), '')%]",
        r"[uU][sS][eE][rR][nN][aA][mM][eE]\(\s*\)": "[%@user_account_name%]",
    }

    # 🔹 **Build a regex that matches any function name in `patterns`**
    pattern_regex = "|".join(patterns.keys())

    def quote(group) -> str:
        if not re.search(r"\{\d+\}", group):
            group = "'{}'".format(group)
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
            # quoted_group = [quote(group) for grou`p in sub_matches.groups()]

            # replacement is quoted if specified in the pattern replacement
            formatted_group = re.sub(pattern, replacement, formatted_group)

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

    # backreference are not quoted while {num} are quoted if they do not refer to a placeholder
    patterns = {
        r"[eE][vV]\(\s*(\w+)\s*\)": r"\1",  # non formatter group
        r"[iI][fF][nN][oO][tT][nN][uU][lL][lL]\(\s*(\w+)\s*,\s*([^)]+)\s*\)": "if(attribute({0}), {1}, '')",  # formatter groups
        r"[iI][fF][nN][uU][lL][lL]\(\s*(\w+)\s*,\s*([^)]+)\s*\)": "if(attribute({0}), '', {1})",  # formatter groups
    }

    # 🔹 **Build a regex that matches any function name in `patterns`**
    pattern_regex = "|".join(patterns.keys())

    def quote(group) -> str:
        if not re.search(r"\{\d+\}", group):
            group = "'{}'".format(group)
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

def _extract_rgba(qgis_color_string):
    rgba = qgis_color_string.split(',')
    if len(rgba) >= 4:
        r, g, b, a = map(int, rgba[:4])
        return f"rgb({r},{g},{b})", str(round(a / 255.0, 2))
    return "#000000", "1"

def _replace_param(match, param_to_value):
    key = match.group(1)
    return param_to_value.get(key, f"param({key})")  # leave untouched if not found

