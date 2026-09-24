from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,QFileDialog,QFormLayout,QGridLayout,QHBoxLayout,QLabel,QLineEdit,QListWidget,
    QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QTextEdit,QVBoxLayout,
)

from ..export_v2 import ExportOptions, export_project
from ..health import check_project
from ..lyrics_v2 import WhisperTranscriber, align_plain_lyrics
from ..providers import create_broker
from ..storage import StorageSettings, folder_size, format_bytes, free_bytes, load_storage_settings, save_storage_settings
from ..versions import create_snapshot, list_snapshots, restore_snapshot
from .common import Page


class LyricsPage(Page):
    title="Lyrics & Timing"
    def __init__(self,host):
        super().__init__(host)
        root=QVBoxLayout(self)
        title=QLabel("Lyrics & Timing"); title.setStyleSheet("font-size:20px;font-weight:700;")
        self.editor=QTextEdit(); self.editor.setPlaceholderText("Paste, transcribe, or edit lyrics here")
        bar=QHBoxLayout()
        transcribe=QPushButton("Transcribe Lead Vocal (Whisper)")
        align=QPushButton("Align Lines to Vocal Duration")
        save=QPushButton("Save Lyrics")
        transcribe.clicked.connect(self.transcribe); save.clicked.connect(self.save_lyrics); align.clicked.connect(self.align)
        bar.addWidget(transcribe); bar.addWidget(save); bar.addWidget(align); bar.addStretch()
        self.status=QLabel("Optional faster-whisper transcription provides timestamped lyrics when installed.")
        self.status.setWordWrap(True)
        self.timing=QTableWidget(0,3); self.timing.setHorizontalHeaderLabels(["Start","End","Text"]); self.timing.horizontalHeader().setStretchLastSection(True)
        root.addWidget(title); root.addWidget(self.editor,1); root.addLayout(bar); root.addWidget(self.status); root.addWidget(self.timing,1)

    def refresh(self):
        if not self.project:return
        self.editor.blockSignals(True); self.editor.setPlainText(self.project.lyrics_text); self.editor.blockSignals(False); self._timing()

    def _lead_vocal_path(self):
        if not self.project:return ""
        for source in self.project.sources:
            if source.enabled and source.path and source.role=="Lead Vocal" and Path(source.path).exists():
                return source.path
        return ""

    def transcribe(self):
        path=self._lead_vocal_path()
        if not path:
            QMessageBox.warning(self,"Lyrics","Add a valid Lead Vocal source before transcription."); return
        transcriber=WhisperTranscriber()
        if not transcriber.available():
            QMessageBox.information(self,"Whisper transcription","faster-whisper is not installed. Install Drellion with the transcription optional extra, then try again."); return
        self.host.run_task(lambda:transcriber.transcribe(path),"Transcribing lead vocal",self._transcribed,inject_progress=False)

    def _transcribed(self,result):
        text,lines=result
        self.project.lyrics_text=text
        self.project.lyrics_timed=[{"start":line.start,"end":line.end,"text":line.text} for line in lines]
        self.project.touch(); self.project.save()
        self.editor.setPlainText(text); self.status.setText(f"Transcribed {len(lines)} timed lyric segment(s).")
        self._timing(); self.host.project_changed()

    def save_lyrics(self):
        if not self.project:return
        self.project.lyrics_text=self.editor.toPlainText(); self.project.touch(); self.project.save(); self.host.project_changed()

    def align(self):
        if not self.project:return
        duration=0.0
        for s in self.project.sources:
            if s.duration_seconds:duration=max(duration,s.duration_seconds)
            elif s.path and Path(s.path).suffix.lower()==".wav":
                try:
                    from ..audio_core import read_wav
                    duration=max(duration,read_wav(s.path).duration)
                except Exception:pass
        if duration<=0:
            QMessageBox.warning(self,"Lyrics","A WAV source is needed to estimate duration."); return
        self.project.lyrics_text=self.editor.toPlainText()
        lines=align_plain_lyrics(self.project.lyrics_text,duration)
        self.project.lyrics_timed=[{"start":x.start,"end":x.end,"text":x.text} for x in lines]
        self.project.save(); self._timing(); self.host.project_changed()
        self.status.setText(f"Aligned {len(lines)} lyric line(s) across {duration:.1f} seconds.")

    def _timing(self):
        self.timing.setRowCount(0)
        if not self.project:return
        for i,line in enumerate(self.project.lyrics_timed):
            self.timing.insertRow(i)
            self.timing.setItem(i,0,QTableWidgetItem(f"{float(line.get('start',0)):.3f}"))
            self.timing.setItem(i,1,QTableWidgetItem(f"{float(line.get('end',0)):.3f}"))
            self.timing.setItem(i,2,QTableWidgetItem(str(line.get('text',''))))


