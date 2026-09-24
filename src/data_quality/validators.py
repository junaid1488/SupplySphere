from dataclasses import dataclass
import pandas as pd

@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str

def null_analysis(df: pd.DataFrame, threshold=0.95) -> CheckResult:
    bad = [c for c in df.columns if df[c].isna().mean() > threshold]
    return CheckResult("null_threshold", not bad, f"columns_over_threshold={bad}")

def duplicate_detection(df: pd.DataFrame) -> CheckResult:
    n = int(df.duplicated().sum())
    return CheckResult("duplicates", n == 0, f"duplicate_rows={n}")

def numeric_validation(df: pd.DataFrame, nonnegative=()) -> CheckResult:
    bad = []
    for c in nonnegative:
        if c in df and (pd.to_numeric(df[c], errors="coerce").dropna() < 0).any():
            bad.append(c)
    return CheckResult("numeric_validation", not bad, f"negative_columns={bad}")

def date_consistency(df: pd.DataFrame, start_col: str, end_col: str) -> CheckResult:
    if start_col not in df or end_col not in df:
        return CheckResult("date_consistency", True, "columns_not_present")
    a = pd.to_datetime(df[start_col], errors="coerce")
    b = pd.to_datetime(df[end_col], errors="coerce")
    bad = int((a.notna() & b.notna() & (b < a)).sum())
    return CheckResult("date_consistency", bad == 0, f"inconsistent_rows={bad}")

def referential_integrity(child, child_key, parent, parent_key) -> CheckResult:
    if child_key not in child or parent_key not in parent:
        return CheckResult("referential_integrity", True, "columns_not_present")
    missing = int((~child[child_key].isin(parent[parent_key])).sum())
    return CheckResult("referential_integrity", missing == 0, f"orphan_rows={missing}")
