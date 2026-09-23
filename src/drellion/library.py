from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib,json

SUPPORTED_AUDIO={'.wav','.flac','.mp3','.m4a','.aac','.ogg','.opus','.aiff','.aif','.wma'}

@dataclass
class SoundItem:
    path:str
    name:str
    extension:str
    size:int
    fingerprint:str

class SoundLibrary:
    def __init__(self,root:str|Path):
        self.root=Path(root)
        self.items:list[SoundItem]=[]
    def scan(self)->list[SoundItem]:
        self.items=[]
        if not self.root.exists(): return self.items
        seen=set()
        for path in sorted(self.root.rglob('*')):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_AUDIO: continue
            stat=path.stat(); key=f'{stat.st_size}:{path.name.lower()}'
            fp=hashlib.sha1(key.encode()).hexdigest()
            if fp in seen: continue
            seen.add(fp)
            self.items.append(SoundItem(str(path),path.stem,path.suffix.lower(),stat.st_size,fp))
        return self.items
    def save_catalog(self,path:str|Path)->Path:
        target=Path(path); target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps([asdict(x) for x in self.items],indent=2),encoding='utf-8')
        return target