class EnginesPage(Page):
    title="AI Engines"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); title=QLabel("AI Engine Broker"); title.setStyleSheet("font-size:20px;font-weight:700;"); desc=QLabel("Automatic tries configured production engines in order. The Basic Test Engine is never selected silently."); desc.setWordWrap(True)
        form=QFormLayout(); self.ace=QLineEdit(); self.diff=QLineEdit(); self.local=QLineEdit(); self.basic=QCheckBox("Allow Basic Test Engine only when explicitly selected"); form.addRow("ACE-Step endpoint",self.ace); form.addRow("DiffRhythm endpoint",self.diff); form.addRow("DiffRhythm local repo",self.local); form.addRow(self.basic)
        bar=QHBoxLayout(); save=QPushButton("Save Engine Settings"); test=QPushButton("Test Availability"); bar.addWidget(save); bar.addWidget(test); bar.addStretch(); self.status=QTableWidget(0,4); self.status.setHorizontalHeaderLabels(["Engine","Status","Mode","Detail"]); self.status.horizontalHeader().setStretchLastSection(True); save.clicked.connect(self.save_settings); test.clicked.connect(self.test); root.addWidget(title); root.addWidget(desc); root.addLayout(form); root.addLayout(bar); root.addWidget(self.status,1)
    def refresh(self):
        if not self.project:return
        p=self.project.engine_preferences; self.ace.setText(str(p.get("ace_step_url",""))); self.diff.setText(str(p.get("diffrhythm_url",""))); self.local.setText(str(p.get("diffrhythm_local",""))); self.basic.setChecked(bool(p.get("explicit_basic_test_engine",False))); self.test()
    def save_settings(self):
        if not self.project:return
        p=self.project.engine_preferences; p["ace_step_url"]=self.ace.text().strip(); p["diffrhythm_url"]=self.diff.text().strip(); p["diffrhythm_local"]=self.local.text().strip(); p["explicit_basic_test_engine"]=self.basic.isChecked(); self.project.save(); self.test(); self.host.project_changed()
    def test(self):
        self.status.setRowCount(0)
        if not self.project:return
        for i,s in enumerate(create_broker(self.project.engine_preferences).statuses()):
            self.status.insertRow(i); self.status.setItem(i,0,QTableWidgetItem(s.name)); self.status.setItem(i,1,QTableWidgetItem("Ready" if s.ready else "Unavailable")); self.status.setItem(i,2,QTableWidgetItem(s.mode)); self.status.setItem(i,3,QTableWidgetItem(s.detail))


class HealthPage(Page):
    title="Project Health"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); title=QLabel("Project Check"); title.setStyleSheet("font-size:20px;font-weight:700;"); run=QPushButton("Run Project Check"); run.clicked.connect(self.refresh); self.summary=QLabel(); self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(["Check","Status","Detail"]); self.table.horizontalHeader().setStretchLastSection(True); root.addWidget(title); root.addWidget(run); root.addWidget(self.summary); root.addWidget(self.table,1)
    def refresh(self):
        self.table.setRowCount(0)
        if not self.project:return
        report=check_project(self.project,create_broker(self.project.engine_preferences)); self.summary.setText("PROJECT READY" if report.ready else "PROJECT NEEDS ATTENTION")
        for i,item in enumerate(report.items):
            self.table.insertRow(i); self.table.setItem(i,0,QTableWidgetItem(item.name)); self.table.setItem(i,1,QTableWidgetItem("✓" if item.ok else ("⚠" if item.severity=="warning" else "✗"))); self.table.setItem(i,2,QTableWidgetItem(item.detail))


class VersionsPage(Page):
    title="Versions"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); title=QLabel("Versions & Snapshots"); title.setStyleSheet("font-size:20px;font-weight:700;"); bar=QHBoxLayout(); self.name=QLineEdit(); self.name.setPlaceholderText("Snapshot name, e.g. Before new chorus"); make=QPushButton("Create Snapshot"); restore=QPushButton("Restore Selected Snapshot"); bar.addWidget(self.name,1); bar.addWidget(make); bar.addWidget(restore); self.list=QListWidget(); make.clicked.connect(self.make); restore.clicked.connect(self.restore); root.addWidget(title); root.addLayout(bar); root.addWidget(self.list,1)
    def refresh(self):
        self.list.clear()
        if not self.project:return
        for p in list_snapshots(self.project):self.list.addItem(str(p))
    def make(self):
        if not self.project:return
        path=create_snapshot(self.project,self.name.text().strip() or "Snapshot"); self.name.clear(); self.refresh(); QMessageBox.information(self,"Snapshot",f"Created {path.name}")
    def restore(self):
        if not self.project or not self.list.currentItem():return
        restored=restore_snapshot(self.list.currentItem().text()); restored.root=self.project.root; self.host.set_project(restored); restored.save(); self.refresh()


