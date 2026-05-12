"""
backend/prompt_generator.py
============================
Genera un prompt flexible y personalizado para Claude + Power BI MCP.

La lógica de este generador es consultiva:
- No fuerza páginas fijas.
- No obliga a crear visuales predefinidos.
- Convierte la matriz de factibilidad en bloques candidatos de análisis.
- Para cada bloque, explica preguntas, KPIs, visuales recomendados,
  visuales alternativos y limitaciones.
- Obliga a Claude a validar el modelo real mediante MCP antes de escribir
  Power Query, DAX o crear visuales.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from config import ANALYSIS_BLOCKS
from models.table_profile import DiagnosticReport, FeasibilityResult, TableProfile


# ---------------------------------------------------------------------------
# API PÚBLICA
# ---------------------------------------------------------------------------

def generate_mcp_prompt(
    report: DiagnosticReport,
    project_name: str = "",
    options: Optional[Dict[str, object]] = None,
) -> str:
    """
    Genera el prompt completo para pegar en Claude conectado a Power BI MCP.

    Args:
        report: DiagnosticReport con diagnóstico, calidad y factibilidad.
        project_name: Nombre opcional del proyecto/cliente.
        options: Opciones opcionales desde la UI:
            - report_mode: Ejecutivo / Operativo / Técnico completo
            - report_focus: Diagnóstico general / Pedidos / Stock / etc.
            - force_plan_first: bool
            - allow_visual_creation: bool

    Returns:
        Texto del prompt.
    """
    options = _normalize_options(options)

    sections = [
        _section_header(project_name, options),
        _section_execution_protocol(options),
        _section_context_and_objective(),
        _section_loaded_data(report),
        _section_column_mapping(report),
        _section_data_quality(report),
        _section_feasibility_matrix(report),
        _section_candidate_analysis_blocks(report, options),
        _section_assumptions(report),
        _section_modeling_rules(),
        _section_power_query_tasks(report, options),
        _section_dax_tasks(report, options),
        _section_auxiliary_tables(report),
        _section_report_strategy(report, options),
        _section_expected_output(options),
        _section_final_checklist(report),
    ]

    return "\n\n".join(s for s in sections if s and s.strip())


# ---------------------------------------------------------------------------
# OPCIONES
# ---------------------------------------------------------------------------

def _normalize_options(options: Optional[Dict[str, object]]) -> Dict[str, object]:
    options = dict(options or {})
    options.setdefault("report_mode", "Técnico completo")
    options.setdefault("report_focus", "Diagnóstico general")
    options.setdefault("force_plan_first", True)
    options.setdefault("allow_visual_creation", False)
    return options


# ---------------------------------------------------------------------------
# SECCIONES PRINCIPALES
# ---------------------------------------------------------------------------

def _section_header(project_name: str, options: Dict[str, object]) -> str:
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    name_str = f" — Proyecto: {project_name}" if project_name else ""

    return f"""================================================================================
PROMPT PARA CLAUDE + POWER BI MCP
Diagnóstico Logístico General Flexible{name_str}
Generado: {date_str}
================================================================================

Actuá como un especialista senior en Power BI, Power Query, DAX y análisis logístico de depósitos, inventarios y cadena de suministro.

Modo de salida solicitado: {options['report_mode']}
Foco principal del reporte: {options['report_focus']}

Vas a trabajar conectado a Power BI mediante MCP. Tu tarea NO es crear siempre las mismas páginas ni aplicar un layout fijo. Tu tarea es analizar la data real disponible, decidir qué análisis tienen sentido y construir/proponer el mejor reporte posible según esa data.

