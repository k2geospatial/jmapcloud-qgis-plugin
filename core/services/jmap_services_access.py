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

import re
import urllib.parse

from qgis.PyQt.QtCore import pyqtSignal

from ..constant import (
    API_DAS_URL,
    API_MCS_URL,
    API_MIS_URL,
    AUTH_CONFIG_ID,
)
from ..DTOS.project_dto import ProjectDTO
from .request_manager import RequestManager
from .session_manager import SessionManager


class JMapMCS:
    """Class to handle JMap MCS api end point requests"""

    @staticmethod
    def get_projects_async() -> pyqtSignal:
        organization_id = SessionManager().get_organization_id()
        if organization_id is None:
            return None
        url = f"{API_MCS_URL}/organizations/{organization_id}/projects"
        request = RequestManager.RequestData(url, type="GET")

        return RequestManager.instance().add_requests(request)

    @staticmethod
    def get_wms_layer_uri(source: str) -> dict:
        """
        Get all uri of selected WMS sub-layers from a spatial data source

        :param spatialDataSourceId: id of the spatial data source
        :param layers: list of sub-layers with their names as value
        :return: a dictionary with the layer names as key and their uri as value
        """
        match = re.search(r"(https?:\/\/.+\..+\?)", source)
        if match:
            url = match.group(0)
            url = "{}SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities&SERVICE=WMS&REQUEST=GetCapabilities".format(url)
        else:
            return None
        match2 = re.search(r"&?LAYERS=(\w+(,\w+)*)&?", source)
        if match2:
            layers = match2.group(1).split(",")
        else:
            return None

        safe_string = urllib.parse.quote_plus(url)
        layer_uris = {}
        for layer in layers:
            layer_uris[layer] = "format=image/png&layers={}&styles&url={}".format(layer, safe_string)
        return layer_uris

    def get_wmts_layer_uri(url: str, minZoom: int = 0, maxZoom: int = 21) -> str:
        return "http-header:referer=&type=xyz&url={}&zmax={}&zmin={}".format(url, maxZoom, minZoom)

    @staticmethod
    def get_project_sprites(url: str) -> tuple[dict, bytes]:
        organization_id = SessionManager().get_organization_id()
        if organization_id is None:
            return None
        json_url = "{}.json".format(url)
        png_url = "{}.png".format(url)
        prefix = "Error loading sprites"
        json_sprites = RequestManager.get_request(json_url, error_prefix=prefix).content
        if not bool(json_sprites):
            return None, None
        png_sprites = RequestManager.get_request(png_url, error_prefix=prefix).content
        return json_sprites, png_sprites

    @staticmethod
    def post_project(organization_id: str, project_data: ProjectDTO) -> RequestManager.ResponseData:

        url = "{}/organizations/{}/projects".format(API_MCS_URL, organization_id)
        prefix = "error creating project"
        body = project_data.to_json()
        return RequestManager.post_request(url, body, error_prefix=prefix)


class JMapMIS:

    @staticmethod
    def get_raster_layer_uri(layer_id, organization_id) -> str:
        organization_id = SessionManager().get_organization_id()
        if organization_id is None:
            return None

        safe_string = urllib.parse.quote_plus("organizationId={}&VERSION=1.3.0".format(organization_id))
        uri = (
            "authcfg={}".format(AUTH_CONFIG_ID)
            + "&crs=EPSG:3857"
            + "&dpiMode=0"
            + "&format=image/png"
            + "&layers={}".format(layer_id)
            + "&styles"
            + "&tilePixelRatio=0"
            + "&url={}?{}".format(API_MIS_URL, safe_string)
            + "&request=GetMap"
        )
        return uri


class JMapDAS:

    @staticmethod
    def get_vector_layer_uri(layer_id, organization_id) -> str:
        organization_id = SessionManager().get_organization_id()
        if organization_id is None:
            return None
        uri = (
            "authcfg={} ".format(AUTH_CONFIG_ID)
            + "pagingEnabled='true' "
            + "preferCoordinatesForWfsT11='false' "
            + "typename='{}' ".format(layer_id)
            + "url='{}/organizations/{}'".format(API_DAS_URL, organization_id)
        )
        return uri

    def get_vector_tile_uri(spatial_datasource_id: str, organization_id: str) -> str:
        organization_id = SessionManager().get_organization_id()
        if organization_id is None:
            return None
        uri = (
            "type=xyz"
            + "&url={}/organizations/{}/mvt/datasources/{}".format(API_DAS_URL, organization_id, spatial_datasource_id)
            + "/{x}/{y}/{z}"
            + "&zmax=23"
            + "&zmin=0"
            + "&authcfg={}".format(AUTH_CONFIG_ID)
        )
        return uri
