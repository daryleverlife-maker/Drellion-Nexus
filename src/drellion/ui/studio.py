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
    QLineEdit,
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
from .waveform import WaveformWidget


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
        outer.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel("CUSTOM STUDIO")
        title.setStyleSheet("font-size:18pt;font-weight:700;")
        top.addWidget(title)
        top.addStretch()

        controls = [
            ("Add Audio", self.add_audio),
            ("Sync Generated", self.sync_generated),
            ("Duplicate", self.duplicate_selected),
            ("Split", self.split_selected),
            ("Fades", self.set_fades),
            ("Remove", self.remove_selected),
            ("Render Mix", self.render_mix),
        ]
        for name, callback in controls:
            button = QPushButton(name)
            button.clicked.connect(callback)
            top.addWidget(button)
        outer.addLayout(top)

        center = QHBoxLayout()
        center.setSpacing(10)

        left = QFrame()
        left.setObjectName("Card")
        left.setFixedWidth(280)
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("PROJECT BROWSER"))
        self.asset_list = QListWidget()
        self.asset_list.setAccessibleName("Project sources and generated assets")
        self.asset_list.itemDoubleClicked.connect(self.asset_double_clicked)
        left_layout.addWidget(self.asset_list, 1)

        left_layout.addWidget(QLabel("TRACKS"))
        self.track_list = QListWidget()
        self.track_list.setAccessibleName("Studio tracks")
        self.track_list.currentItemChanged.connect(self.track_changed)
        left_layout.addWidget(self.track_list, 1)
        track_buttons = QHBoxLayout()
        mute = QPushButton("Mute")
        mute.clicked.connect(self.toggle_track_mute)
        solo = QPushButton("Solo")
        solo.clicked.connect(self.toggle_track_solo)
        track_buttons.addWidget(mute)
        track_buttons.addWidget(solo)
        left_layout.addLayout(track_buttons)
        center.addWidget(left)

        timeline_panel = QFrame()
        timeline_panel.setObjectName("Card")
        timeline_layout = QVBoxLayout(timeline_panel)
        heading = QLabel("TIMELINE")
        heading.setStyleSheet("font-weight:650;")
        timeline_layout.addWidget(heading)
        self.waveform = WaveformWidget()
        timeline_layout.addWidget(self.waveform)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setAccessibleName("Non-destructive clip timeline")
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemSelectionChanged.connect(self.clip_selection_changed)
        self.table.itemChanged.connect(self.clip_item_changed)
        self.table.horizontalHeader().setStretchLastSection(True)
        timeline_layout.addWidget(self.table, 1)
        center.addWidget(timeline_panel, 1)

        inspector = QFrame()
        inspector.setObjectName("Card")
        inspector.setFixedWidth(280)
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.addWidget(QLabel("INSPECTOR / MIXER"))
        self.track_name = QLabel("No track selected")
        self.track_name.setWordWrap(True)
        inspector_layout.addWidget(self.track_name)

        inspector_layout.addWidget(QLabel("Track volume"))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setAccessibleName("Selected track volume in decibels")
        self.volume.setRange(-240, 120)
        self.volume.setValue(0)
        self.volume.valueChanged.connect(self.track_mix_changed)
        self.volume.sliderReleased.connect(lambda: self.main.snapshot("Changed Studio track volume"))
        inspector_layout.addWidget(self.volume)
        self.volume_value = QLabel("0.0 dB")
        inspector_layout.addWidget(self.volume_value)

        inspector_layout.addWidget(QLabel("Track pan"))
        self.pan = QSlider(Qt.Horizontal)
        self.pan.setAccessibleName("Selected track pan")
        self.pan.setRange(-100, 100)
        self.pan.setValue(0)
        self.pan.valueChanged.connect(self.track_mix_changed)
        self.pan.sliderReleased.connect(lambda: self.main.snapshot("Changed Studio track pan"))
        inspector_layout.addWidget(self.pan)
        self.pan_value = QLabel("Center")
        inspector_layout.addWidget(self.pan_value)

        self.mute_box = QCheckBox("Mute selected track")
        self.solo_box = QCheckBox("Solo selected track")
        self.mute_box.toggled.connect(self.track_flags_changed)
        self.solo_box.toggled.connect(self.track_flags_changed)
        inspector_layout.addWidget(self.mute_box)
        inspector_layout.addWidget(self.solo_box)

        inspector_layout.addWidget(QLabel("Keyboard editing"))
        help_text = QLabel(
            "All clip values are editable in the timeline table. Dragging is optional: "
            "start, offset, duration, gain, pan and fades can be typed directly."
        )
        help_text.setWordWrap(True)
        help_text.setObjectName("Muted")
        inspector_layout.addWidget(help_text)
        inspector_layout.addStretch()
        center.addWidget(inspector)
        outer.addLayout(center, 1)

        self.player = PlayerBar(self)
        outer.addWidget(self.player)

        command_frame = QFrame()
        command_frame.setObjectName("Card")
        command_row = QHBoxLayout(command_frame)
        command_row.addWidget(QLabel("✦ Ask Drellion"))
        self.ai_command = QLineEdit()
        self.ai_command.setAccessibleName("Ask Drellion Studio command")
        self.ai_command.setPlaceholderText(
            'Try: "make the production harder", "duplicate clip", "mute track", or "make verse sparser"'
        )
        self.ai_command.returnPressed.connect(self.run_ai_command)
        command_row.addWidget(self.ai_command, 1)
        run = QPushButton("Apply")
        run.setObjectName("Primary")
        run.clicked.connect(self.run_ai_command)
        command_row.addWidget(run)
        outer.addWidget(command_frame)

    def refresh_assets(self):
        if not hasattr(self, "asset_list"):
            return
        self.asset_list.clear()
        for source in self.main.project.sources:
            if source.path and Path(source.path).is_file():
                item = QListWidgetItem(f"{source.role} · {source.label or Path(source.path).name}")
                item.setData(Qt.UserRole, source.path)
                self.asset_list.addItem(item)
        for path in self.main.project.settings.get("last_stem_outputs", []) or []:
            if Path(path).is_file():
                item = QListWidgetItem(f"Stem · {Path(path).name}")
                item.setData(Qt.UserRole, path)
                self.asset_list.addItem(item)
        instrumental = str(self.main.project.settings.get("generated_instrumental", "") or "")
        if instrumental and Path(instrumental).is_file():
            item = QListWidgetItem("Generated Instrumental")
            item.setData(Qt.UserRole, instrumental)
            self.asset_list.addItem(item)

    def asset_double_clicked(self, item):
        path = str(item.data(Qt.UserRole) or "")
        if not path:
            return
        track = self._track()
        if track is None:
            track = TrackState(name=Path(path).stem, role="audio")
            self.main.project.tracks.append(track)
            self._selected_track_id = track.id
        clip = add_clip(track, path)
        self._selected_clip_id = clip.id
        self.main.snapshot("Added browser asset to Studio")
        self.refresh()

    def run_ai_command(self):
        text = self.ai_command.text().strip()
        if not text:
            return
        lowered = text.lower()
        history = list(self.main.project.settings.get("studio_ai_commands", []) or [])
        history.append(text)
        self.main.project.settings["studio_ai_commands"] = history[-100:]

        if "duplicate" in lowered:
            self.duplicate_selected()
        elif "mute" in lowered:
            self.toggle_track_mute()
        elif "solo" in lowered:
            self.toggle_track_solo()
        elif "harder" in lowered or "punch" in lowered:
            prompt = str(self.main.project.settings.get("production_direction_prompt", "") or "")
            addition = "stronger drum impact, more punch and stronger section lift"
            self.main.project.settings["production_direction_prompt"] = (prompt + ", " + addition).strip(", ")
            self.main.snapshot("Studio AI direction: harder")
            QMessageBox.information(self, "Ask Drellion", "Production direction updated. Regenerate/repaint the selected musical section with the production engine.")
        elif "sparser" in lowered or "less busy" in lowered:
            prompt = str(self.main.project.settings.get("production_direction_prompt", "") or "")
            addition = "sparser arrangement under vocals, fewer competing layers"
            self.main.project.settings["production_direction_prompt"] = (prompt + ", " + addition).strip(", ")
            self.main.snapshot("Studio AI direction: sparser")
            QMessageBox.information(self, "Ask Drellion", "Production direction updated for a sparser arrangement.")
        else:
            self.main.project.settings["pending_studio_ai_command"] = text
            self.main.snapshot("Queued Studio AI command")
            QMessageBox.information(
                self,
                "Ask Drellion",
                "Command saved with the project. Provider-specific section repaint routing will use this command when a generation range is selected.",
            )
        self.ai_command.clear()

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
        self.refresh_assets()
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
        clip = self._clip()
        if clip is not None:
            self.waveform.load_path(clip.path)
        else:
            self.waveform.clear()
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