Reglas críticas:
1. No inventes columnas, tablas, relaciones, medidas ni valores.
2. No escribas DAX ni Power Query hasta validar los nombres reales del modelo mediante MCP.
3. No construyas páginas completas para análisis no posibles.
4. Para análisis parciales, construí solo lo confiable y dejá visible la limitación.
5. Documentá todos los supuestos en el modelo y en la página de diagnóstico.
6. Si una instrucción de este prompt entra en conflicto con la data real, prevalece la data real."""


def _section_execution_protocol(options: Dict[str, object]) -> str:
    visual_rule = (
        "Podés crear visuales directamente si el modelo y las medidas quedan validados."
        if options.get("allow_visual_creation")
        else "No crees visuales directamente sin proponer antes la estructura de páginas y recibir validación del usuario."
    )

    plan_rule = (
        "OBLIGATORIO: antes de ejecutar cambios grandes, devolvé primero un plan de trabajo y esperá validación del usuario."
        if options.get("force_plan_first")
        else "Podés ejecutar tareas técnicas, pero igualmente explicá brevemente la secuencia de cambios."
    )

    return f"""================================================================================
A. PROTOCOLO DE EJECUCIÓN EN CLAUDE + MCP
================================================================================

Seguí este orden:

1. Inspeccioná el modelo real de Power BI mediante MCP.
   - Listá tablas reales.
   - Listá columnas reales relevantes.
   - Revisá relaciones existentes.
   - Identificá tipos de datos.

2. Contrastá el modelo real contra este diagnóstico.
   - Confirmá qué tablas detectadas existen realmente.
   - Confirmá qué columnas coinciden con el mapeo sugerido.
   - Marcá diferencias entre diagnóstico y modelo actual.

3. Proponé un plan de reporte antes de construir.
   - Páginas recomendadas.
   - Páginas descartadas y motivo.
   - Medidas necesarias.
   - Transformaciones necesarias.
   - Riesgos o supuestos.

4. Recién después de validar nombres reales:
   - Crear o ajustar Power Query.
   - Crear dimensiones y hechos.
   - Crear medidas DAX.
   - Crear tablas auxiliares.
   - Proponer o construir visuales.

{plan_rule}
{visual_rule}

Formato inicial esperado antes de crear medidas:
- Diagnóstico rápido del modelo real.
- Matriz actualizado de análisis posibles/parciales/no posibles.
- Plan de páginas recomendado.
- Lista de medidas a crear.
- Lista de transformaciones necesarias."""


def _section_context_and_objective() -> str:
    return """================================================================================
B. CONTEXTO Y OBJETIVO DEL REPORTE
================================================================================

El objetivo final es construir un Power BI de diagnóstico logístico general para una empresa. El reporte debe transformar archivos CSV/Excel sueltos en un análisis operativo útil para tomar decisiones sobre depósito, abastecimiento, stock, layout, slotting, capacidad y control de operación.

El reporte debe responder, solo si la data lo permite:
1. Qué información existe y qué tan completa está.
2. Qué movimientos logísticos pueden analizarse.
3. Cómo se comportan stock, recepciones, pedidos/preparaciones, transferencias, devoluciones y ajustes.
4. Si el stock puede cerrarse mediante balance de masa.
5. Qué clientes, proveedores, SKUs y familias concentran carga operativa.
6. Qué productos tienen exceso, baja cobertura o stock inmovilizado.
7. Qué SKUs concentran picking/preparación.
8. Qué limitaciones de data impiden análisis confiables.

