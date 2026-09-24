from pathlib import Path
import pandas as pd
from src.ingestion.manifest import discover, inspect_file

def test_discover_and_inspect(tmp_path):
    p=tmp_path/"olist_customers_dataset.csv"
    pd.DataFrame({"customer_id":["a","b"],"customer_city":["x","y"]}).to_csv(p,index=False)
    found=discover(tmp_path)
    assert found["customers"]==p
    info=inspect_file(p)
    assert info["rows"]==2
    assert "customer_id" in info["candidate_primary_keys"]
