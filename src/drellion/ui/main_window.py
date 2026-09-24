from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool,QTimer,Qt,QUrl
from PySide6.QtGui import QAction,QDesktopServices,QKeySequence
from PySide6.QtWidgets import (
    QApplication,QFileDialog,QHBoxLayout,QLabel,QListWidget,QMainWindow,QMessageBox,
    QProgressBar,QPushButton,QStackedWidget,QStatusBar,QVBoxLayout,QWidget,QInputDialog,
)

from ..accessibility import AccessibilitySettings
from ..autosave import clear_autosave,load_autosave,newer_autosave,write_autosave
from ..project import PROJECT_FILENAME,ProjectState
from ..storage import load_storage_settings
from ..versions import create_snapshot
from .auto_pages import BuildPage,DirectionPage,MasterPage,PreviewsPage,ProjectPage,ReferencesPage,SourcesPage
from .dialogs import AccessibilityDialog,NewProjectDialog
from .studio import StudioPage
from .utility_pages import EnginesPage,ExportPage,HealthPage,LibraryPage,LyricsPage,ProjectFilesPage,StoragePage,VersionsPage
from .worker import Worker


class HomePage(QWidget):
    def __init__(self,host):
        super().__init__(); self.host=host; root=QVBoxLayout(self); root.setContentsMargins(40,30,40,30)
        title=QLabel("DRELLION NEXUS 2.0"); title.setStyleSheet("font-size:30px;font-weight:800;")
        subtitle=QLabel("Give Drellion your voice and production references. Build an original, editable production around your performance."); subtitle.setWordWrap(True); subtitle.setStyleSheet("font-size:15px;")
        buttons=QHBoxLayout(); vocal=QPushButton("CREATE FROM VOCAL\nBuild a new production around my voice"); rework=QPushButton("REWORK A SONG\nRebuild or transform an existing song"); studio=QPushButton("OPEN STUDIO\nStart an empty multitrack project")
        for b in (vocal,rework,studio):b.setMinimumHeight(84); buttons.addWidget(b)
        vocal.clicked.connect(lambda:host.new_project("Vocal / Acapella")); rework.clicked.connect(lambda:host.new_project("Full Song")); studio.clicked.connect(lambda:host.new_project("Empty Studio"))
        recent_label=QLabel("Recent Projects"); recent_label.setStyleSheet("font-size:20px;font-weight:700;"); self.recent=QListWidget(); self.recent.itemDoubleClicked.connect(lambda item:host.open_project_path(Path(item.data(Qt.UserRole)))); open_btn=QPushButton("Open Existing Project"); open_btn.clicked.connect(host.open_project)
        root.addWidget(title); root.addWidget(subtitle); root.addSpacing(10); root.addLayout(buttons); root.addSpacing(20); root.addWidget(recent_label); root.addWidget(self.recent,1); root.addWidget(open_btn)
    def refresh(self):
        self.recent.clear(); root=Path(load_storage_settings().projects)
        if not root.exists():return
        candidates=[]
        try:
            for p in root.glob(f"*/{PROJECT_FILENAME}"):
                try:candidates.append((p.stat().st_mtime,p))
                except OSError:pass
        except OSError:return
        for _mtime,p in sorted(candidates,reverse=True)[:30]:
            try:
                project=ProjectState.load(p); text=f"{project.title}  ·  {project.artist or 'Untitled artist'}  ·  {len(project.sources)} source(s)  ·  {len(project.builds)} build(s)"
            except Exception:text=p.parent.name
            from PySide6.QtWidgets import QListWidgetItem
            item=QListWidgetItem(text); item.setData(Qt.UserRole,str(p)); self.recent.addItem(item)


