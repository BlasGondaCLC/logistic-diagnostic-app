"""
backend/data_quality_engine.py
================================
Motor de calidad de datos.
Para cada tabla detecta: nulos críticos, fechas inválidas, negativos,
ceros, duplicados, SKUs vacíos, documentos vacíos, cross-table issues.

También genera advertencias cross-table (ej: SKUs en pedidos que no están en maestro).
"""

import logging
from typing import List, Dict, Optional, Tuple

import pandas as pd
import numpy as np

from config import NULL_WARNING_THRESHOLD, NULL_ERROR_THRESHOLD
from models.table_profile import TableProfile, QualityIssue

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# ---------------------------------------------------------------------------

def run_quality_checks(
    profiles: List[TableProfile],
    loaded_tables: list,  # List[(df, file_name, sheet_name)]
) -> Tuple[List[TableProfile], List[str]]:
    """
    Ejecuta todas las verificaciones de calidad.

    Args:
        profiles: Lista de TableProfile con semánticas y tipos ya detectados.
        loaded_tables: DataFrames originales para análisis de contenido.

    Returns:
        (profiles_con_issues, cross_table_warnings)
    """
    # Mapa de table_id → DataFrame
    df_map = _build_df_map(loaded_tables)

    # Checks individuales por tabla
    for profile in profiles:
        df = df_map.get(profile.table_id)
        if df is not None:
            _check_single_table(profile, df)

    # Checks cross-tabla
    cross_warnings = _check_cross_table(profiles, df_map)

    return profiles, cross_warnings


# ---------------------------------------------------------------------------
# CHECKS POR TABLA
# ---------------------------------------------------------------------------

def _check_single_table(profile: TableProfile, df: pd.DataFrame) -> None:
    """
    Ejecuta todos los checks de calidad para una tabla.
    Agrega QualityIssue a profile.quality_issues.
    """
    issues = []

    # 1. Nulos por columna crítica
    issues.extend(_check_nulls(profile, df))

    # 2. Fechas inválidas
    issues.extend(_check_invalid_dates(profile, df))

    # 3. Cantidades negativas
    issues.extend(_check_negative_quantities(profile, df))

    # 4. Cantidades cero
    issues.extend(_check_zero_quantities(profile, df))

    # 5. Duplicados potenciales
    issues.extend(_check_duplicates(profile, df))

    # 6. SKUs vacíos
    issues.extend(_check_empty_keys(profile, df))

    # 7. Columnas críticas faltantes según tipo de tabla
    issues.extend(_check_missing_critical_columns(profile))

    profile.quality_issues = issues


def _check_nulls(profile: TableProfile, df: pd.DataFrame) -> List[QualityIssue]:
    """Verifica nulos en columnas críticas según el tipo de tabla."""
    issues = []

    # Columnas críticas por tipo de tabla
    critical_semantics = _get_critical_semantics_for_type(profile.table_type)

    for col_profile in profile.columns:
        pct = col_profile.null_percentage

        # Solo reportar si supera umbral
        if pct < NULL_WARNING_THRESHOLD:
            continue

        severity = "error" if pct >= NULL_ERROR_THRESHOLD else "warning"

        # Determinar si es una columna crítica para este tipo de tabla
        is_critical = col_profile.detected_semantic in critical_semantics
        if is_critical:
            severity = "error"

        issues.append(QualityIssue(
            severity=severity,
            column=col_profile.original_name,
            issue_type="nulls",
            description=(
                f"Columna '{col_profile.original_name}' "
                f"({'crítica: ' + col_profile.detected_semantic if is_critical else 'opcional'}) "
                f"tiene {pct*100:.1f}% de valores nulos."
            ),
            affected_count=col_profile.null_count,
            affected_percentage=pct,
        ))

    return issues


