"""
backend/feasibility_engine.py
===============================
Motor de factibilidad.
Evalúa qué análisis son posibles, parciales o no posibles,
basándose en las tablas cargadas, sus tipos y los campos semánticos detectados.

Este módulo es el más fácil de extender:
- Para agregar un nuevo análisis, agregar una entrada en config.FEASIBILITY_RULES.
- Para cambiar las reglas, modificar los campos required/partial_if/impossible_if.
"""

import logging
from typing import List, Dict, Set

from config import FEASIBILITY_RULES
from models.table_profile import (
    TableProfile,
    FeasibilityResult,
    DiagnosticReport,
)

logger = logging.getLogger(__name__)

# Status labels
STATUS_POSSIBLE = "✅ Posible"
STATUS_PARTIAL = "⚠️ Parcial"
STATUS_IMPOSSIBLE = "❌ No posible"


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# ---------------------------------------------------------------------------

def run_feasibility_analysis(profiles: List[TableProfile]) -> DiagnosticReport:
    """
    Ejecuta el análisis de factibilidad para todos los análisis posibles.

    Args:
        profiles: Lista de TableProfile ya procesados (con tipo, semánticas y calidad).

    Returns:
        DiagnosticReport con la matriz de factibilidad y resumen ejecutivo.
    """
    active_tables = [p for p in profiles if p.include_in_analysis]

    # Construir mapa de tipos de tabla disponibles
    available_types = _get_available_types(active_tables)

    # Construir mapa de campos semánticos disponibles (global, de todas las tablas)
    available_semantics = _get_available_semantics(active_tables)

    # Evaluar cada análisis
    feasibility_matrix: List[FeasibilityResult] = []

    for analysis_name, rules in FEASIBILITY_RULES.items():
        result = _evaluate_analysis(
            analysis_name=analysis_name,
            rules=rules,
            active_tables=active_tables,
            available_types=available_types,
            available_semantics=available_semantics,
        )
        feasibility_matrix.append(result)

    # Construir resumen ejecutivo
    report = _build_diagnostic_report(profiles, feasibility_matrix)

    return report


# ---------------------------------------------------------------------------
# EVALUADOR POR ANÁLISIS
# ---------------------------------------------------------------------------

