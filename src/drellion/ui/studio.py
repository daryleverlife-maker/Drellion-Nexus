from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGraphicsItem,
    QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView, QGroupBox, QHBoxLayout,
    QLabel, QListWidget, QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from ..audio_core import read_wav
from ..project import StudioClip
from ..studio_model import add_clip, add_track, clip as find_clip, duplicate_clip, move_clip, remove_clip, set_fades, split_clip, trim_clip
from .common import AudioTransport, Page


class ClipItem(QGraphicsRectItem):
    def __init__(self, clip: StudioClip, rect: QRectF, locked_y: float, moved_callback, selected_callback):
        super().__init__(rect)
        self.locked_y = float(locked_y); self.clip_id = clip.id; self.moved_callback = moved_callback; self.selected_callback = selected_callback
        self.setBrush(QBrush(QColor(46,125,186))); self.setPen(QPen(QColor(166,215,248)))
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        self.setToolTip(f"{clip.label}\n{clip.source_path}")
        label=QGraphicsTextItem(clip.label,self); label.setDefaultTextColor(QColor("white")); label.setPos(4,2)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            p=value; p.setY(self.locked_y); p.setX(max(0.0,round(p.x()/10.0)*10.0)); return p
        if change == QGraphicsItem.ItemSelectedHasChanged and bool(value): self.selected_callback(self.clip_id)
        return super().itemChange(change,value)

    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event); self.moved_callback(self.clip_id,self.pos().x())


class TimelineView(QGraphicsView):
    px_per_second=20.0; track_height=62.0
    def __init__(self,studio):
        super().__init__(); self.studio=studio; self.scene_=QGraphicsScene(self); self.setScene(self.scene_)
        self.setAccessibleName("Multitrack timeline"); self.setMinimumHeight(300); self.setDragMode(QGraphicsView.RubberBandDrag)

    def rebuild(self):
        self.scene_.clear(); project=self.studio.project
        if not project:return
        max_seconds=60.0
        for ti,track in enumerate(project.studio_tracks):
            y=ti*self.track_height; self.scene_.addText(track.name).setPos(0,y)
            self.scene_.addLine(0,y+self.track_height-2,2000,y+self.track_height-2,QPen(QColor(70,80,95)))
            for c in track.clips:
                duration=max(c.duration_seconds,2.0); x=c.start_seconds*self.px_per_second+120; width=max(40,duration*self.px_per_second)
                item=ClipItem(c,QRectF(0,0,width,self.track_height-12),y+4,self._moved,self.studio.select_clip); item.setPos(x,y+4); self.scene_.addItem(item)
                max_seconds=max(max_seconds,c.start_seconds+duration)
        for sec in range(0,int(max_seconds)+1,5):
            x=sec*self.px_per_second+120
            self.scene_.addLine(x,0,x,max(100,len(project.studio_tracks)*self.track_height),QPen(QColor(52,60,72)))
            label=self.scene_.addText(f"{sec}s"); label.setPos(x+2,-22)
        self.scene_.setSceneRect(0,-25,max_seconds*self.px_per_second+180,max(340,len(project.studio_tracks)*self.track_height+40))

    def _moved(self,clip_id,scene_x):
        seconds=max(0.0,(scene_x-120.0)/self.px_per_second)
        try: move_clip(self.studio.project,clip_id,seconds); self.studio.save_and_refresh(False)
        except Exception:self.rebuild()


