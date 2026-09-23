from __future__ import annotations
from pathlib import Path
import numpy as np
import librosa
import pyloudnorm as pyln
import soundfile as sf

SR=48000

def load_stereo(path:str|Path,sr:int=SR)->np.ndarray:
    y,_=librosa.load(str(path),sr=sr,mono=False)
    if y.ndim==1:
        y=np.vstack([y,y])
    elif y.shape[0]>2:
        y=y[:2]
    if y.shape[0]==1:
        y=np.vstack([y[0],y[0]])
    return y.T.astype(np.float32)

def pad_to(data:np.ndarray,n:int)->np.ndarray:
    if len(data)>=n:return data[:n]
    return np.pad(data,((0,n-len(data)),(0,0)))

def normalize_peak(data:np.ndarray,peak:float=0.98)->np.ndarray:
    m=float(np.max(np.abs(data)) or 1.0)
    return (data*(peak/m if m>peak else 1.0)).astype(np.float32)

def mix_vocal_instrumental(vocal:np.ndarray,instrumental:np.ndarray,vocal_gain:float=1.0,inst_gain:float=0.70)->np.ndarray:
    n=max(len(vocal),len(instrumental))
    v=pad_to(vocal,n); i=pad_to(instrumental,n)
    out=v*vocal_gain+i*inst_gain
    return normalize_peak(out,0.96)

def integrated_lufs(data:np.ndarray,sr:int=SR)->float:
    try:
        value=float(pyln.Meter(sr).integrated_loudness(data))
        return value if np.isfinite(value) else -70.0
    except Exception:
        return -70.0

def loudness_master(data:np.ndarray,target_lufs:float=-14.0,sr:int=SR,peak_limit:float=0.89)->np.ndarray:
    current=integrated_lufs(data,sr)
    if current>-69:
        gain_db=float(np.clip(target_lufs-current,-18.0,12.0))
        data=data*(10.0**(gain_db/20.0))
    return normalize_peak(data,peak_limit)

def write_audio(path:str|Path,data:np.ndarray,sr:int=SR)->Path:
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True)
    sf.write(target,data,sr,subtype="PCM_24")
    return target
