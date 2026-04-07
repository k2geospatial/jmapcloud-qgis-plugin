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
from html import escape
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsMapLayerType,
    QgsMessageLog,
    QgsProject,
    QgsRectangle,
    QgsReferencedRectangle,
)
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QCoreApplication, QSettings, Qt, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QMessageBox

# from JMapCloud import resources_rc
from .core.constant import LANGUAGE_SUFFIX, SETTINGS_PREFIX, AuthState
from .core.services.auth_manager import JMapAuth
from .core.services.export_layer_manager import ExportLayerManager
from .core.services.export_project_manager import ExportProjectManager
from .core.services.import_project_manager import ImportProjectManager
from .core.services.jmap_services_access import JMapDAS, JMapMCS, JMapMIS
from .core.services.request_manager import RequestManager
from .core.services.session_manager import SessionManager
from .core.services.style_manager import StyleManager
from .core.views import ExportSelectedLayerData, ProjectData
from .ui.py_files.action_dialog import ActionDialog
from .ui.py_files.connection_dialog import ConnectionDialog
from .ui.py_files.export_layer_dialog import ExportLayerDialog
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
        self.export_layer_manager = ExportLayerManager(self.request_manager, self.jmap_mcs)
        self.export_layer_manager.data_source_references_loaded.connect(
            self._handle_project_references
        )

        # # initialize ui
        self.connection_dialog = ConnectionDialog(self.auth_manager)
        self.connection_dialog.logged_in_signal.connect(self._logged_in)
        self.connection_dialog.logout_signal.connect(self.auth_manager.logout)
        self.load_project_dialog = OpenProjectDialog(self.jmap_mcs)
        self.load_project_dialog.open_project_pushButton.clicked.connect(self._load_project)
        self.export_project_dialog = ExportProjectDialog()
        self.export_project_dialog.export_project_pushButton.clicked.connect(self._export_project)
        self.export_layer_dialog = ExportLayerDialog(self.jmap_mcs)
        self.export_layer_dialog.export_layer_pushButton.clicked.connect(self._export_layer)

        self._layer_tree_context_menu_connected = False
        self._selected_layer_for_export = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Translate a string.
        :param message: String to translate.
        :return: Translated string.
        """
        translated_message = QCoreApplication.translate("JMapCloud", message)
        print(translated_message)
        return translated_message

    def _create_actions(
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

    def _create_menu(self):
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

        self.connection_action = self._create_actions(
            text=self.tr("Connection"),
            callback=self._open_connection_dialog,
            parent=self.iface.mainWindow(),
        )
        self.load_project_action = self._create_actions(
            text=self.tr("Open project"),
            callback=self._open_load_project_dialog,
            parent=self.iface.mainWindow(),
        )
        self.export_project_action = self._create_actions(
            text=self.tr("Export project"),
            callback=self._open_export_project_dialog,
            parent=self.iface.mainWindow(),
        )
        self.trigger_refresh_token_action = self._create_actions(
            text=self.tr("Refresh token"),
            callback=self.auth_manager.refresh_auth_settings,
            parent=self.iface.mainWindow(),
        )

        self.menu.addAction(self.connection_action)
        self.actions.append(self.connection_action)

        self.menu.addAction(self.trigger_refresh_token_action)
        self.actions.append(self.trigger_refresh_token_action)

        self.menu.addAction(self.load_project_action)
        self.actions.append(self.load_project_action)

        self.menu.addAction(self.export_project_action)
        self.actions.append(self.export_project_action)

    def _create_layer_export_options_menu(self):
        """
        Create the menu entries for layer export options inside the QGIS GUI.
        This function is called when the user click on export project button and
        before showing the export project dialog.
        """
        if self._layer_tree_context_menu_connected:
            return
        self.iface.layerTreeView().contextMenuAboutToShow.connect(
            self._on_layer_tree_context_menu_about_to_show
        )
        self._layer_tree_context_menu_connected = True

    def _on_layer_tree_context_menu_about_to_show(self, menu: QMenu):
        """
        Add a custom action in the layer "Export" submenu for vector and raster layers.
        """
        layer = self.iface.layerTreeView().currentLayer()
        if not layer:
            return
        if layer.type() not in (QgsMapLayerType.VectorLayer, QgsMapLayerType.RasterLayer):
            return

        export_menu = None
        export_menu_labels = {"export", self.tr("Export").lower()}
        for action in menu.actions():
            submenu = action.menu()
            if submenu and action.text().replace("&", "").strip().lower() in export_menu_labels:
                export_menu = submenu
                break

        target_menu = export_menu or menu
        for action in target_menu.actions():
            if action.objectName() == "jmapcloud_export_layer_action":
                return

        export_to_jmap_action = QAction(self.tr("Export to JMap Cloud"), target_menu)
        export_to_jmap_action.setObjectName("jmapcloud_export_layer_action")
        export_to_jmap_action.setIcon(QIcon(":images/images/icon.svg"))
        export_to_jmap_action.triggered.connect(
            lambda checked=False, selected_layer=layer: self._open_export_layer_dialog(
                selected_layer
            )
        )
        target_menu.addAction(export_to_jmap_action)

    def _on_export_layer_action_placeholder(self, layer):
        """
        Temporary handler while the dedicated layer export UI is not implemented.
        """
        if layer:
            self.export_layer_dialog.show()

    def initGui(self):
        self._create_menu()
        self._create_layer_export_options_menu()

        self.auth_manager.logged_out_signal.connect(
            lambda: self._set_authorized_action(AuthState.NOT_AUTHENTICATED)
        )
        auth_state = self.auth_manager.get_auth_state()
        if auth_state == AuthState.AUTHENTICATED:
            self.auth_manager.get_refresh_auth_event().start()
        self._set_authorized_action(auth_state)

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
        if self._layer_tree_context_menu_connected:
            self.iface.layerTreeView().contextMenuAboutToShow.disconnect(
                self._on_layer_tree_context_menu_about_to_show
            )
            self._layer_tree_context_menu_connected = False

        # remove the toolbar
        # del self.toolbar

    def _set_authorized_action(self, authState: AuthState):
        """
        Enable or disable project-related actions based on the authentication state.

        :param authState: The current authentication state, determining whether
                          the user is authenticated and has an organization.
        """
        isAuthenticated = authState == AuthState.AUTHENTICATED
        self.load_project_action.setEnabled(isAuthenticated)
        self.export_project_action.setEnabled(isAuthenticated)
        self.trigger_refresh_token_action.setEnabled(isAuthenticated)

    def _open_connection_dialog(self):
        """
        Show the connection dialog.
        """
        auth_state = self.auth_manager.get_auth_state()
        if auth_state != AuthState.NOT_AUTHENTICATED:
            self.connection_dialog.list_organizations()
        self.connection_dialog.show()

    def _open_load_project_dialog(self):
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

    def _open_export_project_dialog(self):
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

    def _open_export_layer_dialog(self, layer):
        """
        Show the export layer dialog if the user is authenticated and not exporting
        a layer right now. If the user is already exporting a layer, show the
        export layer action dialog instead.
        """
        if not layer:
            return

        if self.export_layer_manager.is_exporting_layer():
            self.export_layer_manager._action_dialog.show()
            return

        claims = self.session_manager.get_claims()
        if not claims or "organizationId" not in claims:
            self.auth_manager.logout("Error : Authentication failed")
            return

        self.export_layer_dialog.set_selected_layer(layer)
        if self.export_layer_dialog.load_JMC_projects():
            self.export_layer_dialog.show()
        else:
            self.auth_manager.logout("Error : Authentication failed")

    def _logged_in(self):
        """
        enable the load project and export project buttons and show successful login popup dialog

        This function will be called when the user as successfully logged in.
        """

        self.connection_dialog.close()
        self._set_authorized_action(AuthState.AUTHENTICATED)
        self.auth_manager.get_refresh_auth_event().start()
        action_dialog = ActionDialog()
        action_dialog.show()
        action_dialog.action_finished("Login successful", False)

    def _load_project(self):
        """
        Start the process to load a selected project in QGIS
        """
        project_data = self.load_project_dialog.get_selected_project_data()
        if project_data:
            auth_state = self.auth_manager.get_auth_state()
            if auth_state == AuthState.AUTHENTICATED:
                self.load_project_dialog.close()
                crs = QgsCoordinateReferenceSystem(project_data["crs"])
                initial_extent = (
                    QgsReferencedRectangle(
                        QgsRectangle.fromWkt(project_data["initial_extent"]), crs
                    )
                    if project_data["initial_extent"]
                    else None
                )
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

    def _export_project(self):
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
                if self._selected_layer_for_export:
                    selected_layer = QgsProject.instance().mapLayer(
                        self._selected_layer_for_export.id()
                    )
                    self._selected_layer_for_export = None
                    if selected_layer:
                        project_data.layers = [selected_layer]
                self.export_project_manager.export_project(project_data)

    def _export_layer(self):
        """
        start the exportation of a selected layer from QGIS to JMap Cloud.
        Before starting the exportation,
        we must display a warning dialog if the layer is trying to be replaced and
        can have an important impact on other project that are using the same layer in JMap Cloud.
        The warning dialog will ask the user to confirm the exportation or not.
        If the user confirm the exportation, the exportation will be started.
        Otherwise, the exportation will be cancelled.
        The exportation of a layer can be done in two modes :
        """

        export_selected_layer_data = self.export_layer_dialog.get_selected_layer_to_export()

        if not export_selected_layer_data:
            return

        if self.auth_manager.get_auth_state() != AuthState.AUTHENTICATED:
            self.auth_manager.logout("Error : Authentication failed")
            return

        export_selected_layer_data.JMC_project.organization_id = (
            self.session_manager.get_organization_id()
        )
        if export_selected_layer_data.mode == ExportSelectedLayerData.ExportMode.replace:
            self.export_layer_manager.load_data_source_referenced_by_other_projects(
                export_selected_layer_data.target_JMC_data_source_id,
                export_selected_layer_data.JMC_project.project_id,
            )
        else:
            self.export_layer_dialog.close()
            self.export_layer_manager.create_new_layer(
                self.session_manager.get_organization_id(), export_selected_layer_data
            )

    def _handle_project_references(self, references: list[dict[str, list[str]]]):
        """Handle the project references of a layer to replace before exporting it."""
        if references is None or len(references) == 0:
            self.export_layer_dialog.close()
            self.export_layer_manager.replace_layer(
                self.session_manager.get_organization_id(),
                self.export_layer_dialog.get_selected_layer_to_export(),
            )
            return

        html_content = """
                <p><b>{}</b> {}</p>
                <ul>
                """.format(
            self.tr("Warning:"),
            self.tr(
                "The layer you are trying to replace is referenced by the "
                "following projects and layers:"
            ),
        )
        for reference in references:
            project_name = escape(reference.get("project_name", self.tr("Unknown Project")))
            layer_names = reference.get("layer_names", [])
            html_content += (
                f"<li>{project_name}: {', '.join(escape(name) for name in layer_names)}</li>"
            )
        html_content += "</ul>"
        html_content += "<p>{}</p>".format(
            self.tr(
                "Replacing the layer will impact all these projects and layers. "
                "Do you want to continue?"
            )
        )

        message_box = QMessageBox(self.iface.mainWindow())
        message_box.setIcon(QMessageBox.Icon.Warning)
        message_box.setWindowTitle(self.tr("Layer replacement warning"))
        message_box.setTextFormat(Qt.TextFormat.RichText)
        message_box.setText(html_content)
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        result = message_box.exec()

        if result == QMessageBox.StandardButton.Yes:
            export_selected_layer_data = self.export_layer_dialog.get_selected_layer_to_export()
            message_box.close()
            self.export_layer_dialog.close()

            if not export_selected_layer_data:
                return

            export_selected_layer_data.JMC_project.organization_id = (
                self.session_manager.get_organization_id()
            )
            self.export_layer_manager.replace_layer(
                export_selected_layer_data.JMC_project.organization_id, export_selected_layer_data
            )

            QgsMessageLog.logMessage(
                "User confirmed the layer replacement, starting exportation",
                level=Qgis.MessageLevel.Info,
            )
        else:
            message_box.close()
            QgsMessageLog.logMessage(
                "User cancelled the layer replacement, exportation cancelled",
                level=Qgis.MessageLevel.Info,
            )

            self.export_layer_manager.replace_layer(
                export_selected_layer_data.JMC_project.organization_id, export_selected_layer_data
            )

            QgsMessageLog.logMessage(
                "User confirmed the layer replacement, starting exportation",
                level=Qgis.MessageLevel.Info,
            )
