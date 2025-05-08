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
from qgis.utils import iface

from .export_project_dialog_base_ui import Ui_Dialog


class ExportProjectDialog(QtWidgets.QDialog, Ui_Dialog):

    def __init__(self):
        """Constructor."""
        super(ExportProjectDialog, self).__init__(iface.mainWindow())
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.error_label.setText("")
        self.set_export_project_enable_action(True)

    def get_input_data(self) -> dict:
        return {"projectTitle": self.project_title_lineEdit.text(), "language": "en"}

    def set_export_project_enable_action(self, enable: bool):
        self.project_title_lineEdit.setEnabled(enable)
        self.export_project_pushButton.setEnabled(enable)

    def validate_input(self) -> bool:

        if not self.project_title_lineEdit.text():
            self.error_label.setText(self.tr("Project title needed"))
            return False

        self.error_label.clear()
        return True
