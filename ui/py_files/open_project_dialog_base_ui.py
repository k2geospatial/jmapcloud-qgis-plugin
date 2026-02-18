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


from qgis.PyQt import QtCore, QtGui, QtWidgets
from ...resources_rc import qInitResources

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(611, 531)
        Dialog.setStyleSheet("background-color:rgb(36, 46, 52)")
        self.jmap_image_label = QtWidgets.QLabel(Dialog)
        self.jmap_image_label.setGeometry(QtCore.QRect(10, 10, 121, 71))
        self.jmap_image_label.setText("")
        self.jmap_image_label.setPixmap(QtGui.QPixmap(":/images/images/Logo_JMap_Cloud.svg"))
        self.jmap_image_label.setObjectName("jmap_image_label")
        self.widget = QtWidgets.QWidget(Dialog)
        self.widget.setGeometry(QtCore.QRect(10, 100, 591, 421))
        self.widget.setStyleSheet("background-color:rgb(240, 240, 240);\n" "border: 1px solid")
        self.widget.setObjectName("widget")
        self.open_project_pushButton = QtWidgets.QPushButton(self.widget)
        self.open_project_pushButton.setGeometry(QtCore.QRect(260, 360, 321, 41))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.open_project_pushButton.sizePolicy().hasHeightForWidth())
        self.open_project_pushButton.setSizePolicy(sizePolicy)
        self.open_project_pushButton.setFocusPolicy(QtCore.Qt.FocusPolicy.WheelFocus)
        self.open_project_pushButton.setStyleSheet("background-color:rgb(255, 255, 255)")
        self.open_project_pushButton.setObjectName("open_project_pushButton")
        self.project_List_listWidget = QtWidgets.QListWidget(self.widget)
        self.project_List_listWidget.setGeometry(QtCore.QRect(10, 10, 571, 341))
        self.project_List_listWidget.setStyleSheet("font-size:17px;\n" "background-color:rgb(255, 255, 255)")
        self.project_List_listWidget.setIconSize(QtCore.QSize(100, 75))
        self.project_List_listWidget.setViewMode(QtWidgets.QListView.ViewMode.ListMode)
        self.project_List_listWidget.setObjectName("project_List_listWidget")
        self.vector_type_label = QtWidgets.QLabel(self.widget)
        self.vector_type_label.setGeometry(QtCore.QRect(10, 360, 111, 41))
        self.vector_type_label.setStyleSheet("border : none;\n" "color:black")
        self.vector_type_label.setObjectName("vector_type_label")
        self.vector_type_comboBox = QtWidgets.QComboBox(self.widget)
        self.vector_type_comboBox.setGeometry(QtCore.QRect(130, 360, 121, 41))
        self.vector_type_comboBox.setAutoFillBackground(False)
        self.vector_type_comboBox.setStyleSheet("background-color:white;\n" "color:black")
        self.vector_type_comboBox.setObjectName("vector_type_comboBox")
        self.vector_type_comboBox.addItem("")
        self.vector_type_comboBox.addItem("")
        self.vector_type_comboBox.addItem("")

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Open project"))
        self.open_project_pushButton.setText(_translate("Dialog", "Open project"))
        self.vector_type_label.setText(_translate("Dialog", " Vector layer type :"))
        self.vector_type_comboBox.setItemText(0, _translate("Dialog", "Default"))
        self.vector_type_comboBox.setItemText(1, _translate("Dialog", "All in GeoJSON"))
        self.vector_type_comboBox.setItemText(2, _translate("Dialog", "All in Vector Tiles"))


qInitResources()
