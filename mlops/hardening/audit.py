from __future__ import annotations
from pathlib import Path
import json, subprocess, sys

REQUIRED_FILES=[
 'realtime/events.py','realtime/broker.py','realtime/simulator.py','realtime/processor.py','api/routes/realtime.py',
 'mlops/registry.py','mlops/monitoring.py','mlops/integration.py','api/routes/mlops.py','docs/PHASE15_17.md'
]

def run_audit(root:Path|str='.'):
    root=Path(root); files={p: (root/p).exists() for p in REQUIRED_FILES}
    compile_cmd=[sys.executable,'-m','compileall','-q','realtime','mlops','api']
    compile_ok=subprocess.run(compile_cmd,cwd=root,capture_output=True,text=True).returncode==0
    return {'required_files':files,'compile':compile_ok,'all_required_files':all(files.values())}

if __name__=='__main__':
    result=run_audit(); print(json.dumps(result,indent=2)); raise SystemExit(0 if result['compile'] and result['all_required_files'] else 1)
