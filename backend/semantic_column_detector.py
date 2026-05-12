"""
backend/semantic_column_detector.py
====================================
Detecta el tipo semántico de cada columna.

Estrategia en dos capas:
1. HEURÍSTICAS: matching por nombre de columna (normalizado) contra diccionario de patrones.
   Rápido, determinista, sin costo de API.
2. LLM (Claude API): para columnas con baja confianza heurística.
   Envía batch de columnas con nombre + muestra de valores → Claude devuelve clasificación JSON.

El resultado enriquece el TableProfile con detected_semantic y detection_confidence.
"""

import json
import logging
import re
from typing import List, Dict, Optional

import anthropic

from config import (
    COLUMN_SEMANTIC_PATTERNS,
    HEURISTIC_CONFIDENCE_THRESHOLD,
    LLM_ENRICHMENT_THRESHOLD,
    LLM_MODEL_FAST,
    MAX_SAMPLE_VALUES,
    ALL_SEMANTIC_TYPES,
)
from models.table_profile import ColumnProfile, TableProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# ---------------------------------------------------------------------------

def detect_column_semantics(
    profiles: List[TableProfile],
    api_key: Optional[str] = None,
    use_llm: bool = True,
) -> List[TableProfile]:
    """
    Detecta semántica de columnas para todos los TableProfile.
    Primero aplica heurísticas, luego LLM para las de baja confianza.

    Args:
        profiles: Lista de TableProfile con columnas ya perfiladas.
        api_key: Anthropic API key. Si es None, solo usa heurísticas.
        use_llm: Si False, fuerza solo heurísticas (útil para tests).

    Returns:
        Lista de TableProfile con detected_semantic y detection_confidence actualizados.
    """
    for profile in profiles:
        # Paso 1: Heurísticas para todas las columnas
        for col in profile.columns:
            semantic, confidence = _heuristic_detect(col.original_name, col.sample_values)
            col.detected_semantic = semantic
            col.detection_confidence = confidence
            col.detection_method = "heuristic"

        # Paso 2: LLM para columnas con baja confianza
        if use_llm and api_key:
            low_conf_cols = [
                col for col in profile.columns
                if col.detection_confidence < LLM_ENRICHMENT_THRESHOLD
            ]
            if low_conf_cols:
                _llm_enrich_columns(low_conf_cols, profile, api_key)

    return profiles


# ---------------------------------------------------------------------------
# CAPA 1: HEURÍSTICAS
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    """
    Normaliza un nombre de columna para comparación:
    - lowercase
    - sin espacios, guiones, underscores
    - sin acentos
    """
    import unicodedata
    name = name.lower().strip()
    # Quitar acentos
    name = "".join(
        c for c in unicodedata.normalize("NFD", name)
        if unicodedata.category(c) != "Mn"
    )
    # Quitar caracteres no alfanuméricos
    name = re.sub(r"[^a-z0-9]", "", name)
    return name


def _heuristic_detect(
    col_name: str,
    sample_values: list,
) -> tuple[str, float]:
    """
    Detecta el tipo semántico de una columna por su nombre.
    Retorna (semantic_type, confidence).
    """
    normalized = _normalize_name(col_name)

    best_semantic = "Desconocido"
    best_score = 0.0

    for semantic, patterns in COLUMN_SEMANTIC_PATTERNS.items():
        score = _score_column_against_patterns(normalized, col_name, patterns)
        if score > best_score:
            best_score = score
            best_semantic = semantic

    # Boost adicional por tipo de dato / valores de muestra
    if best_semantic != "Desconocido":
        boost = _sample_value_boost(best_semantic, sample_values)
        best_score = min(1.0, best_score + boost)

    return best_semantic, best_score


def _score_column_against_patterns(
    normalized_name: str,
    original_name: str,
    patterns: List[str],
) -> float:
    """
    Calcula un score de 0 a 1 para el match de un nombre contra una lista de patrones.
    - Match exacto: 1.0
    - Contiene el patrón: 0.8
    - Patrón contiene el nombre: 0.6
    - Distancia de edición baja: 0.4
    """
    best_score = 0.0

    for pattern in patterns:
        norm_pattern = _normalize_name(pattern)
        if not norm_pattern:
            continue

        # Match exacto
        if normalized_name == norm_pattern:
            return 1.0

        # El nombre contiene el patrón (o viceversa)
        if norm_pattern in normalized_name:
            score = len(norm_pattern) / len(normalized_name)
            score = max(0.6, score)  # al menos 0.6
            best_score = max(best_score, score)

        elif normalized_name in norm_pattern:
            score = len(normalized_name) / len(norm_pattern)
            score = max(0.5, score * 0.8)
            best_score = max(best_score, score)

        # Empieza con el patrón
        elif normalized_name.startswith(norm_pattern[:4]) and len(norm_pattern) >= 4:
            best_score = max(best_score, 0.55)

    return best_score


def _sample_value_boost(semantic: str, sample_values: list) -> float:
    """
    Boost de confianza basado en los valores de muestra.
    Por ejemplo, si el semantic es "Fecha" y los valores parecen fechas → +0.15
    """
    if not sample_values:
        return 0.0

    import re as _re

    boost = 0.0
    sample_strs = [str(v) for v in sample_values]

    if semantic == "Fecha":
        date_patterns = [
            r"\d{1,2}/\d{1,2}/\d{4}",
            r"\d{4}-\d{2}-\d{2}",
            r"\d{1,2}-\d{1,2}-\d{4}",
        ]
        matches = sum(
            1 for v in sample_strs
            if any(_re.match(p, v.strip()) for p in date_patterns)
        )
        boost = 0.15 * (matches / len(sample_strs))

    elif semantic in ("Cantidad", "Stock", "Costo", "Valor"):
        try:
            numeric_count = sum(
                1 for v in sample_strs
                if v.replace(".", "").replace(",", "").replace("-", "").strip().isnumeric()
            )
            boost = 0.10 * (numeric_count / len(sample_strs))
        except Exception:
            pass

    elif semantic == "SKU":
        # SKUs suelen ser códigos cortos (< 20 chars) con mezcla alfanumérica
        short_count = sum(1 for v in sample_strs if 1 <= len(v) <= 30)
        boost = 0.08 * (short_count / len(sample_strs))

    return boost