No se busca una maqueta rígida. Para cada bloque de análisis, evaluá:
- Qué información está disponible.
- Qué preguntas se pueden responder.
- Qué KPIs conviene calcular.
- Qué visuales son recomendables.
- Qué visuales alternativos podrían usarse.
- Qué limitaciones existen.
- Qué insights preliminares aparecen.
- Qué página conviene crear, integrar o descartar."""


def _section_loaded_data(report: DiagnosticReport) -> str:
    lines = [
        "================================================================================",
        "C. DATA CARGADA Y TABLAS DETECTADAS",
        "================================================================================",
        "",
        f"Total de tablas incluidas en análisis: {len(report.active_tables)}",
        f"Total de filas: {sum(t.row_count for t in report.active_tables):,}",
        "",
    ]

    for table in report.active_tables:
        lines.extend([
            f"TABLA: {table.display_name}",
            f"  Tipo probable: {table.table_type} (confianza {table.type_confidence * 100:.0f}%)",
            f"  Filas: {table.row_count:,} | Columnas: {table.col_count}",
            f"  Rango de fechas detectado: {table.date_range_str}",
            f"  Calidad: {table.quality_label}",
        ])
        if table.type_reasoning:
            lines.append(f"  Razonamiento de clasificación: {table.type_reasoning}")

        mapped = [
            f"    - {col.original_name} → {col.detected_semantic} ({col.detection_confidence * 100:.0f}%, {col.detection_method})"
            for col in table.columns
            if col.detected_semantic != "Desconocido"
        ]
        if mapped:
            lines.append("  Columnas con semántica detectada:")
            lines.extend(mapped[:30])
            if len(mapped) > 30:
                lines.append(f"    - ... {len(mapped) - 30} columnas adicionales mapeadas")

        unknown_count = sum(1 for c in table.columns if c.detected_semantic == "Desconocido")
        if unknown_count:
            lines.append(f"  Columnas sin clasificar: {unknown_count}")

        lines.append("")

    return "\n".join(lines)


def _section_column_mapping(report: DiagnosticReport) -> str:
    lines = [
        "================================================================================",
        "D. MAPEO SUGERIDO DE COLUMNAS",
        "================================================================================",
        "",
        "Usá este mapeo como referencia, pero validá nombres reales en Power BI antes de escribir DAX o Power Query.",
        "",
    ]

    any_mapping = False
    for table in report.active_tables:
        mapping = table.build_effective_mapping()
        if not mapping:
            continue
        any_mapping = True
        lines.append(f"--- {table.display_name} ({table.table_type}) ---")
        for semantic, original in sorted(mapping.items()):
            lines.append(f"  {original} → {semantic}")
        lines.append("")

    if not any_mapping:
        lines.append("No hay mapeos confiables detectados. Claude debe inspeccionar el modelo y proponer mapeo manual.")
        lines.append("")

    lines.extend([
        "Nombres estándar recomendados para el modelo:",
        "SKU, Descripcion, Fecha, Cantidad, Documento, Cliente, Proveedor, Deposito, Origen, Destino, Familia, Subfamilia, TipoMovimiento, Stock, Costo, Valor.",
        "",
        "Regla: mantener SKU y Documento como texto para evitar pérdida de ceros a la izquierda.",
    ])

    return "\n".join(lines)


def _section_data_quality(report: DiagnosticReport) -> str:
    lines = [
        "================================================================================",
        "E. DIAGNÓSTICO DE CALIDAD DE DATOS",
        "================================================================================",
        "",
    ]

    for table in report.active_tables:
        errors = [i for i in table.quality_issues if i.severity == "error"]
        warnings = [i for i in table.quality_issues if i.severity == "warning"]
        infos = [i for i in table.quality_issues if i.severity == "info"]

        lines.append(f"TABLA: {table.display_name} ({table.table_type}) — {table.quality_label}")
        if not table.quality_issues:
            lines.append("  Sin problemas relevantes detectados por reglas.")
        else:
            for label, issues in (("Errores críticos", errors), ("Advertencias", warnings), ("Información", infos)):
                if issues:
                    lines.append(f"  {label}:")
                    for issue in issues[:12]:
                        lines.append(f"    - {issue.description}")
                    if len(issues) > 12:
                        lines.append(f"    - ... {len(issues) - 12} issues adicionales")
        lines.append("")

    if report.cross_table_issues:
        lines.append("INCONSISTENCIAS ENTRE TABLAS:")
        for issue in report.cross_table_issues:
            lines.append(f"  - {issue}")
        lines.append("")

    if report.warnings:
        lines.append("ADVERTENCIAS GLOBALES:")
        for warning in report.warnings:
            lines.append(f"  - {warning}")
        lines.append("")

    lines.extend([
        "Instrucción para Claude:",
        "Crear o proponer una página 'Diagnóstico de Data' con semáforo por análisis, problemas críticos, advertencias, supuestos y rango temporal. Esta página debe existir antes que cualquier página operativa.",
    ])

    return "\n".join(lines)


def _section_feasibility_matrix(report: DiagnosticReport) -> str:
    lines = [
        "================================================================================",
        "F. MATRIZ DE FACTIBILIDAD",
        "================================================================================",
        "",
        f"Viabilidad general estimada: {report.overall_feasibility_percentage:.1f}%",
        "",
    ]

    for status_title, analysis_names in (
        ("ANÁLISIS POSIBLES", report.possible_analyses),
        ("ANÁLISIS PARCIALES", report.partial_analyses),
        ("ANÁLISIS NO POSIBLES", report.impossible_analyses),
    ):
        lines.append(status_title)
        if not analysis_names:
            lines.append("  - Ninguno")
        for name in analysis_names:
            result = _find_result(report, name)
            if not result:
                continue
            lines.append(f"  - {result.status} {result.analysis_name}")
            if result.source_tables:
                lines.append(f"    Fuente: {', '.join(result.source_tables[:5])}")
            if result.found_fields:
                lines.append(f"    Campos encontrados: {', '.join(result.found_fields)}")
            if result.missing_fields:
                lines.append(f"    Campos faltantes: {', '.join(result.missing_fields)}")
            if result.reasoning:
                lines.append(f"    Motivo: {result.reasoning}")
            if result.proxy_available:
                lines.append(f"    Proxy posible: {result.proxy_description}")
        lines.append("")

    lines.extend([
        "Regla para Claude:",
        "- Los análisis posibles pueden transformarse en páginas o secciones del reporte.",
        "- Los análisis parciales pueden construirse solo con nota visible de limitación.",
        "- Los análisis no posibles NO deben construirse como páginas operativas; explicar qué falta.",
    ])

    return "\n".join(lines)


def _section_candidate_analysis_blocks(report: DiagnosticReport, options: Dict[str, object]) -> str:
    lines = [
        "================================================================================",
        "G. BLOQUES CANDIDATOS DE ANÁLISIS — ENFOQUE FLEXIBLE",
        "================================================================================",
        "",
        "Para cada bloque, usá la ficha siguiente como guía. No copies visuales de forma mecánica: elegí los que mejor comuniquen la data real.",
        "",
    ]

    focus = str(options.get("report_focus", "Diagnóstico general"))
    results = _ordered_results_for_focus(report, focus)

    for result in results:
        lines.extend(_build_analysis_block_card(result, report))
        lines.append("")

    return "\n".join(lines)


def _section_assumptions(report: DiagnosticReport) -> str:
    default_assumptions = [
        "Si no hay tabla de Preparaciones, usar Pedidos como proxy de picking, aclarándolo explícitamente.",
        "Si no hay Maestro de Productos, analizar por SKU y descripción disponible, sin inventar familia.",
        "Si no hay stock inicial/final, no cerrar balance de masa; mostrar solo evolución de movimientos.",
        "Si no hay Cliente, analizar demanda por documento/SKU y no crear análisis de clientes.",
        "Si no hay Proveedor, analizar recepciones por SKU/fecha y no crear ranking de proveedores.",
        "Si no hay Familia, crear 'Sin Familia' solo para agrupar nulos existentes; no inferir categorías.",
        "Si no hay Documento, no afirmar líneas por documento reales; usar aproximaciones solo con etiqueta de proxy.",
        "Si hay cantidades negativas, validar si representan devoluciones, anulaciones, reversas o errores antes de asignar signo.",
        "Para edad de stock, usar consumo histórico representativo y declarar ventana temporal usada.",
        "Para Pareto, priorizar líneas si hay Documento+SKU; si no, usar unidades como alternativa.",
    ]

    lines = [
        "================================================================================",
        "H. SUPUESTOS PERMITIDOS Y LIMITACIONES",
        "================================================================================",
        "",
        "Supuestos generales permitidos:",
    ]
    lines.extend(f"  - {s}" for s in default_assumptions)

    if report.suggested_assumptions:
        lines.append("")
        lines.append("Supuestos específicos sugeridos por el diagnóstico:")
        lines.extend(f"  - {s}" for s in report.suggested_assumptions)

    lines.extend([
        "",
        "Regla: todo supuesto usado debe quedar documentado en Power Query, en descripción de medidas críticas y en la página Diagnóstico de Data.",
    ])
    return "\n".join(lines)


def _section_modeling_rules() -> str:
    return """================================================================================