class MainWindow(QMainWindow):
    NAV=["Home","Project","Sources","References","Direction","Previews","Build","Master","Studio","Library","Export","Versions","Project Files","Lyrics & Timing","AI Engines","Project Health","Storage"]
    def __init__(self,accessibility:AccessibilitySettings|None=None):
        super().__init__(); self.accessibility=accessibility or AccessibilitySettings(); self.project:ProjectState|None=None; self.thread_pool=QThreadPool.globalInstance(); self.current_worker:Worker|None=None; self._autosave_pending=False
        self.setWindowTitle("Drellion Nexus 2.0"); self.resize(1500,900); self.setAcceptDrops(True); self._build_ui(); self._build_menu(); self._build_status(); self._periodic=QTimer(self); self._periodic.timeout.connect(self.autosave); self._periodic.start(120_000); self.home.refresh(); self._set_project_enabled(False); self._decorate_accessibility(self)

    def _build_ui(self):
        central=QWidget(); root=QVBoxLayout(central); root.setContentsMargins(0,0,0,0)
        header=QWidget(); hh=QHBoxLayout(header); hh.setContentsMargins(12,8,12,8); self.project_label=QLabel("Drellion Nexus 2.0"); self.project_label.setStyleSheet("font-size:17px;font-weight:700;"); auto=QPushButton("AI AUTO"); auto.clicked.connect(lambda:self.navigate("Sources")); studio=QPushButton("STUDIO"); studio.clicked.connect(lambda:self.navigate("Studio")); access=QPushButton("♿ Accessibility"); access.clicked.connect(self.open_accessibility); folder=QPushButton("📁 Open Project Folder"); folder.clicked.connect(self.open_project_folder); hh.addWidget(self.project_label); hh.addStretch(); hh.addWidget(auto); hh.addWidget(studio); hh.addWidget(folder); hh.addWidget(access)
        body=QWidget(); bh=QHBoxLayout(body); bh.setContentsMargins(0,0,0,0); self.nav=QListWidget(); self.nav.setFixedWidth(190); self.nav.addItems(self.NAV); self.nav.currentTextChanged.connect(self.navigate); self.stack=QStackedWidget(); self.pages={}; self.home=HomePage(self); self.pages["Home"]=self.home; self.stack.addWidget(self.home)
        for cls in (ProjectPage,SourcesPage,ReferencesPage,DirectionPage,PreviewsPage,BuildPage,MasterPage,StudioPage,LibraryPage,ExportPage,VersionsPage,ProjectFilesPage,LyricsPage,EnginesPage,HealthPage,StoragePage):
            page=cls(self); self.pages[page.title]=page; self.stack.addWidget(page)
        bh.addWidget(self.nav); bh.addWidget(self.stack,1); root.addWidget(header); root.addWidget(body,1); self.setCentralWidget(central); self.nav.setCurrentRow(0)

    def _build_menu(self):
        file=self.menuBar().addMenu("&File"); actions=[("New Project",QKeySequence.New,lambda:self.new_project()),("Open Project",QKeySequence.Open,self.open_project),("Save",QKeySequence.Save,self.save_project),("Save As",QKeySequence.SaveAs,self.save_as),("Save Copy",None,self.save_copy),("Snapshot",None,self.snapshot),("Consolidate Imported Media",None,self.consolidate),("Open Project Folder",None,self.open_project_folder),("Exit",QKeySequence.Quit,self.close)]
        for text,shortcut,slot in actions:
            action=QAction(text,self); action.triggered.connect(slot)
            if shortcut:action.setShortcut(shortcut)
            file.addAction(action)
        edit=self.menuBar().addMenu("&Navigate")
        for name in self.NAV:
            action=QAction(name,self); action.triggered.connect(lambda _=False,n=name:self.navigate(n)); edit.addAction(action)
        help_menu=self.menuBar().addMenu("&Help"); about=QAction("About Drellion Nexus 2.0",self); about.triggered.connect(lambda:QMessageBox.information(self,"About","Drellion Nexus 2.0\nVocal-first, reference-guided, editable music production.")); help_menu.addAction(about)

    def _build_status(self):
        status=QStatusBar(); self.setStatusBar(status); self.task_label=QLabel("Ready"); self.progress=QProgressBar(); self.progress.setRange(0,0); self.progress.setMaximumWidth(220); self.progress.hide(); self.cancel=QPushButton("Cancel"); self.cancel.hide(); self.cancel.clicked.connect(self.cancel_task); status.addWidget(self.task_label,1); status.addPermanentWidget(self.progress); status.addPermanentWidget(self.cancel)

    def _decorate_accessibility(self,widget):
        from PySide6.QtWidgets import QAbstractButton,QLabel,QLineEdit,QComboBox,QAbstractSpinBox,QAbstractSlider
        for child in widget.findChildren(QWidget):
            if child.accessibleName():continue
            name=""
            if isinstance(child,QAbstractButton):name=child.text().replace("&","")
            elif isinstance(child,QLabel):name=child.text()
            elif isinstance(child,QLineEdit):name=child.placeholderText()
            elif isinstance(child,QComboBox):name="Choice"
            elif isinstance(child,QAbstractSpinBox):name="Numeric value"
            elif isinstance(child,QAbstractSlider):name="Slider"
            if name:child.setAccessibleName(name[:160])

    def _set_project_enabled(self,enabled):
        for i,name in enumerate(self.NAV):
            item=self.nav.item(i); item.setHidden(False); item.setFlags(item.flags()|Qt.ItemIsEnabled if enabled or name in {"Home","Storage"} else item.flags()&~Qt.ItemIsEnabled)

    def navigate(self,name):
        if name not in self.pages:return
        if name not in {"Home","Storage"} and not self.project:return
        page=self.pages[name]; self.stack.setCurrentWidget(page)
        for i in range(self.nav.count()):
            if self.nav.item(i).text()==name:self.nav.blockSignals(True); self.nav.setCurrentRow(i); self.nav.blockSignals(False); break
        if hasattr(page,"refresh"):page.refresh()

    def new_project(self,preset_mode=None):
        dialog=NewProjectDialog(self)
        if preset_mode:dialog.mode.setCurrentText(preset_mode)
        if not dialog.exec():return
        v=dialog.values()
        try:
            project=ProjectState.create(v["parent"],v["title"],v["artist"],v["mode"],v["keep"]); project.autosave_seconds=v["autosave_seconds"]; project.save(); self.set_project(project); self.navigate("Studio" if v["mode"]=="Empty Studio" else "Sources")
        except Exception as exc:QMessageBox.critical(self,"New Project",str(exc))

    def open_project(self):
        settings=load_storage_settings(); path,_=QFileDialog.getOpenFileName(self,"Open Drellion Project",settings.projects,"Drellion Project (*.drellion);;All files (*)")
        if path:self.open_project_path(Path(path))

    def open_project_path(self,path):
        try:
            recovery=newer_autosave(path)
            if recovery:
                box=QMessageBox(self); box.setWindowTitle("Recovery Found"); box.setText("Drellion found a newer recovery version."); recover=box.addButton("Recover Autosave",QMessageBox.AcceptRole); box.addButton("Open Last Saved",QMessageBox.RejectRole); box.exec()
                if box.clickedButton()==recover:project=load_autosave(recovery); project.root=str(path.parent)
                else:project=ProjectState.load(path)
            else:project=ProjectState.load(path)
            self.set_project(project); self.navigate("Project")
        except Exception as exc:QMessageBox.critical(self,"Open Project",str(exc))

    def set_project(self,project):
        self.project=project; project.ensure_layout(); self.project_label.setText(f"{project.title} — {project.artist or 'Untitled artist'}"); self._periodic.setInterval(max(30,project.autosave_seconds)*1000); self._set_project_enabled(True); self.project_changed()

    def project_changed(self):
        if not self.project:return
        for page in self.pages.values():
            if page is self.stack.currentWidget() and hasattr(page,"refresh"):page.refresh()
        self.home.refresh(); self.schedule_autosave()

    def schedule_autosave(self):
        if not self.project or self._autosave_pending:return
        self._autosave_pending=True
        def later():self._autosave_pending=False; self.autosave()
        QTimer.singleShot(1500,later)
    def autosave(self):
        if self.project:
            try:write_autosave(self.project)
            except Exception:pass
    def save_project(self):
        if not self.project:return
        try:self.project.save(); clear_autosave(self.project); self.task_label.setText("Saved")
        except Exception as exc:QMessageBox.critical(self,"Save",str(exc))
    def save_as(self):
        if not self.project:return
        folder=QFileDialog.getExistingDirectory(self,"Save As — choose new project folder")
        if not folder:return
        try:self.set_project(self.project.save_as(folder)); self.navigate("Project")
        except Exception as exc:QMessageBox.critical(self,"Save As",str(exc))
    def save_copy(self):
        if not self.project:return
        path,_=QFileDialog.getSaveFileName(self,"Save Copy",str(self.project.root_path/f"{self.project.title}-Copy.drellion"),"Drellion Project (*.drellion)")
        if path:self.project.save_copy(path)
    def snapshot(self):
        if not self.project:return
        name,ok=QInputDialog.getText(self,"Snapshot","Snapshot name")
        if ok:create_snapshot(self.project,name or "Snapshot"); self.pages["Versions"].refresh()
    def consolidate(self):
        if not self.project:return
        counts=self.project.consolidate_imported_media(); self.project.save(); QMessageBox.information(self,"Consolidate",f"Copied {counts['sources']} source(s) and {counts['references']} reference(s).")
    def open_project_folder(self):
        if self.project:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.project.root_path.resolve())))
    def open_accessibility(self):
        AccessibilityDialog(QApplication.instance(),self.accessibility,self).exec(); self._decorate_accessibility(self)

    def run_task(self,fn,label,on_done=None,inject_progress=True):
        if self.current_worker:QMessageBox.information(self,"Drellion","Another task is already running."); return
        worker=Worker(fn,inject_progress=inject_progress); self.current_worker=worker; self.task_label.setText(label); self.progress.show(); self.cancel.show(); self.cancel.setEnabled(True); worker.signals.progress.connect(self.task_label.setText)
        def finish(result):
            self.current_worker=None; self.progress.hide(); self.cancel.hide(); self.task_label.setText("Ready")
            if on_done:on_done(result)
        def error(message):
            self.current_worker=None; self.progress.hide(); self.cancel.hide(); self.task_label.setText("Cancelled" if message=="Cancelled" else "Task failed")
            if message=="Cancelled":
                return
            if "No production AI engine is ready" in message:
                box=QMessageBox(self); box.setIcon(QMessageBox.Critical); box.setWindowTitle("AI Engine Required")
                box.setText(message); box.setInformativeText("Start ACE-Step or DiffRhythm, then configure it in AI Engines. For local ACE-Step, the default endpoint is http://127.0.0.1:8001.")
                setup=box.addButton("Open AI Engines",QMessageBox.ActionRole); box.addButton("Close",QMessageBox.RejectRole); box.exec()
                if box.clickedButton()==setup:self.navigate("AI Engines")
            else:
                QMessageBox.critical(self,"Drellion",message)
        worker.signals.finished.connect(finish); worker.signals.error.connect(error); self.thread_pool.start(worker)
    def cancel_task(self):
        if self.current_worker:self.current_worker.cancel(); self.cancel.setEnabled(False); self.task_label.setText("Cancellation requested…")
    def closeEvent(self,event):
        if self.project:
            try:write_autosave(self.project)
            except Exception:pass
        super().closeEvent(event)
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls():event.acceptProposedAction()
    def dropEvent(self,event):
        paths=[Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        for p in paths:
            if p.suffix.lower()==".drellion":self.open_project_path(p);return
        if self.project:
            for p in paths:
                if p.is_file():
                    try:self.project.add_source(p,role="Other")
                    except Exception:break
            self.project.save(); self.project_changed(); self.navigate("Sources")