def _check_invalid_dates(profile: TableProfile, df: pd.DataFrame) -> List[QualityIssue]:
    """Verifica fechas inválidas o fuera de rango razonable."""
    issues = []

    date_cols = [col for col in profile.columns if col.inferred_type == "date"]

    for col_profile in date_cols:
        col_name = col_profile.original_name
        if col_name not in df.columns:
            continue

        series = pd.to_datetime(df[col_name], errors="coerce")
        invalid_count = series.isna().sum() - df[col_name].isna().sum()

        if invalid_count > 0:
            pct = invalid_count / len(df)
            issues.append(QualityIssue(
                severity="warning" if pct < 0.05 else "error",
                column=col_name,
                issue_type="invalid_date",
                description=f"Columna '{col_name}': {invalid_count} fechas no parseables.",
                affected_count=int(invalid_count),
                affected_percentage=float(pct),
            ))

        # Detectar fechas fuera de rango razonable (1990 - 2030)
        if series.notna().sum() > 0:
            valid_dates = series.dropna()
            min_date = pd.Timestamp("1990-01-01")
            max_date = pd.Timestamp("2030-12-31")
            out_of_range = ((valid_dates < min_date) | (valid_dates > max_date)).sum()
            if out_of_range > 0:
                issues.append(QualityIssue(
                    severity="warning",
                    column=col_name,
                    issue_type="date_out_of_range",
                    description=(
                        f"Columna '{col_name}': {out_of_range} fechas fuera de rango 1990-2030. "
                        f"Verificar formato de fecha."
                    ),
                    affected_count=int(out_of_range),
                    affected_percentage=float(out_of_range / len(df)),
                ))

    return issues


def _check_negative_quantities(profile: TableProfile, df: pd.DataFrame) -> List[QualityIssue]:
    """Detecta cantidades negativas en columnas de tipo Cantidad o Stock."""
    issues = []

    qty_semantics = ["Cantidad", "Stock"]
    qty_cols = [
        col for col in profile.columns
        if col.detected_semantic in qty_semantics and col.inferred_type == "numeric"
    ]

    for col_profile in qty_cols:
        col_name = col_profile.original_name
        if col_name not in df.columns:
            continue

        series = pd.to_numeric(df[col_name], errors="coerce").dropna()
        if len(series) == 0:
            continue

        negative_count = (series < 0).sum()
        if negative_count > 0:
            pct = negative_count / len(series)
            # Cantidades negativas no son siempre un error (reversas, ajustes)
            # pero son una advertencia si no es tabla de ajustes/movimientos
            severity = "info" if profile.table_type in ("Ajustes",) else "warning"

            issues.append(QualityIssue(
                severity=severity,
                column=col_name,
                issue_type="negative_quantity",
                description=(
                    f"Columna '{col_name}': {negative_count} valores negativos "
                    f"({pct*100:.1f}%). "
                    + ("Posibles reversas o ajustes. Validar." if severity == "warning"
                       else "Esperado para tabla de ajustes.")
                ),
                affected_count=int(negative_count),
                affected_percentage=float(pct),
            ))

    return issues


def _check_zero_quantities(profile: TableProfile, df: pd.DataFrame) -> List[QualityIssue]:
    """Detecta movimientos con cantidad cero, que suelen ser errores."""
    issues = []

    # Solo relevante en tablas de movimientos
    movement_types = [
        "Recepciones", "Pedidos", "Preparaciones",
        "Transferencias", "Ajustes",
        "Devoluciones Cliente", "Devoluciones Proveedor",
    ]
    if profile.table_type not in movement_types:
        return issues

    qty_cols = [
        col for col in profile.columns
        if col.detected_semantic == "Cantidad" and col.inferred_type == "numeric"
    ]

    for col_profile in qty_cols:
        col_name = col_profile.original_name
        if col_name not in df.columns:
            continue

        series = pd.to_numeric(df[col_name], errors="coerce").dropna()
        if len(series) == 0:
            continue

        zero_count = (series == 0).sum()
        if zero_count > 0:
            pct = zero_count / len(series)
            if pct > 0.02:  # Más del 2% de ceros es sospechoso
                issues.append(QualityIssue(
                    severity="warning",
                    column=col_name,
                    issue_type="zero_quantity",
                    description=(
                        f"Columna '{col_name}': {zero_count} movimientos con cantidad = 0 "
                        f"({pct*100:.1f}%). Verificar si son registros válidos."
                    ),
                    affected_count=int(zero_count),
                    affected_percentage=float(pct),
                ))

    return issues


