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
from qgis.PyQt.QtNetwork import QNetworkReply

from JMapCloud.core.constant import (
    API_DAS_URL,
    API_MCS_URL,
    API_MIS_URL,
    API_VTCS_URL,
    AUTH_CONFIG_ID,
)
from JMapCloud.core.DTOS.project_dto import ProjectDTO
from JMapCloud.core.services.request_manager import RequestManager
from JMapCloud.core.signal_object import TemporarySignalObject


class JMapMCS:
    """Class to handle JMap MCS api end point requests"""

    @staticmethod
    def get_projects(organization_id) -> dict:
        url = f"{API_MCS_URL}/organizations/{organization_id}/projects"
        prefix = "Error getting projects"

        return RequestManager.get_request(url, error_prefix=prefix).content

    @staticmethod
    def get_projects_async(organization_id) -> pyqtSignal:
        url = f"{API_MCS_URL}/organizations/{organization_id}/projects"
        request = RequestManager.RequestData(url, type="GET")

        return RequestManager.instance().add_requests(request)

    @staticmethod
    def get_project_layers_data(project_id, organization_id) -> dict:
        url = f"{API_MCS_URL}/organizations/{organization_id}/projects/{project_id}/layers"
        prefix = "Error getting projects"

        return RequestManager.get_request(url, error_prefix=prefix).content

    @staticmethod
    def get_project_layer_order(project_id, organization_id) -> dict:
        url = f"{API_MCS_URL}/organizations/{organization_id}/projects/{project_id}/layers-order"
        prefix = "Error loading layers order"
        return RequestManager.get_request(url, error_prefix=prefix).content

    @staticmethod
    def get_project_layer_groups(project_id, organization_id) -> dict:
        url = f"{API_MCS_URL}/organizations/{organization_id}/projects/{project_id}/layers-groups"
        prefix = "Error loading layers groups"
        return RequestManager.get_request(url, error_prefix=prefix).content

    @staticmethod
    def get_project_mapbox_style(project_id, organization_id) -> dict:

        url = f"{API_MCS_URL}/organizations/{organization_id}/projects/{project_id}/mapbox-styles"
        prefix = "Error loading style"
        return RequestManager.get_request(url, error_prefix=prefix).content

    @staticmethod
    def get_project_permissions_self(project_id: str, organization_id: str) -> dict:
        url = f"{API_MCS_URL}/organizations/{organization_id}/projects/{project_id}/permissions/self"
        prefix = "Error loading project permissions"
        return RequestManager.get_request(url, error_prefix=prefix).content

    @staticmethod
    def get_layer_style_rules(project_id, layer_id, organization_id) -> dict:

        url = f"{API_MCS_URL}/organizations/{organization_id}/projects/{project_id}/layers/{layer_id}/style-rules"
        prefix = "Error loading style"
        return RequestManager.get_request(url, error_prefix=prefix).content

    @staticmethod
    def get_organization_style(style_id, organization_id) -> dict:

        url = f"{API_MCS_URL}/organizations/{organization_id}/styles/{style_id}"
        prefix = "Error loading layers"
        return RequestManager.get_request(url, error_prefix=prefix).content

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
            url = f"{url}SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities&SERVICE=WMS&REQUEST=GetCapabilities"
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
            layer_uris[layer] = f"format=image/png&layers={layer}&styles&url={safe_string}"
        return layer_uris

    def get_project_graphql_style_data(project_id: str, language: str, organization_id):
        query = (
            """{
            getStyleRules(organizationId: """
            f'"{organization_id}"'
            """,projectId: """
            f'"{project_id}"'
            """, locale: """
            f'"{language}"'
            """){
                id
                layerId
                name
                conditions{
                    id
                    name
                    styleMapScales{
                        id
                        styleId
                    }
                }
            }
        }"""
        )
        variables = {}
        url = "https://api.qa.jmapcloud.io/api/mcs/graphql"
        body = {"query": query, "variables": variables}
        headers = {
            "Organizationid": f"{organization_id}",
        }
        prefix = "GraphQL error"
        return RequestManager.post_request(url, body, headers, error_prefix=prefix).content

    @staticmethod
    def get_project_sprites(url: str) -> tuple[dict, bytes]:
        json_url = f"{url}.json"
        png_url = f"{url}.png"
        prefix = "Error loading sprites"
        json_sprites = RequestManager.get_request(json_url, error_prefix=prefix).content
        if not bool(json_sprites):
            return None, None
        png_sprites = RequestManager.get_request(png_url, error_prefix=prefix).content
        return json_sprites, png_sprites

    @staticmethod
    def post_project(organization_id: str, project_data: ProjectDTO) -> RequestManager.ResponseData:
        url = f"{API_MCS_URL}/organizations/{organization_id}/projects"
        prefix = "error creating project"
        body = project_data.to_json()
        return RequestManager.post_request(url, body, error_prefix=prefix)


class JMapMIS:

    @staticmethod
    def get_raster_layer_uri(layer_id, organization_id) -> str:

        safe_string = urllib.parse.quote_plus(f"organizationId={organization_id}&VERSION=1.3.0")
        uri = (
            f"authcfg={AUTH_CONFIG_ID}"
            "&crs=EPSG:3857"
            "&dpiMode=0"
            "&format=image/png"
            f"&layers={layer_id}"
            "&styles"
            "&tilePixelRatio=0"
            f"&url={API_MIS_URL}?{safe_string}"
            "&request=GetMap"
        )
        return uri


class JMapVTCS:

    @staticmethod
    def get_projects_vector_tile_uri(project_id: str, organization_id: str) -> str:
        uri = (
            f"type=xyz&url={API_VTCS_URL}/organizations/{organization_id}/projects/{project_id}/mvt"
            + "/{x}/{y}/{z}"
            + f"&zmax=14&zmin=0&authcfg={AUTH_CONFIG_ID}"
        )
        return uri


class JMapDAS:

    @staticmethod
    def get_vector_layer_uri(layer_id, org_id) -> str:
        uri = (
            f"authcfg={AUTH_CONFIG_ID} "
            "pagingEnabled='true' "
            "preferCoordinatesForWfsT11='false' "
            f"typename='{layer_id}' "
            f"url='{API_DAS_URL}/organizations/{org_id}'"
        )
        return uri

    def get_vector_tile_uri(spatial_datasource_id: str, organization_id: str) -> str:
        uri = (
            "type=xyz"
            f"&url={API_DAS_URL}/organizations/{organization_id}/mvt/datasources/{spatial_datasource_id}"
            "/{x}/{y}/{z}"
            f"&zmax=23"
            "&zmin=0"
            f"&authcfg={AUTH_CONFIG_ID}"
        )
        return uri
