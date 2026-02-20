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


from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtCore import QCoreApplication, QSettings
from qgis.PyQt.QtNetwork import QNetworkReply
from qgis.utils import iface

from ...core.constant import LANGUAGE_SUFFIX, SETTINGS_PREFIX
from ...core.plugin_util import find_value_in_dict_or_first
from ...core.services.jmap_services_access import JMapMCS
from ...core.services.request_manager import RequestManager

from .open_project_dialog_base_ui import Ui_Dialog


class CustomListWidgetItem(QtWidgets.QListWidgetItem):
    def __init__(self):
        super().__init__()
        self.metadata = None


class OpenProjectDialog(QtWidgets.QDialog, Ui_Dialog):
    def __init__(self, jmap_mcs: JMapMCS):
        """Constructor."""
        super(OpenProjectDialog, self).__init__(iface.mainWindow())
        self.setupUi(self)
        self.language = QSettings().value("{}/{}".format(SETTINGS_PREFIX, LANGUAGE_SUFFIX), "en")
        self.jmap_mcs = jmap_mcs

    def list_projects(self) -> bool:
        """
        Populate the list widget with projects from the specified organization.
        """
        self.open_project_pushButton.setEnabled(False)
        self.project_List_listWidget.clear()
        item = QtWidgets.QListWidgetItem()
        item.setText(self.tr("loading..."))
        self.project_List_listWidget.addItem(item)
        self.project_List_listWidget.setEnabled(False)

        def next_func(reply: RequestManager.ResponseData):
            if reply.status == QNetworkReply.NetworkError.NoError:
                self.add_project_item_to_list(reply.content)
            else:
                self.project_List_listWidget.clear()
                item = QtWidgets.QListWidgetItem()
                item.setText(self.tr("Error loading projects, please try again"))
                self.project_List_listWidget.addItem(item)

        if not self.jmap_mcs.get_projects_async().connect(next_func):
            return False

        return True

    def add_project_item_to_list(self, projects: list):
        if projects:
            self.project_List_listWidget.clear()
            self.project_List_listWidget.setEnabled(True)
            for project in projects:
                project["name"] = find_value_in_dict_or_first(
                    project["name"], [self.language, project["defaultLanguage"]], "no name"
                )
            sorted_projects = sorted(projects, key=lambda p: p["name"].lower())
            for project in sorted_projects:
                item = CustomListWidgetItem()
                icon = QtGui.QIcon()
                icon.addPixmap(
                    QtGui.QPixmap(":/images/images/default_map.jpg"),
                    QtGui.QIcon.Mode.Normal,
                    QtGui.QIcon.State.Off,
                )
                item.setIcon(icon)
                # lastModificationDate = datetime.strptime(str(project["lastModificationDate"]), "%Y-%m-%dT%H:%M:%SZ")
                name = project["name"]
                description = find_value_in_dict_or_first(
                    project["description"],
                    [self.language, project["defaultLanguage"]],
                    "",
                )
                crs = project["mapCrs"]
                initial_extent = project["initialExtent"] if "initialExtent" in project else None
                text = name + ("\n{}".format(description) if description else "") + "\nCRS : {}".format(crs)
                item.setText(text)
                item.metadata = {
                    "id": project["id"],
                    "name": name,
                    "description": description,
                    "language": project["defaultLanguage"],
                    "crs": crs,
                    "initial_extent": initial_extent,
                }

                self.project_List_listWidget.addItem(item)
            self.open_project_pushButton.setEnabled(True)
        else:
            self.open_project_pushButton.setEnabled(False)
            item = QtWidgets.QListWidgetItem()
            item.setText(self.tr("No project found"))
            self.project_List_listWidget.clear()
            self.project_List_listWidget.addItem(item)
            self.project_List_listWidget.setEnabled(False)

    def get_selected_project_data(self) -> dict:
        item: CustomListWidgetItem = self.project_List_listWidget.currentItem()
        if item:
            return {
                **item.metadata,
                "layerType": self.vector_type_comboBox.currentIndex(),
            }
        else:
            return None
