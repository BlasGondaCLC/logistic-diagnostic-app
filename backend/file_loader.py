"""
backend/file_loader.py
======================
Carga archivos Excel (.xlsx, .xls) y CSV.
Detecta automáticamente:
- Hojas en archivos Excel (cada hoja se trata como tabla separada)
- Separador en CSV (coma, punto y coma, tab)
- Encoding en CSV (chardet)
- Filas de header no estándar (headers en fila 2 o 3)

Retorna: List[Tuple[pd.DataFrame, str, Optional[str]]]
         (dataframe, nombre_archivo, nombre_hoja_o_None)
"""

import io
import logging
from pathlib import Path
from typing import List, Tuple, Optional, BinaryIO

import chardet
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TIPO DE RETORNO
# ---------------------------------------------------------------------------

LoadedTable = Tuple[pd.DataFrame, str, Optional[str]]
# (dataframe, file_name, sheet_name)


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# ---------------------------------------------------------------------------

def load_files(uploaded_files: list) -> Tuple[List[LoadedTable], List[str]]:
    """
    Carga múltiples archivos subidos desde Streamlit.

    Args:
        uploaded_files: Lista de objetos UploadedFile de Streamlit.

    Returns:
        (tables, errors)
        - tables: lista de (df, file_name, sheet_name_or_None)
        - errors: lista de mensajes de error para mostrar al usuario
    """
    tables: List[LoadedTable] = []
    errors: List[str] = []

    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name
        suffix = Path(file_name).suffix.lower()

        try:
            if suffix in (".xlsx", ".xls"):
                loaded, errs = _load_excel(uploaded_file, file_name)
            elif suffix == ".csv":
                loaded, errs = _load_csv(uploaded_file, file_name)
            else:
                errors.append(f"⚠️ Formato no soportado: {file_name}")
                continue

            tables.extend(loaded)
            errors.extend(errs)

        except Exception as e:
            logger.exception(f"Error inesperado cargando {file_name}: {e}")
            errors.append(f"🔴 Error cargando {file_name}: {str(e)}")

    return tables, errors


# ---------------------------------------------------------------------------
# CARGA DE EXCEL
# ---------------------------------------------------------------------------

def _load_excel(
    file_obj: BinaryIO,
    file_name: str,
) -> Tuple[List[LoadedTable], List[str]]:
    """
    Carga todas las hojas de un archivo Excel.
    Cada hoja se convierte en una tabla independiente.
    Descarta hojas totalmente vacías o con menos de 2 filas.
    """
    tables: List[LoadedTable] = []
    errors: List[str] = []

    try:
        # Leer todas las hojas como dict
        excel_data = pd.read_excel(
            file_obj,
            sheet_name=None,    # Todas las hojas
            dtype=str,          # Leer todo como texto para preservar formato
            na_values=["", "N/A", "NA", "null", "NULL", "None", "NONE", "#N/A"],
            keep_default_na=True,
        )
    except Exception as e:
        errors.append(f"🔴 No se pudo abrir {file_name}: {str(e)}")
        return tables, errors

    for sheet_name, df in excel_data.items():
        # Descartar hojas vacías
        if df is None or df.empty or len(df) < 1:
            logger.debug(f"Hoja vacía ignorada: {file_name}::{sheet_name}")
            continue

        # Intentar detectar si el header real no está en la fila 0
        df = _fix_header_row(df)

        # Limpiar nombres de columnas
        df = _clean_column_names(df)

        # Eliminar filas completamente vacías
        df = df.dropna(how="all")

        if len(df) < 1:
            continue

        # Convertir tipos de datos apropiados
        df = _coerce_types(df)

        tables.append((df, file_name, str(sheet_name)))
        logger.info(f"Cargada hoja '{sheet_name}' de '{file_name}': {df.shape}")

    if not tables:
        errors.append(f"⚠️ No se encontraron hojas con datos en {file_name}")

    return tables, errors


# ---------------------------------------------------------------------------
# CARGA DE CSV
# ---------------------------------------------------------------------------

