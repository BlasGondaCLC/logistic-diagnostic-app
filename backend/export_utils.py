"""
backend/export_utils.py
========================
Utilidades de exportación.
Genera TXT (diagnóstico + prompt) y JSON técnico del análisis.
"""

import json
from datetime import datetime
from typing import Optional

from models.table_profile import DiagnosticReport, TableProfile, FeasibilityResult


# ---------------------------------------------------------------------------
# EXPORTAR DIAGNÓSTICO COMO TXT
# ---------------------------------------------------------------------------

def export_diagnostic_txt(report: DiagnosticReport, project_name: str = "") -> str:
    """
    Genera el diagnóstico completo como texto plano.
    Incluye: resumen, archivos, calidad y matriz de factibilidad.
    """
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    name_str = f" — {project_name}" if project_name else ""

    lines = [
        f"DIAGNÓSTICO LOGÍSTICO{name_str}",
        f"Generado: {date_str}",
        "=" * 80,
        "",
        "RESUMEN EJECUTIVO",
        "-" * 40,
        report.general_summary,
        "",
        f"Análisis posibles: {len(report.possible_analyses)}",
        f"Análisis parciales: {len(report.partial_analyses)}",
        f"Análisis no posibles: {len(report.impossible_analyses)}",
        "",
    ]

    # Advertencias
    if report.warnings:
        lines.append("ADVERTENCIAS")
        lines.append("-" * 40)
        for w in report.warnings:
            lines.append(f"  {w}")
        lines.append("")

    # Archivos cargados
    lines.append("ARCHIVOS CARGADOS")
    lines.append("-" * 40)
    for table in report.active_tables:
        lines.append(f"\n  {table.display_name}")
        lines.append(f"    Tipo: {table.table_type} (confianza: {table.type_confidence*100:.0f}%)")
        lines.append(f"    Filas: {table.row_count:,} | Columnas: {table.col_count}")
        lines.append(f"    Período: {table.date_range_str}")
        lines.append(f"    Calidad: {table.quality_label}")

        # Mapeo de columnas
        mapping = table.build_effective_mapping()
        if mapping:
            lines.append("    Mapeo de columnas:")
            for semantic, original in mapping.items():
                lines.append(f"      {original} → {semantic}")

        # Problemas
        errors = [i for i in table.quality_issues if i.severity == "error"]
        warnings_list = [i for i in table.quality_issues if i.severity == "warning"]
        if errors:
            lines.append(f"    Errores ({len(errors)}):")
            for e in errors:
                lines.append(f"      🔴 {e.description}")
        if warnings_list:
            lines.append(f"    Advertencias ({len(warnings_list)}):")
            for w in warnings_list:
                lines.append(f"      🟡 {w.description}")

    lines.append("")

    # Matriz de factibilidad
    lines.append("MATRIZ DE FACTIBILIDAD")
    lines.append("-" * 40)

    for result in report.feasibility_matrix:
        lines.append(f"\n  {result.status}  {result.analysis_name}")
        lines.append(f"    {result.reasoning}")
        if result.missing_fields:
            lines.append(f"    Faltan: {', '.join(result.missing_fields)}")
        if result.partial_reasons:
            for r in result.partial_reasons:
                lines.append(f"    Parcial por: {r}")
        if result.proxy_available:
            lines.append(f"    Proxy: {result.proxy_description}")

    lines.append("")

    # Supuestos sugeridos
    if report.suggested_assumptions:
        lines.append("SUPUESTOS SUGERIDOS")
        lines.append("-" * 40)
        for s in report.suggested_assumptions:
            lines.append(f"  - {s}")
        lines.append("")

    # Problemas cross-tabla
    if report.cross_table_issues:
        lines.append("INCONSISTENCIAS ENTRE TABLAS")
        lines.append("-" * 40)
        for issue in report.cross_table_issues:
            lines.append(f"  {issue}")
        lines.append("")

    lines.append("=" * 80)
    lines.append("FIN DEL DIAGNÓSTICO")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# EXPORTAR PERFIL TÉCNICO COMO JSON
# ---------------------------------------------------------------------------

def export_technical_profile_json(
    report: DiagnosticReport,
    project_name: str = "",
) -> str:
    """
    Genera un JSON técnico con todos los metadatos del análisis.
    Útil para versionado, auditoría o reutilización.
    """
    data = {
        "metadata": {
            "project_name": project_name,
            "generated_at": datetime.now().isoformat(),
            "total_tables": len(report.active_tables),
            "total_rows": sum(t.row_count for t in report.active_tables),
            "feasibility_summary": {
                "possible": len(report.possible_analyses),
                "partial": len(report.partial_analyses),
                "impossible": len(report.impossible_analyses),
                "overall_pct": round(report.overall_feasibility_percentage, 1),
            },
        },
        "tables": [_table_to_dict(t) for t in report.active_tables],
        "feasibility_matrix": [_feasibility_to_dict(r) for r in report.feasibility_matrix],
        "warnings": report.warnings,
        "cross_table_issues": report.cross_table_issues,
        "suggested_assumptions": report.suggested_assumptions,
        "possible_analyses": report.possible_analyses,
        "partial_analyses": report.partial_analyses,
        "impossible_analyses": report.impossible_analyses,
        "general_summary": report.general_summary,
    }

    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _table_to_dict(table: TableProfile) -> dict:
    return {
        "table_id": table.table_id,
        "display_name": table.display_name,
        "file_name": table.file_name,
        "sheet_name": table.sheet_name,
        "row_count": table.row_count,
        "col_count": table.col_count,
        "table_type": table.table_type,
        "type_confidence": round(table.type_confidence, 3),
        "type_reasoning": table.type_reasoning,
        "date_min": str(table.date_min) if table.date_min else None,
        "date_max": str(table.date_max) if table.date_max else None,
        "quality_score": round(table.quality_score, 3),
        "quality_label": table.quality_label,
        "column_mapping": table.build_effective_mapping(),
        "columns": [
            {
                "original_name": col.original_name,
                "inferred_type": col.inferred_type,
                "detected_semantic": col.detected_semantic,
                "detection_confidence": round(col.detection_confidence, 3),
                "detection_method": col.detection_method,
                "null_percentage": round(col.null_percentage, 3),
                "unique_count": col.unique_count,
                "sample_values": col.sample_values[:3],
            }
            for col in table.columns
        ],
        "quality_issues": [
            {
                "severity": issue.severity,
                "column": issue.column,
                "issue_type": issue.issue_type,
                "description": issue.description,
                "affected_count": issue.affected_count,
                "affected_percentage": round(issue.affected_percentage, 3),
            }
            for issue in table.quality_issues
        ],
    }


def _feasibility_to_dict(result: FeasibilityResult) -> dict:
    return {
        "analysis_name": result.analysis_name,
        "status": result.status,
        "required_fields": result.required_fields,
        "found_fields": result.found_fields,
        "missing_fields": result.missing_fields,
        "source_tables": result.source_tables,
        "reasoning": result.reasoning,
        "partial_reasons": result.partial_reasons,
        "suggestions": result.suggestions,
        "proxy_available": result.proxy_available,
        "proxy_description": result.proxy_description,
    }