def _evaluate_analysis(
    analysis_name: str,
    rules: dict,
    active_tables: List[TableProfile],
    available_types: Set[str],
    available_semantics: Dict[str, List[str]],  # semantic → [table_ids que lo tienen]
) -> FeasibilityResult:
    """
    Evalúa la factibilidad de un análisis específico.
    Retorna un FeasibilityResult con el status y razonamiento.
    """
    required_tables = rules.get("required_tables", [])
    required_fields = rules.get("required_fields", [])
    partial_if = rules.get("partial_if", [])
    impossible_if = rules.get("impossible_if", [])
    notes = rules.get("notes", "")
    requires_stock = rules.get("requires_stock", False)
    requires_stock_and_movement = rules.get("requires_stock_and_movement", False)

    # --------------- Verificar condiciones de IMPOSIBILIDAD ------------------

    # Caso especial: información recibida → siempre posible
    if analysis_name == "Información Recibida":
        return FeasibilityResult(
            analysis_name=analysis_name,
            status=STATUS_POSSIBLE,
            required_fields=required_fields,
            found_fields=list(available_semantics.keys()),
            missing_fields=[],
            source_tables=[t.display_name for t in active_tables],
            reasoning="Siempre posible con al menos un archivo cargado.",
            suggestions=[],
        )

    # Verificar si hay al menos una tabla del tipo requerido
    found_tables = []
    for req_type in required_tables:
        matching = [t for t in active_tables if t.table_type == req_type]
        found_tables.extend(matching)

    has_required_table = len(found_tables) > 0 or not required_tables

    # Balance de masa: necesita stock
    if requires_stock:
        stock_tables = [t for t in active_tables if t.table_type == "Stock"]
        if not stock_tables:
            return FeasibilityResult(
                analysis_name=analysis_name,
                status=STATUS_IMPOSSIBLE,
                required_fields=required_fields,
                found_fields=[],
                missing_fields=["Stock inicial/final"],
                source_tables=[],
                reasoning="No existe tabla de Stock. El balance de masa requiere stock inicial y/o final.",
                suggestions=["Cargar una tabla de stock con fecha y cantidad por SKU."],
            )

    # Edad de stock: necesita stock + movimientos
    if requires_stock_and_movement:
        stock_tables = [t for t in active_tables if t.table_type == "Stock"]
        movement_tables = [
            t for t in active_tables
            if t.table_type in ("Pedidos", "Preparaciones", "Recepciones")
        ]
        if not stock_tables:
            return FeasibilityResult(
                analysis_name=analysis_name,
                status=STATUS_IMPOSSIBLE,
                required_fields=required_fields,
                found_fields=[],
                missing_fields=["Stock actual/final"],
                source_tables=[],
                reasoning="No existe tabla de Stock. La edad de stock requiere stock actual.",
                suggestions=["Cargar una tabla de stock actual por SKU."],
            )
        if not movement_tables:
            return FeasibilityResult(
                analysis_name=analysis_name,
                status=STATUS_IMPOSSIBLE,
                required_fields=required_fields,
                found_fields=[],
                missing_fields=["Historial de consumo (pedidos/preparaciones)"],
                source_tables=[t.display_name for t in stock_tables],
                reasoning="No hay historial de consumo. La edad de stock requiere pedidos o preparaciones para calcular consumo promedio.",
                suggestions=["Cargar tabla de pedidos o preparaciones con fecha y cantidad."],
            )

    # Si no hay tablas requeridas → imposible
    if not has_required_table and required_tables:
        missing_type_str = " o ".join(required_tables)
        return FeasibilityResult(
            analysis_name=analysis_name,
            status=STATUS_IMPOSSIBLE,
            required_fields=required_fields,
            found_fields=[],
            missing_fields=required_fields,
            source_tables=[],
            reasoning=f"No existe tabla de tipo: {missing_type_str}.",
            suggestions=_build_suggestions(required_tables, required_fields),
        )

    # --------------- Verificar campos requeridos ---------------------------

    found_fields = []
    missing_fields = []

    # Buscar campos requeridos en las tablas del análisis
    search_tables = found_tables if found_tables else active_tables

    for field in required_fields:
        field_found = any(t.has_semantic(field) for t in search_tables)
        if field_found:
            found_fields.append(field)
        else:
            missing_fields.append(field)

    # Si hay campos requeridos faltantes → imposible o parcial
    if missing_fields:
        # Si falta más de la mitad de los campos críticos → imposible
        if len(missing_fields) > len(required_fields) / 2:
            return FeasibilityResult(
                analysis_name=analysis_name,
                status=STATUS_IMPOSSIBLE,
                required_fields=required_fields,
                found_fields=found_fields,
                missing_fields=missing_fields,
                source_tables=[t.display_name for t in found_tables],
                reasoning=f"Faltan campos críticos: {', '.join(missing_fields)}.",
                suggestions=_build_suggestions(required_tables, missing_fields),
            )
        else:
            # Parcial: tiene algunos campos críticos pero no todos
            return FeasibilityResult(
                analysis_name=analysis_name,
                status=STATUS_PARTIAL,
                required_fields=required_fields,
                found_fields=found_fields,
                missing_fields=missing_fields,
                source_tables=[t.display_name for t in found_tables],
                reasoning=f"Análisis parcial. Campos encontrados: {', '.join(found_fields)}. Faltan: {', '.join(missing_fields)}.",
                partial_reasons=[f"Campo faltante: {f}" for f in missing_fields],
                suggestions=_build_suggestions(required_tables, missing_fields),
            )

    # --------------- Análisis es posible - determinar si completo o parcial ---

    partial_reasons = []

    # Verificar condiciones que hacen el análisis parcial
    for partial_condition in partial_if:
        if _evaluate_partial_condition(partial_condition, search_tables, available_semantics):
            partial_reasons.append(partial_condition)

    # Determinar proxies disponibles
    proxy_available, proxy_desc = _check_proxy_availability(analysis_name, active_tables)

    if partial_reasons:
        return FeasibilityResult(
            analysis_name=analysis_name,
            status=STATUS_PARTIAL,
            required_fields=required_fields,
            found_fields=found_fields,
            missing_fields=[],
            source_tables=[t.display_name for t in found_tables],
            reasoning=f"Posible con limitaciones: {'; '.join(partial_reasons)}",
            partial_reasons=partial_reasons,
            proxy_available=proxy_available,
            proxy_description=proxy_desc,
        )

    return FeasibilityResult(
        analysis_name=analysis_name,
        status=STATUS_POSSIBLE,
        required_fields=required_fields,
        found_fields=found_fields,
        missing_fields=[],
        source_tables=[t.display_name for t in found_tables],
        reasoning=f"Todos los campos requeridos están disponibles. {notes}",
        proxy_available=proxy_available,
        proxy_description=proxy_desc,
    )


