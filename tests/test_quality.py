import pandas as pd
from src.data_quality.validators import null_analysis,duplicate_detection,numeric_validation,date_consistency,referential_integrity

def test_quality_checks():
    df=pd.DataFrame({"id":[1,2],"value":[1,2]})
    assert null_analysis(df).passed
    assert duplicate_detection(df).passed
    assert numeric_validation(df,["value"]).passed

def test_date_and_fk():
    df=pd.DataFrame({"a":["2024-01-01"],"b":["2024-01-02"]})
    assert date_consistency(df,"a","b").passed
    child=pd.DataFrame({"id":[1,2]}); parent=pd.DataFrame({"id":[1,2,3]})
    assert referential_integrity(child,"id",parent,"id").passed

def test_database_contract_files_are_present():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert (root / 'sql' / '001_schemas.sql').exists()
    assert (root / 'sql' / '002_core_tables.sql').exists()
    assert (root / 'sql' / '003_analytics_views.sql').exists()
    sql = (root / 'sql' / '002_core_tables.sql').read_text()
    for table in ('customers','orders','order_items','products','sellers','payments','reviews','geolocation'):
        assert f'core.{table}' in sql