# ---------------------------------------------------------------------------
# CAPA 2: LLM (Claude API)
# ---------------------------------------------------------------------------

def _llm_enrich_columns(
    low_conf_cols: List[ColumnProfile],
    table_profile: TableProfile,
    api_key: str,
) -> None:
    """
    Llama a Claude para clasificar las columnas de baja confianza.
    Modifica los ColumnProfile in-place.
    """
    # Construir contexto de la tabla para que Claude entienda el dominio
    table_context = f"Tabla: {table_profile.display_name} ({table_profile.row_count} filas)"
    if table_profile.date_min:
        table_context += f"\nRango de fechas: {table_profile.date_range_str}"

    # Construir descripción de columnas
    columns_info = []
    for col in low_conf_cols:
        info = {
            "nombre_columna": col.original_name,
            "tipo_dato": col.inferred_type,
            "porcentaje_nulos": round(col.null_percentage * 100, 1),
            "valores_unicos": col.unique_count,
            "muestras": col.sample_values[:5],
        }
        columns_info.append(info)

    prompt = _build_llm_prompt(table_context, columns_info)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=LLM_MODEL_FAST,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text

        # Parsear respuesta JSON
        results = _parse_llm_response(response_text)

        # Actualizar columnas con resultados del LLM
        for col in low_conf_cols:
            if col.original_name in results:
                llm_result = results[col.original_name]
                semantic = llm_result.get("tipo_semantico", "Desconocido")
                confidence = float(llm_result.get("confianza", 0.5))

                # Solo actualizar si el LLM es más confiante que la heurística
                if confidence > col.detection_confidence:
                    col.detected_semantic = semantic if semantic in ALL_SEMANTIC_TYPES else "Desconocido"
                    col.detection_confidence = confidence
                    col.detection_method = "llm"

    except anthropic.AuthenticationError:
        logger.error("API key de Anthropic inválida o no configurada.")
    except anthropic.RateLimitError:
        logger.warning("Rate limit de Anthropic alcanzado. Usando solo heurísticas.")
    except Exception as e:
        logger.exception(f"Error llamando a Claude API: {e}")


def _build_llm_prompt(table_context: str, columns_info: list) -> str:
    """
    Construye el prompt para Claude para clasificación de columnas.
    """
    semantic_types_str = ", ".join(ALL_SEMANTIC_TYPES)

    columns_json = json.dumps(columns_info, ensure_ascii=False, indent=2)

    return f"""Sos un experto en análisis de datos logísticos de depósitos, almacenes y cadena de suministro.

CONTEXTO:
{table_context}

TAREA:
Para cada columna de la siguiente lista, determiná su tipo semántico en el dominio logístico.

TIPOS SEMÁNTICOS POSIBLES:
{semantic_types_str}

DEFINICIONES:
- SKU: código de producto o artículo
- Descripcion: nombre o descripción del producto
- Fecha: cualquier campo de fecha o timestamp
- Cantidad: unidades, volumen, cantidad de movimiento
- Documento: número de factura, pedido, remito, orden
- Cliente: nombre o código de cliente/destinatario
- Proveedor: nombre o código de proveedor
- Deposito: nombre o código de depósito, almacén, sucursal
- Origen: depósito o ubicación de origen de una transferencia
- Destino: depósito o ubicación de destino de una transferencia
- Familia: categoría, familia, rubro, grupo de productos
- Subfamilia: subcategoría, subfamilia de productos
- TipoMovimiento: tipo o clase de movimiento logístico
- Stock: cantidad en stock, existencias actuales
- Costo: precio o costo unitario
- Valor: importe total, monto en dinero
- Desconocido: no se puede clasificar con certeza en ninguno de los anteriores

COLUMNAS A CLASIFICAR:
{columns_json}

RESPUESTA:
Devolvé ÚNICAMENTE un JSON válido con el siguiente formato (sin texto adicional antes o después):
{{
  "NOMBRE_COLUMNA_1": {{
    "tipo_semantico": "TIPO",
    "confianza": 0.85,
    "razon": "breve explicación"
  }},
  "NOMBRE_COLUMNA_2": {{
    "tipo_semantico": "TIPO",
    "confianza": 0.70,
    "razon": "breve explicación"
  }}
}}

IMPORTANTE:
- La confianza va de 0.0 a 1.0
- Si no podés clasificar una columna con más de 0.5 de confianza, usá "Desconocido"
- No inventes tipos que no estén en la lista
- El campo "tipo_semantico" debe ser EXACTAMENTE uno de los tipos de la lista"""


def _parse_llm_response(response_text: str) -> Dict[str, dict]:
    """
    Parsea la respuesta JSON de Claude.
    Con tolerancia a texto extra antes/después del JSON.
    """
    # Intentar extraer el JSON si hay texto extra
    text = response_text.strip()

    # Buscar el bloque JSON
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        json_str = text[start:end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # Intentar parsear directamente
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"No se pudo parsear respuesta del LLM: {text[:200]}")
        return {}
