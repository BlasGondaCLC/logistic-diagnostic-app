"""
backend/schema_profiler.py
==========================
Genera el perfil de cada tabla cargada.
Para cada columna detecta: tipo de dato, nulos, únicos, rango de fechas.
Convierte (df, file_name, sheet_name) → TableProfile.
"""

import logging
from typing import List, Optional, Tuple

import pandas as pd
import numpy as np

from models.table_profile import ColumnProfile, TableProfile

logger = logging.getLogger(__name__)


def profile_tables(
    loaded_tables: list,  # List[Tuple[pd.DataFrame, str, Optional[str]]]
) -> List[TableProfile]:
    """
    Genera TableProfile para cada tabla cargada.

    Args:
        loaded_tables: lista de (df, file_name, sheet_name) del file_loader.

    Returns:
        Lista de TableProfile.
    """
    profiles = []
    for df, file_name, sheet_name in loaded_tables:
        try:
            profile = _profile_single_table(df, file_name, sheet_name)
            profiles.append(profile)
        except Exception as e:
            logger.exception(f"Error perfilando {file_name}::{sheet_name}: {e}")
    return profiles


def _profile_single_table(
    df: pd.DataFrame,
    file_name: str,
    sheet_name: Optional[str],
) -> TableProfile:
    """Genera el perfil completo de una sola tabla."""

    row_count = len(df)
    col_count = len(df.columns)

    # Perfil de columnas
    column_profiles = []
    date_min_global = None
    date_max_global = None

    for col_name in df.columns:
        series = df[col_name]
        col_profile = _profile_column(series, col_name)
        column_profiles.append(col_profile)

        # Recopilar rango de fechas global
        if col_profile.inferred_type == "date":
            dates = series.dropna()
            if len(dates) > 0:
                try:
                    col_min = dates.min()
                    col_max = dates.max()
                    if pd.notna(col_min):
                        if date_min_global is None or col_min < date_min_global:
                            date_min_global = col_min
                    if pd.notna(col_max):
                        if date_max_global is None or col_max > date_max_global:
                            date_max_global = col_max
                except Exception:
                    pass

    return TableProfile(
        file_name=file_name,
        sheet_name=sheet_name,
        row_count=row_count,
        col_count=col_count,
        columns=column_profiles,
        date_min=pd.Timestamp(date_min_global).to_pydatetime() if date_min_global is not None else None,
        date_max=pd.Timestamp(date_max_global).to_pydatetime() if date_max_global is not None else None,
    )


def _profile_column(series: pd.Series, col_name: str) -> ColumnProfile:
    """Genera el perfil de una columna individual."""

    total_count = len(series)
    null_count = series.isna().sum()
    null_pct = (null_count / total_count) if total_count > 0 else 0.0

    non_null = series.dropna()
    unique_count = non_null.nunique()

    # Detectar tipo
    inferred_type = _infer_column_type(series)

    # Muestras representativas
    sample_values = _get_sample_values(non_null, inferred_type)

    return ColumnProfile(
        original_name=col_name,
        inferred_type=inferred_type,
        null_count=int(null_count),
        null_percentage=float(null_pct),
        unique_count=int(unique_count),
        total_count=int(total_count),
        sample_values=sample_values,
    )


def _infer_column_type(series: pd.Series) -> str:
    """
    Infiere el tipo lógico de una columna pandas.
    Posibles: "date", "numeric", "categorical", "text", "boolean", "mixed"
    """
    dtype = series.dtype

    # Ya fue parseado como datetime por el file_loader
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "date"

    # Numérico (entero o float)
    if pd.api.types.is_numeric_dtype(dtype):
        return "numeric"

    # Boolean
    if pd.api.types.is_bool_dtype(dtype):
        return "boolean"

    # Object/string: distinguir entre categórico y texto libre
    non_null = series.dropna()
    if len(non_null) == 0:
        return "text"

    unique_ratio = non_null.nunique() / len(non_null)

    # Si la columna tiene poca variedad, es categórica
    if unique_ratio < 0.15 and non_null.nunique() < 100:
        return "categorical"

    # Si los valores son cortos (< 30 chars promedio), texto corto / categórico
    avg_len = non_null.astype(str).str.len().mean()
    if avg_len < 30:
        return "categorical"

    return "text"


def _get_sample_values(non_null_series: pd.Series, inferred_type: str) -> list:
    """
    Extrae hasta 5 valores representativos de la columna.
    Para fechas: formateadas como string.
    Para numéricos: como float.
    Para categóricos: los más frecuentes.
    """
    from config import MAX_SAMPLE_VALUES

    if len(non_null_series) == 0:
        return []

    try:
        if inferred_type == "date":
            # Mostrar rango
            vals = non_null_series.sort_values()
            sample = list(vals.head(2)) + list(vals.tail(2))
            return [str(v)[:10] for v in sample[:MAX_SAMPLE_VALUES]]

        elif inferred_type == "numeric":
            # Mostrar min, max y algunos valores del medio
            vals = non_null_series.sort_values()
            indices = [0, len(vals) // 4, len(vals) // 2, len(vals) * 3 // 4, -1]
            sample = [vals.iloc[i] for i in indices if abs(i) < len(vals)]
            return [round(float(v), 2) for v in sample[:MAX_SAMPLE_VALUES]]

        elif inferred_type == "categorical":
            # Mostrar los más frecuentes
            return list(non_null_series.value_counts().head(MAX_SAMPLE_VALUES).index)

        else:
            # Texto: muestras aleatorias
            return list(non_null_series.sample(
                min(MAX_SAMPLE_VALUES, len(non_null_series)),
                random_state=42,
            ))

    except Exception:
        return list(non_null_series.head(MAX_SAMPLE_VALUES))


# ---------------------------------------------------------------------------
# FUNCIÓN DE UTILIDAD: reconstruir DF desde TableProfile
# ---------------------------------------------------------------------------

def get_dataframe_for_table(
    loaded_tables: list,
    table_id: str,
) -> Optional[pd.DataFrame]:
    """
    Recupera el DataFrame original para una tabla dada por su table_id.

    Args:
        loaded_tables: lista de (df, file_name, sheet_name)
        table_id: en formato "file_name::sheet_name" o solo "file_name"

    Returns:
        DataFrame o None si no se encuentra.
    """
    for df, file_name, sheet_name in loaded_tables:
        if sheet_name:
            tid = f"{file_name}::{sheet_name}"
        else:
            tid = file_name
        if tid == table_id:
            return df
    return None