def _load_csv(
    file_obj: BinaryIO,
    file_name: str,
) -> Tuple[List[LoadedTable], List[str]]:
    """
    Carga un archivo CSV con detección automática de:
    - Encoding (via chardet)
    - Separador (coma, punto y coma, tab, pipe)
    """
    errors: List[str] = []

    # Leer bytes para detectar encoding
    raw_bytes = file_obj.read()

    # Detectar encoding
    encoding = _detect_encoding(raw_bytes)
    logger.info(f"Encoding detectado para {file_name}: {encoding}")

    # Detectar separador
    separator = _detect_separator(raw_bytes, encoding)
    logger.info(f"Separador detectado para {file_name}: repr={repr(separator)}")

    try:
        df = pd.read_csv(
            io.BytesIO(raw_bytes),
            sep=separator,
            encoding=encoding,
            dtype=str,
            na_values=["", "N/A", "NA", "null", "NULL", "None", "NONE", "#N/A"],
            keep_default_na=True,
            on_bad_lines="warn",
            engine="python",    # Más tolerante a errores de formato
        )
    except Exception as e:
        # Intentar con fallback
        try:
            df = pd.read_csv(
                io.BytesIO(raw_bytes),
                sep=None,       # Autodetección de pandas
                encoding="latin-1",
                dtype=str,
                on_bad_lines="skip",
                engine="python",
            )
            errors.append(
                f"⚠️ {file_name}: cargado con modo de recuperación. "
                f"Verificar que las columnas sean correctas."
            )
        except Exception as e2:
            errors.append(f"🔴 No se pudo cargar {file_name}: {str(e2)}")
            return [], errors

    # Limpiar
    df = _fix_header_row(df)
    df = _clean_column_names(df)
    df = df.dropna(how="all")
    df = _coerce_types(df)

    if df.empty:
        errors.append(f"⚠️ {file_name} quedó vacío después de limpieza.")
        return [], errors

    logger.info(f"CSV cargado: {file_name} → {df.shape}")
    return [(df, file_name, None)], errors


# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------------------------

def _detect_encoding(raw_bytes: bytes) -> str:
    """Detecta el encoding de un archivo via chardet."""
    result = chardet.detect(raw_bytes[:50_000])  # sample de 50KB
    encoding = result.get("encoding", "utf-8") or "utf-8"

    # Normalizar encodings comunes
    encoding_map = {
        "ascii": "utf-8",
        "windows-1252": "latin-1",
        "iso-8859-1": "latin-1",
    }
    return encoding_map.get(encoding.lower(), encoding)


def _detect_separator(raw_bytes: bytes, encoding: str) -> str:
    """
    Detecta el separador más probable en un CSV.
    Prueba: punto y coma, coma, tab, pipe.
    El separador con más columnas consistentes gana.
    """
    try:
        sample = raw_bytes[:5000].decode(encoding, errors="replace")
    except Exception:
        sample = raw_bytes[:5000].decode("latin-1", errors="replace")

    # Tomar las primeras 5 líneas no vacías
    lines = [l for l in sample.splitlines() if l.strip()][:5]
    if not lines:
        return ","

    candidates = [";", ",", "\t", "|"]
    scores = {}

    for sep in candidates:
        counts = [line.count(sep) for line in lines]
        if max(counts, default=0) == 0:
            scores[sep] = 0
            continue
        # Score: promedio de columnas * consistencia (std baja = más consistente)
        import statistics
        avg = statistics.mean(counts)
        try:
            std = statistics.stdev(counts)
        except Exception:
            std = 0
        # Penalizar inconsistencia
        scores[sep] = avg * (1 / (1 + std))

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else ","


