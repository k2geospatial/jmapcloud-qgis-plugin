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
from enum import Enum

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsLayerTree,
    QgsMapLayer,
    QgsProject,
    QgsReferencedRectangle,
)

from .plugin_util import convert_crs_to_epsg


class SupportedFileType(Enum):
    SHP = "SHP"
    GeoJSON = "GEOJSON"
    CSV = "CSV"
    GML = "GML"
    FileGeoDatabase = "FILE_GEO_DATABASE"
    GeoPackage = "GEO_PACKAGE"
    CAD = "CAD"
    DXF = "DXF"
    KML = "KML"
    MapInfo = "MAP_INFO"
    raster = "RASTER"
    zip = "ZIP"


class LayerFile:

    class Status(Enum):
        no_error = "NO_ERROR"
        uploading_error = "UPLOADING_ERROR"

    def __init__(
        self,
        jmc_file_id: str = None,
        file_name: str = None,
        file_path: str = None,
        file_type: SupportedFileType = None,
        fields: dict = None,
    ):
        self.jmc_file_id = jmc_file_id
        self.file_name = file_name
        self.file_path = file_path
        self.upload_status = self.Status.no_error
        self.file_type = file_type
        self.fields = fields or {}


class LayerData:
    """
    data class for layer reference file
    layer_id and file name are the same
    """

    class Status(Enum):
        no_error = "NO_ERROR"
        file_creation_error = "FILE_CREATING_ERROR"
        file_compressing_error = "FILE_COMPRESSING_ERROR"
        datasource_error = "CREATING_ERROR"
        file_analyzing_error = "FILE_ANALYZING_ERROR"
        creating_datasource_error = "CREATING_DATASOURCE_ERROR"
        datasource_analyzing_error = "DATASOURCE_ANALYZING_ERROR"
        layer_creation_error = "LAYER_CREATING_ERROR"
        unknown_error = "UNKNOWN_ERROR"
        timeout = "TIMEOUT"

    class LayerType(Enum):
        file_vector = "FILE_VECTOR"
        file_raster = "FILE_RASTER"
        API_FEATURES = "OGC_API_FEATURES"
        WMS_WMTS = "WMS_WMTS"

    class ElementType(Enum):
        POINT = "POINT"
        LINE = "LINE"
        POLYGON = "POLYGON"

    longitude: str = None
    latitude: str = None

    def __init__(
        self,
        datasource: str = None,
        datasource_creation_status: str = None,
        datasource_id: str = None,
        layer_file: LayerFile = None,
        file_type: SupportedFileType = None,
        layer: QgsMapLayer = None,
        layer_id: str = None,
        layer_name: str = None,
        layer_type: LayerType = None,
        element_type: str = None,
        datasource_layer: str = None,
        format: str = None,
        jmc_layer_id: str = None,
        uri_components: dict = None,
    ):
        self.datasource = datasource
        self.datasource_creation_status = datasource_creation_status
        self.datasource_id = datasource_id
        self.layer_file = layer_file
        self.file_type = file_type
        self.layer = layer
        self.layer_id = layer_id
        self.layer_name = layer_name
        self.layer_type = layer_type
        self.status = self.Status.no_error
        self.element_type = element_type
        self.datasource_layer = datasource_layer
        self.format = format
        self.jmc_layer_id = jmc_layer_id
        self.uri_components = uri_components


class ProjectData:
    project_id: str
    organization_id: str
    name: str
    description: str
    default_language: str
    layers: list[QgsMapLayer]

    def __init__(
        self,
        project_id: str = None,
        organization_id: str = None,
        name: str = None,
        description: str = None,
        crs: QgsCoordinateReferenceSystem = None,
        initial_extent: QgsReferencedRectangle = None,
        default_language: str = None,
        layers: list[QgsMapLayer] = None,
        legendRoot: QgsLayerTree = None,
    ):
        self.project_id = project_id
        self.organization_id = organization_id
        self.name = name
        self.description = description
        self.crs = crs
        self.initial_extent = initial_extent
        self.default_language = default_language
        self.layers = layers
        self.legendRoot = legendRoot

    def setup_with_QGIS_project(self, project: QgsProject):
        self.crs = convert_crs_to_epsg(project.crs())
        self.initial_extent = QgsReferencedRectangle(project.fullExtent(), self.crs)
        self.layers = project.layerTreeRoot().customLayerOrder()
        self.legendRoot = project.layerTreeRoot()


class ProjectLayersData:
    layer_groups: list[dict]
    layer_order: list[dict]
    layers_data: dict
    layers_properties: dict

    def __init__(
        self,
        layer_groups: list[dict] = None,
        layer_order: list[dict] = None,
        layers_data: dict = None,
        layers_properties: dict = None,
    ):
        self.layer_groups = layer_groups
        self.layer_order = layer_order
        self.Labels_config = layers_data
        self.formatted_styles = layers_properties