def _check_duplicates(profile: TableProfile, df: pd.DataFrame) -> List[QualityIssue]:
    """Detecta filas duplicadas potenciales."""
    issues = []

    if len(df) < 2:
        return issues

    # Verificar duplicados por columnas clave
    key_semantics = ["SKU", "Documento", "Fecha", "Cliente", "Proveedor"]
    key_cols = [
        col.original_name for col in profile.columns
        if col.detected_semantic in key_semantics
        and col.original_name in df.columns
    ]

    if len(key_cols) >= 2:
        subset_cols = key_cols[:4]  # Máximo 4 columnas clave
        try:
            dup_count = df.duplicated(subset=subset_cols, keep="first").sum()
            if dup_count > 0:
                pct = dup_count / len(df)
                issues.append(QualityIssue(
                    severity="warning" if pct < 0.05 else "error",
                    column=None,
                    issue_type="duplicates",
                    description=(
                        f"{dup_count} filas duplicadas detectadas "
                        f"({pct*100:.1f}%) usando columnas clave: {', '.join(subset_cols)}."
                    ),
                    affected_count=int(dup_count),
                    affected_percentage=float(pct),
                ))
        except Exception:
            pass

    # También verificar duplicados de filas totales
    total_dups = df.duplicated(keep="first").sum()
    if total_dups > 0:
        pct = total_dups / len(df)
        if pct > 0.001:  # Más del 0.1% de duplicados totales
            issues.append(QualityIssue(
                severity="warning",
                column=None,
                issue_type="exact_duplicates",
                description=f"{total_dups} filas exactamente duplicadas ({pct*100:.1f}%).",
                affected_count=int(total_dups),
                affected_percentage=float(pct),
            ))

    return issues


def _check_empty_keys(profile: TableProfile, df: pd.DataFrame) -> List[QualityIssue]:
    """Verifica claves vacías: SKU, Documento, Cliente, Proveedor."""
    issues = []

    key_semantics = ["SKU", "Documento", "Cliente", "Proveedor", "Deposito"]

    for col_profile in profile.columns:
        if col_profile.detected_semantic not in key_semantics:
            continue

        col_name = col_profile.original_name
        if col_name not in df.columns:
            continue

        series = df[col_name]
        # Verificar vacíos (nulo + string vacío)
        empty_mask = series.isna() | (series.astype(str).str.strip() == "")
        empty_count = empty_mask.sum()

        if empty_count > 0:
            pct = empty_count / len(df)
            severity = "error" if col_profile.detected_semantic == "SKU" else "warning"
            issues.append(QualityIssue(
                severity=severity,
                column=col_name,
                issue_type="empty_key",
                description=(
                    f"Clave '{col_profile.detected_semantic}' (columna '{col_name}'): "
                    f"{empty_count} valores vacíos ({pct*100:.1f}%). "
                    "Esto puede afectar relaciones y análisis."
                ),
                affected_count=int(empty_count),
                affected_percentage=float(pct),
            ))

    return issues


def _check_missing_critical_columns(profile: TableProfile) -> List[QualityIssue]:
    """
    Verifica si faltan columnas críticas para el tipo de tabla clasificado.
    """
    issues = []

    from config import TABLE_TYPE_INDICATORS

    if profile.table_type not in TABLE_TYPE_INDICATORS:
        return issues

    rules = TABLE_TYPE_INDICATORS[profile.table_type]
    required = rules.get("required", [])

    detected_semantics = {col.detected_semantic for col in profile.columns}

    missing = [f for f in required if f not in detected_semantics]

    for field_name in missing:
        issues.append(QualityIssue(
            severity="error",
            column=None,
            issue_type="missing_critical_column",
            description=(
                f"Tabla clasificada como '{profile.table_type}' "
                f"pero falta columna crítica: {field_name}. "
                "Verificar mapeo de columnas."
            ),
            affected_count=0,
            affected_percentage=0.0,
        ))

    return issues


# ---------------------------------------------------------------------------
# CHECKS CROSS-TABLA
# ---------------------------------------------------------------------------

