from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,QCheckBox,QComboBox,QDoubleSpinBox,QFileDialog,QFormLayout,QDialog,
    QGridLayout,QGroupBox,QHBoxLayout,QHeaderView,QLabel,QLineEdit,QMessageBox,QPushButton,
    QSlider,QSpinBox,QTableWidget,QTableWidgetItem,QTextEdit,QVBoxLayout,QWidget,
)

from ..production_v2 import build_from_preview,generate_three_previews,master_selected_build
from ..providers import create_broker
from ..reference import analyze_reference,fetch_youtube_metadata,youtube_video_id
from ..stems import best_available_separator
from ..vocal_analysis import analyze_vocal
from .common import AudioTransport,Page

AUDIO_FILTER="Audio (*.wav *.mp3 *.flac *.m4a *.aac *.ogg);;All files (*)"
SOURCE_ROLES=["Lead Vocal","Backing Vocal","Drums","Bass","Music","Instrument","Other","Full Song"]


class ProjectPage(Page):
    title="Project"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); self.heading=QLabel("No project open"); self.heading.setStyleSheet("font-size: 24px; font-weight: 700;"); self.info=QLabel(); self.info.setWordWrap(True); actions=QHBoxLayout(); open_folder=QPushButton("Open Project Folder"); health=QPushButton("Project Check"); consolidate=QPushButton("Consolidate Imported Media"); relink=QPushButton("Relink Missing Audio")
        for w in (open_folder,health,consolidate,relink):actions.addWidget(w)
        actions.addStretch(); open_folder.clicked.connect(host.open_project_folder); health.clicked.connect(lambda:host.navigate("Project Health")); consolidate.clicked.connect(self.consolidate); relink.clicked.connect(self.relink); root.addWidget(self.heading); root.addWidget(self.info); root.addLayout(actions); root.addStretch()
    def refresh(self):
        p=self.project
        if not p:self.heading.setText("No project open"); self.info.setText("Create or open a project from Home."); return
        self.heading.setText(f"{p.title} — {p.artist or 'Untitled artist'}"); self.info.setText(f"Mode: {p.mode}\nLocation: {p.root}\nSources: {len(p.sources)} / 6 Auto\nReferences: {len(p.references)} / 6 Auto\nPreviews: {len(p.previews)}\nBuilds: {len(p.builds)}\nMasters: {len(p.masters)}")
    def consolidate(self):
        if not self.project:return
        counts=self.project.consolidate_imported_media(); self.project.save(); QMessageBox.information(self,"Consolidate",f"Copied {counts['sources']} source(s) and {counts['references']} reference(s) into the project."); self.refresh()
    def relink(self):
        if not self.project:return
        folder=QFileDialog.getExistingDirectory(self,"Search for missing audio")
        if not folder:return
        fixed=self.project.relink_missing([folder]); self.project.save(); QMessageBox.information(self,"Relink",f"Relinked {len(fixed)} file(s)."); self.refresh()


