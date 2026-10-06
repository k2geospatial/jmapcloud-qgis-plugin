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

from urllib.parse import urlencode

from qgis.core import QgsMessageLog, QgsNetworkAccessManager, QgsSettings
from qgis.PyQt.QtCore import QObject, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtNetwork import QNetworkReply

from ..constant import (
    API_AUTH_URL,
    AUTH0_CLIENT_ID,
    AUTH0_LOGOUT_URL,
    ORG_NAME_SUFFIX,
    SETTINGS_PREFIX,
)
from ..qgs_message_bar_handler import Qgis, QgsMessageBarHandler
from .request_manager import RequestManager
from .session_manager import SessionManager

MESSAGE_CATEGORY = "JMapAuth"


class JMapAuth(QObject):
    logged_out_signal = pyqtSignal()

    def __init__(self, session_manager: SessionManager, request_manager: RequestManager):
        super().__init__()
        self._session_manager = session_manager
        self._request_manager = request_manager
        self._login_in_progress = False

    def is_logged_in(self) -> bool:
        return self._session_manager.has_session() and not self._login_in_progress

    def is_login_in_progress(self) -> bool:
        return self._login_in_progress

    def login(self) -> bool:
        """
        Open the Auth0 login page in the browser to authenticate the user in a JMap organization.

        :return: True if the user is authenticated in an organization, False otherwise
        """
        self._login_in_progress = True
        try:
            self._session_manager.create_session()
            organization_id = self._session_manager.get_organization_id()
        except Exception as e:
            QgsMessageLog.logMessage(str(e), MESSAGE_CATEGORY, Qgis.MessageLevel.Critical)
            organization_id = None
        finally:
            self._login_in_progress = False
        if organization_id is None:
            self._session_manager.revoke_session()
            return False

        user = self.get_user_self()
        organizations = user["organizations"] if user else []
        organization_name = next(
            (org["name"] for org in organizations if org["id"] == organization_id), ""
        )
        QgsSettings().setValue(f"{SETTINGS_PREFIX}/{ORG_NAME_SUFFIX}", organization_name)
        return True

    def cancel_login(self) -> None:
        QgsNetworkAccessManager.instance().abortAuthBrowser()

    def get_user_self(self) -> dict:
        """
        Get the authenticated user.

        :return:
            A dictionary with the user information and all his organizations
            if the request is successful, otherwise None
        """
        url = f"{API_AUTH_URL}/users/self"
        prefix = "Authentication Error"
        response = self._request_manager.get_request(url, error_prefix=prefix)

        if response.status == QNetworkReply.NetworkError.NoError:
            return response.content
        else:
            return None

    def get_username(self) -> str:
        return self._session_manager.get_username()

    def get_email(self) -> str:
        return self._session_manager.get_email()

    def get_organization_name(self) -> str:
        return QgsSettings().value(f"{SETTINGS_PREFIX}/{ORG_NAME_SUFFIX}", "")

    def get_roles(self) -> list[str]:
        return self._session_manager.get_roles()

    def logout(self, error_message: str = None, end_auth0_session: bool = False) -> None:
        """
        Remove the JMap Cloud OAuth2 config from QGIS auth manager.

        :param error_message:
            An optional error message to display in the QGIS message bar
        :param end_auth0_session:
            Open the Auth0 logout page in the browser to end the Auth0 session
        """
        if error_message:
            QgsMessageBarHandler.send_message_to_message_bar(
                error_message, level=Qgis.MessageLevel.Warning
            )

        if self._session_manager.has_session():
            self._session_manager.revoke_session()
        if end_auth0_session:
            QDesktopServices.openUrl(
                QUrl(f"{AUTH0_LOGOUT_URL}?{urlencode({'client_id': AUTH0_CLIENT_ID})}")
            )
        QgsSettings().setValue(f"{SETTINGS_PREFIX}/{ORG_NAME_SUFFIX}", "")
        self.logged_out_signal.emit()
