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

# QSetting path
SETTINGS_PREFIX = "JMap"
LANGUAGE_SUFFIX = "Language"


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

    @staticmethod
    def operator_translate() -> dict[str, str]:
        return {
            ">=": JMCOperator.GREATER_OR_EQUALS_TO.name,
            "<=": JMCOperator.LOWER_OR_EQUALS_TO.name,
            ">": JMCOperator.GREATER_THAN.name,
            "<": JMCOperator.LOWER_THAN.name,
            "!=\s*(?:[nN][uU][lL][lL]|[nN][oO][nN][eE])|[iI][sS]\s+[nN][oO][tT]\s+(?:[nN][uU][lL][lL]|[nN][oO][nN][eE])": JMCOperator.IS_NOT_NULL.name,
            "=\s*(?:[nN][uU][lL][lL]|[nN][oO][nN][eE])|[iI][sS]\s+(?:[nN][uU][lL][lL]|[nN][oO][nN][eE])": JMCOperator.IS_NULL.name,
            "!=|[iI][sS]\s+[nN][oO][tT]": JMCOperator.NOT_EQUALS.name,
            "=|[iI][sS]": JMCOperator.EQUALS.name,
        }

    @staticmethod
    def translate(operator: str) -> str:

        for pattern, replacement in JMCOperator.operator_translate().items():
            if re.match(pattern, operator):
                return replacement
        return None

    @staticmethod
    def reverse(operator: str) -> str:
        if operator == JMCOperator.GREATER_OR_EQUALS_TO.name:
            return JMCOperator.LOWER_OR_EQUALS_TO.name
        elif operator == JMCOperator.LOWER_OR_EQUALS_TO.name:
            return JMCOperator.GREATER_OR_EQUALS_TO.name
        elif operator == JMCOperator.GREATER_THAN.name:
            return JMCOperator.LOWER_THAN.name
        elif operator == JMCOperator.LOWER_THAN.name:
            return JMCOperator.GREATER_THAN.name

    @staticmethod
    def inverse(operator: str) -> str:
        if operator == JMCOperator.GREATER_OR_EQUALS_TO.name:
            return JMCOperator.LOWER_THAN.name
        elif operator == JMCOperator.LOWER_OR_EQUALS_TO.name:
            return JMCOperator.GREATER_THAN.name
        elif operator == JMCOperator.GREATER_THAN.name:
            return JMCOperator.LOWER_OR_EQUALS_TO.name
        elif operator == JMCOperator.LOWER_THAN.name:
            return JMCOperator.GREATER_OR_EQUALS_TO.name
        elif operator == JMCOperator.IS_NOT_NULL.name:
            return JMCOperator.IS_NULL.name
        elif operator == JMCOperator.IS_NULL.name:
            return JMCOperator.IS_NOT_NULL.name
        elif operator == JMCOperator.NOT_EQUALS.name:
            return JMCOperator.EQUALS.name
        elif operator == JMCOperator.EQUALS.name:
            return JMCOperator.NOT_EQUALS.name
        else:
            return None