I. REGLAS DE MODELADO
================================================================================

1. Separar hechos y dimensiones siempre que la data lo permita.
2. Crear DimFecha si existe al menos una columna de fecha confiable.
3. Crear DimSKU desde maestro si existe; si no, deduplicar SKUs desde movimientos y marcar origen como proxy.
4. Crear DimCliente, DimProveedor, DimDeposito y DimFamilia solo si existen columnas reales.
5. Crear hechos por tipo de movimiento cuando existan: recepciones, pedidos, preparaciones, transferencias, ajustes, devoluciones y stock.
6. Crear MovimientosUnificados solo si aporta valor para balance de masa o perfil global. Debe incluir: Fecha, SKU, Deposito, Documento, TipoMovimiento, CantidadOriginal, CantidadSignada, FuenteArchivo y campos origen/destino si existen.
7. Definir signos con cuidado:
   - Recepciones: positivo.
   - Pedidos/ventas/preparaciones: negativo si representan salida de stock.
   - Devoluciones de cliente: positivo si retornan stock.
   - Devoluciones a proveedor: negativo.
   - Ajustes: según signo o tipo de ajuste.
   - Transferencias: negativo en origen y positivo en destino si se modela por depósito.
8. Evitar relaciones muchos-a-muchos innecesarias.
9. No usar FORMAT() en medidas numéricas que se usarán en gráficos.
10. No hardcodear nombres de tablas/columnas sin validarlos primero en MCP."""


def _section_power_query_tasks(report: DiagnosticReport, options: Dict[str, object]) -> str:
    lines = [
        "================================================================================",
        "J. TAREAS POWER QUERY SUGERIDAS",
        "================================================================================",
        "",
        "Aplicar solo las tareas que tengan sentido según la data real.",
        "",
        "Limpieza general:",
        "  - Confirmar separador, encoding y encabezados.",
        "  - Limpiar nombres de columnas.",
        "  - Convertir fechas con configuración regional correcta.",
        "  - Convertir cantidades, stock, costo y valor a número.",
        "  - Mantener SKU y Documento como texto.",
        "  - Eliminar filas totalmente vacías.",
        "  - Crear FuenteArchivo.",
        "  - Crear TipoMovimiento si no existe y el tipo de tabla lo permite.",
        "  - Crear CantidadSignada solo cuando el signo sea confiable o esté documentado.",
        "  - Reemplazar nulos de Familia por 'Sin Familia' solo si la columna existe.",
        "",
        "Tareas por tabla detectada:",
    ]

    for table in report.active_tables:
        mapping = table.build_effective_mapping()
        lines.append(f"  - {table.display_name} ({table.table_type}):")
        if mapping:
            lines.append(f"    Mapeo clave: {', '.join(f'{v}->{k}' for k, v in sorted(mapping.items()))}")
        else:
            lines.append("    Sin mapeo confiable; revisar manualmente.")

        if table.table_type in ("Recepciones", "Pedidos", "Preparaciones"):
            sign_text = "positivo" if table.table_type == "Recepciones" else "negativo si representa salida de stock"
            lines.append(f"    Crear TipoMovimiento='{table.table_type}' y evaluar CantidadSignada ({sign_text}).")
        elif table.table_type == "Transferencias":
            lines.append("    Evaluar si conviene duplicar filas origen(-)/destino(+) o mantener matriz origen-destino.")
        elif table.table_type == "Ajustes":
            lines.append("    Validar motivo/tipo/signo antes de sumar al balance de masa.")
        elif table.table_type == "Stock":
            lines.append("    Determinar si es snapshot actual, stock inicial/final o histórico por fecha.")

    lines.extend([
        "",
        "Tabla calendario:",
        "  - Crear calendario desde la fecha mínima hasta la máxima solo si hay fechas confiables.",
        "  - Incluir Año, Mes, AñoMes, Semana, DíaSemana y nombre de mes/día.",
    ])

    return "\n".join(lines)


def _section_dax_tasks(report: DiagnosticReport, options: Dict[str, object]) -> str:
    lines = [
        "================================================================================",
        "K. TAREAS DAX SUGERIDAS",
        "================================================================================",
        "",
        "Crear medidas SOLO cuando existan tablas y columnas necesarias. Validar nombres reales mediante MCP antes de escribir código.",
        "",
        "Medidas base candidatas:",
        "  - Total Unidades: suma de Cantidad o CantidadSignada según contexto.",
        "  - Total Documentos: distinctcount de Documento si existe.",
        "  - Total Líneas: countrows de la tabla de movimiento.",
        "  - Total SKUs: distinctcount de SKU.",
        "  - Fecha mínima / Fecha máxima.",
        "  - Días con actividad.",
        "  - Promedio diario.",
        "  - Percentil 90 diario de unidades, documentos, líneas o SKUs si aplica.",
        "",
        "Medidas por bloque viable:",
    ]

    viable_results = [r for r in report.feasibility_matrix if not _result_is_impossible(r)]
    for result in viable_results:
        block = ANALYSIS_BLOCKS.get(result.analysis_name, {})
        kpis = block.get("recommended_kpis", [])
        if not kpis:
            continue
        lines.append(f"  - {result.analysis_name} ({result.status}):")
        for kpi in kpis[:10]:
            lines.append(f"    - {kpi}")
        if _result_is_partial(result):
            lines.append("    Nota: crear solo medidas respaldadas por campos reales y agregar advertencia visible.")

    lines.extend([
        "",
        "Reglas para DAX:",
        "  - No usar FORMAT() en medidas usadas en gráficos.",
        "  - No crear medidas que referencien columnas faltantes.",
        "  - Si una medida requiere proxy, incluirlo en el nombre o descripción.",
        "  - Validar totales contra tablas base antes de construir visuales.",
    ])

    return "\n".join(lines)


def _section_auxiliary_tables(report: DiagnosticReport) -> str:
    lines = [
        "================================================================================",
        "L. TABLAS AUXILIARES CANDIDATAS",
        "================================================================================",
        "",
        "Crear tablas auxiliares solo si el visual o cálculo realmente las requiere.",
        "",
        "Candidatas:",
        "  - Bins de unidades por documento.",
        "  - Bins de líneas por documento.",
        "  - Bins de unidades por línea.",
        "  - Bins de días de cobertura para edad de stock.",
        "  - Clasificación ABC / Alta Rotación vs Resto.",
        "  - Tabla de estados de calidad/factibilidad para la página de diagnóstico.",
        "",
        "Regla: si no hay Documento, no crear bins por documento como si fueran reales. Si no hay consumo histórico, no crear bins de edad de stock operativa.",
    ]
    return "\n".join(lines)


def _section_report_strategy(report: DiagnosticReport, options: Dict[str, object]) -> str:
    lines = [
        "================================================================================",
        "M. ESTRATEGIA FLEXIBLE DE PÁGINAS Y VISUALES",
        "================================================================================",
        "",
        "No construyas una página por cada análisis de forma automática. Primero decidí si el bloque merece página propia, sección dentro de otra página o solo advertencia.",
        "",
        "Páginas siempre recomendadas:",
        "  1. Diagnóstico de Data: calidad, factibilidad, campos disponibles, supuestos y limitaciones.",
        "  2. Resumen Ejecutivo: hallazgos reales, confiabilidad y principales oportunidades.",
        "",
        "Páginas candidatas según factibilidad:",
    ]

    for result in report.feasibility_matrix:
        if _result_is_impossible(result):
            continue
        block = ANALYSIS_BLOCKS.get(result.analysis_name, {})
        objective = block.get("objective", "")
        lines.append(f"  - {result.analysis_name} ({result.status}): {objective}")
        if _result_is_partial(result):
            lines.append("    Crear solo si el aporte es claro; incluir nota visible de limitación.")

    if report.impossible_analyses:
        lines.append("")
        lines.append("Bloques que NO deben tener página operativa completa:")
        for name in report.impossible_analyses:
            result = _find_result(report, name)
            reason = result.reasoning if result else "Falta de datos."
            lines.append(f"  - {name}: {reason}")

    lines.extend([
        "",
        "Criterio visual:",
        "  - Usar tarjetas solo para indicadores de alto nivel.",
        "  - Usar series temporales cuando el período sea suficientemente confiable.",
        "  - Usar histogramas para tamaño de documentos/líneas si existe Documento.",
        "  - Usar Pareto cuando haya concentración por SKU/cliente/proveedor.",
        "  - Usar tablas de detalle para validar excepciones y diferencias.",
        "  - Usar notas visibles para proxies y limitaciones.",
    ])

    return "\n".join(lines)


def _section_expected_output(options: Dict[str, object]) -> str:
    return """================================================================================
