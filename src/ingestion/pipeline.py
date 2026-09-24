from pathlib import Path
import json
import pandas as pd
from .manifest import discover, build_data_dictionary
from src.common.io import write_csv

class OlistIngestion:
    def __init__(self, raw_dir: Path, staging_dir: Path):
        self.raw_dir, self.staging_dir = Path(raw_dir), Path(staging_dir)

    def run(self) -> dict:
        files = discover(self.raw_dir)
        if not files:
            raise FileNotFoundError(f"No recognized Olist CSV files found in {self.raw_dir}")
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        manifest = build_data_dictionary(self.raw_dir)
        for name, path in files.items():
            df = pd.read_csv(path, low_memory=False)
            write_csv(df, self.staging_dir / f"{name}.csv")
        (self.staging_dir / "data_dictionary.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        return manifest
