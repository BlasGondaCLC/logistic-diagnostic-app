"""
backend/llm_analyzer.py
========================
Análisis enriquecido con Claude API.
Corre DESPUÉS del pipeline heurístico y mejora/complementa los resultados.

Tres funciones principales:
  1. llm_classify_tables()      → Claude clasifica el tipo de cada tabla
  2. llm_analyze_quality()      → Claude genera insights de calidad por tabla
  3. llm_generate_summary()     → Claude escribe el resumen ejecutivo del diagnóstico

Diseño:
- Usa claude-haiku para clasificación (rápido, barato)
- Usa claude-sonnet para insights y resumen ejecutivo (más profundo)
- Las heurísticas son el fallback: si la API falla, los resultados heurísticos se mantienen
- Envía solo muestras de datos (no DataFrames completos) para controlar tokens y costo
"""

import json
import logging
from typing import List, Optional, Dict, Tuple

import pandas as pd
import anthropic

from config import ALL_TABLE_TYPES, LLM_MODEL_FAST, LLM_MODEL_ANALYSIS
from models.table_profile import TableProfile, DiagnosticReport

logger = logging.getLogger(__name__)

# Cantidad de filas de muestra que se envían a Claude
SAMPLE_ROWS = 15


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE ENRIQUECIMIENTO
# ---------------------------------------------------------------------------

def llm_enrich_all(
    profiles: List[TableProfile],
    loaded_tables: list,   # List[(df, file_name, sheet_name)]
    report: DiagnosticReport,
    api_key: str,
    use_llm_classification: bool = True,
    use_llm_insights: bool = True,
    use_llm_summary: bool = True,
) -> Tuple[List[TableProfile], DiagnosticReport]:
    """
    Ejecuta todas las capas de enriquecimiento LLM sobre los resultados heurísticos.

    Args:
        profiles: TableProfiles ya procesados por el pipeline heurístico.
        loaded_tables: DataFrames originales.
        report: DiagnosticReport generado por la feasibility engine.
        api_key: Anthropic API key.

    Returns:
        (profiles enriquecidos, report con resumen ejecutivo actualizado)
    """
    if not api_key:
        logger.warning("Sin API key: saltando enriquecimiento LLM.")
        return profiles, report

    df_map = _build_df_map(loaded_tables)

    # --- Capa 1: Clasificación de tablas ---
    if use_llm_classification:
        logger.info("LLM: clasificando tipos de tabla...")
        profiles = llm_classify_tables(profiles, df_map, api_key)

    # --- Capa 2: Insights de calidad por tabla ---
    if use_llm_insights:
        logger.info("LLM: generando insights de calidad...")
        profiles = llm_analyze_quality(profiles, df_map, api_key)

    # --- Capa 3: Resumen ejecutivo ---
    if use_llm_summary:
        logger.info("LLM: generando resumen ejecutivo...")
        report = llm_generate_summary(report, api_key)

    return profiles, report


# ---------------------------------------------------------------------------
# CAPA 1: CLASIFICACIÓN DE TABLAS
# ---------------------------------------------------------------------------

def llm_classify_tables(
    profiles: List[TableProfile],
    df_map: Dict[str, pd.DataFrame],
    api_key: str,
) -> List[TableProfile]:
    """
    Claude clasifica el tipo de cada tabla activa.
    Solo reemplaza la clasificación heurística si la confianza del LLM es mayor.
    """
    client = _get_client(api_key)
    if client is None:
        return profiles

    for profile in profiles:
        if not profile.include_in_analysis:
            continue

        df = df_map.get(profile.table_id)
        if df is None:
            continue

        try:
            result = _classify_single_table_llm(client, profile, df)
            if result:
                llm_type, llm_confidence, llm_reasoning = result

                # Solo actualizar si el LLM es más confiante
                if llm_confidence > profile.type_confidence:
                    profile.table_type = llm_type
                    profile.type_confidence = llm_confidence
                    profile.type_reasoning = f"[Claude] {llm_reasoning}"
                    logger.info(f"LLM clasificó '{profile.display_name}' como '{llm_type}' ({llm_confidence:.0%})")

        except Exception as e:
            logger.warning(f"LLM clasificación falló para {profile.display_name}: {e}")
            # Mantener resultado heurístico sin cambios

    return profiles


