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

import re
from enum import Enum, auto

from qgis.core import Qgis

from JMapCloud.config import CONFIG

# config
_base_url = CONFIG["API_URL"]

# api URLs
API_AUTH_URL = f"{_base_url}/api/ss/rest/v1"
API_MCS_URL = f"{_base_url}/api/mcs/rest/v1"
API_VTCS_URL = f"{_base_url}/api/vtcs/rest/v1"
API_MIS_URL = f"{_base_url}/api/mis/wms"
API_DAS_URL = f"{_base_url}/api/das/rest/v1"
API_FUS_URL = f"{_base_url}/api/fus/rest/v1"

# auth setting id
ACCESS_TOKEN_SETTING_ID = "JMapCf1"
REFRESH_TOKEN_SETTING_ID = "JMapCf2"
EXPIRATION_SETTING_ID = "JMapCf3"
ORGANIZATION_SETTING_ID = "JMapCf4"
USERNAME_SETTING_ID = "JMapCf5"
AUTH_CONFIG_ID = "JMapACF"

# QgsSetting path
SETTINGS_PREFIX = "JMap"
ORG_NAME_SUFFIX = "Organization"
LANGUAGE_SUFFIX = "Language"
EMAIL_SUFFIX = "login_email"


# layer permission
VECTOR_LAYER_EDIT_PERMISSIONS = [
    "EXTRACT_FEATURE",
    "CREATE_FEATURE",
    "DELETE_FEATURE",
    "EDIT_FEATURE_ATTRIBUTES",
    "EDIT_FEATURE_GEOMETRY",
]


class AuthState(Enum):
    AUTHENTICATED = auto()
    NOT_AUTHENTICATED = auto()
    NO_ORGANIZATION = auto()


class ElementTypeWrapper(Enum):
    POINT = "POINT"
    LINE = "LINE"
    POLYGON = "POLYGON"
    TEXT = "TEXT"
    IMAGE = "IMAGE"

    def to_qgis_geometry_type(self) -> int:
        return {
            self.POINT: Qgis.GeometryType.Point,
            self.LINE: Qgis.GeometryType.Line,
            self.POLYGON: Qgis.GeometryType.Polygon,
            self.TEXT: Qgis.GeometryType.Point,
            self.IMAGE: Qgis.GeometryType.Unknown,
        }[self]


class JMCOperator(Enum):
    """
    Class to translate QGIS expression operators to JMap cloud operators
    """

    GREATER_OR_EQUALS_TO = auto()
    LOWER_OR_EQUALS_TO = auto()
    GREATER_THAN = auto()
    LOWER_THAN = auto()
    IS_NOT_NULL = auto()
    IS_NULL = auto()
    EQUALS = auto()
    NOT_EQUALS = auto()

    @classmethod
    def operator_translate(cls) -> dict[str, str]:
        return {
            r">=": cls.GREATER_OR_EQUALS_TO.name,
            r"<=": cls.LOWER_OR_EQUALS_TO.name,
            r">": cls.GREATER_THAN.name,
            r"<": cls.LOWER_THAN.name,
            r"!=\s*(?:[nN][uU][lL][lL]|[nN][oO][nN][eE])|[iI][sS]\s+[nN][oO][tT]\s+(?:[nN][uU][lL][lL]|[nN][oO][nN][eE])": cls.IS_NOT_NULL.name,
            r"=\s*(?:[nN][uU][lL][lL]|[nN][oO][nN][eE])|[iI][sS]\s+(?:[nN][uU][lL][lL]|[nN][oO][nN][eE])": cls.IS_NULL.name,
            r"!=|[iI][sS]\s+[nN][oO][tT]": cls.NOT_EQUALS.name,
            r"=|[iI][sS]": cls.EQUALS.name,
        }

    @classmethod
    def translate(cls, operator: str) -> str:

        for pattern, replacement in cls.operator_translate().items():
            if re.match(pattern, operator):
                return replacement
        return None

    @classmethod
    def reverse(cls, operator: str) -> str:
        if operator == cls.GREATER_OR_EQUALS_TO.name:
            return cls.LOWER_OR_EQUALS_TO.name
        elif operator == cls.LOWER_OR_EQUALS_TO.name:
            return cls.GREATER_OR_EQUALS_TO.name
        elif operator == cls.GREATER_THAN.name:
            return cls.LOWER_THAN.name
        elif operator == cls.LOWER_THAN.name:
            return cls.GREATER_THAN.name

    @classmethod
    def inverse(cls, operator: str) -> str:
        if operator == cls.GREATER_OR_EQUALS_TO.name:
            return cls.LOWER_THAN.name
        elif operator == cls.LOWER_OR_EQUALS_TO.name:
            return cls.GREATER_THAN.name
        elif operator == cls.GREATER_THAN.name:
            return cls.LOWER_OR_EQUALS_TO.name
        elif operator == cls.LOWER_THAN.name:
            return cls.GREATER_OR_EQUALS_TO.name
        elif operator == cls.IS_NOT_NULL.name:
            return cls.IS_NULL.name
        elif operator == cls.IS_NULL.name:
            return cls.IS_NOT_NULL.name
        elif operator == cls.NOT_EQUALS.name:
            return cls.EQUALS.name
        elif operator == cls.EQUALS.name:
            return cls.NOT_EQUALS.name
        else:
            return None
