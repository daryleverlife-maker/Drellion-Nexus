from pathlib import Path
import shutil
import numpy as np
from drellion.audio_core import write_wav
from drellion.export_v2 import ExportOptions,export_project
from drellion.master_v2 import master_wav
from drellion.production_v2 import direction_prompt,representative_preview_region
from drellion.project import BuildRecord,GeneratedStem,MasterRecord,ProjectState

def make_wav(path:Path,seconds=4,sr=8000):
    t=np.arange(int(seconds*sr),dtype=np.float32)/sr; signal=0.15*np.sin(2*np.pi*70*t); signal+=0.08*np.sin(2*np.pi*220*t); write_wav(path,signal.astype(np.float32),sr)

def test_direction_and_preview_region(tmp_path):
    vocal=tmp_path/"vocal.wav"; make_wav(vocal,40); project=ProjectState.create(tmp_path/"p","Song"); project.add_source(vocal); project.direction["cinematic"]=True; project.direction["notes"]="sparse verse, large chorus"; prompt=direction_prompt(project); assert "cinematic" in prompt; assert "Do not reproduce exact melodies" in prompt; start,duration=representative_preview_region(project,25); assert 0<=start<=15; assert 20<=duration<=25

def test_master_and_export(tmp_path):
    source=tmp_path/"mix.wav"; make_wav(source); project=ProjectState.create(tmp_path/"p","Song","Artist"); generated=project.folder("Generated")/"mix.wav"; shutil.copy2(source,generated); build=BuildRecord(label="Build 01",mix_path=str(generated),instrumental_path=str(generated),stems=[GeneratedStem(role="Instrumental",path=str(generated))]); project.builds.append(build); project.selected_build_id=build.id; master_path,engine,measurements=master_wav(generated,project.folder("Masters")/"master.wav"); assert master_path.exists(); master=MasterRecord(source_build_id=build.id,path=str(master_path),engine=engine,measurements=measurements.to_dict()); project.masters.append(master); project.selected_master_id=master.id; result=export_project(project,project.folder("Exports"),ExportOptions(mp3=False,lyrics_lrc=False,lyrics_srt=False)); assert any(p.suffix==".wav" for p in result.files); assert any("metadata" in p.name for p in result.files)
