from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import numpy as np
import pandas as pd

from dataset_analyzer.models import (
    DatasetProfile,
    ColumnProfile,
    InferredType,
    SemanticRole,
    SchemaIntelligence,
)
from dataset_analyzer.reader import DatasetReader


@dataclass(frozen=True)
class AnalyticsResult:
    name: str
    result_type: str
    data: dict[str, Any] | list[dict[str, Any]]
    source_columns: list[str]
    calculation_basis: str
    available: bool = True
    reason: str | None = None
    limitations: list[str] = None

    def __post_init__(self):
        if self.limitations is None:
            object.__setattr__(self, "limitations", [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "result_type": self.result_type,
            "data": self.data,
            "source_columns": self.source_columns,
            "calculation_basis": self.calculation_basis,
            "available": self.available,
            "reason": self.reason,
            "limitations": self.limitations,
        }


@dataclass(frozen=True)
class AnalyticsReport:
    dataset_id: str
    results: list[AnalyticsResult]
    computed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "results": [r.to_dict() for r in self.results],
            "computed_at": self.computed_at.isoformat(),
        }


class AnalyticsEngine:
    MAX_CATEGORIES = 50
    MAX_GROUPBY_RESULTS = 100
    MAX_CORRELATION_PAIRS = 20

    def __init__(
        self,
        profile: DatasetProfile,
        schema_intelligence: SchemaIntelligence | None = None,
        reader_provider: Callable[[], DatasetReader | None] | None = None,
    ):
        self._profile = profile
        self._schema = schema_intelligence
        self._reader_provider = reader_provider
        self._reader = None

    def _get_reader(self) -> DatasetReader | None:
        if self._reader is None:
            if self._reader_provider:
                try:
                    self._reader = self._reader_provider()
                except Exception:
                    pass
        return self._reader

    def compute_all(self) -> AnalyticsReport:
        results = []

        results.extend(self._compute_numeric_aggregations())
        results.extend(self._compute_groupby_analysis())
        results.extend(self._compute_category_frequency())
        results.extend(self._compute_numeric_vs_categorical())
        results.extend(self._compute_correlations())
        results.extend(self._compute_top_bottom_categories())
        results.extend(self._compute_descriptive_statistics())

        return AnalyticsReport(
            dataset_id=self._profile.dataset_id,
            results=results,
            computed_at=datetime.utcnow(),
        )

    def _compute_numeric_aggregations(self) -> list[AnalyticsResult]:
        results = []

        for col_name in self._profile.numeric_columns:
            col_profile = self._profile.column_profiles[col_name]
            stats = col_profile.numeric_stats

            if not stats:
                results.append(AnalyticsResult(
                    name=f"aggregations_{col_name}",
                    result_type="numeric_aggregations",
                    data={},
                    source_columns=[col_name],
                    calculation_basis="No valid numeric statistics available",
                    available=False,
                    reason="Column has no computable numeric statistics",
                ))
                continue

            data = {
                "count": stats.get("count"),
                "sum": stats.get("sum"),
                "mean": stats.get("mean"),
                "std": stats.get("std"),
                "min": stats.get("min"),
                "q25": stats.get("q25"),
                "median": stats.get("median"),
                "q75": stats.get("q75"),
                "max": stats.get("max"),
                "missing_count": col_profile.null_count,
                "missing_percentage": col_profile.null_percentage,
            }

            results.append(AnalyticsResult(
                name=f"aggregations_{col_name}",
                result_type="numeric_aggregations",
                data=data,
                source_columns=[col_name],
                calculation_basis=f"Standard descriptive statistics on non-null values of {col_name} (n={stats.get('count', 0)})",
            ))

        return results

    def _compute_groupby_analysis(self) -> list[AnalyticsResult]:
        results = []
        reader = self._get_reader()
        if not reader:
            return results

        categorical_cols = [c for c in self._profile.categorical_columns if self._profile.column_profiles[c].unique_count <= self.MAX_CATEGORIES]
        numeric_cols = self._profile.numeric_columns

        if not categorical_cols or not numeric_cols:
            return results

        for cat_col in categorical_cols[:3]:
            for num_col in numeric_cols[:3]:
                try:
                    df_chunks = reader.read_csv_chunked(columns=[cat_col, num_col], max_chunks=50)
                    all_rows = []
                    for chunk in df_chunks:
                        all_rows.extend(chunk["rows"])

                    if not all_rows:
                        continue

                    df = pd.DataFrame(all_rows)
                    df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
                    df = df.dropna(subset=[cat_col, num_col])

                    if len(df) == 0:
                        continue

                    grouped = df.groupby(cat_col)[num_col].agg(["count", "mean", "sum", "min", "max"]).reset_index()
                    grouped = grouped.head(self.MAX_GROUPBY_RESULTS)

                    data = grouped.to_dict(orient="records")
                    results.append(AnalyticsResult(
                        name=f"groupby_{cat_col}_by_{num_col}",
                        result_type="groupby_analysis",
                        data=data,
                        source_columns=[cat_col, num_col],
                        calculation_basis=f"Group {num_col} by {cat_col}: count, mean, sum, min, max per category (n={len(df)} rows)",
                        limitations=[f"Limited to top {self.MAX_GROUPBY_RESULTS} categories", f"Processed up to 50 chunks ({50 * 10000} rows max)"],
                    ))
                except Exception as e:
                    results.append(AnalyticsResult(
                        name=f"groupby_{cat_col}_by_{num_col}",
                        result_type="groupby_analysis",
                        data=[],
                        source_columns=[cat_col, num_col],
                        calculation_basis=f"Group {num_col} by {cat_col}",
                        available=False,
                        reason=f"Computation failed: {str(e)}",
                    ))

        return results

    def _compute_category_frequency(self) -> list[AnalyticsResult]:
        results = []

        for col_name in self._profile.categorical_columns:
            col_profile = self._profile.column_profiles[col_name]
            if not col_profile.categorical_summary:
                continue

            top_categories = dict(list(col_profile.categorical_summary.items())[:self.MAX_CATEGORIES])
            total = sum(col_profile.categorical_summary.values())

            data = {
                "categories": [
                    {"category": cat, "count": cnt, "percentage": round(cnt / total * 100, 2)}
                    for cat, cnt in top_categories.items()
                ],
                "total_count": total,
                "unique_categories": col_profile.unique_count,
                "missing_count": col_profile.null_count,
                "missing_percentage": col_profile.null_percentage,
            }

            limitations = []
            if col_profile.unique_count > self.MAX_CATEGORIES:
                limitations.append(f"Only top {self.MAX_CATEGORIES} categories shown (total unique: {col_profile.unique_count})")

            results.append(AnalyticsResult(
                name=f"frequency_{col_name}",
                result_type="category_frequency",
                data=data,
                source_columns=[col_name],
                calculation_basis=f"Value counts for {col_name} (n={total} non-null values, {col_profile.unique_count} unique)",
                limitations=limitations,
            ))

        return results

    def _compute_numeric_vs_categorical(self) -> list[AnalyticsResult]:
        results = []
        reader = self._get_reader()
        if not reader:
            return results

        categorical_cols = [c for c in self._profile.categorical_columns if self._profile.column_profiles[c].unique_count <= self.MAX_CATEGORIES]
        numeric_cols = self._profile.numeric_columns

        if not categorical_cols or not numeric_cols:
            return results

        for cat_col in categorical_cols[:2]:
            for num_col in numeric_cols[:2]:
                try:
                    df_chunks = reader.read_csv_chunked(columns=[cat_col, num_col], max_chunks=30)
                    all_rows = []
                    for chunk in df_chunks:
                        all_rows.extend(chunk["rows"])

                    if not all_rows:
                        continue

                    df = pd.DataFrame(all_rows)
                    df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
                    df = df.dropna(subset=[cat_col, num_col])

                    if len(df) == 0:
                        continue

                    grouped = df.groupby(cat_col)[num_col].agg(["count", "mean", "std", "min", "max"]).reset_index()
                    grouped = grouped.sort_values("mean", ascending=False).head(self.MAX_GROUPBY_RESULTS)

                    data = grouped.to_dict(orient="records")
                    results.append(AnalyticsResult(
                        name=f"numeric_vs_categorical_{num_col}_by_{cat_col}",
                        result_type="numeric_vs_categorical",
                        data=data,
                        source_columns=[cat_col, num_col],
                        calculation_basis=f"Numeric {num_col} statistics grouped by categorical {cat_col} (n={len(df)} rows)",
                        limitations=[f"Top {self.MAX_GROUPBY_RESULTS} categories by mean", f"Processed up to 30 chunks"],
                    ))
                except Exception as e:
                    results.append(AnalyticsResult(
                        name=f"numeric_vs_categorical_{num_col}_by_{cat_col}",
                        result_type="numeric_vs_categorical",
                        data=[],
                        source_columns=[cat_col, num_col],
                        calculation_basis=f"Numeric {num_col} statistics grouped by categorical {cat_col}",
                        available=False,
                        reason=f"Computation failed: {str(e)}",
                    ))

        return results

    def _compute_correlations(self) -> list[AnalyticsResult]:
        results = []
        reader = self._get_reader()
        if not reader:
            return results

        numeric_cols = self._profile.numeric_columns
        if len(numeric_cols) < 2:
            return results

        try:
            df_chunks = reader.read_csv_chunked(columns=numeric_cols, max_chunks=20)
            all_rows = []
            for chunk in df_chunks:
                all_rows.extend(chunk["rows"])

            if not all_rows:
                return results

            df = pd.DataFrame(all_rows)
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df_clean = df.dropna()
            if len(df_clean) < 10:
                results.append(AnalyticsResult(
                    name="correlation_matrix",
                    result_type="correlation",
                    data={},
                    source_columns=numeric_cols,
                    calculation_basis="Insufficient non-null rows for correlation (< 10)",
                    available=False,
                    reason="Not enough valid observations after removing missing values",
                ))
                return results

            corr_matrix = df_clean[numeric_cols].corr(method="pearson")

            pairs = []
            for i, col1 in enumerate(numeric_cols):
                for j, col2 in enumerate(numeric_cols):
                    if i < j:
                        val = corr_matrix.loc[col1, col2]
                        if not pd.isna(val):
                            pairs.append({
                                "column_1": col1,
                                "column_2": col2,
                                "correlation": round(float(val), 4),
                                "n_observations": len(df_clean),
                            })

            pairs = sorted(pairs, key=lambda x: abs(x["correlation"]), reverse=True)[:self.MAX_CORRELATION_PAIRS]

            results.append(AnalyticsResult(
                name="correlation_matrix",
                result_type="correlation",
                data={"pairs": pairs, "method": "pearson", "n_observations": len(df_clean)},
                source_columns=numeric_cols,
                calculation_basis=f"Pearson correlation on {len(df_clean)} complete observations across {len(numeric_cols)} numeric columns",
                limitations=[f"Top {self.MAX_CORRELATION_PAIRS} pairs by absolute correlation", "Pairwise deletion of missing values", "Processed up to 20 chunks"],
            ))
        except Exception as e:
            results.append(AnalyticsResult(
                name="correlation_matrix",
                result_type="correlation",
                data={},
                source_columns=numeric_cols,
                calculation_basis="Pearson correlation on numeric columns",
                available=False,
                reason=f"Computation failed: {str(e)}",
            ))

        return results

    def _compute_top_bottom_categories(self) -> list[AnalyticsResult]:
        results = []
        reader = self._get_reader()
        if not reader:
            return results

        categorical_cols = [c for c in self._profile.categorical_columns if self._profile.column_profiles[c].unique_count <= self.MAX_CATEGORIES]
        numeric_cols = self._profile.numeric_columns

        if not categorical_cols or not numeric_cols:
            return results

        for cat_col in categorical_cols[:2]:
            for num_col in numeric_cols[:2]:
                try:
                    df_chunks = reader.read_csv_chunked(columns=[cat_col, num_col], max_chunks=30)
                    all_rows = []
                    for chunk in df_chunks:
                        all_rows.extend(chunk["rows"])

                    if not all_rows:
                        continue

                    df = pd.DataFrame(all_rows)
                    df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
                    df = df.dropna(subset=[cat_col, num_col])

                    if len(df) == 0:
                        continue

                    grouped = df.groupby(cat_col)[num_col].mean().reset_index()
                    grouped = grouped.sort_values(num_col, ascending=False)

                    top_n = min(10, len(grouped))
                    bottom_n = min(10, len(grouped))

                    top_data = grouped.head(top_n).to_dict(orient="records")
                    bottom_data = grouped.tail(bottom_n).sort_values(num_col).to_dict(orient="records")

                    data = {
                        "top": top_data,
                        "bottom": bottom_data,
                        "metric": "mean",
                        "total_categories": len(grouped),
                    }

                    results.append(AnalyticsResult(
                        name=f"top_bottom_{cat_col}_by_{num_col}_mean",
                        result_type="top_bottom_categories",
                        data=data,
                        source_columns=[cat_col, num_col],
                        calculation_basis=f"Top/bottom {top_n} categories in {cat_col} by mean of {num_col} (n={len(df)} rows)",
                        limitations=[f"Limited to categories with at least 1 observation", "Mean used as ranking metric"],
                    ))
                except Exception as e:
                    results.append(AnalyticsResult(
                        name=f"top_bottom_{cat_col}_by_{num_col}_mean",
                        result_type="top_bottom_categories",
                        data={},
                        source_columns=[cat_col, num_col],
                        calculation_basis=f"Top/bottom categories in {cat_col} by mean of {num_col}",
                        available=False,
                        reason=f"Computation failed: {str(e)}",
                    ))

        return results

    def _compute_descriptive_statistics(self) -> list[AnalyticsResult]:
        results = []

        for col_name in self._profile.numeric_columns:
            col_profile = self._profile.column_profiles[col_name]
            stats = col_profile.numeric_stats

            if not stats:
                continue

            count = stats.get("count", 0)
            if count == 0:
                continue

            data = {
                "column": col_name,
                "count": count,
                "mean": stats.get("mean"),
                "std": stats.get("std"),
                "variance": stats.get("std", 0) ** 2 if stats.get("std") else 0,
                "min": stats.get("min"),
                "max": stats.get("max"),
                "range": (stats.get("max", 0) - stats.get("min", 0)) if stats.get("max") and stats.get("min") else 0,
                "median": stats.get("median"),
                "q25": stats.get("q25"),
                "q75": stats.get("q75"),
                "iqr": (stats.get("q75", 0) - stats.get("q25", 0)) if stats.get("q75") and stats.get("q25") else 0,
                "skewness": None,
                "kurtosis": None,
                "missing_count": col_profile.null_count,
                "missing_percentage": col_profile.null_percentage,
            }

            reader = self._get_reader()
            if reader:
                try:
                    df_chunks = reader.read_csv_chunked(columns=[col_name], max_chunks=10)
                    all_rows = []
                    for chunk in df_chunks:
                        all_rows.extend(chunk["rows"])
                    if all_rows:
                        df = pd.DataFrame(all_rows)
                        series = pd.to_numeric(df[col_name], errors="coerce").dropna()
                        if len(series) > 2:
                            data["skewness"] = float(series.skew())
                            data["kurtosis"] = float(series.kurtosis())
                except Exception:
                    pass

            results.append(AnalyticsResult(
                name=f"descriptive_{col_name}",
                result_type="descriptive_statistics",
                data=data,
                source_columns=[col_name],
                calculation_basis=f"Full descriptive statistics for {col_name} (n={count} non-null values)",
            ))

        for col_name in self._profile.categorical_columns:
            col_profile = self._profile.column_profiles[col_name]
            if not col_profile.categorical_summary:
                continue

            total = sum(col_profile.categorical_summary.values())
            if total == 0:
                continue

            mode_cat = max(col_profile.categorical_summary.items(), key=lambda x: x[1])[0]
            mode_count = col_profile.categorical_summary[mode_cat]

            data = {
                "column": col_name,
                "count": total,
                "unique": col_profile.unique_count,
                "mode": mode_cat,
                "mode_count": mode_count,
                "mode_percentage": round(mode_count / total * 100, 2),
                "missing_count": col_profile.null_count,
                "missing_percentage": col_profile.null_percentage,
            }

            results.append(AnalyticsResult(
                name=f"descriptive_{col_name}",
                result_type="descriptive_statistics",
                data=data,
                source_columns=[col_name],
                calculation_basis=f"Categorical descriptive statistics for {col_name} (n={total} non-null values)",
            ))

        return results


def create_analytics_engine(
    profile: DatasetProfile,
    schema_intelligence: SchemaIntelligence | None = None,
    reader_provider: Callable[[], DatasetReader | None] | None = None,
) -> AnalyticsEngine:
    return AnalyticsEngine(profile, schema_intelligence, reader_provider)