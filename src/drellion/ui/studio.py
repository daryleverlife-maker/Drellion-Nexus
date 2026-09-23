from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..project import TrackState
from ..timeline import (
    add_clip,
    duplicate_clip,
    ensure_track,
    remove_clip,
    render_timeline,
    split_clip,
    sync_generated_tracks,
)
from .player import PlayerBar


class StudioWindow(QDialog):
    COLUMNS = [
        "Track",
        "Clip",
        "Start",
        "Offset",
        "Duration",
        "Gain dB",
        "Pan",
        "Fade In",
        "Fade Out",
        "Mute",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self.setWindowTitle("Drellion Nexus — Custom Studio")
        self.resize(1500, 900)
        self.setModal(False)
        self._selected_track_id = ""
        self._selected_clip_id = ""
        self._updating = False

        sync_generated_tracks(self.main.project)
        self.build_ui()
        self.refresh()

    def build_ui(self):
        outer = QVBoxLayout(self)

        top = QHBoxLayout()
        title = QLabel("CUSTOM STUDIO")
        title.setStyleSheet("font-size:18pt;font-weight:700;")
        top.addWidget(title)
        top.addStretch()

        controls = [
            ("Add Audio", self.add_audio),
            ("Sync Generated", self.sync_generated),
            ("Duplicate Clip", self.duplicate_selected),
            ("Split Clip", self.split_selected),
            ("Set Fades", self.set_fades),
            ("Remove Clip", self.remove_selected),
            ("Render Mix", self.render_mix),
        ]
        for name, callback in controls:
            button = QPushButton(name)
            button.clicked.connect(callback)
            top.addWidget(button)
        outer.addLayout(top)

        center = QHBoxLayout()

        track_panel = QFrame()
        track_panel.setObjectName("Card")
        track_layout = QVBoxLayout(track_panel)
        track_layout.addWidget(QLabel("TRACKS"))
        self.track_list = QListWidget()
        self.track_list.currentItemChanged.connect(self.track_changed)
        track_layout.addWidget(self.track_list, 1)

        row = QHBoxLayout()
        mute = QPushButton("Mute")
        mute.clicked.connect(self.toggle_track_mute)
        solo = QPushButton("Solo")
        solo.clicked.connect(self.toggle_track_solo)
        row.addWidget(mute)
        row.addWidget(solo)
        track_layout.addLayout(row)
        center.addWidget(track_panel, 0)

        timeline_panel = QFrame()
        timeline_panel.setObjectName("Card")
        timeline_layout = QVBoxLayout(timeline_panel)

        timeline_layout.addWidget(
            QLabel("TIMELINE  •  non-destructive clips  •  values are editable")
        )
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemSelectionChanged.connect(self.clip_selection_changed)
        self.table.itemChanged.connect(self.clip_item_changed)
        self.table.horizontalHeader().setStretchLastSection(True)
        timeline_layout.addWidget(self.table, 1)
        center.addWidget(timeline_panel, 1)

        mixer = QFrame()
        mixer.setObjectName("Card")
        mixer.setFixedWidth(250)
        mixer_layout = QVBoxLayout(mixer)
        mixer_layout.addWidget(QLabel("SELECTED TRACK"))
        self.track_name = QLabel("No track selected")
        self.track_name.setWordWrap(True)
        mixer_layout.addWidget(self.track_name)

        mixer_layout.addWidget(QLabel("Volume"))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(-240, 120)
        self.volume.setValue(0)
        self.volume.valueChanged.connect(self.track_mix_changed)
        self.volume.sliderReleased.connect(lambda: self.main.snapshot("Changed Studio track volume"))
        mixer_layout.addWidget(self.volume)
        self.volume_value = QLabel("0.0 dB")
        mixer_layout.addWidget(self.volume_value)

        mixer_layout.addWidget(QLabel("Pan"))
        self.pan = QSlider(Qt.Horizontal)
        self.pan.setRange(-100, 100)
        self.pan.setValue(0)
        self.pan.valueChanged.connect(self.track_mix_changed)
        self.pan.sliderReleased.connect(lambda: self.main.snapshot("Changed Studio track pan"))
        mixer_layout.addWidget(self.pan)
        self.pan_value = QLabel("Center")
        mixer_layout.addWidget(self.pan_value)

        self.mute_box = QCheckBox("Mute")
        self.solo_box = QCheckBox("Solo")
        self.mute_box.toggled.connect(self.track_flags_changed)
        self.solo_box.toggled.connect(self.track_flags_changed)
        mixer_layout.addWidget(self.mute_box)
        mixer_layout.addWidget(self.solo_box)
        mixer_layout.addStretch()
        center.addWidget(mixer)

        outer.addLayout(center, 1)

        self.player = PlayerBar(self)
        outer.addWidget(self.player)

    def _track(self, track_id: str | None = None) -> TrackState | None:
        wanted = track_id or self._selected_track_id
        for track in self.main.project.tracks:
            if track.id == wanted:
                return track
        return None

    def _clip(self):
        track = self._track()
        if track is None:
            return None
        for clip in track.clips:
            if clip.id == self._selected_clip_id:
                return clip
        return None

    def refresh(self):
        self._updating = True
        try:
            self.track_list.clear()
            for track in self.main.project.tracks:
                flags = []
                if track.muted:
                    flags.append("M")
                if track.solo:
                    flags.append("S")
                prefix = f"[{''.join(flags)}] " if flags else ""
                item = QListWidgetItem(prefix + track.name)
                item.setData(Qt.UserRole, track.id)
                self.track_list.addItem(item)
                if track.id == self._selected_track_id:
                    self.track_list.setCurrentItem(item)

            rows = sum(len(track.clips) for track in self.main.project.tracks)
            self.table.setRowCount(rows)
            row_index = 0
            for track in self.main.project.tracks:
                for clip in track.clips:
                    values = [
                        track.name,
                        clip.label,
                        f"{clip.start:.3f}",
                        f"{clip.source_offset:.3f}",
                        f"{clip.duration:.3f}",
                        f"{clip.gain_db:.2f}",
                        f"{clip.pan:.3f}",
                        f"{clip.fade_in:.3f}",
                        f"{clip.fade_out:.3f}",
                        "Yes" if clip.muted else "No",
                    ]
                    for column, value in enumerate(values):
                        item = QTableWidgetItem(value)
                        item.setData(Qt.UserRole, (track.id, clip.id))
                        if column == 0:
                            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        self.table.setItem(row_index, column, item)
                    if track.id == self._selected_track_id and clip.id == self._selected_clip_id:
                        self.table.selectRow(row_index)
                    row_index += 1

            self._refresh_mixer()
        finally:
            self._updating = False

    def _refresh_mixer(self):
        track = self._track()
        self._updating = True
        try:
            if track is None:
                self.track_name.setText("No track selected")
                self.volume.setValue(0)
                self.pan.setValue(0)
                self.mute_box.setChecked(False)
                self.solo_box.setChecked(False)
                return
            self.track_name.setText(track.name)
            self.volume.setValue(round(track.volume_db * 10))
            self.pan.setValue(round(track.pan * 100))
            self.mute_box.setChecked(track.muted)
            self.solo_box.setChecked(track.solo)
            self.volume_value.setText(f"{track.volume_db:.1f} dB")
            self.pan_value.setText(
                "Center" if abs(track.pan) < 0.01 else f"{'L' if track.pan < 0 else 'R'} {abs(track.pan):.2f}"
            )
        finally:
            self._updating = False

    def track_changed(self, current, previous):
        if current is None:
            return
        self._selected_track_id = current.data(Qt.UserRole) or ""
        self._selected_clip_id = ""
        self._refresh_mixer()

    def clip_selection_changed(self):
        items = self.table.selectedItems()
        if not items:
            return
        ids = items[0].data(Qt.UserRole)
        if not ids:
            return
        self._selected_track_id, self._selected_clip_id = ids
        self._refresh_mixer()

    def clip_item_changed(self, item):
        if self._updating:
            return
        ids = item.data(Qt.UserRole)
        if not ids:
            return
        track = self._track(ids[0])
        if track is None:
            return
        clip = next((clip for clip in track.clips if clip.id == ids[1]), None)
        if clip is None:
            return

        try:
            value = item.text().strip()
            column = item.column()
            if column == 1:
                clip.label = value or clip.label
            elif column == 2:
                clip.start = max(0.0, float(value))
            elif column == 3:
                clip.source_offset = max(0.0, float(value))
            elif column == 4:
                clip.duration = max(0.0, float(value))
            elif column == 5:
                clip.gain_db = min(24.0, max(-60.0, float(value)))
            elif column == 6:
                clip.pan = min(1.0, max(-1.0, float(value)))
            elif column == 7:
                clip.fade_in = max(0.0, float(value))
            elif column == 8:
                clip.fade_out = max(0.0, float(value))
            elif column == 9:
                clip.muted = value.lower() in {"yes", "true", "1", "mute", "muted"}
            self.main.snapshot("Edited Studio clip")
        except ValueError:
            QMessageBox.warning(self, "Invalid value", "Enter a valid numeric value.")
        self.refresh()

    def add_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Add Audio to Studio",
            "",
            "Audio (*.wav *.flac *.mp3 *.m4a *.aac *.ogg *.opus *.aiff *.aif *.wma)",
        )
        if not path:
            return

        track = self._track()
        if track is None:
            name, ok = QInputDialog.getText(self, "Track Name", "Track name:", text=Path(path).stem)
            if not ok:
                return
            track = TrackState(name=name or Path(path).stem, role="audio")
            self.main.project.tracks.append(track)
            self._selected_track_id = track.id

        clip = add_clip(track, path)
        self._selected_clip_id = clip.id
        self.main.snapshot("Added Studio audio")
        self.refresh()

    def sync_generated(self):
        sync_generated_tracks(self.main.project)
        self.main.snapshot("Synced generated Studio tracks")
        self.refresh()

    def duplicate_selected(self):
        track = self._track()
        clip = self._clip()
        if track is None or clip is None:
            QMessageBox.information(self, "Duplicate", "Select a clip first.")
            return
        clone = duplicate_clip(track, clip.id, offset=max(0.25, clip.duration))
        self._selected_clip_id = clone.id
        self.main.snapshot("Duplicated Studio clip")
        self.refresh()

    def split_selected(self):
        track = self._track()
        clip = self._clip()
        if track is None or clip is None:
            QMessageBox.information(self, "Split", "Select a clip first.")
            return
        default = clip.start + (clip.duration / 2.0 if clip.duration > 0 else 0.0)
        position, ok = QInputDialog.getDouble(
            self,
            "Split Clip",
            "Timeline position (seconds):",
            default,
            0.0,
            86400.0,
            3,
        )
        if not ok:
            return
        try:
            left, right = split_clip(track, clip.id, position)
            self._selected_clip_id = right.id
            self.main.snapshot("Split Studio clip")
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Split failed", str(exc))

    def set_fades(self):
        clip = self._clip()
        if clip is None:
            QMessageBox.information(self, "Fades", "Select a clip first.")
            return
        fade_in, ok = QInputDialog.getDouble(
            self, "Fade In", "Fade-in seconds:", clip.fade_in, 0.0, 60.0, 3
        )
        if not ok:
            return
        fade_out, ok = QInputDialog.getDouble(
            self, "Fade Out", "Fade-out seconds:", clip.fade_out, 0.0, 60.0, 3
        )
        if not ok:
            return
        clip.fade_in = fade_in
        clip.fade_out = fade_out
        self.main.snapshot("Changed Studio fades")
        self.refresh()

    def remove_selected(self):
        track = self._track()
        clip = self._clip()
        if track is None or clip is None:
            QMessageBox.information(self, "Remove", "Select a clip first.")
            return
        remove_clip(track, clip.id)
        self._selected_clip_id = ""
        self.main.snapshot("Removed Studio clip")
        self.refresh()

    def toggle_track_mute(self):
        track = self._track()
        if track is None:
            return
        track.muted = not track.muted
        self.main.snapshot("Toggled Studio track mute")
        self.refresh()

    def toggle_track_solo(self):
        track = self._track()
        if track is None:
            return
        track.solo = not track.solo
        self.main.snapshot("Toggled Studio track solo")
        self.refresh()

    def track_mix_changed(self):
        if self._updating:
            return
        track = self._track()
        if track is None:
            return
        track.volume_db = self.volume.value() / 10.0
        track.pan = self.pan.value() / 100.0
        self.volume_value.setText(f"{track.volume_db:.1f} dB")
        self.pan_value.setText(
            "Center" if abs(track.pan) < 0.01 else f"{'L' if track.pan < 0 else 'R'} {abs(track.pan):.2f}"
        )
        self.main.project.touch()

    def track_flags_changed(self):
        if self._updating:
            return
        track = self._track()
        if track is None:
            return
        track.muted = self.mute_box.isChecked()
        track.solo = self.solo_box.isChecked()
        self.main.snapshot("Changed Studio mute/solo")
        self.refresh()

    def render_mix(self):
        try:
            sync_generated_tracks(self.main.project)
            target = self.main.project_output_dir() / "Studio" / "studio-mix.wav"
            output = render_timeline(self.main.project, target)
            self.main.project.settings["studio_mix"] = str(output)
            self.main.snapshot("Rendered Studio mix")
            self.player.load_path(str(output), "Studio Mix")
            self.player.player.play()
            self.main.player.load_path(str(output), "Studio Mix")
            QMessageBox.information(self, "Studio render complete", str(output))
        except Exception as exc:
            QMessageBox.critical(self, "Studio render failed", str(exc))