class StudioPage(Page):
    title="Studio"
    def __init__(self,host):
        super().__init__(host); self.selected_clip_id=""; root=QVBoxLayout(self); transport_row=QHBoxLayout()
        title=QLabel("STUDIO"); title.setStyleSheet("font-size: 20px; font-weight: 700;")
        add_track_btn=QPushButton("+ Track"); add_audio_btn=QPushButton("+ Audio Clip"); duplicate_btn=QPushButton("Duplicate Clip"); split_btn=QPushButton("Split at Midpoint"); remove_btn=QPushButton("Remove Clip")
        for w in (title,add_track_btn,add_audio_btn,duplicate_btn,split_btn,remove_btn): transport_row.addWidget(w)
        transport_row.addStretch(); add_track_btn.clicked.connect(self.add_track_action); add_audio_btn.clicked.connect(self.add_audio_action); duplicate_btn.clicked.connect(self.duplicate); split_btn.clicked.connect(self.split); remove_btn.clicked.connect(self.remove); root.addLayout(transport_row)
        self.transport=AudioTransport("Studio audition"); root.addWidget(self.transport)
        main_split=QSplitter(Qt.Horizontal); left=QWidget(); left_l=QVBoxLayout(left); left_l.addWidget(QLabel("LIBRARY")); self.browser=QListWidget(); left_l.addWidget(self.browser)
        self.timeline=TimelineView(self); inspector=QGroupBox("INSPECTOR"); form=QFormLayout(inspector); self.clip_name=QLabel("No clip selected")
        self.start=QDoubleSpinBox(); self.start.setRange(0,36000); self.start.setSuffix(" s"); self.offset=QDoubleSpinBox(); self.offset.setRange(0,36000); self.offset.setSuffix(" s"); self.duration=QDoubleSpinBox(); self.duration.setRange(0,36000); self.duration.setSuffix(" s"); self.gain=QDoubleSpinBox(); self.gain.setRange(-60,24); self.gain.setSuffix(" dB"); self.fade_in=QDoubleSpinBox(); self.fade_in.setRange(0,60); self.fade_in.setSuffix(" s"); self.fade_out=QDoubleSpinBox(); self.fade_out.setRange(0,60); self.fade_out.setSuffix(" s"); self.crossfade=QDoubleSpinBox(); self.crossfade.setRange(0,60); self.crossfade.setSuffix(" s"); self.track_combo=QComboBox()
        apply_btn=QPushButton("Apply Clip Changes"); left_btn=QPushButton("Move Left 1s"); right_btn=QPushButton("Move Right 1s"); move_buttons=QWidget(); mh=QHBoxLayout(move_buttons); mh.setContentsMargins(0,0,0,0); mh.addWidget(left_btn); mh.addWidget(right_btn)
        for label,widget in (("Clip",self.clip_name),("Track",self.track_combo),("Start",self.start),("Source offset",self.offset),("Duration",self.duration),("Clip gain",self.gain),("Fade in",self.fade_in),("Fade out",self.fade_out),("Crossfade",self.crossfade)): form.addRow(label,widget)
        form.addRow(move_buttons); form.addRow(apply_btn); apply_btn.clicked.connect(self.apply_clip); left_btn.clicked.connect(lambda:self.nudge(-1)); right_btn.clicked.connect(lambda:self.nudge(1))
        main_split.addWidget(left); main_split.addWidget(self.timeline); main_split.addWidget(inspector); main_split.setSizes([190,760,260]); root.addWidget(main_split,1)
        mixer_box=QGroupBox("MIXER"); ml=QVBoxLayout(mixer_box); self.mixer=QTableWidget(0,5); self.mixer.setHorizontalHeaderLabels(["Track","Volume dB","Pan","Mute","Solo"]); self.mixer.horizontalHeader().setStretchLastSection(True); self.mixer.setSelectionBehavior(QAbstractItemView.SelectRows); ml.addWidget(self.mixer); root.addWidget(mixer_box)

    def refresh(self):
        self.browser.clear(); self.track_combo.clear(); self.mixer.setRowCount(0)
        if not self.project:self.timeline.rebuild(); return
        for s in self.project.sources:self.browser.addItem(f"Source · {s.role} · {s.label}")
        b=self.project.selected_build()
        if b:
            for s in b.stems:self.browser.addItem(f"Generated · {s.role}")
        for i,t in enumerate(self.project.studio_tracks):
            self.track_combo.addItem(t.name,t.id); self.mixer.insertRow(i); self.mixer.setItem(i,0,QTableWidgetItem(t.name))
            vol=QDoubleSpinBox(); vol.setRange(-60,24); vol.setValue(t.volume_db); vol.setSuffix(" dB"); vol.valueChanged.connect(lambda v,tr=t:self._track_set(tr,"volume_db",v)); self.mixer.setCellWidget(i,1,vol)
            pan=QDoubleSpinBox(); pan.setRange(-1,1); pan.setSingleStep(.05); pan.setValue(t.pan); pan.valueChanged.connect(lambda v,tr=t:self._track_set(tr,"pan",v)); self.mixer.setCellWidget(i,2,pan)
            mute=QPushButton("Muted" if t.mute else "Mute"); mute.setCheckable(True); mute.setChecked(t.mute); mute.toggled.connect(lambda v,b=mute,tr=t:self._track_toggle(tr,"mute",v,b)); self.mixer.setCellWidget(i,3,mute)
            solo=QPushButton("Soloed" if t.solo else "Solo"); solo.setCheckable(True); solo.setChecked(t.solo); solo.toggled.connect(lambda v,b=solo,tr=t:self._track_toggle(tr,"solo",v,b)); self.mixer.setCellWidget(i,4,solo)
        self.timeline.rebuild()
        if self.selected_clip_id:
            try:self._load_inspector()
            except KeyError:self.selected_clip_id=""; self.clip_name.setText("No clip selected")

    def _track_set(self,t,field,value):setattr(t,field,value); self.save_and_refresh(False)
    def _track_toggle(self,t,field,value,button):setattr(t,field,value); button.setText(("Muted" if field=="mute" else "Soloed") if value else ("Mute" if field=="mute" else "Solo")); self.save_and_refresh(False)
    def save_and_refresh(self,refresh=True):
        self.project.touch(); self.host.schedule_autosave()
        if refresh:self.refresh()
    def add_track_action(self):
        if self.project:add_track(self.project,f"Track {len(self.project.studio_tracks)+1}"); self.save_and_refresh()
    def add_audio_action(self):
        if not self.project:return
        if not self.project.studio_tracks:add_track(self.project,"Audio")
        path,_=QFileDialog.getOpenFileName(self,"Add audio clip","","Audio (*.wav *.mp3 *.flac *.m4a);;All files (*)")
        if not path:return
        duration=0.0
        if Path(path).suffix.lower()==".wav":
            try:duration=read_wav(path).duration
            except Exception:pass
        add_clip(self.project,self.project.studio_tracks[0].id,path,Path(path).stem,duration_seconds=duration); self.save_and_refresh()
    def select_clip(self,clip_id):
        self.selected_clip_id=clip_id; self._load_inspector()
        try:_t,c=find_clip(self.project,clip_id); self.transport.set_path(c.source_path)
        except Exception:pass
    def _load_inspector(self):
        t,c=find_clip(self.project,self.selected_clip_id); self.clip_name.setText(c.label); idx=self.track_combo.findData(t.id); self.track_combo.setCurrentIndex(max(0,idx)); self.start.setValue(c.start_seconds); self.offset.setValue(c.source_offset_seconds); self.duration.setValue(c.duration_seconds); self.gain.setValue(c.gain_db); self.fade_in.setValue(c.fade_in_seconds); self.fade_out.setValue(c.fade_out_seconds); self.crossfade.setValue(c.crossfade_seconds)
    def apply_clip(self):
        if not self.selected_clip_id:return
        try:
            _t,c=find_clip(self.project,self.selected_clip_id); move_clip(self.project,c.id,self.start.value(),self.track_combo.currentData()); trim_clip(self.project,c.id,self.offset.value(),self.duration.value()); _t,c=find_clip(self.project,c.id); c.gain_db=self.gain.value(); set_fades(self.project,c.id,self.fade_in.value(),self.fade_out.value(),self.crossfade.value()); self.save_and_refresh()
        except Exception as exc:QMessageBox.warning(self,"Studio",str(exc))
    def nudge(self,seconds):
        if not self.selected_clip_id:return
        _t,c=find_clip(self.project,self.selected_clip_id); move_clip(self.project,c.id,max(0,c.start_seconds+seconds)); self.save_and_refresh()
    def duplicate(self):
        if not self.selected_clip_id:return
        clone=duplicate_clip(self.project,self.selected_clip_id,0.25); self.selected_clip_id=clone.id; self.save_and_refresh()
    def split(self):
        if not self.selected_clip_id:return
        try:
            _t,c=find_clip(self.project,self.selected_clip_id)
            if c.duration_seconds<=0:raise ValueError("Set clip duration before splitting")
            _left,right=split_clip(self.project,c.id,c.start_seconds+c.duration_seconds/2); self.selected_clip_id=right.id; self.save_and_refresh()
        except Exception as exc:QMessageBox.warning(self,"Studio",str(exc))
    def remove(self):
        if not self.selected_clip_id:return
        remove_clip(self.project,self.selected_clip_id); self.selected_clip_id=""; self.save_and_refresh()
