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
from pathlib import Path

from qgis.core import QgsCoordinateReferenceSystem, QgsProject, QgsReferencedRectangle, QgsRectangle
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QCoreApplication, QSettings, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu

# from JMapCloud import resources_rc
from .core.constant import LANGUAGE_SUFFIX, SETTINGS_PREFIX, AuthState
from .core.services.auth_manager import JMapAuth
from .core.services.export_project_manager import ExportProjectManager
from .core.services.import_project_manager import ImportProjectManager
from .core.services.request_manager import RequestManager
from .core.services.session_manager import SessionManager
from .core.services.style_manager import StyleManager
from .core.services.jmap_services_access import JMapDAS, JMapMCS, JMapMIS
from .core.views import ProjectData
from .ui.py_files.action_dialog import ActionDialog
from .ui.py_files.connection_dialog import ConnectionDialog
from .ui.py_files.export_project_dialog import ExportProjectDialog
from .ui.py_files.open_project_dialog import OpenProjectDialog


class JMapCloud:
    def __init__(self, iface: QgisInterface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = Path(__file__).parent

        # initialize locale
        locale = QSettings().value("locale/userLocale", "en")
        self.language = locale[0:2]
        QSettings().setValue("{}/{}".format(SETTINGS_PREFIX, LANGUAGE_SUFFIX), self.language)
        locale_path = Path(self.plugin_dir, "i18n", "jmap_cloud_{}.qm".format(self.language))
        if Path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(str(locale_path))
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []


        # initialize services and managers
        self.session_manager = SessionManager()
        self.request_manager = RequestManager(self.session_manager)

        self.jmap_mcs = JMapMCS(self.request_manager, self.session_manager)
        self.jmap_das = JMapDAS()
        self.jmap_mis = JMapMIS()

        self.style_manager = StyleManager(self.jmap_mcs)
        self.auth_manager = JMapAuth(self.session_manager, self.request_manager)
        self.export_project_manager = ExportProjectManager(self.request_manager, self.jmap_mcs)
        self.import_project_manager = ImportProjectManager(
            self.style_manager, self.request_manager, self.jmap_mcs, self.jmap_das, self.jmap_mis
        )

        # # initialize ui
        self.connection_dialog = ConnectionDialog(self.auth_manager)
        self.connection_dialog.logged_in_signal.connect(self.logged_in)
        self.connection_dialog.logout_signal.connect(self.auth_manager.logout)
        self.load_project_dialog = OpenProjectDialog(self.jmap_mcs)
        self.load_project_dialog.open_project_pushButton.clicked.connect(self.load_project)
        self.export_project_dialog = ExportProjectDialog()
        self.export_project_dialog.export_project_pushButton.clicked.connect(self.export_project)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Translate a string.
        :param message: String to translate.
        :return: Translated string.
        """
        translated_message = QCoreApplication.translate("JMapCloud", message)
        print(translated_message)
        return translated_message

    def create_actions(
        self,
        text: str,
        callback: callable,
        icon_path: str = None,
        enabled_flag: bool = True,
        status_tip: str = None,
        whats_this: str = None,
        parent: object = None,
    ) -> QAction:
        """Create QAction with given parameters."""
        if icon_path:
            icon = QIcon(icon_path)
            action = QAction(icon, text, parent)
        else:
            action = QAction(text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)
        return action

    def add_action(self, action: QAction, add_to_menu: bool = True, add_to_toolbar: bool = True):
        """Add action to the toolbar and plugin menu.

        :param action: QAction to add to the toolbar and menu.
        :param add_to_menu: indicate whether to add to menu. Defaults to True.
        :param add_to_toolbar:  indicate whether to add to toolbar. Defaults to True.
        :return: The action that was passed in.
        """
        # if add_to_toolbar:
        #    self.toolbar.addAction(action)

        if add_to_menu:
            self.menu.addAction(action)

        self.actions.append(action)

        return action

    def remove_action(self, action):
        """Remove an action from the toolbar and plugin menu.

        :param action: Action to remove.
        :type action: QAction
        """
        self.menu.removeAction(action)
        # self.toolbar.removeAction(action)
        if action in self.actions:
            self.actions.remove(action)

    def initGui(self):
        """
        Create the menu entries and toolbar icons inside the QGIS GUI.
        This function must exist for the plugin to load.
        """
        # create plugin menu
        icon_path = ":images/images/icon.svg"
        temp_action = QAction()
        # This manipulation prevent the web menu to bug
        self.iface.addPluginToWebMenu("JMap Cloud", temp_action)
        web_menu = self.iface.webMenu()
        self.menu = QMenu("JMap Cloud")
        self.menu.setIcon(QIcon(icon_path))
        web_menu.addMenu(self.menu)
        self.iface.removePluginWebMenu("JMap Cloud", temp_action)
        # -----------------------------------------------

        self.connection_action = self.create_actions(
            text=self.tr("Connection"),
            callback=self.open_connection_dialog,
            parent=self.iface.mainWindow(),
        )
        self.load_project_action = self.create_actions(
            text=self.tr("Open project"),
            callback=self.open_load_project_dialog,
            parent=self.iface.mainWindow(),
        )
        self.export_project_action = self.create_actions(
            text=self.tr("Export project"),
            callback=self.open_export_project_dialog,
            parent=self.iface.mainWindow(),
        )
        self.trigger_refresh_token_action = self.create_actions(
            text=self.tr("Refresh token"),
            callback=self.auth_manager.refresh_auth_settings,
            parent=self.iface.mainWindow(),
        )

        self.add_action(self.connection_action)
        self.add_action(self.trigger_refresh_token_action)
        self.add_action(self.load_project_action)
        self.add_action(self.export_project_action)
        self.auth_manager.logged_out_signal.connect(lambda: self.set_authorized_action(AuthState.NOT_AUTHENTICATED))

        auth_state = self.auth_manager.get_auth_state()
        if auth_state == AuthState.AUTHENTICATED:
            self.auth_manager.get_refresh_auth_event().start()
        self.set_authorized_action(auth_state)

    def unload(self):
        """
        Removes the plugin menu item and icon from QGIS GUI.
        This function must exist for the plugin to load.
        """
        self.iface.webMenu().removeAction(self.menu.menuAction())
        self.auth_manager.get_refresh_auth_event().stop()
        self.connection_dialog.close()
        self.load_project_dialog.close()
        self.export_project_dialog.close()

        # remove the toolbar
        # del self.toolbar

    def set_authorized_action(self, authState: AuthState):
        """
        Enable or disable project-related actions based on the authentication state.

        :param authState: The current authentication state, determining whether
                          the user is authenticated and has an organization.
        """
        isAuthenticated = authState == AuthState.AUTHENTICATED
        self.load_project_action.setEnabled(isAuthenticated)
        self.export_project_action.setEnabled(isAuthenticated)
        self.trigger_refresh_token_action.setEnabled(isAuthenticated)

    def open_connection_dialog(self):
        """
        Show the connection dialog.
        """
        auth_state = self.auth_manager.get_auth_state()
        if auth_state != AuthState.NOT_AUTHENTICATED:
            self.connection_dialog.list_organizations()
        self.connection_dialog.show()

    def open_load_project_dialog(self):
        """
        Show the load project dialog if the user is authenticated.
        If the user is already importing a project, show the
        import project action dialog instead.
        """
        if not self.import_project_manager.is_importing_project():
            if self.load_project_dialog.list_projects():
                self.load_project_dialog.show()
            else:
                self.auth_manager.logout("Error : Authentication failed")
        else:
            self.import_project_manager.action_dialog.show()

    def open_export_project_dialog(self):
        """
        Show the export project dialog if the user is authenticated and not exporting
        a project right now. If the user is already exporting a project, show the
        export project action dialog instead.
        """
        if not self.export_project_manager.is_exporting_project():
            claims = self.session_manager.get_claims()
            if claims and "organizationId" in claims:
                self.export_project_dialog.show()
            else:
                self.auth_manager.logout("Error : Authentication failed")
        else:
            self.export_project_manager.action_dialog.show()

    def logged_in(self):
        """
        enable the load project and export project buttons and show successful login popup dialog

        This function will be called when the user as successfully logged in.
        """

        self.connection_dialog.close()
        self.set_authorized_action(AuthState.AUTHENTICATED)
        self.auth_manager.get_refresh_auth_event().start()
        action_dialog = ActionDialog()
        action_dialog.show()
        action_dialog.action_finished("Login successful", False)

    def load_project(self):
        """
        Start the process to load a selected project in QGIS
        """
        project_data = self.load_project_dialog.get_selected_project_data()
        if project_data:
            auth_state = self.auth_manager.get_auth_state()
            if auth_state == AuthState.AUTHENTICATED:
                self.load_project_dialog.close()
                crs = QgsCoordinateReferenceSystem(project_data["crs"])
                initial_extent = QgsReferencedRectangle(QgsRectangle.fromWkt(project_data["initial_extent"]), crs) if project_data["initial_extent"] else None
                vector_layer_type = project_data["layerType"]
                project_data = ProjectData(
                    name=project_data["name"],
                    description=project_data["description"],
                    default_language=project_data["language"],
                    project_id=project_data["id"],
                    organization_id=self.session_manager.get_organization_id(),
                    crs=crs,
                    initial_extent=initial_extent,
                )

                self.import_project_manager.init_import(project_data, vector_layer_type)

    def export_project(self):
        """
        start the exportation of a selected project from QGIS to JMap Cloud.
        """

        if not self.export_project_dialog.validate_input():
            return
        project_data = self.export_project_dialog.get_input_data()
        project_data["description"] = ""
        if project_data:
            auth_state = self.auth_manager.get_auth_state()
            if auth_state == AuthState.AUTHENTICATED:
                self.export_project_dialog.close()
                project_data = ProjectData(
                    name=project_data["projectTitle"],
                    description=project_data["description"],
                    default_language=self.language,
                    organization_id=self.session_manager.get_organization_id(),
                )
                project_data.setup_with_QGIS_project(QgsProject.instance())
                self.export_project_manager.export_project(project_data)