def _classify_single_table_llm(
    client: anthropic.Anthropic,
    profile: TableProfile,
    df: pd.DataFrame,
) -> Optional[Tuple[str, float, str]]:
    """
    Llama a Claude para clasificar una tabla.
    Retorna (tipo, confianza, razonamiento) o None si falla.
    """
    # Preparar muestra de datos
    sample = _get_data_sample(df, n=SAMPLE_ROWS)
    col_info = _get_column_summary(profile)
    table_types_str = "\n".join(f"  - {t}" for t in ALL_TABLE_TYPES)

    prompt = f"""Sos un experto en logística de depósitos y análisis de datos.

Archivo: "{profile.file_name}"
{f'Hoja: "{profile.sheet_name}"' if profile.sheet_name else ''}
Filas totales: {profile.row_count:,}
Columnas: {profile.col_count}

RESUMEN DE COLUMNAS:
{col_info}

MUESTRA DE DATOS ({len(sample)} filas):
{sample}

TIPOS DE TABLA POSIBLES:
{table_types_str}

DEFINICIONES:
- Maestro de Productos: catálogo con SKU, descripción y atributos (sin movimientos).
- Stock: cantidades de inventario actuales o históricos por SKU.
- Recepciones: ingresos de mercadería (compras, entradas de proveedor).
- Pedidos: solicitudes de clientes o ventas (salidas hacia clientes).
- Preparaciones: proceso interno de picking/preparación de pedidos.
- Transferencias: movimientos entre depósitos o sucursales.
- Devoluciones Cliente: mercadería devuelta por clientes.
- Devoluciones Proveedor: mercadería devuelta a proveedores.
- Ajustes: correcciones manuales de inventario.
- Clientes: tabla maestra de clientes (sin movimientos).
- Proveedores: tabla maestra de proveedores (sin movimientos).
- Depósitos: tabla maestra de depósitos/ubicaciones.
- Otro: no encaja en ninguna categoría logística.

Respondé ÚNICAMENTE con este JSON (sin texto adicional):
{{
  "tipo": "nombre exacto del tipo",
  "confianza": 0.85,
  "razonamiento": "explicación concisa de 1-2 oraciones de por qué es ese tipo"
}}"""

    response = client.messages.create(
        model=LLM_MODEL_FAST,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    parsed = _parse_json_response(text)

    if not parsed:
        return None

    tipo = parsed.get("tipo", "Otro")
    confianza = float(parsed.get("confianza", 0.5))
    razon = parsed.get("razonamiento", "")

    # Validar que el tipo sea uno de los permitidos
    if tipo not in ALL_TABLE_TYPES:
        tipo = "Otro"
        confianza = 0.3

    return tipo, confianza, razon


# ---------------------------------------------------------------------------
# CAPA 2: INSIGHTS DE CALIDAD POR TABLA
# ---------------------------------------------------------------------------

def llm_analyze_quality(
    profiles: List[TableProfile],
    df_map: Dict[str, pd.DataFrame],
    api_key: str,
) -> List[TableProfile]:
    """
    Claude genera un párrafo de insights de calidad y contenido para cada tabla.
    El resultado se guarda en profile.llm_insights (atributo dinámico).
    """
    client = _get_client(api_key)
    if client is None:
        return profiles

    for profile in profiles:
        if not profile.include_in_analysis:
            continue

        df = df_map.get(profile.table_id)
        if df is None:
            continue

        try:
            insights = _analyze_table_quality_llm(client, profile, df)
            # Guardamos los insights como atributo dinámico del profile
            # (no modifica el dataclass, solo agrega metadata extra para la UI)
            profile.__dict__["llm_insights"] = insights
            logger.info(f"LLM insights generados para {profile.display_name}")

        except Exception as e:
            logger.warning(f"LLM insights fallaron para {profile.display_name}: {e}")
            profile.__dict__["llm_insights"] = ""

    return profiles


def _analyze_table_quality_llm(
    client: anthropic.Anthropic,
    profile: TableProfile,
    df: pd.DataFrame,
) -> str:
    """
    Genera un análisis de calidad e insights para una tabla.
    Retorna un string en markdown con observaciones.
    """
    sample = _get_data_sample(df, n=SAMPLE_ROWS)
    col_info = _get_column_summary(profile)

    # Estadísticas de calidad
    null_issues = [
        f"  - '{i.column}': {i.affected_percentage*100:.1f}% nulos"
        for i in profile.quality_issues
        if i.issue_type == "nulls" and i.column
    ]
    other_issues = [
        f"  - {i.description[:100]}"
        for i in profile.quality_issues
        if i.issue_type != "nulls"
    ]

    issues_str = "\n".join(null_issues + other_issues) if (null_issues or other_issues) else "  Sin problemas detectados por reglas."

    prompt = f"""Sos un analista de datos logísticos senior. Analizá esta tabla y generá observaciones útiles.

TABLA: "{profile.display_name}"
TIPO: {profile.table_type}
FILAS: {profile.row_count:,}
PERÍODO: {profile.date_range_str}

COLUMNAS DETECTADAS:
{col_info}

PROBLEMAS DETECTADOS POR REGLAS:
{issues_str}

MUESTRA DE DATOS:
{sample}

TU TAREA:
Escribí un análisis breve (3-5 oraciones) que responda:
1. ¿La tabla tiene sentido para su tipo clasificado?
2. ¿Hay algo llamativo en los datos (concentración, valores raros, inconsistencias)?
3. ¿La calidad es suficiente para el análisis logístico?
4. ¿Algún supuesto o advertencia importante que debería documentarse?

Escribí en español, en prosa directa. Sin bullets. Sin repetir el nombre de la tabla al inicio.
Sé concreto y útil para un consultor logístico."""

    response = client.messages.create(
        model=LLM_MODEL_ANALYSIS,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# CAPA 3: RESUMEN EJECUTIVO
# ---------------------------------------------------------------------------

def llm_generate_summary(
    report: DiagnosticReport,
    api_key: str,
) -> DiagnosticReport:
    """
    Claude genera el resumen ejecutivo del diagnóstico completo.
    Reemplaza el resumen generado por templates con uno más contextual y natural.
    """
    client = _get_client(api_key)
    if client is None:
        return report

    try:
        summary = _generate_summary_llm(client, report)
        report.general_summary = summary
        logger.info("LLM resumen ejecutivo generado correctamente.")
    except Exception as e:
        logger.warning(f"LLM resumen ejecutivo falló: {e}")
        # Mantener el resumen heurístico sin cambios

    return report


def _generate_summary_llm(
    client: anthropic.Anthropic,
    report: DiagnosticReport,
) -> str:
    """
    Genera el resumen ejecutivo del diagnóstico completo.
    """
    # Construir descripción de tablas
    tables_desc = []
    for t in report.active_tables:
        desc = f"  - {t.display_name}: {t.table_type}, {t.row_count:,} filas"
        if t.date_min and t.date_max:
            desc += f", período {t.date_range_str}"
        mapping = t.build_effective_mapping()
        if mapping:
            desc += f", campos: {', '.join(mapping.keys())}"
        tables_desc.append(desc)

    # Análisis posibles/parciales/imposibles
    possible_str = ", ".join(report.possible_analyses) if report.possible_analyses else "ninguno"
    partial_str = ", ".join(report.partial_analyses) if report.partial_analyses else "ninguno"
    impossible_str = ", ".join(report.impossible_analyses) if report.impossible_analyses else "ninguno"

    # Advertencias y supuestos
    warnings_str = "\n".join(f"  - {w}" for w in report.warnings) or "  Ninguna."
    assumptions_str = "\n".join(f"  - {s}" for s in report.suggested_assumptions) or "  Ninguno."

    # Cross-table issues
    cross_str = "\n".join(f"  - {i}" for i in report.cross_table_issues) or "  Ninguno."

    prompt = f"""Sos un consultor senior de logística y análisis de datos.
Se realizó un diagnóstico automático de los archivos de un cliente. Necesito que escribas el resumen ejecutivo.

ARCHIVOS ANALIZADOS:
{chr(10).join(tables_desc)}

ANÁLISIS POSIBLES: {possible_str}

ANÁLISIS PARCIALES: {partial_str}

ANÁLISIS NO POSIBLES: {impossible_str}

ADVERTENCIAS DETECTADAS:
{warnings_str}

INCONSISTENCIAS ENTRE TABLAS:
{cross_str}

SUPUESTOS SUGERIDOS:
{assumptions_str}

INSTRUCCIÓN:
Escribí un resumen ejecutivo en español de 4-6 oraciones que:
1. Describa qué datos se tienen disponibles (tipos de tabla, período, volumen).
2. Evalúe la viabilidad general del análisis (qué se puede hacer y qué no).
3. Mencione los puntos críticos de calidad o limitaciones más importantes.
4. Sea directo, profesional y útil para un consultor que va a presentar esto a un cliente.

Escribí en prosa continua, sin bullets, sin secciones. Máximo 6 oraciones."""

    response = client.messages.create(
        model=LLM_MODEL_ANALYSIS,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# FUNCIÓN DE CONTEXTO ADICIONAL PARA EL PROMPT MCP
# ---------------------------------------------------------------------------

def llm_generate_prompt_context(
    report: DiagnosticReport,
    api_key: str,
) -> str:
    """
    Genera un bloque de contexto adicional basado en el análisis real de los datos.
    Se inserta en el prompt MCP en la sección de observaciones.
    Útil para darle a Claude más contexto sobre patrones reales detectados.
    """
    client = _get_client(api_key)
    if client is None:
        return ""

    try:
        # Recopilar insights de todas las tablas
        all_insights = []
        for t in report.active_tables:
            insight = t.__dict__.get("llm_insights", "")
            if insight:
                all_insights.append(f"**{t.display_name} ({t.table_type}):**\n{insight}")

        if not all_insights:
            return ""

        return "\n\n".join(all_insights)

    except Exception as e:
        logger.warning(f"Error generando contexto adicional: {e}")
        return ""


# ---------------------------------------------------------------------------
# UTILIDADES INTERNAS
# ---------------------------------------------------------------------------

def _get_client(api_key: str) -> Optional[anthropic.Anthropic]:
    """Crea el cliente de Anthropic con manejo de errores."""
    if not api_key:
        return None
    try:
        return anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        logger.error(f"No se pudo crear cliente Anthropic: {e}")
        return None


def _get_data_sample(df: pd.DataFrame, n: int = SAMPLE_ROWS) -> str:
    """
    Genera una representación legible de una muestra del DataFrame.
    Toma filas del inicio, medio y final para mayor representatividad.
    Limita a columnas no completamente vacías.
    """
    if df.empty:
        return "(tabla vacía)"

    # Filtrar columnas con demasiados nulos
    useful_cols = [c for c in df.columns if df[c].notna().sum() > 0][:15]
    df_sample = df[useful_cols]

    # Tomar muestra representativa
    total = len(df_sample)
    if total <= n:
        sample = df_sample
    else:
        # Inicio, medio y final
        n3 = n // 3
        idx = (
            list(range(n3)) +
            list(range(total // 2 - n3 // 2, total // 2 + n3 // 2)) +
            list(range(total - n3, total))
        )
        idx = sorted(set(i for i in idx if 0 <= i < total))[:n]
        sample = df_sample.iloc[idx]

    # Convertir a string tabular compacto
    try:
        return sample.to_string(index=False, max_colwidth=30, na_rep="(vacío)")
    except Exception:
        return "(no se pudo representar la muestra)"


def _get_column_summary(profile: TableProfile) -> str:
    """Genera un resumen compacto de columnas para incluir en prompts."""
    lines = []
    for col in profile.columns:
        semantic = col.detected_semantic if col.detected_semantic != "Desconocido" else "?"
        null_str = f"{col.null_percentage*100:.0f}% nulos" if col.null_percentage > 0 else "sin nulos"
        lines.append(
            f"  - '{col.original_name}' [{col.inferred_type}] → {semantic} | {null_str} | {col.unique_count} únicos"
        )
    return "\n".join(lines)


def _build_df_map(loaded_tables: list) -> Dict[str, pd.DataFrame]:
    """Construye mapa table_id → DataFrame."""
    df_map = {}
    for df, file_name, sheet_name in loaded_tables:
        tid = f"{file_name}::{sheet_name}" if sheet_name else file_name
        df_map[tid] = df
    return df_map


def _parse_json_response(text: str) -> Optional[dict]:
    """Parsea respuesta JSON de Claude con tolerancia a texto extra."""
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
