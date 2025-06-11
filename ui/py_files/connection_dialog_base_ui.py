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


from PyQt5 import QtCore, QtGui, QtWidgets
from ...resources_rc import qInitResources

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(491, 286)
        self.verticalLayoutWidget_3 = QtWidgets.QWidget(Dialog)
        self.verticalLayoutWidget_3.setGeometry(QtCore.QRect(30, 28, 441, 231))
        self.verticalLayoutWidget_3.setObjectName("verticalLayoutWidget_3")
        self.form_layout = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_3)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setObjectName("form_layout")
        self.email_layout = QtWidgets.QHBoxLayout()
        self.email_layout.setObjectName("email_layout")
        self.email_label = QtWidgets.QLabel(self.verticalLayoutWidget_3)
        self.email_label.setMinimumSize(QtCore.QSize(70, 22))
        self.email_label.setObjectName("email_label")
        self.email_layout.addWidget(self.email_label)
        self.email_input = QtWidgets.QLineEdit(self.verticalLayoutWidget_3)
        self.email_input.setMinimumSize(QtCore.QSize(150, 0))
        self.email_input.setText("")
        self.email_input.setObjectName("email_input")
        self.email_layout.addWidget(self.email_input)
        self.form_layout.addLayout(self.email_layout)
        self.password_layout = QtWidgets.QHBoxLayout()
        self.password_layout.setObjectName("password_layout")
        self.password_label = QtWidgets.QLabel(self.verticalLayoutWidget_3)
        self.password_label.setMinimumSize(QtCore.QSize(70, 22))
        self.password_label.setObjectName("password_label")
        self.password_layout.addWidget(self.password_label)
        self.password_input = QtWidgets.QLineEdit(self.verticalLayoutWidget_3)
        self.password_input.setMinimumSize(QtCore.QSize(150, 0))
        self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password_input.setObjectName("password_input")
        self.password_layout.addWidget(self.password_input)
        self.show_password_checkBox = QtWidgets.QCheckBox(self.verticalLayoutWidget_3)
        self.show_password_checkBox.setStyleSheet(
            "QCheckBox::indicator:unchecked {\n"
            "    image: url(:/images/images/eye-password-show.svg)\n"
            "}\n"
            "QCheckBox::indicator:checked {\n"
            "    image: url(:/images/images/eye-password-hide.svg)\n"
            "}\n"
            "\n"
            ""
        )
        self.show_password_checkBox.setText("")
        self.show_password_checkBox.setObjectName("show_password_checkBox")
        self.password_layout.addWidget(self.show_password_checkBox)
        self.form_layout.addLayout(self.password_layout)
        self.connection_button = QtWidgets.QPushButton(self.verticalLayoutWidget_3)
        self.connection_button.setObjectName("connection_button")
        self.form_layout.addWidget(self.connection_button)
        self.message_label = QtWidgets.QLabel(self.verticalLayoutWidget_3)
        self.message_label.setStyleSheet("font-size:20px")
        self.message_label.setText("")
        self.message_label.setAlignment(QtCore.Qt.AlignCenter)
        self.message_label.setObjectName("message_label")
        self.form_layout.addWidget(self.message_label)
        self.organization_form_layout = QtWidgets.QHBoxLayout()
        self.organization_form_layout.setObjectName("organization_form_layout")
        self.choose_organization_label = QtWidgets.QLabel(self.verticalLayoutWidget_3)
        self.choose_organization_label.setEnabled(False)
        self.choose_organization_label.setObjectName("choose_organization_label")
        self.organization_form_layout.addWidget(self.choose_organization_label)
        self.organization_list_comboBox = QtWidgets.QComboBox(self.verticalLayoutWidget_3)
        self.organization_list_comboBox.setEnabled(False)
        self.organization_list_comboBox.setObjectName("organization_list_comboBox")
        self.organization_form_layout.addWidget(self.organization_list_comboBox)
        self.form_layout.addLayout(self.organization_form_layout)
        self.accept_button = QtWidgets.QPushButton(self.verticalLayoutWidget_3)
        self.accept_button.setEnabled(False)
        self.accept_button.setObjectName("accept_button")
        self.form_layout.addWidget(self.accept_button)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Connection to JMap Cloud"))
        self.email_label.setText(_translate("Dialog", "Email : "))
        self.password_label.setText(_translate("Dialog", "Password :"))
        self.connection_button.setText(_translate("Dialog", "login"))
        self.choose_organization_label.setText(_translate("Dialog", "Choose organization :"))
        self.accept_button.setText(_translate("Dialog", "OK"))

qInitResources()