class SourcesPage(Page):
    title="Sources"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); title=QLabel("Sources — material belonging to your song"); title.setStyleSheet("font-size: 20px; font-weight: 700;"); desc=QLabel("Auto supports up to six source uploads. Preserve keeps material; Rebuild marks a role for replacement. Original files are never modified."); desc.setWordWrap(True)
        bar=QHBoxLayout(); add=QPushButton("+ Add Source"); split=QPushButton("Split Selected Full Song Into Stems"); add.clicked.connect(self.add_source); split.clicked.connect(self.split_stems); bar.addWidget(add); bar.addWidget(split); bar.addStretch()
        self.table=QTableWidget(0,8); self.table.setHorizontalHeaderLabels(["Use","Source","Role","Preserve","Rebuild","Gain dB","Analysis","Actions"]); self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.player=AudioTransport("Source")
        root.addWidget(title); root.addWidget(desc); root.addLayout(bar); root.addWidget(self.table,1); root.addWidget(self.player)
    def add_source(self):
        if not self.project:return
        paths,_=QFileDialog.getOpenFileNames(self,"Add sources","",AUDIO_FILTER)
        for path in paths:
            try:
                asset=self.project.add_source(path,role="Lead Vocal" if not self.project.sources else "Other")
                if Path(asset.path).suffix.lower()==".wav" and asset.role=="Lead Vocal":
                    result=analyze_vocal(asset.path); asset.analysis=result.to_dict(); asset.duration_seconds=result.duration_seconds
            except Exception as exc:QMessageBox.warning(self,"Source",str(exc)); break
        self.project.save(); self.host.project_changed(); self.refresh()
    def split_stems(self):
        if not self.project or self.table.currentRow()<0:return
        row=self.table.currentRow()
        if row>=len(self.project.sources):return
        source=self.project.sources[row]; separator=best_available_separator()
        if not separator:QMessageBox.information(self,"Stem separation","No separation engine is installed. Install the Open-Unmix or Spleeter optional extra."); return
        self.host.run_task(lambda progress=None:separator.split(source.path,self.project.folder("Stems")/source.id),"Separating stems",self._stems_done)
    def _stems_done(self,result):
        for role,path in result.stems.items():
            mapped={"vocals":"Lead Vocal","drums":"Drums","bass":"Bass","piano":"Instrument","other":"Music","accompaniment":"Music"}.get(role,"Other")
            try:self.project.add_source(path,role=mapped,preserve=True)
            except ValueError:break
        self.project.save(); self.host.project_changed(); self.refresh()
    def refresh(self):
        self.table.setRowCount(0)
        if not self.project:return
        for i,source in enumerate(self.project.sources):
            self.table.insertRow(i); use=QCheckBox(); use.setChecked(source.enabled); use.toggled.connect(lambda value,s=source:self._set(s,"enabled",value)); self.table.setCellWidget(i,0,use)
            item=QTableWidgetItem(source.label); item.setToolTip(source.path); self.table.setItem(i,1,item); role=QComboBox(); role.addItems(SOURCE_ROLES); role.setCurrentText(source.role); role.currentTextChanged.connect(lambda value,s=source:self._set(s,"role",value)); self.table.setCellWidget(i,2,role)
            preserve=QCheckBox(); preserve.setChecked(source.preserve); preserve.toggled.connect(lambda value,s=source:self._set(s,"preserve",value)); self.table.setCellWidget(i,3,preserve); rebuild=QCheckBox(); rebuild.setChecked(source.rebuild); rebuild.toggled.connect(lambda value,s=source:self._set(s,"rebuild",value)); self.table.setCellWidget(i,4,rebuild)
            gain=QDoubleSpinBox(); gain.setRange(-60,24); gain.setValue(source.gain_db); gain.setSuffix(" dB"); gain.valueChanged.connect(lambda value,s=source:self._set(s,"gain_db",value)); self.table.setCellWidget(i,5,gain)
            analysis=source.analysis or {}; pitch=analysis.get("pitch_median_hz"); summary=(f"{analysis.get('phrase_count',0)} phrases"+(f", {pitch:.0f} Hz median pitch" if isinstance(pitch,(int,float)) else "")) if analysis else "Not analysed"; self.table.setItem(i,6,QTableWidgetItem(summary))
            actions=QWidget(); row=QHBoxLayout(actions); row.setContentsMargins(0,0,0,0); play=QPushButton("Play"); replace=QPushButton("Replace"); remove=QPushButton("Remove"); play.clicked.connect(lambda _=False,s=source:self.player.set_path(s.path,True)); replace.clicked.connect(lambda _=False,s=source:self.replace(s)); remove.clicked.connect(lambda _=False,s=source:self.remove(s))
            for b in (play,replace,remove):row.addWidget(b)
            self.table.setCellWidget(i,7,actions)
    def _set(self,source,field,value):setattr(source,field,value); self.project.touch(); self.project.save(); self.host.project_changed()
    def replace(self,source):
        path,_=QFileDialog.getOpenFileName(self,"Replace source","",AUDIO_FILTER)
        if path:
            self.project.replace_source(source.id,path)
            if Path(source.path).suffix.lower()==".wav" and source.role=="Lead Vocal":
                result=analyze_vocal(source.path); source.analysis=result.to_dict(); source.duration_seconds=result.duration_seconds
            self.project.save(); self.refresh(); self.host.project_changed()
    def remove(self,source):self.project.remove_source(source.id); self.project.save(); self.refresh(); self.host.project_changed()


