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

from qgis.core import QgsSettings
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal
from qgis.utils import iface

from JMapCloud.core.constant import SETTINGS_PREFIX, AuthState
from JMapCloud.core.services.auth_manager import JMapAuth

from .connection_dialog_base_ui import Ui_Dialog

EMAIL_SUFFIX = "login_email"


class ConnectionDialog(QtWidgets.QDialog, Ui_Dialog):
    logout_signal = pyqtSignal()
    logged_in_signal = pyqtSignal()

    def __init__(self):
        """Constructor."""
        super(ConnectionDialog, self).__init__(iface.mainWindow())
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.auth_manager = JMapAuth()
        auth_state = self.auth_manager.get_auth_state()
        if auth_state == AuthState.AUTHENTICATED:
            self.connection_button.setText("logout")
            self.connection_button.clicked.connect(self.logout)
            self.set_choose_organization_layout_enable(True)
            self.set_login_input_enable(False)
        elif auth_state == AuthState.NO_ORGANIZATION:
            self.connection_button.setText("login")
            self.connection_button.clicked.connect(self.login)
            self.set_login_input_enable(True)
            self.set_choose_organization_layout_enable(True)
        else:
            self.message_label.setStyleSheet("")
            self.connection_button.setText("login")
            self.connection_button.clicked.connect(self.login)
            self.message_label.setText("")
            self.set_login_input_enable(True)
            self.set_choose_organization_layout_enable(False)
        self.email_input.setText(QgsSettings().value(f"{SETTINGS_PREFIX}/{EMAIL_SUFFIX}", ""))
        self.show_password_checkBox.stateChanged.connect(self.set_echo_mode)
        self.accept_button.clicked.connect(self.choose_organization)

    def login(self):
        self.connection_button.setEnabled(False)
        access_token_config = self.auth_manager.get_access_token(self.email_input.text(), self.password_input.text())
        if access_token_config != None:
            self.message_label.setText("")
            self.list_organizations()
            self.password_input.clear()
            QgsSettings().setValue(f"{SETTINGS_PREFIX}/{EMAIL_SUFFIX}", self.email_input.text())
        else:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText("wrong email or password")
        self.connection_button.setEnabled(True)

    def logout(self):
        self.logout_signal.emit()
        self.connection_button.clicked.disconnect()
        self.connection_button.setText("login")
        self.connection_button.clicked.connect(self.login)
        self.organization_list_comboBox.clear()
        self.message_label.setText("")
        self.set_login_input_enable(True)
        self.set_choose_organization_layout_enable(False)

    def list_organizations(self):
        result = self.auth_manager.get_user_self()
        if result != None:
            self.message_label.setStyleSheet("font-size: 20px;")
            self.message_label.setText(f"Welcome {result['name']}")
            organizations = result["organizations"]
            # to modify ui for ask for organization
            if len(organizations) > 0:
                self.set_choose_organization_layout_enable(True)
                self.organization_list_comboBox.clear()
                sorted_organizations = sorted(organizations, key=lambda k: k["name"])
                for organization in sorted_organizations:
                    self.organization_list_comboBox.addItem(organization["name"], organization["id"])
            else:
                self.message_label.setStyleSheet("color: red;")
                self.message_label.setText("no organization found")
        else:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText("Authentication expired")
            self.logout()

    def choose_organization(self):
        self.accept_button.setEnabled(False)
        organization_id = self.organization_list_comboBox.currentData()
        auth_state = self.auth_manager.get_auth_state()
        if auth_state != AuthState.NOT_AUTHENTICATED and self.auth_manager.refresh_auth_settings(
            org_id=organization_id
        ):
            self.password_input.clear()
            self.set_login_input_enable(False)
            self.accept_button.setEnabled(True)
            self.connection_button.clicked.disconnect()
            self.connection_button.setText("logout")
            self.connection_button.clicked.connect(self.logout)
            self.logged_in_signal.emit()
        else:
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText("Authentication error")
            self.accept_button.setEnabled(True)

    def set_choose_organization_layout_enable(self, enable: bool):

        self.accept_button.setEnabled(enable)
        self.choose_organization_label.setEnabled(enable)
        self.organization_list_comboBox.setEnabled(enable)

    def set_login_input_enable(self, enable: bool):
        self.email_label.setEnabled(enable)
        self.email_input.setEnabled(enable)
        self.password_label.setEnabled(enable)
        self.password_input.setEnabled(enable)

    def set_echo_mode(self):
        if self.show_password_checkBox.isChecked():
            self.password_input.setEchoMode(QtWidgets.QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
