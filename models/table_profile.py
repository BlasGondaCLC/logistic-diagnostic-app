"""
models/table_profile.py
=======================
Dataclasses compartidas por todo el pipeline de diagnóstico logístico.

Este archivo concentra los objetos de dominio usados por:
- carga y perfilado de tablas
- detección semántica de columnas
- calidad de datos
- matriz de factibilidad
- exportación y generación del prompt MCP
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ColumnProfile:
    """Perfil técnico y semántico de una columna."""

    original_name: str
    inferred_type: str = "text"  # date, numeric, categorical, text, boolean, mixed
    null_count: int = 0
    null_percentage: float = 0.0
    unique_count: int = 0
    total_count: int = 0
    sample_values: List[Any] = field(default_factory=list)
    detected_semantic: str = "Desconocido"
    detection_confidence: float = 0.0
    detection_method: str = "none"  # heuristic, llm, manual, none


@dataclass
class QualityIssue:
    """Problema o advertencia de calidad de datos."""

    severity: str  # error, warning, info
    column: Optional[str]
    issue_type: str
    description: str
    affected_count: int = 0
    affected_percentage: float = 0.0


@dataclass
class FeasibilityResult:
    """Resultado de factibilidad para un bloque/análisis logístico."""

    analysis_name: str
    status: str
    required_fields: List[str] = field(default_factory=list)
    found_fields: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    source_tables: List[str] = field(default_factory=list)
    reasoning: str = ""
    partial_reasons: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    proxy_available: bool = False
    proxy_description: str = ""

    @property
    def is_possible(self) -> bool:
        return self.status.startswith("✅")

    @property
    def is_partial(self) -> bool:
        return self.status.startswith("⚠️")

    @property
    def is_impossible(self) -> bool:
        return self.status.startswith("❌")


@dataclass
class TableProfile:
    """Perfil completo de una tabla cargada desde Excel/CSV."""

    file_name: str
    sheet_name: Optional[str]
    row_count: int
    col_count: int
    columns: List[ColumnProfile] = field(default_factory=list)
    date_min: Optional[datetime] = None
    date_max: Optional[datetime] = None

    table_type: str = "Otro"
    type_confidence: float = 0.0
    type_reasoning: str = ""
    type_scores: Dict[str, float] = field(default_factory=dict)

    include_in_analysis: bool = True
    column_mapping: Dict[str, str] = field(default_factory=dict)  # SemanticType -> original column name
    quality_issues: List[QualityIssue] = field(default_factory=list)

    @property
    def table_id(self) -> str:
        return f"{self.file_name}::{self.sheet_name}" if self.sheet_name else self.file_name

    @property
    def display_name(self) -> str:
        return f"{self.file_name} · {self.sheet_name}" if self.sheet_name else self.file_name

    @property
    def date_range_str(self) -> str:
        if self.date_min and self.date_max:
            try:
                start = self.date_min.strftime("%d/%m/%Y")
                end = self.date_max.strftime("%d/%m/%Y")
                return f"{start} → {end}"
            except Exception:
                return f"{self.date_min} → {self.date_max}"
        return "Sin fechas detectadas"

    @property
    def quality_score(self) -> float:
        """
        Score simple 0-1 basado en severidad y porcentaje afectado.
        No pretende reemplazar auditoría humana; sirve como semáforo rápido.
        """
        if not self.quality_issues:
            return 1.0

        penalty = 0.0
        for issue in self.quality_issues:
            base = {
                "error": 0.22,
                "warning": 0.10,
                "info": 0.03,
            }.get(issue.severity, 0.05)
            pct_factor = min(max(issue.affected_percentage, 0.0), 1.0)
            # Si el issue no trae porcentaje pero es crítico, aplicar penalización mínima.
            if pct_factor == 0 and issue.severity == "error":
                pct_factor = 0.25
            penalty += base * (0.5 + pct_factor)

        return max(0.0, min(1.0, 1.0 - penalty))

    @property
    def quality_label(self) -> str:
        score = self.quality_score
        has_error = any(i.severity == "error" for i in self.quality_issues)
        has_warning = any(i.severity == "warning" for i in self.quality_issues)

        if has_error or score < 0.55:
            return "🔴 Revisar"
        if has_warning or score < 0.80:
            return "🟡 Aceptable con advertencias"
        return "🟢 Buena"

    def build_effective_mapping(self) -> Dict[str, str]:
        """
        Devuelve el mapeo final SemanticType -> columna original.
        Prioriza correcciones manuales y completa con detecciones automáticas.
        """
        mapping: Dict[str, str] = dict(self.column_mapping or {})
        for col in self.columns:
            semantic = col.detected_semantic
            if semantic and semantic != "Desconocido" and semantic not in mapping:
                mapping[semantic] = col.original_name
        return mapping

    def has_semantic(self, semantic: str) -> bool:
        if semantic in self.column_mapping:
            return True
        return any(c.detected_semantic == semantic for c in self.columns)

    def get_column_for_semantic(self, semantic: str) -> Optional[str]:
        if semantic in self.column_mapping:
            return self.column_mapping[semantic]
        for col in self.columns:
            if col.detected_semantic == semantic:
                return col.original_name
        return None

    def get_all_semantics(self) -> List[str]:
        semantics = set(self.column_mapping.keys())
        for col in self.columns:
            if col.detected_semantic and col.detected_semantic != "Desconocido":
                semantics.add(col.detected_semantic)
        return sorted(semantics)


@dataclass
class DiagnosticReport:
    """Resultado global del diagnóstico."""

    tables: List[TableProfile] = field(default_factory=list)
    feasibility_matrix: List[FeasibilityResult] = field(default_factory=list)
    general_summary: str = ""
    possible_analyses: List[str] = field(default_factory=list)
    partial_analyses: List[str] = field(default_factory=list)
    impossible_analyses: List[str] = field(default_factory=list)
    suggested_assumptions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    cross_table_issues: List[str] = field(default_factory=list)

    @property
    def active_tables(self) -> List[TableProfile]:
        return [t for t in self.tables if t.include_in_analysis]

    @property
    def overall_feasibility_percentage(self) -> float:
        total = len(self.feasibility_matrix)
        if total == 0:
            return 0.0
        possible = len(self.possible_analyses)
        partial = len(self.partial_analyses)
        return round(((possible + partial * 0.5) / total) * 100, 1)