class ReferencesPage(Page):
    title="References"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); title=QLabel("Reference Board"); title.setStyleSheet("font-size: 20px; font-weight: 700;"); desc=QLabel("Up to six references guide production characteristics. Local audio can be analysed. YouTube links are identity/playback references; Drellion does not silently rip them."); desc.setWordWrap(True)
        bar=QHBoxLayout(); local=QPushButton("+ Local Reference Audio"); self.url=QLineEdit(); self.url.setPlaceholderText("Paste YouTube URL"); add_url=QPushButton("Add YouTube Reference"); local.clicked.connect(self.add_local); add_url.clicked.connect(self.add_youtube); bar.addWidget(local); bar.addWidget(self.url,1); bar.addWidget(add_url)
        self.table=QTableWidget(0,11); self.table.setHorizontalHeaderLabels(["Reference","Weight","Drums","Bass","Energy","Arrangement","Tone","Stereo","Master","Analysis","Actions"]); self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch); self.player=AudioTransport("Reference"); root.addWidget(title); root.addWidget(desc); root.addLayout(bar); root.addWidget(self.table,1); root.addWidget(self.player)
    def add_local(self):
        if not self.project:return
        path,_=QFileDialog.getOpenFileName(self,"Add reference audio","",AUDIO_FILTER)
        if not path:return
        try:
            ref=self.project.add_reference(path); ref.analysis=analyze_reference(ref.path).to_dict(); self.project.save(); self.host.project_changed(); self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Reference",str(exc))
    def add_youtube(self):
        if not self.project:return
        url=self.url.text().strip()
        if not youtube_video_id(url):QMessageBox.warning(self,"Reference","That does not look like a supported YouTube URL."); return
        self.host.run_task(lambda:fetch_youtube_metadata(url),"Loading YouTube reference metadata",lambda meta:self._add_youtube_metadata(url,meta),inject_progress=False)
    def _add_youtube_metadata(self,url,meta):
        try:
            ref=self.project.add_reference(youtube_url=url,title=meta.get("title") or f"YouTube {youtube_video_id(url)}",artist=meta.get("artist","")); ref.channel=meta.get("channel",""); ref.analysis["thumbnail_url"]=meta.get("thumbnail_url",""); self.project.save(); self.url.clear(); self.host.project_changed(); self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Reference",str(exc))
    def open_youtube(self,ref):
        if not ref.youtube_url:return
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            video_id=youtube_video_id(ref.youtube_url)
            if not video_id:raise ValueError("Invalid YouTube reference")
            dialog=QDialog(self); dialog.setWindowTitle(ref.title or "YouTube Reference"); dialog.resize(900,560); layout=QVBoxLayout(dialog); view=QWebEngineView(dialog)
            html=("<!doctype html><html><body style='margin:0;background:#000'>"+f"<iframe width='100%' height='100%' src='https://www.youtube.com/embed/{video_id}?enablejsapi=1' title='YouTube reference player' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe></body></html>")
            view.setHtml(html,QUrl("https://www.youtube.com/")); layout.addWidget(view); dialog.exec()
        except Exception:QDesktopServices.openUrl(QUrl(ref.youtube_url))
    def refresh(self):
        self.table.setRowCount(0)
        if not self.project:return
        for i,ref in enumerate(self.project.references):
            self.table.insertRow(i); label=QTableWidgetItem(ref.title+(f" — {ref.artist}" if ref.artist else "")); label.setToolTip(ref.path or ref.youtube_url); self.table.setItem(i,0,label)
            weight=QSpinBox(); weight.setRange(0,100); weight.setValue(round(ref.weight*100)); weight.setSuffix("%"); weight.valueChanged.connect(lambda value,r=ref:self._weight(r,value)); self.table.setCellWidget(i,1,weight)
            for col,key in enumerate(("drums","bass","energy","arrangement","tone","stereo","master"),2):
                cb=QCheckBox(); cb.setChecked(ref.influences.get(key,True)); cb.toggled.connect(lambda value,r=ref,k=key:self._influence(r,k,value)); self.table.setCellWidget(i,col,cb)
            analysis=ref.analysis or {}; summary=", ".join(str(analysis.get(k)) for k in ("bpm_estimate","low_end","energy","stereo") if analysis.get(k) is not None) or "Not analysed"; self.table.setItem(i,9,QTableWidgetItem(summary))
            actions=QWidget(); row=QHBoxLayout(actions); row.setContentsMargins(0,0,0,0); play=QPushButton("Play"); web=QPushButton("YouTube"); rean=QPushButton("Analyse"); remove=QPushButton("Remove"); play.setEnabled(bool(ref.path)); play.clicked.connect(lambda _=False,r=ref:self.player.set_path(r.path,True)); web.setEnabled(bool(ref.youtube_url)); web.clicked.connect(lambda _=False,r=ref:self.open_youtube(r)); rean.setEnabled(bool(ref.path)); rean.clicked.connect(lambda _=False,r=ref:self.analyse(r)); remove.clicked.connect(lambda _=False,r=ref:self.remove(r))
            for b in (play,web,rean,remove):row.addWidget(b)
            self.table.setCellWidget(i,10,actions)
    def _weight(self,ref,value):ref.weight=value/100.0; self.project.normalize_reference_weights(); self.project.save(); self.host.project_changed()
    def _influence(self,ref,key,value):ref.influences[key]=value; self.project.touch(); self.project.save(); self.host.project_changed()
    def analyse(self,ref):
        try:ref.analysis=analyze_reference(ref.path).to_dict(); self.project.save(); self.refresh(); self.host.project_changed()
        except Exception as exc:QMessageBox.warning(self,"Analyse",str(exc))
    def remove(self,ref):self.project.remove_reference(ref.id); self.project.save(); self.refresh(); self.host.project_changed()


