from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
from configs.settings import settings
from src.ingestion.manifest import build_data_dictionary

if __name__ == "__main__":
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_data_dictionary(settings.raw_data_dir)
    out = settings.staging_data_dir / "data_dictionary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
