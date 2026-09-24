from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.settings import settings
from src.db.engine import make_engine
from src.db.schema import initialize_database
from src.db.loader import rebuild_core_from_staging

if __name__ == "__main__":
    engine = make_engine(settings.database_url)
    initialize_database(engine)
    counts = rebuild_core_from_staging(engine, settings.staging_data_dir)
    print("Core load complete:")
    for name, count in counts.items():
        print(f"  {name}: {count:,}")