class DirectionPage(Page):
    title="Direction"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); title=QLabel("Production Direction"); title.setStyleSheet("font-size: 20px; font-weight: 700;"); group=QGroupBox("How close should the production direction be?"); form=QFormLayout(group); self.strength=QSlider(Qt.Horizontal); self.strength.setRange(0,100); self.strength.setAccessibleName("Reference production influence"); self.strength_label=QLabel(); holder=QWidget(); h=QHBoxLayout(holder); h.setContentsMargins(0,0,0,0); h.addWidget(QLabel("Original")); h.addWidget(self.strength,1); h.addWidget(QLabel("Strong reference")); h.addWidget(self.strength_label); form.addRow(holder)
        choices=QHBoxLayout(); self.checks={}
        for key,label in (("cinematic","Cinematic"),("harder","Harder"),("cleaner","Cleaner"),("darker","Darker")):
            cb=QCheckBox(label); self.checks[key]=cb; choices.addWidget(cb)
        choice_holder=QWidget(); choice_holder.setLayout(choices); form.addRow("Production choices",choice_holder); self.notes=QTextEdit(); self.notes.setPlaceholderText("Optional direction notes, e.g. sparse verses, larger chorus lift"); form.addRow("Notes",self.notes); safety=QLabel("Reference guidance uses high-level production characteristics. Do not copy the reference recording, exact beat sequence, melody/hook, or samples."); safety.setWordWrap(True); root.addWidget(title); root.addWidget(group); root.addWidget(safety); root.addStretch(); self.strength.valueChanged.connect(self.changed)
        for cb in self.checks.values():cb.toggled.connect(self.changed)
        self.notes.textChanged.connect(self.changed)
    def refresh(self):
        if not self.project:return
        d=self.project.direction; self.strength.blockSignals(True); self.strength.setValue(round(float(d.get("reference_strength",.55))*100)); self.strength.blockSignals(False); self.strength_label.setText(f"{self.strength.value()}%")
        for key,cb in self.checks.items():cb.blockSignals(True); cb.setChecked(bool(d.get(key,False))); cb.blockSignals(False)
        self.notes.blockSignals(True); self.notes.setPlainText(str(d.get("notes",""))); self.notes.blockSignals(False)
    def changed(self,*_):
        if not self.project:return
        self.strength_label.setText(f"{self.strength.value()}%"); self.project.direction["reference_strength"]=self.strength.value()/100.0
        for key,cb in self.checks.items():self.project.direction[key]=cb.isChecked()
        self.project.direction["notes"]=self.notes.toPlainText(); self.project.touch(); self.host.schedule_autosave()


