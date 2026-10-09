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

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal
from qgis.utils import iface

from ...core.services.auth_manager import JMapAuth
from .connection_dialog_base_ui import Ui_Dialog


class ConnectionDialog(QtWidgets.QDialog, Ui_Dialog):
    logout_signal = pyqtSignal()
    logged_in_signal = pyqtSignal()

    def __init__(self, auth_manager: JMapAuth):
        """Constructor."""
        super(ConnectionDialog, self).__init__(iface.mainWindow())
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.auth_manager = auth_manager
        self.connection_button.clicked.connect(self.toggle_connection)

    def refresh(self):
        if self.auth_manager.is_logged_in():
            self.connection_button.setText(self.tr("logout"))
            self.message_label.setStyleSheet("font-size: 18px;")
            welcome_message = self.tr("Welcome {}<br />{}").format(
                self.auth_manager.get_username(), self.auth_manager.get_email()
            )
            organization_name = self.auth_manager.get_organization_name()
            if organization_name:
                welcome_message += self.tr("<br />Organisation: {}").format(organization_name)
            self.message_label.setText(welcome_message)
        else:
            self.connection_button.setText(self.tr("login"))
            self.message_label.setStyleSheet("")
            self.message_label.setText(self.tr("A browser window will open to sign in"))

    def toggle_connection(self):
        if self.auth_manager.is_login_in_progress():
            self.auth_manager.cancel_login()
        elif self.auth_manager.is_logged_in():
            self.logout()
        else:
            self.login()

    def login(self):
        self.connection_button.setText(self.tr("cancel"))
        self.message_label.setStyleSheet("")
        self.message_label.setText(self.tr("Complete the sign in from your browser"))
        if self.auth_manager.login():
            self.refresh()
            self.logged_in_signal.emit()
        else:
            self.refresh()
            self.message_label.setStyleSheet("color: red;")
            self.message_label.setText(self.tr("Sign in cancelled or failed"))

    def logout(self):
        self.logout_signal.emit()
        self.refresh()

    def reject(self):
        if self.auth_manager.is_login_in_progress():
            self.auth_manager.cancel_login()
        super().reject()
