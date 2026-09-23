import numpy as np
import soundfile as sf

from drellion.audio.analysis import analyze_reference_file, analyze_vocal_file
from drellion.audio.contracts import ReferenceAnalysis, VocalAnalysis
from drellion.audio.generator import generate_original_arrangement, write_arrangement

SR=48000

def test_vocal_analysis_detects_pitch_and_phrases(tmp_path):
    t=np.arange(SR*4)/SR
    y=np.zeros_like(t,dtype=np.float32)
    y[:SR]=0.25*np.sin(2*np.pi*220*t[:SR])
    y[SR*2:SR*3]=0.25*np.sin(2*np.pi*247*t[:SR])
    path=tmp_path/"vocal.wav"
    sf.write(path,y,SR)
    result=analyze_vocal_file(path)
    assert result.duration>3.9
    assert result.pitch_track
    assert result.phrase_regions

def test_reference_analysis_detects_rhythm(tmp_path):
    seconds=8
    y=np.zeros(SR*seconds,dtype=np.float32)
    bpm=120
    spacing=int(SR*60/bpm)
    for i in range(0,len(y),spacing):
        n=min(int(0.03*SR),len(y)-i)
        if n>0:
            y[i:i+n]+=0.8*np.hanning(n).astype(np.float32)
    path=tmp_path/"ref.wav"
    sf.write(path,y,SR)
    result=analyze_reference_file(path)
    assert 90<=result.bpm<=150
    assert len(result.energy_curve)==16
    assert "lufs" in result.dynamics

def test_generator_creates_original_stereo_audio(tmp_path):
    vocal=VocalAnalysis(duration=6.0,pitch_track=[(0.0,220.0),(1.0,220.0),(2.0,246.9)])
    ref=ReferenceAnalysis(bpm=92.0,duration=6.0,energy_curve=[0.4,0.5,0.6,0.7]*4)
    arrangement=generate_original_arrangement(vocal,ref,6.0,variant=1)
    assert arrangement.stereo.shape[1]==2
    assert float(np.max(np.abs(arrangement.stereo)))>0.05
    out=write_arrangement(tmp_path/"arrangement.wav",arrangement)
    assert out.exists() and out.stat().st_size>1000
