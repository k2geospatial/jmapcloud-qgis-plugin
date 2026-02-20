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
# -----------------------------------------------------------s


from qgis.PyQt import QtCore, QtGui, QtWidgets
from ...resources_rc import qInitResources


class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(391, 361)
        Dialog.setStyleSheet("background-color:rgb(36, 46, 52)")
        self.jmap_image_label = QtWidgets.QLabel(Dialog)
        self.jmap_image_label.setGeometry(QtCore.QRect(10, 10, 121, 71))
        self.jmap_image_label.setText("")
        self.jmap_image_label.setPixmap(QtGui.QPixmap(":/images/images/Logo_JMap_Cloud.svg"))
        self.jmap_image_label.setObjectName("jmap_image_label")
        self.widget = QtWidgets.QWidget(Dialog)
        self.widget.setGeometry(QtCore.QRect(10, 100, 371, 251))
        self.widget.setStyleSheet("background-color:rgb(220, 220, 220)\n" "")
        self.widget.setObjectName("widget")
        self.verticalLayoutWidget = QtWidgets.QWidget(self.widget)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(10, 20, 351, 222))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.progress_info_label = QtWidgets.QLabel(self.verticalLayoutWidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.progress_info_label.sizePolicy().hasHeightForWidth())
        self.progress_info_label.setSizePolicy(sizePolicy)
        self.progress_info_label.setStyleSheet("color: rgb(0, 0, 0);")
        self.progress_info_label.setText("")
        self.progress_info_label.setObjectName("progress_info_label")
        self.verticalLayout.addWidget(self.progress_info_label)
        self.progressBar = QtWidgets.QProgressBar(self.verticalLayoutWidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.progressBar.sizePolicy().hasHeightForWidth())
        self.progressBar.setSizePolicy(sizePolicy)
        self.progressBar.setAutoFillBackground(False)
        self.progressBar.setStyleSheet(
            "QProgressBar {"
            " background-color: rgb(255, 255, 255);"
            " color: rgb(0, 0, 0);"
            " border: 1px solid rgb(180, 180, 180);"
            "}"
            "QProgressBar::chunk {"
            " background-color: rgb(90, 170, 255);"
            "}"
        )
        self.progressBar.setProperty("value", 0)
        self.progressBar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.progressBar.setFormat("")
        self.progressBar.setObjectName("progressBar")
        self.verticalLayout.addWidget(self.progressBar)
        self.status_textBrowser = QtWidgets.QTextBrowser(self.verticalLayoutWidget)
        self.status_textBrowser.setObjectName("status_textBrowser")
        self.verticalLayout.addWidget(self.status_textBrowser)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.exit_pushButton = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.exit_pushButton.setStyleSheet(
            "QPushButton {"
            " background-color: rgb(255, 255, 255);"
            " color: rgb(0, 0, 0);"
            "}"
            "QPushButton:disabled {"
            " color: rgb(120, 120, 120);"
            "}"
        )
        self.exit_pushButton.setObjectName("exit_pushButton")
        self.verticalLayout.addWidget(self.exit_pushButton)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Action"))
        self.exit_pushButton.setText(_translate("Dialog", "Close"))

qInitResources()
