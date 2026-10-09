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

import base64
import json
from pathlib import Path

from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt.QtNetwork import QNetworkRequest

from ..constant import (
    AUTH0_AUDIENCE,
    AUTH0_AUTHORIZE_URL,
    AUTH0_CLIENT_ID,
    AUTH0_DOMAIN,
    AUTH0_REDIRECT_PORT,
    AUTH0_SCOPE,
    AUTH0_TOKEN_URL,
    AUTH_CONFIG_ID,
    EMAIL_CLAIM,
    LEGACY_AUTH_CONFIG_ID,
    LEGACY_AUTH_SETTING_IDS,
    NAME_CLAIM,
    OAUTH2_ACCESS_METHOD_HEADER,
    OAUTH2_CONFIG_TYPE_CUSTOM,
    OAUTH2_GRANT_FLOW_PKCE,
    ORGANIZATION_CLAIM,
    ROLES_CLAIM,
)


class SessionManager:
    def __init__(self):
        self._claims = None
        self._remove_legacy_session()

    def has_session(self) -> bool:
        return AUTH_CONFIG_ID in QgsApplication.authManager().configIds()

    def create_session(self) -> None:
        """
        Store the JMap Cloud OAuth2 config in QgsApplication.authManager()
        :return: None
        """
        oauth2_config = {
            "version": 1,
            "configType": OAUTH2_CONFIG_TYPE_CUSTOM,
            "grantFlow": OAUTH2_GRANT_FLOW_PKCE,
            "requestUrl": AUTH0_AUTHORIZE_URL,
            "tokenUrl": AUTH0_TOKEN_URL,
            "refreshTokenUrl": AUTH0_TOKEN_URL,
            "redirectHost": "127.0.0.1",
            "redirectPort": AUTH0_REDIRECT_PORT,
            "redirectUrl": "",
            "clientId": AUTH0_CLIENT_ID,
            "scope": AUTH0_SCOPE,
            "persistToken": True,
            "accessMethod": OAUTH2_ACCESS_METHOD_HEADER,
            "queryPairs": {"audience": AUTH0_AUDIENCE, "prompt": "login"},
        }
        auth_config = QgsAuthMethodConfig("OAuth2")
        auth_config.setId(AUTH_CONFIG_ID)
        auth_config.setName(f"JMap Cloud ({AUTH0_DOMAIN})")
        auth_config.setConfig("oauth2config", json.dumps(oauth2_config))
        QgsApplication.authManager().storeAuthenticationConfig(auth_config, True)
        self._claims = None

    def get_access_token(self) -> str:
        """
        Get the access token of the JMap Cloud OAuth2 config
        :return: The access token, or None if the user is not authenticated
        """
        if not self.has_session():
            return None
        updated, request = QgsApplication.authManager().updateNetworkRequest(
            QNetworkRequest(), AUTH_CONFIG_ID
        )
        if not updated:
            return None
        header = bytes(request.rawHeader(b"Authorization")).decode()
        return header.removeprefix("Bearer ") or None

    def get_organization_id(self) -> str:
        return self._get_claims().get(ORGANIZATION_CLAIM)

    def get_username(self) -> str:
        return self._get_claims().get(NAME_CLAIM)

    def get_email(self) -> str:
        return self._get_claims().get(EMAIL_CLAIM)

    def get_roles(self) -> list[str]:
        return self._get_claims().get(ROLES_CLAIM, [])

    def revoke_session(self) -> None:
        auth_manager = QgsApplication.authManager()
        auth_manager.clearCachedConfig(AUTH_CONFIG_ID)
        auth_manager.removeAuthenticationConfig(AUTH_CONFIG_ID)
        token_cache = Path(
            QgsApplication.qgisSettingsDirPath(), "oauth2-cache", f"authcfg-{AUTH_CONFIG_ID}.ini"
        )
        token_cache.unlink(missing_ok=True)
        self._claims = None

    def _get_claims(self) -> dict:
        if self._claims is None:
            access_token = self.get_access_token()
            if not access_token:
                return {}
            self._claims = self._decode_claims(access_token)
        return self._claims

    @staticmethod
    def _decode_claims(access_token: str) -> dict:
        payload = access_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))

    @staticmethod
    def _remove_legacy_session() -> None:
        auth_manager = QgsApplication.authManager()
        if LEGACY_AUTH_CONFIG_ID in auth_manager.configIds():
            auth_manager.removeAuthenticationConfig(LEGACY_AUTH_CONFIG_ID)
            for setting_id in LEGACY_AUTH_SETTING_IDS:
                auth_manager.removeAuthSetting(setting_id)
