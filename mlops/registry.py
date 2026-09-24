from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json

@dataclass(frozen=True)
class ModelRecord:
    name: str
    version: str
    stage: str
    artifact_path: str
    dataset: str
    features: list[str]
    parameters: dict
    metrics: dict
    timestamp: str

class ModelRegistry:
    def __init__(self, root: str | Path='ml/artifacts/registry'):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.index=self.root/'registry.json'
    def register(self,name:str,version:str,artifact_path:str,dataset:str,features:list[str],parameters:dict,metrics:dict,stage:str='candidate')->ModelRecord:
        rec=ModelRecord(name,version,stage,artifact_path,dataset,features,parameters,metrics,datetime.now(timezone.utc).isoformat())
        data=json.loads(self.index.read_text()) if self.index.exists() else []
        data=[r for r in data if not (r['name']==name and r['version']==version)]; data.append(asdict(rec)); self.index.write_text(json.dumps(data,indent=2))
        return rec
    def list(self,name:str|None=None):
        data=json.loads(self.index.read_text()) if self.index.exists() else []
        return [r for r in data if name is None or r['name']==name]
    def promote(self,name:str,version:str,stage:str='production'):
        rows=self.list(); found=False
        for r in rows:
            if r['name']==name:
                r['stage']=stage if r['version']==version else ('archived' if stage=='production' else r['stage']); found |= r['version']==version
        if not found: raise KeyError(f'Model {name}:{version} not found')
        self.index.write_text(json.dumps(rows,indent=2)); return next(r for r in rows if r['name']==name and r['version']==version)
