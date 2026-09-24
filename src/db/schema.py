from pathlib import Path
from sqlalchemy import text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "sql"


def initialize_database(engine: Engine) -> None:
    """Create SupplySphere schemas, core tables, indexes and analytics views."""
    scripts = [SQL_DIR / "001_schemas.sql", SQL_DIR / "002_core_tables.sql", SQL_DIR / "003_analytics_views.sql"]
    with engine.begin() as conn:
        for script in scripts:
            sql = script.read_text(encoding="utf-8")
            for statement in sql.split(";\n"):
                statement = statement.strip()
                if statement:
                    conn.execute(text(statement))
