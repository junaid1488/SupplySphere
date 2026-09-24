from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.settings import settings
from src.common.logging_config import configure_logging
from src.ingestion.pipeline import OlistIngestion

if __name__ == "__main__":
    configure_logging(settings.log_level)
    result = OlistIngestion(settings.raw_data_dir, settings.staging_data_dir).run()
    print(f"Ingested {len(result)} Olist datasets.")