def _check_cross_table(
    profiles: List[TableProfile],
    df_map: Dict[str, pd.DataFrame],
) -> List[str]:
    """
    Verifica consistencia entre tablas.
    Por ejemplo: SKUs en pedidos que no están en el maestro de productos.
    """
    warnings = []

    active = [p for p in profiles if p.include_in_analysis]

    # Buscar maestro de productos
    maestros = [p for p in active if p.table_type == "Maestro de Productos"]
    movement_tables = [
        p for p in active
        if p.table_type in (
            "Recepciones", "Pedidos", "Preparaciones",
            "Transferencias", "Stock",
        )
    ]

    if maestros and movement_tables:
        warnings.extend(_check_skus_vs_master(maestros, movement_tables, df_map))

    # Verificar consistencia de fechas entre tablas (rangos muy diferentes)
    dated_tables = [p for p in active if p.date_min and p.date_max]
    if len(dated_tables) >= 2:
        warnings.extend(_check_date_range_consistency(dated_tables))

    return warnings


def _check_skus_vs_master(
    maestros: List[TableProfile],
    movement_tables: List[TableProfile],
    df_map: Dict[str, pd.DataFrame],
) -> List[str]:
    """Verifica SKUs en movimientos que no están en el maestro."""
    warnings = []

    # Recopilar SKUs del maestro
    master_skus = set()
    for m in maestros:
        df = df_map.get(m.table_id)
        if df is None:
            continue
        sku_col = m.get_column_for_semantic("SKU")
        if sku_col and sku_col in df.columns:
            master_skus.update(df[sku_col].dropna().astype(str).str.strip().unique())

    if not master_skus:
        return warnings

    for table in movement_tables:
        df = df_map.get(table.table_id)
        if df is None:
            continue
        sku_col = table.get_column_for_semantic("SKU")
        if not sku_col or sku_col not in df.columns:
            continue

        table_skus = set(df[sku_col].dropna().astype(str).str.strip().unique())
        orphan_skus = table_skus - master_skus

        if orphan_skus:
            pct = len(orphan_skus) / max(len(table_skus), 1) * 100
            warnings.append(
                f"⚠️ {table.display_name}: {len(orphan_skus)} SKUs ({pct:.1f}%) "
                f"no están en el maestro de productos. "
                f"Ejemplos: {', '.join(list(orphan_skus)[:5])}."
            )

    return warnings


def _check_date_range_consistency(dated_tables: List[TableProfile]) -> List[str]:
    """Advierte si las tablas tienen rangos temporales muy distintos."""
    warnings = []

    date_mins = [(t.display_name, t.date_min) for t in dated_tables if t.date_min]
    date_maxs = [(t.display_name, t.date_max) for t in dated_tables if t.date_max]

    if not date_mins or not date_maxs:
        return warnings

    import statistics
    from datetime import datetime

    all_mins = [d for _, d in date_mins]
    all_maxs = [d for _, d in date_maxs]

    global_min = min(all_mins)
    global_max = max(all_maxs)

    # Si hay tablas con rango muy diferente (más de 1 año de diferencia)
    span_days = (global_max - global_min).days if hasattr(global_max - global_min, 'days') else 0

    if span_days > 365 * 2:
        warnings.append(
            f"⚠️ Las tablas cubren un rango de {span_days} días en total. "
            f"Verificar que los períodos sean compatibles para el análisis."
        )

    # Verificar si alguna tabla tiene un rango muy chico comparado con el resto
    for name, d_min in date_mins:
        for _, d_max in date_maxs:
            if hasattr(d_max - d_min, 'days'):
                table_span = (d_max - d_min).days
                if table_span < 30 and span_days > 180:
                    warnings.append(
                        f"⚠️ La tabla '{name}' tiene un rango de solo {table_span} días "
                        "mientras otras tablas cubren períodos más largos."
                    )
                    break

    return warnings


# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def _build_df_map(loaded_tables: list) -> Dict[str, pd.DataFrame]:
    """Construye un mapa de table_id → DataFrame."""
    df_map = {}
    for df, file_name, sheet_name in loaded_tables:
        if sheet_name:
            tid = f"{file_name}::{sheet_name}"
        else:
            tid = file_name
        df_map[tid] = df
    return df_map


def _get_critical_semantics_for_type(table_type: str) -> List[str]:
    """Retorna los campos críticos (semánticos) para un tipo de tabla."""
    from config import TABLE_TYPE_INDICATORS
    if table_type not in TABLE_TYPE_INDICATORS:
        return []
    return TABLE_TYPE_INDICATORS[table_type].get("required", [])