class ExportPage(Page):
    title="Export"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); title=QLabel("Export Center"); title.setStyleSheet("font-size:20px;font-weight:700;"); grid=QGridLayout(); self.opts={}
        for i,(key,label,checked) in enumerate((("wav","Master WAV",True),("mp3","MP3",True),("flac","FLAC",False),("m4a","M4A",False),("stems","Stems",True),("lyrics_lrc","Lyrics LRC",True),("lyrics_srt","Lyrics SRT",True),("metadata","Metadata",True),("project_archive","Project archive",False),("premaster","Premaster",False))):
            cb=QCheckBox(label); cb.setChecked(checked); self.opts[key]=cb; grid.addWidget(cb,i//2,i%2)
        self.location=QLineEdit(); choose=QPushButton("Change Export Folder"); choose.clicked.connect(self.choose); bar=QHBoxLayout(); bar.addWidget(self.location,1); bar.addWidget(choose); go=QPushButton("EXPORT ALL"); go.setProperty("primary",True); go.clicked.connect(self.export); self.result=QLabel(); self.result.setWordWrap(True); root.addWidget(title); root.addLayout(grid); root.addLayout(bar); root.addWidget(go); root.addWidget(self.result); root.addStretch()
    def refresh(self):
        if self.project:self.location.setText(str(self.project.folder("Exports")))
    def choose(self):
        folder=QFileDialog.getExistingDirectory(self,"Export location",self.location.text())
        if folder:self.location.setText(folder)
    def export(self):
        if not self.project:return
        options=ExportOptions(**{k:cb.isChecked() for k,cb in self.opts.items()})
        try:
            result=export_project(self.project,self.location.text().strip() or None,options); self.result.setText(f"Exported {len(result.files)} file(s) to {result.output_dir}")
        except Exception as exc:QMessageBox.warning(self,"Export",str(exc))


class ProjectFilesPage(Page):
    title="Project Files"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); title=QLabel("Project Files"); title.setStyleSheet("font-size:20px;font-weight:700;"); openb=QPushButton("Open Project Folder"); openb.clicked.connect(lambda:host.open_project_folder()); self.tree=QTableWidget(0,3); self.tree.setHorizontalHeaderLabels(["Folder","Files","Size"]); self.tree.horizontalHeader().setStretchLastSection(True); root.addWidget(title); root.addWidget(openb); root.addWidget(self.tree,1)
    def refresh(self):
        self.tree.setRowCount(0)
        if not self.project:return
        from ..project import PROJECT_FOLDERS
        for i,name in enumerate(PROJECT_FOLDERS):
            p=self.project.folder(name); files=sum(1 for x in p.rglob("*") if x.is_file()); self.tree.insertRow(i); self.tree.setItem(i,0,QTableWidgetItem(name)); self.tree.setItem(i,1,QTableWidgetItem(str(files))); self.tree.setItem(i,2,QTableWidgetItem(format_bytes(folder_size(p))))


class StoragePage(Page):
    title="Storage"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); title=QLabel("Storage"); title.setStyleSheet("font-size:20px;font-weight:700;"); form=QFormLayout(); self.projects=QLineEdit(); self.sound=QLineEdit(); self.models=QLineEdit(); self.temp=QLineEdit(); form.addRow("Projects",self.projects); form.addRow("Sound Library",self.sound); form.addRow("AI Models",self.models); form.addRow("Temporary Files",self.temp); save=QPushButton("Save Storage Settings"); save.clicked.connect(self.save); self.usage=QLabel(); root.addWidget(title); root.addLayout(form); root.addWidget(save); root.addWidget(self.usage); root.addStretch()
    def refresh(self):
        s=load_storage_settings(); self.projects.setText(s.projects); self.sound.setText(s.sound_library); self.models.setText(s.ai_models); self.temp.setText(s.temporary); self.usage.setText(f"Projects: {format_bytes(folder_size(s.projects))}\nSoundbank: {format_bytes(folder_size(s.sound_library)) if s.sound_library else 'Not configured'}\nModels: {format_bytes(folder_size(s.ai_models))}\nCache: {format_bytes(folder_size(s.temporary))}\nFree at project location: {format_bytes(free_bytes(s.projects))}")
    def save(self):
        s=StorageSettings(projects=self.projects.text().strip(),sound_library=self.sound.text().strip(),ai_models=self.models.text().strip(),temporary=self.temp.text().strip()); save_storage_settings(s); self.refresh()


class LibraryPage(Page):
    title="Library"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); title=QLabel("Sound Library"); title.setStyleSheet("font-size:20px;font-weight:700;"); self.path=QLineEdit(); choose=QPushButton("Choose Sound Library Folder"); choose.clicked.connect(self.choose); self.info=QLabel(); root.addWidget(title); row=QHBoxLayout(); row.addWidget(self.path,1); row.addWidget(choose); root.addLayout(row); root.addWidget(self.info); root.addStretch()
    def refresh(self):
        s=load_storage_settings(); self.path.setText(s.sound_library); self.info.setText(f"Library size: {format_bytes(folder_size(s.sound_library))}" if s.sound_library else "No sound library configured.")
    def choose(self):
        folder=QFileDialog.getExistingDirectory(self,"Sound Library",self.path.text())
        if not folder:return
        s=load_storage_settings(); s.sound_library=folder; save_storage_settings(s); self.refresh()