def _fix_header_row(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detecta si el header real no está en la fila 0.
    Esto ocurre cuando los primeros exportados de SAP/ERP incluyen
    filas de título antes del header.
    Heurística: si la fila 0 tiene más de la mitad de las columnas vacías/NaN,
    intenta usar la primera fila con valores como header.
    """
    if df.empty or len(df) < 2:
        return df

    # Verificar si el header actual parece ser datos (columnas como Unnamed:X)
    unnamed_count = sum(1 for c in df.columns if str(c).startswith("Unnamed:"))
    if unnamed_count > len(df.columns) * 0.5:
        # Buscar la fila que parece ser el header real (densidad alta de valores no nulos)
        for i in range(min(5, len(df))):
            row = df.iloc[i]
            non_null = row.notna().sum()
            if non_null >= len(df.columns) * 0.6:
                # Usar esta fila como header
                new_df = df.iloc[i + 1:].copy()
                new_df.columns = [str(v) if pd.notna(v) else f"Col_{j}"
                                   for j, v in enumerate(df.iloc[i])]
                new_df = new_df.reset_index(drop=True)
                return new_df

    return df


def _clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia nombres de columnas:
    - Elimina espacios extremos
    - Reemplaza saltos de línea
    - Elimina caracteres especiales problemáticos
    - Asegura unicidad
    """
    new_cols = []
    seen = {}

    for col in df.columns:
        # Convertir a string y limpiar
        clean = str(col).strip()
        clean = clean.replace("\n", " ").replace("\r", " ")
        clean = clean.replace("\t", " ")

        # Quitar espacios múltiples
        while "  " in clean:
            clean = clean.replace("  ", " ")

        # Si queda vacío, asignar nombre genérico
        if not clean or clean.lower() in ("nan", "none", "null"):
            clean = f"Columna_{len(new_cols)}"

        # Asegurar unicidad
        if clean in seen:
            seen[clean] += 1
            clean = f"{clean}_{seen[clean]}"
        else:
            seen[clean] = 0

        new_cols.append(clean)

    df.columns = new_cols
    return df


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Intenta convertir columnas a tipos apropiados.
    - Columnas numéricas: float64
    - Columnas de fecha: datetime
    - Resto: object (string)

    Usa conversión tolerante: si falla para una celda, la deja como NaN.
    """
    for col in df.columns:
        series = df[col]

        # Intentar fecha primero (antes que numérico)
        if _looks_like_date_column(series):
            df[col] = _parse_dates_flexible(series)
            continue

        # Intentar numérico
        if _looks_like_numeric_column(series):
            df[col] = _parse_numeric_flexible(series)
            continue

    return df


def _looks_like_date_column(series: pd.Series) -> bool:
    """
    Heurística: ¿parece una columna de fechas?
    Verifica que >60% de los valores no-nulos matcheen patrones de fecha.
    """
    import re
    non_null = series.dropna().astype(str)
    if len(non_null) < 3:
        return False

    date_patterns = [
        r"\d{1,2}/\d{1,2}/\d{4}",      # DD/MM/YYYY o MM/DD/YYYY
        r"\d{4}-\d{2}-\d{2}",           # YYYY-MM-DD
        r"\d{1,2}-\d{1,2}-\d{4}",       # DD-MM-YYYY
        r"\d{4}/\d{2}/\d{2}",           # YYYY/MM/DD
        r"\d{8}",                        # YYYYMMDD
    ]

    sample = non_null.head(20)
    matches = 0
    for val in sample:
        for pattern in date_patterns:
            if re.match(pattern, val.strip()):
                matches += 1
                break

    return (matches / len(sample)) > 0.6


def _looks_like_numeric_column(series: pd.Series) -> bool:
    """
    Heurística: ¿parece una columna numérica?
    Limpia separadores de miles y decimales antes de probar.
    """
    non_null = series.dropna().astype(str)
    if len(non_null) < 3:
        return False

    sample = non_null.head(20)
    numeric_count = 0
    for val in sample:
        cleaned = _normalize_number_str(val)
        try:
            float(cleaned)
            numeric_count += 1
        except ValueError:
            pass

    return (numeric_count / len(sample)) > 0.7


def _parse_dates_flexible(series: pd.Series) -> pd.Series:
    """
    Parsea fechas con tolerancia a múltiples formatos locales.
    Maneja DD/MM/YYYY (formato local) correctamente.
    """
    formats_to_try = [
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d%m%Y",
    ]

    def parse_one(val):
        if pd.isna(val):
            return pd.NaT
        val_str = str(val).strip()
        for fmt in formats_to_try:
            try:
                return pd.to_datetime(val_str, format=fmt)
            except (ValueError, TypeError):
                continue
        # Fallback: dejar que pandas intente
        try:
            return pd.to_datetime(val_str, dayfirst=True)
        except Exception:
            return pd.NaT

    return series.apply(parse_one)


def _parse_numeric_flexible(series: pd.Series) -> pd.Series:
    """
    Parsea números con tolerancia a formatos locales:
    - Decimales con coma: 1.234,56 → 1234.56
    - Decimales con punto: 1,234.56 → 1234.56
    """
    def parse_one(val):
        if pd.isna(val):
            return pd.NA
        cleaned = _normalize_number_str(str(val))
        try:
            return float(cleaned)
        except ValueError:
            return pd.NA

    return series.apply(parse_one).astype("Float64")


def _normalize_number_str(val: str) -> str:
    """
    Normaliza un string numérico a formato float estándar.
    Maneja: 1.234,56 → 1234.56 y 1,234.56 → 1234.56
    """
    val = val.strip().replace(" ", "").replace(" ", "")  # non-breaking space

    # Detectar formato: si tiene coma Y punto, el último es el decimal
    if "," in val and "." in val:
        # Ejemplo: 1.234,56 → decimal es la coma
        if val.rfind(",") > val.rfind("."):
            val = val.replace(".", "").replace(",", ".")
        else:
            # Ejemplo: 1,234.56 → decimal es el punto
            val = val.replace(",", "")
    elif "," in val:
        # Solo coma: puede ser decimal (1,5) o miles (1,000)
        parts = val.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Probablemente decimal: 1,5 o 1,50
            val = val.replace(",", ".")
        else:
            # Probablemente miles: 1,000 → 1000
            val = val.replace(",", "")

    return val
