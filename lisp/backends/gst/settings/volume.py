# -*- coding: utf-8 -*-
#
# This file is part of Linux Show Player
#
# Copyright 2012-2016 Francesco Ceruti <ceppofrancy@gmail.com>
#
# Linux Show Player is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Linux Show Player is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Linux Show Player.  If not, see <http://www.gnu.org/licenses/>.

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGroupBox, QHBoxLayout, QSlider, QLabel, QCheckBox, \
    QVBoxLayout

from lisp.backends.base.audio_utils import db_to_linear, linear_to_db
from lisp.backends.gst.elements.volume import Volume
from lisp.backends.gst.settings.settings_page import GstElementSettingsPage
from lisp.ui.qmutebutton import QMuteButton


class VolumeSettings(GstElementSettingsPage):

    NAME = "Volume"
    ELEMENT = Volume

    def __init__(self, element_id, **kwargs):
        super().__init__(element_id)
        self.setLayout(QVBoxLayout())
        self.layout().setAlignment(Qt.AlignTop)

        self.normal = 1

        self.volumeBox = QGroupBox(self)
        self.volumeBox.setLayout(QHBoxLayout())
        self.layout().addWidget(self.volumeBox)

        self.muteButton = QMuteButton(self.volumeBox)
        self.volumeBox.layout().addWidget(self.muteButton)

        self.volume = QSlider(self.volumeBox)
        self.volume.setRange(-1000, 100)
        self.volume.setPageStep(1)
        self.volume.setOrientation(Qt.Horizontal)
        self.volume.valueChanged.connect(self.volume_changed)
        self.volumeBox.layout().addWidget(self.volume)

        self.volumeLabel = QLabel(self.volumeBox)
        self.volumeLabel.setAlignment(Qt.AlignCenter)
        self.volumeBox.layout().addWidget(self.volumeLabel)

        self.volumeBox.layout().setStretch(0, 1)
        self.volumeBox.layout().setStretch(1, 4)
        self.volumeBox.layout().setStretch(2, 1)

        self.normalBox = QGroupBox(self)
        self.normalBox.setLayout(QHBoxLayout())
        self.layout().addWidget(self.normalBox)

        self.normalLabel = QLabel(self.normalBox)
        self.normalLabel.setAlignment(Qt.AlignCenter)
        self.normalBox.layout().addWidget(self.normalLabel)

        self.normalReset = QCheckBox(self.normalBox)
        self.normalBox.layout().addWidget(self.normalReset)
        self.normalBox.layout().setAlignment(self.normalReset, Qt.AlignCenter)

        self.retranslateUi()

    def retranslateUi(self):
        self.volumeBox.setTitle("Volume")
        self.volumeLabel.setText("0.0 dB")
        self.normalBox.setTitle("Normalized volume")
        self.normalLabel.setText("0.0 dB")
        self.normalReset.setText("Reset")

    def enable_check(self, enable):
        for box in [self.normalBox, self.volumeBox]:
            box.setCheckable(enable)
            box.setChecked(False)

    def get_settings(self):
        conf = {}
        checkable = self.volumeBox.isCheckable()

        if not (checkable and not self.volumeBox.isChecked()):
            conf["volume"] = db_to_linear(self.volume.value() / 10)
            conf["mute"] = self.muteButton.isMute()
        if not (checkable and not self.normalBox.isChecked()):
            if self.normalReset.isChecked():
                conf["normal_volume"] = 1
            else:
                conf["normal_volume"] = self.normal

        return {self.id: conf}

    def load_settings(self, settings):
        if settings is not None and self.id in settings:
            self.volume.setValue(linear_to_db(settings[self.id]["volume"]) * 10)
            self.muteButton.setMute(settings[self.id]["mute"])
            self.normal = settings[self.id]["normal_volume"]
            self.normalLabel.setText(str(round(linear_to_db(self.normal), 3))
                                     + " dB")

    def volume_changed(self, value):
        self.volumeLabel.setText(str(value / 10.0) + " dB")

    def pan_changed(self, value):
        if value < 0:
            self.panLabel.setText("Left")
        elif value > 0:
            self.panLabel.setText("Right")
        else:
            self.panLabel.setText("Center")
