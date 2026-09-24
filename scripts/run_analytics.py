from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from configs.settings import settings
from src.db.engine import make_engine
from src.db.schema import initialize_database
from src.analytics.sql_views import ANALYTIC_VIEWS_SQL


if __name__ == "__main__":
    engine = make_engine(settings.database_url)

    # Ensure the database schemas/tables exist.
    initialize_database(engine)

    # Create/update analytics views.
    with engine.begin() as conn:
        for sql in ANALYTIC_VIEWS_SQL.values():
            conn.execute(text(sql))

    print("Analytics views created.")