from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import re

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
class QueryResult:
    question: str
    answer: Any
    result_type: str
    source_columns: List[str]
    calculation_basis: str
    supported: bool = True
    reason: str | None = None
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "result_type": self.result_type,
            "source_columns": self.source_columns,
            "calculation_basis": self.calculation_basis,
            "supported": self.supported,
            "reason": self.reason,
            "limitations": self.limitations,
        }


@dataclass(frozen=True)
class QueryAnalysisReport:
    dataset_id: str
    queries: List[QueryResult]
    searchable_columns: List[str]
    total_searchable: int
    column_coverage: float
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "queries": [q.to_dict() for q in self.queries],
            "searchable_columns": self.searchable_columns,
            "total_searchable": self.total_searchable,
            "column_coverage": self.column_coverage,
            "computed_at": self.computed_at.isoformat(),
        }


class QueryEngine:
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

    def _get_role_columns(self, role: SemanticRole) -> List[str]:
        if not self._schema:
            return []
        role_cols: List[str] = []
        for detection in self._schema.detected_roles:
            if detection.role == role:
                role_cols.extend(detection.source_columns)
        return role_cols

    def _get_all_columns(self) -> List[str]:
        return list(self._profile.column_profiles.keys())

    def _find_matching_column(self, name_hint: str) -> Optional[str]:
        hint_lower = name_hint.lower().strip()
        for col in self._profile.column_profiles:
            if col.lower() == hint_lower:
                return col
        for col in self._profile.column_profiles:
            if hint_lower in col.lower() or col.lower() in hint_lower:
                return col
        for col in self._profile.column_profiles:
            col_words = col.lower().replace("_", " ").replace("-", " ").split()
            hint_words = hint_lower.replace("_", " ").replace("-", " ").split()
            if any(hw in cw for hw in hint_words for cw in col_words):
                return col
        return None

    def answer_question(self, question: str) -> QueryResult:
        q = question.lower().strip()
        q = re.sub(r'[?!.\,]+$', '', q)

        reader = self._get_reader()

        row_match = re.search(r'(?:how many rows|number of rows|row count|total rows|total records|count of records)', q)
        if row_match:
            return QueryResult(
                question=question,
                answer=self._profile.row_count,
                result_type="row_count",
                source_columns=self._profile.column_names,
                calculation_basis=f"Total rows in dataset: {self._profile.row_count}",
                limitations=[],
            )

        col_match = re.search(r'(?:how many columns|number of columns|column count|total columns)', q)
        if col_match:
            return QueryResult(
                question=question,
                answer=self._profile.column_count,
                result_type="column_count",
                source_columns=self._profile.column_names,
                calculation_basis=f"Total columns in dataset: {self._profile.column_count}",
                limitations=[],
            )

        avg_match = re.search(r'(?:average|avg|mean)\s+(?:of\s+)?(.+?)(?:\s*[\?]?\s*$)', q)
        if avg_match:
            col_hint = avg_match.group(1).strip()
            col = self._find_matching_column(col_hint)
            if col and col in self._profile.column_profiles:
                cp = self._profile.column_profiles[col]
                if cp.numeric_stats and "mean" in cp.numeric_stats:
                    return QueryResult(
                        question=question,
                        answer=round(cp.numeric_stats["mean"], 4),
                        result_type="average",
                        source_columns=[col],
                        calculation_basis=f"Mean of {col}: {cp.numeric_stats['mean']:.4f} (count: {cp.numeric_stats.get('count', 0)})",
                        limitations=[],
                    )
                return QueryResult(
                    question=question,
                    answer=None,
                    result_type="average",
                    source_columns=[col],
                    calculation_basis=f"Column '{col}' found but has no numeric statistics",
                    supported=False,
                    reason=f"Column '{col}' is not numeric or has no computable mean",
                )
            return self._unsupported_result(question, f"No numeric column matching '{col_hint}' found")

        total_match = re.search(r'(?:total|sum)\s+(?:of\s+)?(.+?)(?:\s*[\?]?\s*$)', q)
        if total_match:
            col_hint = total_match.group(1).strip()
            col = self._find_matching_column(col_hint)
            if col and col in self._profile.column_profiles:
                cp = self._profile.column_profiles[col]
                if cp.numeric_stats and "sum" in cp.numeric_stats:
                    return QueryResult(
                        question=question,
                        answer=round(cp.numeric_stats["sum"], 4),
                        result_type="total",
                        source_columns=[col],
                        calculation_basis=f"Sum of {col}: {cp.numeric_stats['sum']:.4f} (count: {cp.numeric_stats.get('count', 0)})",
                        limitations=[],
                    )
                return QueryResult(
                    question=question,
                    answer=None,
                    result_type="total",
                    source_columns=[col],
                    calculation_basis=f"Column '{col}' found but has no numeric statistics",
                    supported=False,
                    reason=f"Column '{col}' is not numeric or has no computable sum",
                )
            return self._unsupported_result(question, f"No numeric column matching '{col_hint}' found")

        count_match = re.search(r'(?:how many|count of|number of)\s+(.+?)(?:\s*[\?]?\s*$)', q)
        if count_match:
            col_hint = count_match.group(1).strip()
            if 'row' in col_hint or 'record' in col_hint or 'entry' in col_hint:
                return QueryResult(
                    question=question,
                    answer=self._profile.row_count,
                    result_type="row_count",
                    source_columns=self._profile.column_names,
                    calculation_basis=f"Total rows: {self._profile.row_count}",
                    limitations=[],
                )
            col = self._find_matching_column(col_hint)
            if col and col in self._profile.column_profiles:
                cp = self._profile.column_profiles[col]
                distinct_count = cp.unique_count
                non_null_count = cp.numeric_stats.get("count", 0) if cp.numeric_stats else (self._profile.row_count - cp.null_count)
                return QueryResult(
                    question=question,
                    answer=distinct_count,
                    result_type="distinct_count",
                    source_columns=[col],
                    calculation_basis=f"Distinct count of {col}: {distinct_count} unique values (non-null: {non_null_count})",
                    limitations=["Count based on unique values in column"],
                )
            return self._unsupported_result(question, f"No column matching '{col_hint}' found")

        category_match = re.search(r'(?:which|what)\s+(?:category|categories|group|groups|type|types)\s+(?:has|have|had)\s+(?:the\s+)?(?:highest|most|largest|best)\s+(.+?)(?:\s*[\?]?\s*$)', q)
        if category_match:
            measure_hint = category_match.group(1).strip()
            measure_col = self._find_matching_column(measure_hint)
            cat_cols = self._get_role_columns(SemanticRole.CATEGORY)
            if not cat_cols:
                cat_cols = self._profile.categorical_columns[:3]
            if measure_col and cat_cols:
                cat_col = cat_cols[0]
                answer = self._compute_top_entities(cat_col, measure_col)
                if answer is not None:
                    return QueryResult(
                        question=question,
                        answer=answer,
                        result_type="top_category",
                        source_columns=[cat_col, measure_col],
                        calculation_basis=f"Top categories in {cat_col} by {measure_col}",
                        limitations=["Based on computed analytics"],
                    )
            return self._unsupported_result(question, f"Could not match columns for this question")

        trend_match = re.search(r'(?:show\s+)?(.+?)\s+trend(?:\s+over\s+time)?|(?:trend|over time|time series|evolution)\s+(?:of\s+)?(.+?)(?:\s*[\?]?\s*$)', q)
        if trend_match:
            col_hint = (trend_match.group(1) or trend_match.group(2) or "").strip()
            col = self._find_matching_column(col_hint)
            date_cols = self._get_role_columns(SemanticRole.DATE_TIME) or self._profile.datetime_columns
            if col and date_cols:
                return QueryResult(
                    question=question,
                    answer={"date_columns": date_cols, "measure_column": col, "message": f"Trend of {col} over time available via trend analysis endpoint"},
                    result_type="trend_reference",
                    source_columns=[col] + date_cols,
                    calculation_basis=f"Trend analysis for {col} over {date_cols[0]} - use dedicated trend endpoint for full results",
                    limitations=["Full trend computation available via dedicated trend analysis endpoint"],
                )
            return self._unsupported_result(question, f"No date/time column available for trend analysis of '{col_hint}'")

        max_match = re.search(r'(?:highest|maximum|max|largest|top)\s+(?:value\s+of\s+|of\s+)?(.+?)(?:\s*[\?]?\s*$)', q)
        if max_match:
            col_hint = max_match.group(1).strip()
            col = self._find_matching_column(col_hint)
            if col and col in self._profile.column_profiles:
                cp = self._profile.column_profiles[col]
                if cp.numeric_stats and "max" in cp.numeric_stats:
                    return QueryResult(
                        question=question,
                        answer=cp.numeric_stats["max"],
                        result_type="maximum",
                        source_columns=[col],
                        calculation_basis=f"Maximum of {col}: {cp.numeric_stats['max']}",
                        limitations=[],
                    )
                return QueryResult(
                    question=question,
                    answer=None,
                    result_type="maximum",
                    source_columns=[col],
                    calculation_basis=f"Column '{col}' found but has no numeric statistics",
                    supported=False,
                    reason=f"Column '{col}' is not numeric or has no computable maximum",
                )
            return self._unsupported_result(question, f"No numeric column matching '{col_hint}' found")

        min_match = re.search(r'(?:lowest|minimum|min|smallest|bottom)\s+(?:value\s+of\s+|of\s+)?(.+?)(?:\s*[\?]?\s*$)', q)
        if min_match:
            col_hint = min_match.group(1).strip()
            col = self._find_matching_column(col_hint)
            if col and col in self._profile.column_profiles:
                cp = self._profile.column_profiles[col]
                if cp.numeric_stats and "min" in cp.numeric_stats:
                    return QueryResult(
                        question=question,
                        answer=cp.numeric_stats["min"],
                        result_type="minimum",
                        source_columns=[col],
                        calculation_basis=f"Minimum of {col}: {cp.numeric_stats['min']}",
                        limitations=[],
                    )
                return QueryResult(
                    question=question,
                    answer=None,
                    result_type="minimum",
                    source_columns=[col],
                    calculation_basis=f"Column '{col}' found but has no numeric statistics",
                    supported=False,
                    reason=f"Column '{col}' is not numeric or has no computable minimum",
                )
            return self._unsupported_result(question, f"No numeric column matching '{col_hint}' found")

        median_match = re.search(r'(?:median|middle)\s+(?:value\s+of\s+|of\s+)?(.+?)(?:\s*[\?]?\s*$)', q)
        if median_match:
            col_hint = median_match.group(1).strip()
            col = self._find_matching_column(col_hint)
            if col and col in self._profile.column_profiles:
                cp = self._profile.column_profiles[col]
                if cp.numeric_stats and "median" in cp.numeric_stats:
                    return QueryResult(
                        question=question,
                        answer=cp.numeric_stats["median"],
                        result_type="median",
                        source_columns=[col],
                        calculation_basis=f"Median of {col}: {cp.numeric_stats['median']}",
                        limitations=[],
                    )
            return self._unsupported_result(question, f"No numeric column matching '{col_hint}' found")

        which_highest_match = re.search(r'(?:which|what)\s+(?:are|is|are the)\s+(?:the\s+)?(?:top|highest|best|most)\s+(.+?)(?:\s+with\s+(?:the\s+)?(?:highest|most|largest|best)\s+(.+?))?(?:\s*[\?]?\s*$)', q)
        if which_highest_match:
            entity_hint = which_highest_match.group(1).strip()
            measure_hint = which_highest_match.group(2)
            entity_col = self._find_matching_column(entity_hint)
            if entity_col and entity_col in self._profile.column_profiles:
                if measure_hint:
                    measure_col = self._find_matching_column(measure_hint)
                else:
                    measure_col = None
                    for mc in self._profile.numeric_columns:
                        if mc != entity_col:
                            measure_col = mc
                            break
                if measure_col and measure_col in self._profile.column_profiles:
                    answer = self._compute_top_entities(entity_col, measure_col)
                    if answer is not None:
                        return QueryResult(
                            question=question,
                            answer=answer,
                            result_type="top_entities",
                            source_columns=[entity_col, measure_col],
                            calculation_basis=f"Top entities in {entity_col} ranked by {measure_col}",
                            limitations=["Based on computed analytics; limited to available data"],
                        )
            return self._unsupported_result(question, f"Could not determine matching columns for this question")

        what_is_match = re.search(r'(?:what is|what\'s|tell me about|describe|summary of|info about)\s+(.+?)(?:\s*[\?]?\s*$)', q)
        if what_is_match:
            col_hint = what_is_match.group(1).strip()
            col = self._find_matching_column(col_hint)
            if col and col in self._profile.column_profiles:
                cp = self._profile.column_profiles[col]
                answer = {
                    "column": col,
                    "type": cp.inferred_type.value,
                    "unique_count": cp.unique_count,
                    "null_count": cp.null_count,
                    "null_percentage": cp.null_percentage,
                }
                if cp.numeric_stats:
                    answer["numeric_stats"] = cp.numeric_stats
                if cp.categorical_summary:
                    answer["top_categories"] = dict(list(cp.categorical_summary.items())[:5])
                if cp.sample_values:
                    answer["sample_values"] = cp.sample_values[:5]
                return QueryResult(
                    question=question,
                    answer=answer,
                    result_type="column_info",
                    source_columns=[col],
                    calculation_basis=f"Column profile information for {col}",
                    limitations=[],
                )
            return self._unsupported_result(question, f"No column matching '{col_hint}' found")

        return self._unsupported_result(
            question,
            "This question could not be mapped to a deterministic computation. "
            "Try asking about: row count, column count, average/total/min/max of a column, "
            "distinct count, top entities, or column information."
        )

    def _compute_top_entities(self, entity_col: str, measure_col: str) -> Optional[List[Dict[str, Any]]]:
        reader = self._get_reader()
        if not reader:
            entity_cp = self._profile.column_profiles.get(entity_col)
            if entity_cp and entity_cp.categorical_summary:
                measure_cp = self._profile.column_profiles.get(measure_col)
                if measure_cp and measure_cp.numeric_stats:
                    top_cats = list(entity_cp.categorical_summary.items())[:10]
                    return [{"entity": cat, "count": cnt} for cat, cnt in top_cats]
            return None

        try:
            df_chunks = reader.read_csv_chunked(columns=[entity_col, measure_col], max_chunks=50)
            all_rows = []
            for chunk in df_chunks:
                all_rows.extend(chunk["rows"])
            if not all_rows:
                return None

            df = pd.DataFrame(all_rows)
            df[measure_col] = pd.to_numeric(df[measure_col], errors="coerce")
            df = df.dropna(subset=[entity_col, measure_col])

            if len(df) == 0:
                return None

            grouped = df.groupby(entity_col)[measure_col].mean().reset_index()
            grouped = grouped.sort_values(measure_col, ascending=False).head(10)
            return grouped.to_dict(orient="records")
        except Exception:
            return None

    def _unsupported_result(self, question: str, reason: str) -> QueryResult:
        return QueryResult(
            question=question,
            answer=None,
            result_type="unsupported",
            source_columns=[],
            calculation_basis="Question could not be mapped to a deterministic computation",
            supported=False,
            reason=reason,
            limitations=["Only deterministic questions mapped to existing column data are supported"],
        )

    def compute_all(self) -> QueryAnalysisReport:
        text_cols = self._get_role_columns(SemanticRole.ID_KEY) + self._get_role_columns(
            SemanticRole.ENTITY
        )
        available_text = [c for c in text_cols if c in self._profile.column_profiles]
        numeric_cols = self._profile.numeric_columns
        available_numeric = [c for c in numeric_cols if c in self._profile.column_profiles]
        date_cols = self._get_role_columns(SemanticRole.DATE_TIME) or self._profile.datetime_columns
        available_date = [c for c in date_cols if c in self._profile.column_profiles]

        searchable = list(set(available_text + available_numeric + available_date))
        total_columns = max(len(self._profile.column_names), 1)

        return QueryAnalysisReport(
            dataset_id=self._profile.dataset_id,
            queries=[],
            searchable_columns=searchable,
            total_searchable=len(searchable),
            column_coverage=round(len(searchable) / total_columns, 4),
            computed_at=datetime.utcnow(),
        )


def create_query_engine(
    profile: DatasetProfile,
    schema_intelligence: SchemaIntelligence | None = None,
    reader_provider: Optional[callable] | None = None,
) -> QueryEngine:
    return QueryEngine(profile, schema_intelligence, reader_provider)
