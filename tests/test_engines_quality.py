import numpy as np
import pytest
from drellion.audio_core import write_wav
from drellion.providers import BasicTestEngine,EngineBroker,EngineStatus,GenerationResult
from drellion.quality import evaluate_preview

class ReadyProvider:
    name="Ready"
    def status(self):return EngineStatus(self.name,True,"ok")
    def generate(self,request,progress=None):return GenerationResult(self.name,"1",request.source_audio,seed=request.seed)
class NotReady:
    name="Not Ready"
    def status(self):return EngineStatus(self.name,False,"offline")
    def generate(self,request,progress=None):raise AssertionError

def test_broker_never_silent_basic_fallback(tmp_path):
    broker=EngineBroker([NotReady()])
    with pytest.raises(RuntimeError,match="will not silently fall back"):broker.ready_provider()
    with pytest.raises(RuntimeError,match="explicit opt-in"):broker.ready_provider(BasicTestEngine.name)
    assert EngineBroker([],explicit_basic=True).ready_provider(BasicTestEngine.name).name==BasicTestEngine.name

def test_broker_selects_ready_provider():assert EngineBroker([NotReady(),ReadyProvider()]).ready_provider().name=="Ready"

def test_quality_gate_detects_silent_bad_preview(tmp_path):
    bad=tmp_path/"bad.wav"; write_wav(bad,np.zeros(16000,dtype=np.float32),8000); qc=evaluate_preview(bad); assert not qc.accepted; assert not qc.checks["not_silent"]

def test_vocal_analysis_detects_activity(tmp_path):
    from drellion.vocal_analysis import analyze_vocal
    sr=8000; t=np.arange(sr*3,dtype=np.float32)/sr; x=np.zeros(sr*3,dtype=np.float32); x[sr//2:sr*2]=0.2*np.sin(2*np.pi*220*t[:sr*3//2]); path=tmp_path/"voice.wav"; write_wav(path,x,sr); result=analyze_vocal(path); assert result.duration_seconds==pytest.approx(3.0,rel=1e-3); assert result.phrase_count>=1; assert result.pitch_median_hz is not None
