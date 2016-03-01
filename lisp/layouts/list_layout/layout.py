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
from enum import Enum

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QAction, QToolBar, QHBoxLayout, \
    QVBoxLayout, QLabel, qApp

from lisp.core.signal import Connection
from lisp.cues.cue import Cue, CueState, CueAction
from lisp.cues.media_cue import MediaCue
from lisp.layouts.cue_layout import CueLayout
from lisp.layouts.list_layout.cue_list_model import CueListModel, \
    PlayingMediaCueModel
from lisp.layouts.list_layout.cue_list_view import CueListView
from lisp.layouts.list_layout.list_layout_settings import ListLayoutSettings
from lisp.layouts.list_layout.playing_listwidget import PlayingListWidget
from lisp.ui.mainwindow import MainWindow
from lisp.ui.settings.app_settings import AppSettings
from lisp.ui.settings.cue_settings import CueSettingsRegistry
from lisp.ui.settings.pages.cue_appearance import Appearance
from lisp.ui.settings.pages.cue_general import CueGeneralSettings
from lisp.ui.settings.pages.media_cue_settings import MediaCueSettings
from lisp.utils.configuration import config

AppSettings.register_settings_widget(ListLayoutSettings)


class EndListBehavior(Enum):
    Stop = 'Stop'
    Restart = 'Restart'


