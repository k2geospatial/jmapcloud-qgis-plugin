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


from qgis.core import QgsFeedback
from qgis.PyQt import QtWidgets
from qgis.utils import iface

from .action_dialog_base_ui import Ui_Dialog


class ActionDialog(QtWidgets.QDialog, Ui_Dialog):

    def __init__(self):
        """Constructor."""
        super(ActionDialog, self).__init__(iface.mainWindow())
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self._feedback = QgsFeedback()
        self.exit_pushButton.clicked.connect(self.close)

    def show_dialog(self):
        self.status_textBrowser.setText("")
        self.status_textBrowser.hide()
        self.progress_info_label.setText("")
        self.progress_info_label.show()
        self.progressBar.setValue(0)
        self.progressBar.show()
        self.show()

    def action_finished(self, message: str = "", error: bool = False):
        self.progress_info_label.setText("")
        self.progress_info_label.hide()
        self.progressBar.hide()
        self.status_textBrowser.show()
        self.status_textBrowser.setText(message)
        if error:
            self.status_textBrowser.setStyleSheet("color: red;")
        else:
            self.status_textBrowser.setStyleSheet("color: black;")
        self.set_close_mode()
        self.exit_pushButton.show()

    def set_progress(self, value: float, message: str = None):
        self.progressBar.setValue(round(value))
        if message is not None:
            self.progress_info_label.setText(message)

    def set_text(self, message: str, error: bool = False):
        self.progress_info_label.setText(message)

    def feedback(self) -> QgsFeedback:
        return self._feedback

    def reset_feedback(self):
        self._feedback = QgsFeedback()
        return self._feedback

    def cancel(self, message: str = None):
        self._feedback.cancel()
        if message is not None:
            self.action_finished(message)
        else:
            self.action_finished(self.tr("Action canceled"))
        self.reset_feedback()

    def set_cancelable_mode(self, cancel_message: str = None):
        self.exit_pushButton.disconnect()
        self.exit_pushButton.setText(self.tr("Cancel"))
        self.exit_pushButton.setEnabled(True)

        def callback():
            nonlocal cancel_message
            self.cancel(cancel_message)

        self.exit_pushButton.clicked.connect(callback)

    def set_close_mode(self):
        self.exit_pushButton.setText(self.tr("Close"))
        self.exit_pushButton.setEnabled(True)
        self.exit_pushButton.disconnect()
        self.exit_pushButton.clicked.connect(self.close)

    def set_no_mode(self):
        self.exit_pushButton.setEnabled(False)
        self.exit_pushButton.hide()
        self.exit_pushButton.disconnect()
        self.exit_pushButton.clicked.connect(self.close)
