from pathlib import Path
import json
import numpy as np
import pytest
from drellion.audio_core import write_wav
from drellion.autosave import newer_autosave,write_autosave
from drellion.project import ProjectState
from drellion.versions import create_snapshot

def make_wav(path:Path,seconds:float=1.0,sr:int=8000):
    t=np.arange(int(seconds*sr))/sr; x=(0.2*np.sin(2*np.pi*220*t)).astype(np.float32); write_wav(path,x,sr)

def test_project_layout_roundtrip_and_limits(tmp_path):
    source=tmp_path/"vocal.wav"; ref=tmp_path/"ref.wav"; make_wav(source); make_wav(ref); project=ProjectState.create(tmp_path/"projects","Song","Artist")
    for folder in ("Sources","References","Stems","Generated","Previews","Masters","Exports","Autosaves","Versions"):assert project.folder(folder).is_dir()
    asset=project.add_source(source); reference=project.add_reference(ref); assert Path(asset.path).parent==project.folder("Sources"); assert Path(reference.path).parent==project.folder("References"); project.save(); loaded=ProjectState.load(project.project_file); assert loaded.title=="Song"; assert len(loaded.sources)==1
    for i in range(5):loaded.add_source(source,label=f"s{i}")
    with pytest.raises(ValueError):loaded.add_source(source)
    for i in range(5):loaded.add_reference(ref,title=f"r{i}")
    with pytest.raises(ValueError):loaded.add_reference(ref)

def test_remove_consolidate_save_copy_snapshot(tmp_path):
    source=tmp_path/"outside.wav"; make_wav(source); project=ProjectState.create(tmp_path/"projects","Song",keep_imported_files=False); item=project.add_source(source); assert Path(item.path)==source; counts=project.consolidate_imported_media(); assert counts["sources"]==1; assert Path(project.sources[0].path).parent==project.folder("Sources"); assert project.remove_source(item.id); copy=project.save_copy(tmp_path/"backup.drellion"); assert copy.exists(); snapshot=create_snapshot(project,"Before chorus"); assert snapshot.exists()

def test_autosave_only_reports_real_changes(tmp_path):
    project=ProjectState.create(tmp_path/"projects","Song"); project.save(); recovery=write_autosave(project); recovery.touch(); assert newer_autosave(project.project_file) is None; payload=json.loads(recovery.read_text()); payload["title"]="Unsaved title"; recovery.write_text(json.dumps(payload)); recovery.touch(); assert newer_autosave(project.project_file)==recovery