class ListLayout(QWidget, CueLayout):

    NAME = 'List Layout'
    DESCRIPTION = '''
        This layout organize the cues in a list:
        <ul>
            <li>Side panel with playing media-cues;
            <li>Cues can be moved in the list;
            <li>Space to play, CTRL+Space to select, SHIFT+Space or Double-Click to edit;
        </ul>'''

    def __init__(self, cue_model, **kwargs):
        super().__init__(cue_model=cue_model, **kwargs)

        self._model_adapter = CueListModel(self._cue_model)
        self._model_adapter.item_added.connect(self.__cue_added)
        self._model_adapter.item_removed.connect(self.__cue_removed)

        self._playing_model = PlayingMediaCueModel(self._cue_model)
        self._context_item = None
        self._next_cue_index = 0

        self._show_dbmeter = config['ListLayout']['ShowDbMeters'] == 'True'
        self._seek_visible = config['ListLayout']['ShowSeek'] == 'True'
        self._accurate_time = config['ListLayout']['ShowAccurate'] == 'True'
        self._auto_continue = config['ListLayout']['AutoContinue'] == 'True'
        self._show_playing = config['ListLayout']['ShowPlaying'] == 'True'

        try:
            self._end_list = EndListBehavior(config['ListLayout']['EndList'])
        except ValueError:
            self._end_list = EndListBehavior.Stop

        # Add layout-specific menus
        self.showPlayingAction = QAction(self)
        self.showPlayingAction.setCheckable(True)
        self.showPlayingAction.setChecked(self._show_playing)
        self.showPlayingAction.triggered.connect(self.set_playing_visible)

        self.showDbMeterAction = QAction(self)
        self.showDbMeterAction.setCheckable(True)
        self.showDbMeterAction.setChecked(self._show_dbmeter)
        self.showDbMeterAction.triggered.connect(self.set_dbmeter_visible)

        self.showSeekAction = QAction(self)
        self.showSeekAction.setCheckable(True)
        self.showSeekAction.setChecked(self._seek_visible)
        self.showSeekAction.triggered.connect(self.set_seek_visible)

        self.accurateTimingAction = QAction(self)
        self.accurateTimingAction.setCheckable(True)
        self.accurateTimingAction.setChecked(self._accurate_time)
        self.accurateTimingAction.triggered.connect(self.set_accurate_time)

        self.autoNextAction = QAction(self)
        self.autoNextAction.setCheckable(True)
        self.autoNextAction.setChecked(self._auto_continue)
        self.autoNextAction.triggered.connect(self.set_auto_next)

        MainWindow().menuLayout.addAction(self.showPlayingAction)
        MainWindow().menuLayout.addAction(self.showDbMeterAction)
        MainWindow().menuLayout.addAction(self.showSeekAction)
        MainWindow().menuLayout.addAction(self.accurateTimingAction)
        MainWindow().menuLayout.addAction(self.autoNextAction)

        # Add a toolbar to MainWindow
        self.toolBar = QToolBar(MainWindow())
        self.toolBar.setContextMenuPolicy(Qt.PreventContextMenu)

        self.startAction = QAction(self)
        self.startAction.setIcon(QIcon.fromTheme("media-playback-start"))
        self.startAction.triggered.connect(self.start_current)

        self.pauseAction = QAction(self)
        self.pauseAction.setIcon(QIcon.fromTheme("media-playback-pause"))
        self.pauseAction.triggered.connect(self.pause_current)

        self.stopAction = QAction(self)
        self.stopAction.setIcon(QIcon.fromTheme("media-playback-stop"))
        self.stopAction.triggered.connect(self.stop_current)

        self.stopAllAction = QAction(self)
        self.stopAllAction.font().setBold(True)
        self.stopAllAction.triggered.connect(self.stop_all)

        self.pauseAllAction = QAction(self)
        self.pauseAllAction.font().setBold(True)
        self.pauseAllAction.triggered.connect(self.pause_all)

        self.restartAllAction = QAction(self)
        self.restartAllAction.font().setBold(True)
        self.restartAllAction.triggered.connect(self.restart_all)

        self.toolBar.addAction(self.startAction)
        self.toolBar.addAction(self.pauseAction)
        self.toolBar.addAction(self.stopAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.stopAllAction)
        self.toolBar.addAction(self.pauseAllAction)
        self.toolBar.addAction(self.restartAllAction)

        MainWindow().addToolBar(self.toolBar)

        self.hLayout = QHBoxLayout(self)
        self.hLayout.setContentsMargins(5, 5, 5, 5)

        # On the left (cue list)
        self.listView = CueListView(self._model_adapter, self)
        self.listView.context_event.connect(self.context_event)
        self.listView.itemDoubleClicked.connect(self.double_clicked)
        self.listView.key_event.connect(self.onKeyPressEvent)
        self.hLayout.addWidget(self.listView)

        self.playingLayout = QVBoxLayout()
        self.playingLayout.setContentsMargins(0, 0, 0, 0)
        self.playingLayout.setSpacing(2)

        # On the right (playing media-cues)
        self.playViewLabel = QLabel('Playing', self)
        self.playViewLabel.setAlignment(Qt.AlignCenter)
        self.playViewLabel.setStyleSheet('font-size: 17pt; font-weight: bold;')
        self.playingLayout.addWidget(self.playViewLabel)

        self.playView = PlayingListWidget(self._playing_model, parent=self)
        self.playView.dbmeter_visible = self._show_dbmeter
        self.playView.accurate_time = self._accurate_time
        self.playView.seek_visible = self._seek_visible
        self.playView.setMinimumWidth(300)
        self.playView.setMaximumWidth(300)
        self.playingLayout.addWidget(self.playView)

        self.set_playing_visible(self._show_playing)
        self.hLayout.addLayout(self.playingLayout)

        # TODO: maybe can be moved outside the layout
        # Add cue preferences widgets
        CueSettingsRegistry().add_item(CueGeneralSettings, Cue)
        CueSettingsRegistry().add_item(MediaCueSettings, MediaCue)
        CueSettingsRegistry().add_item(Appearance)

        # Context menu actions
        self.edit_action = QAction(self)
        self.edit_action.triggered.connect(self.edit_context_cue)

        self.remove_action = QAction(self)
        self.remove_action.triggered.connect(self.remove_context_cue)

        self.select_action = QAction(self)
        self.select_action.triggered.connect(self.select_context_cue)

        self.cm_registry.add_item(self.edit_action)
        self.sep1 = self.cm_registry.add_separator()
        self.cm_registry.add_item(self.remove_action)
        self.cm_registry.add_item(self.select_action)

        self.retranslateUi()

    def retranslateUi(self):
        self.showPlayingAction.setText("Show playing")
        self.showDbMeterAction.setText("Show Db-meters")
        self.showSeekAction.setText("Show seek bars")
        self.accurateTimingAction.setText('Accurate timing')
        self.autoNextAction.setText('Auto-change current cue')
        self.startAction.setText("Start current cue")
        self.pauseAction.setText("Pause current cue")
        self.stopAction.setText("Stop current cue")
        self.stopAllAction.setText("Stop All")
        self.pauseAllAction.setText("Pause All")
        self.restartAllAction.setText("Restart All")

        self.edit_action.setText('Edit option')
        self.remove_action.setText('Remove')
        self.select_action.setText('Select')

    @CueLayout.model_adapter.getter
    def model_adapter(self):
        return self._model_adapter

    def current_index(self):
        return self.listView.currentIndex().row()

    def set_current_index(self, index):
        if self._end_list == EndListBehavior.Restart:
            index %= len(self.model_adapter)
        elif 0 <= index < self.listView.topLevelItemCount():
            next_item = self.listView.topLevelItem(index)
            self.listView.setCurrentItem(next_item)

    def go(self, action=CueAction.Default, advance=1):
        current_cue = self.current_cue()
        if current_cue is not None:
            current_cue.execute(action)
            self.cue_executed.emit(current_cue)

        if self._auto_continue:
            self.set_current_index(self.current_index() + advance)

    def current_item(self):
        if self._model_adapter:
            return self.listView.currentItem()

    def select_context_cue(self):
        self._context_item.selected = not self._context_item.selected

    def set_accurate_time(self, accurate):
        self._accurate_time = accurate
        self.playView.accurate_time = accurate

    def set_auto_next(self, enable):
        self._auto_continue = enable

    def set_seek_visible(self, visible):
        self._seek_visible = visible
        self.playView.seek_visible = visible

    def set_dbmeter_visible(self, visible):
        self._show_dbmeter = visible
        self.playView.dbmeter_visible = visible

    def set_playing_visible(self, visible):
        self._show_playing = visible
        self.playView.setVisible(visible)
        self.playViewLabel.setVisible(visible)

    def onKeyPressEvent(self, e):
        if not e.isAutoRepeat() and e.key() == Qt.Key_Space:
            if qApp.keyboardModifiers() == Qt.ShiftModifier:
                cue = self.current_cue()
                if cue is not None:
                    self.edit_cue(cue)
            elif qApp.keyboardModifiers() == Qt.ControlModifier:
                item = self.current_item()
                if item is not None:
                    item.selected = not item.selected
                    return True
            else:
                self.go()
        else:
            self.key_pressed.emit(e)

        e.accept()

    def start_current(self):
        cue = self.current_cue()
        if cue is not None:
            cue.start()

    def pause_current(self):
        cue = self.current_cue()
        if cue is not None:
            cue.pause()

    def stop_current(self):
        cue = self.current_cue()
        if cue is not None:
            cue.stop()

    def double_clicked(self, event):
        cue = self.current_cue()
        if cue is not None:
            self.edit_cue(cue)

    def context_event(self, event):
        self._context_item = self.listView.itemAt(event.pos())
        if self._context_item is not None:
            self.show_context_menu(event.globalPos())

        event.accept()

    def remove_context_cue(self):
        self._model_adapter.remove(self.get_context_cue())

    def edit_context_cue(self):
        self.edit_cue(self.get_context_cue())

    def stop_all(self):
        for cue in self._model_adapter:
            cue.stop()

    def pause_all(self):
        for cue in self._model_adapter:
            cue.pause()

    def restart_all(self):
        for cue in self._model_adapter:
            if cue.state == CueState.Pause:
                cue.start()

    def get_selected_cues(self, cue_class=Cue):
        cues = []
        for index in range(self.listView.topLevelItemCount()):
            item = self.listView.topLevelItem(index)
            if item.selected and isinstance(item.cue, cue_class):
                cues.append(item.cue)
        return cues

    def finalize(self):
        MainWindow().menuLayout.clear()
        MainWindow().removeToolBar(self.toolBar)
        self.toolBar.deleteLater()

        # Disconnect menu-actions signals
        self.edit_action.triggered.disconnect()
        self.remove_action.triggered.disconnect()
        self.select_action.triggered.disconnect()

        # Remove context-items
        self.cm_registry.remove_item(self.edit_action)
        self.cm_registry.remove_item(self.sep1)
        self.cm_registry.remove_item(self.remove_action)
        self.cm_registry.remove_item(self.select_action)

        # Delete the layout
        self.deleteLater()

    def get_context_cue(self):
        return self._context_item.cue

    def select_all(self):
        for index in range(self.listView.topLevelItemCount()):
            self.listView.topLevelItem(index).selected = True

    def deselect_all(self):
        for index in range(self.listView.topLevelItemCount()):
            self.listView.topLevelItem(index).selected = False

    def invert_selection(self):
        for index in range(self.listView.topLevelItemCount()):
            item = self.listView.topLevelItem(index)
            item.selected = not item.selected

    def __cue_added(self, cue):
        cue.next.connect(self.__cue_next, Connection.QtQueued)

    def __cue_removed(self, cue):
        if isinstance(cue, MediaCue):
            cue.media.interrupt()
        else:
            cue.stop()

    def __cue_next(self, cue):
        try:
            next_index = cue.index + 1
            if next_index < len(self._model_adapter):
                next_cue = self._model_adapter.item(next_index)
                next_cue.execute()

                if self._auto_continue and next_cue == self.current_cue():
                    self.set_current_index(next_index + 1)
        except(IndexError, KeyError):
            pass