class PreviewsPage(Page):
    title="Previews"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); title=QLabel("Three real previews — quality checked before Build"); title.setStyleSheet("font-size: 20px; font-weight: 700;"); bar=QHBoxLayout(); generate=QPushButton("Generate 3 Previews"); generate.setProperty("primary",True); regenerate=QPushButton("Regenerate 3"); generate.clicked.connect(self.generate); regenerate.clicked.connect(self.generate); bar.addWidget(generate); bar.addWidget(regenerate); bar.addStretch(); self.cards=QGridLayout(); self.player=AudioTransport("Preview"); root.addWidget(title); root.addLayout(bar); root.addLayout(self.cards); root.addWidget(self.player); root.addStretch()
    def _clear(self):
        while self.cards.count():
            item=self.cards.takeAt(0); w=item.widget()
            if w:w.deleteLater()
    def generate(self):
        if not self.project:return
        broker=create_broker(self.project.engine_preferences); self.host.run_task(lambda progress=None:generate_three_previews(self.project,broker,progress=progress),"Generating three previews",self._done)
    def _done(self,_result):self.host.project_changed(); self.refresh()
    def refresh(self):
        self._clear()
        if not self.project:return
        for i,p in enumerate(self.project.previews):
            box=QGroupBox(p.label); v=QVBoxLayout(box); state="PASSED QC" if p.accepted else "REJECTED BY QC"; label=QLabel(f"{state}\nEngine: {p.engine} {p.engine_version}\nSeed: {p.seed}"); label.setWordWrap(True); v.addWidget(label); checks=p.qc.get("checks",{}) if p.qc else {}; qc=QLabel("\n".join(("✓ " if ok else "✗ ")+key.replace("_"," ") for key,ok in checks.items())); v.addWidget(qc); buttons=QHBoxLayout(); together=QPushButton("Play Together"); inst=QPushButton("Instrumental"); vocal=QPushButton("Vocal Only"); select=QPushButton("Select"); together.clicked.connect(lambda _=False,x=p:self.player.set_path(x.audio_path,True)); inst.clicked.connect(lambda _=False,x=p:self.player.set_path(x.instrumental_path,True)); vocal.clicked.connect(lambda _=False,x=p:self.player.set_path(x.vocal_path,True)); select.setEnabled(p.accepted); select.clicked.connect(lambda _=False,x=p:self.select(x))
            for b in (together,inst,vocal,select):buttons.addWidget(b)
            v.addLayout(buttons); self.cards.addWidget(box,0,i)
    def select(self,preview):self.project.selected_preview_id=preview.id; self.project.save(); self.host.project_changed(); QMessageBox.information(self,"Preview",f"Selected {preview.label}.")


class BuildPage(Page):
    title="Build"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); title=QLabel("Build — extend the selected accepted preview to the full arrangement"); title.setStyleSheet("font-size:20px;font-weight:700;"); self.status=QLabel("No build yet"); self.status.setWordWrap(True); go=QPushButton("Build Full Song"); go.setProperty("primary",True); go.clicked.connect(self.build); self.player=AudioTransport("Build"); root.addWidget(title); root.addWidget(self.status); root.addWidget(go); root.addWidget(self.player); root.addStretch()
    def build(self):
        if not self.project:return
        broker=create_broker(self.project.engine_preferences); self.host.run_task(lambda progress=None:build_from_preview(self.project,broker,progress=progress),"Building full song",self._done)
    def _done(self,_):self.host.project_changed(); self.refresh()
    def refresh(self):
        if not self.project:return
        b=self.project.selected_build()
        if not b:self.status.setText("Select a QC-passed preview first, then build."); return
        self.status.setText(f"{b.label}\nEngine: {b.engine} {b.engine_version}\nGenerated stems: {', '.join(s.role for s in b.stems)}\nCreated: {b.created_at}"); self.player.set_path(b.mix_path)


class MasterPage(Page):
    title="Master"
    def __init__(self,host):
        super().__init__(host); root=QVBoxLayout(self); title=QLabel("Master"); title.setStyleSheet("font-size:20px;font-weight:700;"); form=QFormLayout(); self.lufs=QDoubleSpinBox(); self.lufs.setRange(-24,-5); self.lufs.setValue(-14); self.lufs.setSuffix(" LUFS"); self.tp=QDoubleSpinBox(); self.tp.setRange(-6,-.1); self.tp.setValue(-1); self.tp.setSuffix(" dBTP"); form.addRow("Target loudness",self.lufs); form.addRow("True peak",self.tp); go=QPushButton("Master Selected Build"); go.setProperty("primary",True); go.clicked.connect(self.master); self.result=QLabel("No master yet"); self.player=AudioTransport("Master"); root.addWidget(title); root.addLayout(form); root.addWidget(go); root.addWidget(self.result); root.addWidget(self.player); root.addStretch()
    def master(self):
        if self.project:self.host.run_task(lambda progress=None:master_selected_build(self.project,self.lufs.value(),self.tp.value()),"Mastering",self._done,inject_progress=False)
    def _done(self,_):self.host.project_changed(); self.refresh()
    def refresh(self):
        if not self.project:return
        m=self.project.selected_master()
        if not m:self.result.setText("Build a song before mastering."); return
        self.result.setText(f"Engine: {m.engine}\nMeasurements: {m.measurements}\nTarget: {m.target_lufs} LUFS, {m.target_true_peak} dBTP"); self.player.set_path(m.path)
