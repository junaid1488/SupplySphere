from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://supplysphere:supplysphere@localhost:5432/supplysphere",
    )
    raw_data_dir: Path = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
    staging_data_dir: Path = Path(os.getenv("STAGING_DATA_DIR", "data/staging"))
    processed_data_dir: Path = Path(os.getenv("PROCESSED_DATA_DIR", "data/processed"))
    model_dir: Path = Path(os.getenv("MODEL_DIR", "ml/models"))
    synthetic_seed: int = int(os.getenv("SYNTHETIC_SEED", "42"))

    @property
    def forecast_horizons(self) -> tuple[int, ...]:
        return tuple(int(x.strip()) for x in os.getenv("FORECAST_HORIZONS", "7,30,90").split(","))

settings = Settings()
