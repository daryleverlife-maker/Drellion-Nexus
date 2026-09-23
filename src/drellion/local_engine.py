from __future__ import annotations

from pathlib import Path
import json
import numpy as np

from .audio.analysis import analyze_reference_file,analyze_vocal_file
from .audio.contracts import ArrangementPreview
from .audio.generator import generate_original_arrangement,write_arrangement,SR
from .audio.mix import load_stereo,mix_vocal_instrumental,loudness_master,write_audio
from .engine import BuildResult
from .project import ProjectState

class LocalNexusEngine:
    def analyze_vocal(self,state:ProjectState):
        if not state.vocal.path: raise ValueError("Choose a vocal stem first.")
        return analyze_vocal_file(state.vocal.path)

    def analyze_reference(self,state:ProjectState):
        if not state.reference.path: raise ValueError("Choose a reference track first.")
        return analyze_reference_file(state.reference.path)

    def _analyses(self,state:ProjectState):
        return self.analyze_vocal(state),self.analyze_reference(state)

    def generate_previews(self,state:ProjectState,output_dir:str|Path):
        vocal_analysis,ref=self._analyses(state)
        vocal=load_stereo(state.vocal.path)
        start=vocal_analysis.phrase_regions[0][0] if vocal_analysis.phrase_regions else 0.0
        start=max(0.0,min(start,max(0.0,vocal_analysis.duration-24.0)))
        preview_len=min(24.0,max(8.0,vocal_analysis.duration-start))
        a=int(start*SR); b=min(len(vocal),a+int(preview_len*SR))
        vocal_seg=vocal[a:b]
        out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
        previews=[]
        for variant,name in enumerate(("A","B","C")):
            arr=generate_original_arrangement(vocal_analysis,ref,preview_len,variant=variant)
            mix=mix_vocal_instrumental(vocal_seg,arr.stereo[:len(vocal_seg)],1.0,0.72)
            p=write_audio(out/f"preview-{name}.wav",mix)
            previews.append(ArrangementPreview(name=f"Preview {name}",audio_path=str(p),description=f"Original arrangement variant {name} at {arr.bpm:.1f} BPM"))
        return previews

    def build(self,state:ProjectState,output_dir:str|Path)->BuildResult:
        vocal_analysis,ref=self._analyses(state)
        vocal=load_stereo(state.vocal.path)
        duration=max(vocal_analysis.duration,float(len(vocal)/SR))+2.0
        variant={"Preview A":0,"Preview B":1,"Preview C":2}.get(state.selected_preview,0)
        arr=generate_original_arrangement(vocal_analysis,ref,duration,variant=variant)
        out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
        inst=write_arrangement(out/"instrumental.wav",arr)
        build=mix_vocal_instrumental(vocal,arr.stereo,1.0,0.72)
        build_path=write_audio(out/"build.wav",build)
        report={
            "bpm":arr.bpm,
            "root_pitch_class":arr.root_pc,
            "reference_bpm":ref.bpm,
            "reference_lufs":ref.dynamics.get("lufs"),
            "reference_audio_copied":False,
            "generation_policy":"Vocal pitch/phrasing + broad reference production descriptors; independent progression and exact drum events."
        }
        rp=out/"build-report.json"; rp.write_text(json.dumps(report,indent=2),encoding="utf-8")
        return BuildResult(str(build_path),str(inst),str(rp))

    def master(self,state:ProjectState,output_dir:str|Path)->str:
        if not state.build_path: raise ValueError("Build the song before mastering.")
        data=load_stereo(state.build_path)
        target=float(state.settings.get("target_lufs",-14.0))
        mastered=loudness_master(data,target_lufs=target)
        return str(write_audio(Path(output_dir)/"master.wav",mastered))
