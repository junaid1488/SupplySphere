from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable
from collections import defaultdict

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
class TrendResult:
    name: str
    aggregation_period: str | None
    date_column: str
    measure_column: str
    data: list[dict[str, Any]]
    trend_direction: str | None
    trend_summary: dict[str, Any] | None
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
            "aggregation_period": self.aggregation_period,
            "date_column": self.date_column,
            "measure_column": self.measure_column,
            "data": self.data,
            "trend_direction": self.trend_direction,
            "trend_summary": self.trend_summary,
            "source_columns": self.source_columns,
            "calculation_basis": self.calculation_basis,
            "available": self.available,
            "reason": self.reason,
            "limitations": self.limitations,
        }


@dataclass(frozen=True)
class TrendReport:
    dataset_id: str
    trends: list[TrendResult]
    computed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "trends": [t.to_dict() for t in self.trends],
            "computed_at": self.computed_at.isoformat(),
        }


class TrendEngine:
    MIN_OBSERVATIONS_FOR_TREND = 3
    MAX_POINTS = 500

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

    def compute_all(self) -> TrendReport:
        trends = []

        date_measure_pairs = self._find_valid_date_measure_pairs()

        for date_col, measure_col in date_measure_pairs:
            trend = self._compute_trend(date_col, measure_col)
            trends.append(trend)

        if not trends:
            trends.append(TrendResult(
                name="no_valid_trends",
                aggregation_period=None,
                date_column="",
                measure_column="",
                data=[],
                trend_direction=None,
                trend_summary=None,
                source_columns=[],
                calculation_basis="No valid date/time column paired with a numeric measure column found",
                available=False,
                reason="Trend analysis requires at least one valid date/time column and one numeric measure column",
            ))

        return TrendReport(
            dataset_id=self._profile.dataset_id,
            trends=trends,
            computed_at=datetime.utcnow(),
        )

    def _find_valid_date_measure_pairs(self) -> list[tuple[str, str]]:
        pairs = []

        date_columns = []
        if self._schema:
            for detection in self._schema.detected_roles:
                if detection.role == SemanticRole.DATE_TIME:
                    date_columns.extend(detection.source_columns)

        for col in self._profile.datetime_columns:
            if col not in date_columns:
                date_columns.append(col)

        measure_columns = []
        if self._schema:
            for detection in self._schema.detected_roles:
                if detection.role in (SemanticRole.PRICE_REVENUE_VALUE, SemanticRole.QUANTITY, SemanticRole.INVENTORY_STOCK):
                    measure_columns.extend(detection.source_columns)

        for col in self._profile.measure_candidates:
            if col not in measure_columns:
                measure_columns.append(col)

        for col in self._profile.numeric_columns:
            if col not in measure_columns:
                measure_columns.append(col)

        for date_col in date_columns:
            for measure_col in measure_columns:
                if date_col != measure_col:
                    pairs.append((date_col, measure_col))

        return pairs

    def _compute_trend(self, date_col: str, measure_col: str) -> TrendResult:
        reader = self._get_reader()
        if not reader:
            return TrendResult(
                name=f"trend_{date_col}_vs_{measure_col}",
                aggregation_period=None,
                date_column=date_col,
                measure_column=measure_col,
                data=[],
                trend_direction=None,
                trend_summary=None,
                source_columns=[date_col, measure_col],
                calculation_basis=f"Trend of {measure_col} over {date_col}",
                available=False,
                reason="Could not access dataset reader",
            )

        try:
            df_chunks = reader.read_csv_chunked(columns=[date_col, measure_col], max_chunks=100)
            all_rows = []
            for chunk in df_chunks:
                all_rows.extend(chunk["rows"])

            if not all_rows:
                return TrendResult(
                    name=f"trend_{date_col}_vs_{measure_col}",
                    aggregation_period=None,
                    date_column=date_col,
                    measure_column=measure_col,
                    data=[],
                    trend_direction=None,
                    trend_summary=None,
                    source_columns=[date_col, measure_col],
                    calculation_basis=f"Trend of {measure_col} over {date_col}",
                    available=False,
                    reason="No data rows retrieved",
                )

            df = pd.DataFrame(all_rows)

            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df[measure_col] = pd.to_numeric(df[measure_col], errors="coerce")

            df_clean = df.dropna(subset=[date_col, measure_col])

            if len(df_clean) < self.MIN_OBSERVATIONS_FOR_TREND:
                return TrendResult(
                    name=f"trend_{date_col}_vs_{measure_col}",
                    aggregation_period=None,
                    date_column=date_col,
                    measure_column=measure_col,
                    data=[],
                    trend_direction=None,
                    trend_summary=None,
                    source_columns=[date_col, measure_col],
                    calculation_basis=f"Trend of {measure_col} over {date_col}",
                    available=False,
                    reason=f"Insufficient valid observations ({len(df_clean)} < {self.MIN_OBSERVATIONS_FOR_TREND}) after removing missing values",
                )

            date_range = df_clean[date_col].max() - df_clean[date_col].min()
            total_days = date_range.total_seconds() / 86400

            aggregation_period = self._determine_aggregation_period(df_clean[date_col], total_days)

            if aggregation_period:
                df_clean["period"] = df_clean[date_col].dt.to_period(aggregation_period)
                grouped = df_clean.groupby("period")[measure_col].agg(["count", "sum", "mean"]).reset_index()
                grouped = grouped.sort_values("period")
                grouped["period_str"] = grouped["period"].astype(str)

                data = grouped.to_dict(orient="records")
                calc_basis = f"Period ({aggregation_period}) aggregation of {measure_col} over {date_col} (n={len(df_clean)} rows, {len(grouped)} periods)"
            else:
                df_clean = df_clean.sort_values(date_col).head(self.MAX_POINTS)
                df_clean["period_str"] = df_clean[date_col].dt.strftime("%Y-%m-%d %H:%M:%S")
                grouped = df_clean[[date_col, measure_col]].rename(columns={date_col: "period", measure_col: "mean"})
                grouped["count"] = 1
                grouped["sum"] = grouped["mean"]
                data = grouped.to_dict(orient="records")
                calc_basis = f"Raw date-level analysis of {measure_col} over {date_col} (n={len(df_clean)} rows, no regular period detected)"

            trend_direction, trend_summary = self._analyze_trend(grouped, aggregation_period)

            limitations = []
            if len(df_clean) > self.MAX_POINTS and not aggregation_period:
                limitations.append(f"Raw data truncated to {self.MAX_POINTS} points")
            if total_days == 0:
                limitations.append("Date range is zero (all dates identical)")

            return TrendResult(
                name=f"trend_{date_col}_vs_{measure_col}",
                aggregation_period=aggregation_period,
                date_column=date_col,
                measure_column=measure_col,
                data=data,
                trend_direction=trend_direction,
                trend_summary=trend_summary,
                source_columns=[date_col, measure_col],
                calculation_basis=calc_basis,
                available=True,
                limitations=limitations,
            )

        except Exception as e:
            return TrendResult(
                name=f"trend_{date_col}_vs_{measure_col}",
                aggregation_period=None,
                date_column=date_col,
                measure_column=measure_col,
                data=[],
                trend_direction=None,
                trend_summary=None,
                source_columns=[date_col, measure_col],
                calculation_basis=f"Trend of {measure_col} over {date_col}",
                available=False,
                reason=f"Computation failed: {str(e)}",
            )

    def _determine_aggregation_period(self, date_series: pd.Series, total_days: float) -> str | None:
        if len(date_series) < 2:
            return None

        diffs = date_series.sort_values().diff().dropna()
        if len(diffs) == 0:
            return None

        median_diff = diffs.median()
        median_days = median_diff.total_seconds() / 86400

        if median_days <= 1.5:
            if total_days >= 60:
                return "W"
            elif total_days >= 14:
                return "D"
            else:
                return "D"
        elif median_days <= 8:
            if total_days >= 365:
                return "M"
            elif total_days >= 60:
                return "W"
            else:
                return "W"
        elif median_days <= 31:
            if total_days >= 730:
                return "Q"
            elif total_days >= 180:
                return "M"
            else:
                return "M"
        else:
            if total_days >= 1000:
                return "Y"
            elif total_days >= 365:
                return "Q"
            else:
                return "M"

    def _analyze_trend(self, grouped: pd.DataFrame, aggregation_period: str | None) -> tuple[str | None, dict[str, Any] | None]:
        if len(grouped) < self.MIN_OBSERVATIONS_FOR_TREND:
            return None, {"reason": f"Insufficient periods ({len(grouped)}) for trend analysis"}

        measure_col = "mean" if "mean" in grouped.columns else grouped.columns[1]

        values = grouped[measure_col].dropna()
        if len(values) < self.MIN_OBSERVATIONS_FOR_TREND:
            return None, {"reason": f"Insufficient valid values ({len(values)}) for trend analysis"}

        x = np.arange(len(values))
        y = values.values

        try:
            slope, intercept = np.polyfit(x, y, 1)
            y_pred = slope * x + intercept
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            if abs(slope) < 1e-10:
                direction = "stable"
            elif slope > 0:
                direction = "increasing"
            else:
                direction = "decreasing"

            period_change = None
            if len(values) >= 2:
                period_change = float((values.iloc[-1] - values.iloc[0]) / values.iloc[0] * 100) if values.iloc[0] != 0 else None

            summary = {
                "slope": float(slope),
                "intercept": float(intercept),
                "r_squared": float(r_squared),
                "periods_analyzed": len(values),
                "period_change_percentage": period_change,
                "start_value": float(values.iloc[0]),
                "end_value": float(values.iloc[-1]),
                "mean_value": float(np.mean(y)),
                "std_value": float(np.std(y)),
            }

            return direction, summary

        except Exception:
            return None, {"reason": "Trend computation failed"}


def create_trend_engine(
    profile: DatasetProfile,
    schema_intelligence: SchemaIntelligence | None = None,
    reader_provider: Callable[[], DatasetReader | None] | None = None,
) -> TrendEngine:
    return TrendEngine(profile, schema_intelligence, reader_provider)