def _evaluate_partial_condition(
    condition: str,
    tables: List[TableProfile],
    available_semantics: Dict[str, List[str]],
) -> bool:
    """
    Evalúa si una condición parcial se cumple.
    Las condiciones son texto descriptivo; se mapean a checks lógicos.
    """
    cond_lower = condition.lower()

    # Falta documento
    if "documento" in cond_lower and "líneas" in cond_lower:
        return not any(t.has_semantic("Documento") for t in tables)

    # Falta proveedor
    if "proveedor" in cond_lower:
        return not any(t.has_semantic("Proveedor") for t in tables)

    # Falta cliente
    if "cliente" in cond_lower:
        return not any(t.has_semantic("Cliente") for t in tables)

    # Falta familia
    if "familia" in cond_lower:
        return not any(t.has_semantic("Familia") for t in tables)

    # Falta Origen/Destino
    if "origen" in cond_lower or "destino" in cond_lower:
        has_origen = any(t.has_semantic("Origen") for t in tables)
        has_destino = any(t.has_semantic("Destino") for t in tables)
        return not (has_origen and has_destino)

    # Stock solo como snapshot
    if "snapshot" in cond_lower:
        stock_tables = [t for t in tables if t.table_type == "Stock"]
        if stock_tables:
            return not any(t.has_semantic("Fecha") for t in stock_tables)

    # Por defecto: no se puede evaluar automáticamente → asumir que no aplica
    return False


def _check_proxy_availability(
    analysis_name: str,
    active_tables: List[TableProfile],
) -> tuple[bool, str]:
    """
    Verifica si hay un proxy disponible cuando falta data ideal.
    Ejemplos: usar Pedidos como proxy de Preparaciones.
    """
    if "Pareto" in analysis_name or "Preparación" in analysis_name:
        has_prep = any(t.table_type == "Preparaciones" for t in active_tables)
        has_ped = any(t.table_type == "Pedidos" for t in active_tables)
        if not has_prep and has_ped:
            return True, "Se pueden usar Pedidos como proxy de Preparaciones/Picking."

    if "Devoluciones" in analysis_name:
        has_adj = any(t.table_type == "Ajustes" for t in active_tables)
        if has_adj:
            return True, "Los Ajustes pueden contener registros de devoluciones."

    return False, ""


def _build_suggestions(required_tables: list, missing_fields: list) -> List[str]:
    """Construye sugerencias para el usuario basadas en lo que falta."""
    suggestions = []

    table_suggestions = {
        "Stock": "Cargar una tabla de stock (SKU + Cantidad + Fecha opcional).",
        "Recepciones": "Cargar una tabla de recepciones (SKU + Cantidad + Fecha + Proveedor opcional).",
        "Pedidos": "Cargar una tabla de pedidos o ventas (SKU + Cantidad + Fecha + Cliente opcional).",
        "Preparaciones": "Cargar una tabla de preparaciones/picking.",
        "Transferencias": "Cargar una tabla de transferencias con Origen y Destino.",
        "Maestro de Productos": "Cargar un maestro de productos (SKU + Descripción + Familia).",
        "Ajustes": "Cargar una tabla de ajustes de inventario.",
        "Devoluciones Cliente": "Cargar una tabla de devoluciones de clientes.",
        "Devoluciones Proveedor": "Cargar una tabla de devoluciones a proveedor.",
    }

    field_suggestions = {
        "Fecha": "La tabla debe incluir una columna de fecha.",
        "SKU": "La tabla debe incluir una columna de código de producto/SKU.",
        "Cantidad": "La tabla debe incluir una columna de cantidad o unidades.",
        "Documento": "Agregar número de documento (factura, pedido, remito) para análisis por documento.",
        "Proveedor": "Agregar columna de proveedor para análisis de proveedores.",
        "Cliente": "Agregar columna de cliente para análisis de clientes.",
        "Familia": "Agregar columna de familia/categoría para segmentación.",
        "Deposito": "Agregar columna de depósito para separar análisis por ubicación.",
        "Origen": "Agregar columna de origen para el flujo de transferencias.",
        "Destino": "Agregar columna de destino para el flujo de transferencias.",
    }

    for t in required_tables:
        if t in table_suggestions:
            suggestions.append(table_suggestions[t])

    for f in missing_fields:
        if f in field_suggestions:
            suggestions.append(field_suggestions[f])

    return suggestions[:5]  # Máximo 5 sugerencias