N. OUTPUT ESPERADO DE CLAUDE
================================================================================

Primero devolvé:
1. Diagnóstico del modelo real de Power BI.
2. Confirmación de tablas y columnas reales.
3. Matriz de análisis posibles/parciales/no posibles actualizada.
4. Plan de páginas recomendado.
5. Lista de medidas y transformaciones a crear.

Luego, cuando se apruebe o cuando el usuario pida ejecutar:
1. Código M o pasos de Power Query aplicados.
2. Tablas creadas o modificadas.
3. Relaciones sugeridas o creadas.
4. Medidas DAX creadas, con código.
5. Tablas auxiliares creadas.
6. Visuales/páginas propuestas o creadas.
7. Páginas no creadas y motivo.
8. Supuestos documentados.
9. Checklist final de validación."""


def _section_final_checklist(report: DiagnosticReport) -> str:
    lines = [
        "================================================================================",
        "O. CHECKLIST FINAL DE VALIDACIÓN",
        "================================================================================",
        "",
        "Modelo:",
        "  [ ] Nombres reales de tablas y columnas validados por MCP.",
        "  [ ] Tipos de dato correctos.",
        "  [ ] Relaciones revisadas y sin muchos-a-muchos innecesarios.",
        "  [ ] DimFecha conectada cuando corresponde.",
        "  [ ] DimSKU/Cliente/Proveedor/Deposito creadas solo con data real.",
        "",
        "Calidad:",
    ]

    critical = [issue for t in report.active_tables for issue in t.quality_issues if issue.severity == "error"]
    if critical:
        lines.append("  [ ] Resolver o documentar problemas críticos:")
        for issue in critical[:8]:
            lines.append(f"      - {issue.description}")
        if len(critical) > 8:
            lines.append(f"      - ... {len(critical) - 8} problemas críticos adicionales")
    else:
        lines.append("  [ ] No se detectaron problemas críticos por reglas.")

    lines.extend([
        "",
        "DAX:",
        "  [ ] Ninguna medida referencia columnas inexistentes.",
        "  [ ] Ninguna medida numérica usa FORMAT() si se usa en gráficos.",
        "  [ ] Medidas con proxy están identificadas como proxy.",
        "  [ ] Totales validados contra tablas base.",
        "",
        "Reporte:",
        "  [ ] Diagnóstico de Data creado o propuesto.",
        "  [ ] Resumen Ejecutivo basado en datos reales.",
        "  [ ] Páginas imposibles no fueron creadas como análisis operativos.",
        "  [ ] Supuestos visibles para el usuario final.",
        "  [ ] Limitaciones claras por falta de datos.",
        "",
        "================================================================================",
        "FIN DEL PROMPT",
        "================================================================================",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HELPERS DE BLOQUES
# ---------------------------------------------------------------------------


def _result_is_impossible(result: FeasibilityResult) -> bool:
    status = str(getattr(result, "status", "")).lower()
    return "no posible" in status or "imposible" in status or "impossible" in status


def _result_is_partial(result: FeasibilityResult) -> bool:
    status = str(getattr(result, "status", "")).lower()
    return "parcial" in status or "partial" in status


def _result_is_possible(result: FeasibilityResult) -> bool:
    status = str(getattr(result, "status", "")).lower()
    return "posible" in status and not _result_is_impossible(result) and not _result_is_partial(result)

def _build_analysis_block_card(result: FeasibilityResult, report: DiagnosticReport) -> List[str]:
    block = ANALYSIS_BLOCKS.get(result.analysis_name, {})
    lines = [
        "--------------------------------------------------------------------------------",
        f"BLOQUE: {result.analysis_name}",
        "--------------------------------------------------------------------------------",
        f"Estado: {result.status}",
    ]

    if block.get("objective"):
        lines.append(f"Objetivo: {block['objective']}")
    if result.source_tables:
        lines.append(f"Fuentes detectadas: {', '.join(result.source_tables[:6])}")
    if result.found_fields:
        lines.append(f"Campos encontrados: {', '.join(result.found_fields)}")
    if result.missing_fields:
        lines.append(f"Campos faltantes: {', '.join(result.missing_fields)}")
    if result.reasoning:
        lines.append(f"Diagnóstico: {result.reasoning}")
    if result.partial_reasons:
        lines.append("Limitaciones parciales:")
        lines.extend(f"  - {r}" for r in result.partial_reasons)
    if result.proxy_available:
        lines.append(f"Proxy disponible: {result.proxy_description}")
    if result.suggestions:
        lines.append("Sugerencias para habilitar/mejorar:")
        lines.extend(f"  - {s}" for s in result.suggestions)

    if _result_is_impossible(result):
        lines.extend([
            "Instrucción para Claude:",
            "  - No crear página operativa completa para este bloque.",
            "  - Crear, como máximo, una nota en Diagnóstico de Data explicando qué falta.",
        ])
        return lines

    lines.append("Preguntas que puede responder:")
    for q in block.get("business_questions", ["Definir preguntas a partir de la data real."]):
        lines.append(f"  - {q}")

    lines.append("KPIs sugeridos:")
    for kpi in block.get("recommended_kpis", ["Definir KPIs según campos reales disponibles."]):
        lines.append(f"  - {kpi}")

    lines.append("Visuales recomendados:")
    for visual in block.get("visual_options", ["Elegir visual según granularidad y volumen de datos."]):
        lines.append(f"  - {visual}")

    alt = block.get("alternative_visuals", [])
    if alt:
        lines.append("Visuales alternativos / fallback:")
        for visual in alt:
            lines.append(f"  - {visual}")

    if _result_is_partial(result):
        lines.extend([
            "Instrucción para Claude:",
            "  - Este bloque es parcial: construir solo lo respaldado por campos reales.",
            "  - Incluir una nota visible de limitación en la página o sección.",
        ])
    else:
        lines.extend([
            "Instrucción para Claude:",
            "  - Este bloque puede ser candidato a página o sección principal.",
            "  - Antes de construir, validar columnas reales y proponer métricas/visuales finales.",
        ])

    return lines


def _ordered_results_for_focus(report: DiagnosticReport, focus: str) -> List[FeasibilityResult]:
    priority_map = {
        "Pedidos / Picking": ["Perfil de Pedidos", "Evolución de Pedidos", "Pareto de Preparación / Picking", "Análisis de Clientes", "Pedidos Global (con Transferencias)"],
        "Stock / Cobertura": ["Evolución de Stock", "Edad de Stock", "Balance de Masa", "Ajustes", "Pareto de Preparación / Picking"],
        "Recepciones": ["Perfil de Recepciones", "Evolución de Recepciones", "Análisis de Proveedores", "Pareto de Preparación / Picking"],
        "Balance de masa": ["Balance de Masa", "Ajustes", "Transferencias", "Devoluciones", "Evolución de Stock"],
        "Calidad de datos": ["Información Recibida", "Balance de Masa", "Evolución de Stock", "Perfil de Pedidos", "Perfil de Recepciones"],
    }

    results_by_name = {r.analysis_name: r for r in report.feasibility_matrix}
    ordered: List[FeasibilityResult] = []

    for name in priority_map.get(focus, ["Información Recibida"]):
        if name in results_by_name:
            ordered.append(results_by_name[name])

    for result in report.feasibility_matrix:
        if result.analysis_name not in {r.analysis_name for r in ordered}:
            ordered.append(result)

    return ordered


def _find_result(report: DiagnosticReport, analysis_name: str) -> Optional[FeasibilityResult]:
    return next((r for r in report.feasibility_matrix if r.analysis_name == analysis_name), None)
