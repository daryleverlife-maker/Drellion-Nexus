from pathlib import Path
import numpy as np
import pytest
from drellion.audio_core import write_wav
from drellion.providers import AceStepHttpProvider,BasicTestEngine,EngineBroker,EngineStatus,GenerationRequest,GenerationResult
from drellion.quality import QCMetrics, QCResult, evaluate_preview

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


def test_preview_generation_only_promotes_qc_passed_candidates(tmp_path, monkeypatch):
    from drellion.production_v2 import generate_three_previews
    from drellion.project import ProjectState
    from drellion.providers import GenerationResult

    sr=8000
    tt=np.arange(sr*20,dtype=np.float32)/sr
    voice=tmp_path/"voice.wav"
    write_wav(voice,(0.2*np.sin(2*np.pi*220*tt)).astype(np.float32),sr)
    project=ProjectState.create(tmp_path/"projects","QC Song")
    project.add_source(voice,role="Lead Vocal")

    class Provider:
        name="QC Provider"
        def status(self):return EngineStatus(self.name,True,"ok")
        def generate(self,request,progress=None):
            out=Path(request.output_dir)/f"gen-{request.seed}.wav"
            out.parent.mkdir(parents=True,exist_ok=True)
            write_wav(out,(0.15*np.sin(2*np.pi*70*tt)).astype(np.float32),sr)
            return GenerationResult(self.name,"1",str(out),seed=request.seed)

    calls={"n":0}
    def fake_qc(_instrumental,_vocal=None):
        calls["n"]+=1
        passed=calls["n"]!=1
        checks={"no_clipping":passed,"bass_foundation":passed,"drum_activity":passed,"not_silent":passed,"stereo_phase":True,"not_excessively_repetitive":passed}
        return QCResult(passed,QCMetrics(),checks,[] if passed else ["failed"])

    monkeypatch.setattr("drellion.production_v2.evaluate_preview",fake_qc)
    previews=generate_three_previews(project,EngineBroker([Provider()]),region=(0.0,20.0))
    assert len(previews)==3
    assert calls["n"]==4
    assert all(p.accepted for p in previews)
    assert [p.label for p in previews]==["Preview A","Preview B","Preview C"]


class _FakeResponse:
    def __init__(self,payload,status_code=200,content=b"",content_type="application/json"):
        self._payload=payload; self.status_code=status_code; self.content=content; self.headers={"content-type":content_type}
    def raise_for_status(self):
        if self.status_code>=400:
            raise RuntimeError(f"HTTP {self.status_code}")
    def json(self):return self._payload

class _AceSession:
    def __init__(self):
        self.query_payloads=[]
    def get(self,url,timeout=None):
        if url.endswith("/v1/stats"):
            return _FakeResponse({"data":{"version":"1.5"}})
        if "/v1/audio?" in url:
            return _FakeResponse({},content=b"RIFFfake",content_type="audio/wav")
        raise AssertionError(url)
    def post(self,url,**kwargs):
        if url.endswith("/release_task"):
            assert kwargs["data"]["audio_format"]=="wav"
            assert "src_audio" in kwargs["files"]
            return _FakeResponse({"data":{"task_id":"abc","status":"queued"},"code":200,"error":None})
        if url.endswith("/query_result"):
            self.query_payloads.append(kwargs["json"])
            return _FakeResponse({"data":[{"task_id":"abc","status":1,"result":"[{\"file\":\"/v1/audio?path=%2Ftmp%2Fanswer.wav\"}]"}],"code":200,"error":None})
        raise AssertionError(url)

def test_acestep_current_api_contract(tmp_path):
    src=tmp_path/"voice.wav"; src.write_bytes(b"RIFFsource")
    provider=AceStepHttpProvider("http://127.0.0.1:8001",poll_seconds=0)
    fake=_AceSession(); provider.session=fake
    result=provider.generate(GenerationRequest(source_audio=str(src),prompt="test",seed=7,duration_seconds=20,output_dir=str(tmp_path/"out")))
    assert fake.query_payloads==[{"task_id_list":["abc"]}]
    assert Path(result.audio_path).exists()
    assert result.metadata["task_id"]=="abc"
