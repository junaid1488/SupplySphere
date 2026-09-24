from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from dataset_analyzer.models import (
    DatasetProfile,
    ColumnProfile,
    InferredType,
    SemanticRole,
    SchemaIntelligence,
    CapabilityDetection,
)


@dataclass(frozen=True)
class AnomalyResult:
    method: str
    threshold: float
    affected_rows: int
    total_rows: int
    source_columns: List[str]
    calculation_basis: str
    anomaly_indices: List[int] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "threshold": self.threshold,
            "affected_rows": self.affected_rows,
            "total_rows": self.total_rows,
            "source_columns": self.source_columns,
            "calculation_basis": self.calculation_basis,
            "anomaly_indices": self.anomaly_indices[:100],
            "limitations": self.limitations,
        }


@dataclass(frozen=True)
class AnomalyDetectionReport:
    dataset_id: str
    anomalies: List[AnomalyResult]
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "computed_at": self.computed_at.isoformat(),
        }


class AnomalyEngine:
    def __init__(
        self,
        profile: DatasetProfile,
        schema_intelligence: SchemaIntelligence | None = None,
        reader_provider: Optional[callable] | None = None,
    ):
        self._profile = profile
        self._schema = schema_intelligence
        self._reader_provider = reader_provider
        self._reader = None

    def _get_reader(self) -> Optional[object]:
        if self._reader is None:
            if self._reader_provider:
                try:
                    self._reader = self._reader_provider()
                except Exception:
                    pass
        return self._reader

    def _get_numeric_columns_with_data(self) -> List[str]:
        """Get numeric columns that have valid numeric stats."""
        numeric_cols = self._profile.numeric_columns
        valid_cols: List[str] = []
        for col in numeric_cols:
            col_profile = self._profile.column_profiles.get(col)
            if col_profile and col_profile.numeric_stats:
                stats = col_profile.numeric_stats
                count = stats.get("count", 0)
                if count >= 3:  # Need at least 3 observations for anomaly detection
                    valid_cols.append(col)
        return valid_cols

    def _compute_iqr_outliers(self, series: pd.Series) -> Tuple[List[int], float, str]:
        """Compute IQR-based outliers."""
        if len(series.dropna()) < 3:
            return [], 0.0, "insufficient data"

        series_clean = series.dropna()
        q1 = series_clean.quantile(0.25)
        q3 = series_clean.quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            return [], 0.0, "zero IQR (all values identical)"

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        anomaly_mask = (series_clean < lower_bound) | (series_clean > upper_bound)
        anomaly_indices = anomaly_mask.index.tolist()
        count = len(anomaly_indices)

        return anomaly_indices, count, f"IQR method: bounds [{lower_bound:.2f}, {upper_bound:.2f}]"

    def _compute_z_score_outliers(
        self, series: pd.Series, method: str = "robust"
    ) -> Tuple[List[int], float, str]:
        """Compute z-score based outliers.

        method: 'robust' uses MAD (median absolute deviation), 
                'standard' uses mean/std deviation
        """
        series_clean = series.dropna()

        if method == "robust":
            median = series_clean.median()
            mad = np.median(np.abs(series_clean - median))
            if mad == 0:
                return [], 0.0, "zero MAD (all values identical)"
            # Robust z-score: 0.6745 * (x - median) / MAD
            z_scores = np.abs(0.6745 * (series_clean - median) / mad)
            threshold = 3.5  # Common robust threshold
        else:  # standard
            mean = series_clean.mean()
            std = series_clean.std()
            if std == 0:
                return [], 0.0, "zero std (all values identical)"
            z_scores = np.abs((series_clean - mean) / std)
            threshold = 3.0  # Common standard threshold

        anomaly_mask = z_scores > threshold
        anomaly_indices = anomaly_mask.index.tolist()
        count = len(anomaly_indices)

        return anomaly_indices, count, f"{method} z-score method: threshold {threshold}"

    def compute_all(self) -> AnomalyDetectionReport:
        valid_cols = self._get_numeric_columns_with_data()

        if not valid_cols:
            # No suitable numeric field exists
            return AnomalyDetectionReport(
                dataset_id=self._profile.dataset_id,
                anomalies=[],
                computed_at=datetime.utcnow(),
            )

        anomalies: List[AnomalyResult] = []
        seen_methods: set = set()

        reader = self._get_reader()

        for col in valid_cols:
            col_profile = self._profile.column_profiles[col]
            stats = col_profile.numeric_stats
            series_data = pd.Series([], dtype=float)

            if reader:
                try:
                    df_chunks = reader.read_csv_chunked(columns=[col], max_chunks=100)
                    all_rows = []
                    for chunk in df_chunks:
                        all_rows.extend(chunk["rows"])
                    if all_rows:
                        series_data = pd.Series(
                            [pd.to_numeric(r[col], errors="coerce") for r in all_rows]
                        )
                except Exception:
                    pass
            else:
                # Use profile stats if no reader
                if stats and "values" in stats:
                    series_data = pd.Series(stats["values"])

            if len(series_data.dropna()) < 3:
                continue

            # Try IQR method first, then standard z-score
            method_order = ["IQR", "robust_zscore", "standard_zscore"]

            for method in method_order:
                if method in seen_methods:
                    continue

                if method == "IQR":
                    indices, count, basis = self._compute_iqr_outliers(series_data)
                elif method == "robust_zscore":
                    indices, count, basis = self._compute_z_score_outliers(series_data, "robust")
                elif method == "standard_zscore":
                    indices, count, basis = self._compute_z_score_outliers(series_data, "standard")
                else:
                    continue

                if count > 0 and basis not in seen_methods:
                    seen_methods.add(basis)
                    extracted_threshold = 3.0
                    if method == "IQR":
                        try:
                            parts = basis.split("bounds")
                            if len(parts) == 2:
                                import re as _re
                                nums = _re.findall(r"[-\d.]+", parts[1])
                                if len(nums) == 2:
                                    extracted_threshold = float(nums[0])
                        except (ValueError, IndexError):
                            extracted_threshold = 3.0
                    elif method == "robust_zscore":
                        extracted_threshold = 3.5
                    elif method == "standard_zscore":
                        extracted_threshold = 3.0
                    anomalies.append(AnomalyResult(
                        method=method,
                        threshold=extracted_threshold,
                        affected_rows=count,
                        total_rows=len(series_data),
                        source_columns=[col],
                        calculation_basis=basis,
                        anomaly_indices=indices,
                        limitations=[f"Method: {method}; column: {col}"],
                    ))
                    break  # Only add first valid method per column

        return AnomalyDetectionReport(
            dataset_id=self._profile.dataset_id,
            anomalies=anomalies,
            computed_at=datetime.utcnow(),
        )


def create_anomaly_engine(
    profile: DatasetProfile,
    schema_intelligence: SchemaIntelligence | None = None,
    reader_provider: Optional[callable] | None = None,
) -> AnomalyEngine:
    return AnomalyEngine(profile, schema_intelligence, reader_provider)