# ---------------------------------------------------------------------------
# CONSTRUCCIÓN DEL REPORTE
# ---------------------------------------------------------------------------

def _build_diagnostic_report(
    profiles: List[TableProfile],
    feasibility_matrix: List[FeasibilityResult],
) -> DiagnosticReport:
    """
    Construye el DiagnosticReport completo con resumen ejecutivo.
    """
    possible = [r for r in feasibility_matrix if r.status == STATUS_POSSIBLE]
    partial = [r for r in feasibility_matrix if r.status == STATUS_PARTIAL]
    impossible = [r for r in feasibility_matrix if r.status == STATUS_IMPOSSIBLE]

    active_tables = [p for p in profiles if p.include_in_analysis]
    table_types = list({p.table_type for p in active_tables if p.table_type != "Otro"})
    total_rows = sum(p.row_count for p in active_tables)
    pct_viable = len(possible) / max(len(feasibility_matrix), 1) * 100
    pct_partial = len(partial) / max(len(feasibility_matrix), 1) * 100

    # Generar advertencias
    warnings = []
    all_issues = [issue for p in profiles for issue in p.quality_issues]
    error_issues = [i for i in all_issues if i.severity == "error"]
    if error_issues:
        warnings.append(
            f"Se detectaron {len(error_issues)} problemas críticos de calidad de datos."
        )

    low_conf_tables = [p for p in active_tables if p.type_confidence < 0.5]
    if low_conf_tables:
        warnings.append(
            f"{len(low_conf_tables)} tablas tienen baja confianza de clasificación. "
            "Revisar y corregir manualmente en el paso de revisión."
        )

    # Supuestos sugeridos
    suggestions = []
    table_types_set = {p.table_type for p in active_tables}

    if "Preparaciones" not in table_types_set and "Pedidos" in table_types_set:
        suggestions.append(
            "No hay tabla de Preparaciones. Se puede usar Pedidos como proxy de picking."
        )
    if "Maestro de Productos" not in table_types_set:
        suggestions.append(
            "No hay maestro de productos. El análisis por familia/categoría no será posible."
        )
    if "Proveedor" not in _get_available_semantics(active_tables):
        suggestions.append(
            "No hay campo Proveedor en recepciones. El análisis de proveedores no será posible."
        )
    if "Cliente" not in _get_available_semantics(active_tables):
        suggestions.append(
            "No hay campo Cliente en pedidos. El análisis de clientes no será posible."
        )

    # Generar resumen ejecutivo
    summary_parts = [
        f"Se cargaron {len(active_tables)} tabla(s) con un total de {total_rows:,} filas.",
        f"Tipos detectados: {', '.join(table_types) if table_types else 'no clasificados'}.",
        f"Análisis viables: {len(possible)}/{len(feasibility_matrix)} posibles, "
        f"{len(partial)} parciales, {len(impossible)} no posibles.",
        f"Viabilidad general del diagnóstico: {pct_viable + pct_partial/2:.0f}%.",
    ]

    return DiagnosticReport(
        tables=profiles,
        feasibility_matrix=feasibility_matrix,
        general_summary=" ".join(summary_parts),
        possible_analyses=[r.analysis_name for r in possible],
        partial_analyses=[r.analysis_name for r in partial],
        impossible_analyses=[r.analysis_name for r in impossible],
        suggested_assumptions=suggestions,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def _get_available_types(tables: List[TableProfile]) -> Set[str]:
    return {t.table_type for t in tables}


def _get_available_semantics(tables: List[TableProfile]) -> Dict[str, List[str]]:
    """
    Construye un mapa de semantic_type → [table_ids que lo tienen].
    """
    result: Dict[str, List[str]] = {}
    for table in tables:
        for semantic in table.get_all_semantics():
            result.setdefault(semantic, []).append(table.table_id)
    return result
