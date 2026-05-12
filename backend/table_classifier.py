"""
backend/table_classifier.py
============================
Clasifica cada tabla según su función logística probable.
Usa los campos semánticos detectados + reglas de scoring del config.

Resultado: TableProfile con table_type, type_confidence y type_reasoning actualizados.
"""

import logging
from typing import List, Dict, Tuple

from config import TABLE_TYPE_INDICATORS
from models.table_profile import TableProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# ---------------------------------------------------------------------------

def classify_tables(profiles: List[TableProfile]) -> List[TableProfile]:
    """
    Clasifica el tipo de cada TableProfile según las columnas semánticas detectadas.
    Modifica los profiles in-place.

    Args:
        profiles: Lista de TableProfile con semánticas ya detectadas.

    Returns:
        Lista de TableProfile con table_type, type_confidence, type_reasoning actualizados.
    """
    for profile in profiles:
        table_type, confidence, reasoning, scores = _classify_single(profile)
        profile.table_type = table_type
        profile.type_confidence = confidence
        profile.type_reasoning = reasoning
        profile.type_scores = scores

    return profiles


# ---------------------------------------------------------------------------
# CLASIFICADOR INDIVIDUAL
# ---------------------------------------------------------------------------

def _classify_single(
    profile: TableProfile,
) -> Tuple[str, float, str, Dict[str, float]]:
    """
    Clasifica una tabla y retorna (tipo, confianza, razonamiento, scores_por_tipo).
    """
    # Obtener los tipos semánticos detectados en esta tabla
    detected_semantics = {
        col.detected_semantic
        for col in profile.columns
        if col.detected_semantic != "Desconocido"
    }

    scores: Dict[str, float] = {}
    reasonings: Dict[str, str] = {}

    for table_type, rules in TABLE_TYPE_INDICATORS.items():
        score, reasoning = _score_table_type(detected_semantics, rules, profile)
        scores[table_type] = score
        reasonings[table_type] = reasoning

    # Elegir el tipo con mayor score
    if not scores or max(scores.values()) == 0:
        return "Otro", 0.0, "No se pudo clasificar: campos semánticos insuficientes.", scores

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    # Si el score es demasiado bajo, clasificar como "Otro"
    if best_score < 0.3:
        return "Otro", best_score, f"Score bajo ({best_score:.2f}). Clasificación incierta.", scores

    # Normalizar score a confianza 0-1
    confidence = min(1.0, best_score)

    return best_type, confidence, reasonings[best_type], scores


def _score_table_type(
    detected_semantics: set,
    rules: dict,
    profile: TableProfile,
) -> Tuple[float, str]:
    """
    Calcula el score de una tabla contra las reglas de un tipo.

    Scoring:
    - Cada campo requerido presente: +0.4 / len(required)
    - Cada campo opcional presente: +0.1 / len(optional)
    - Cada disqualifier presente: -0.5
    - must_have_any satisfecho: +0.3 adicional
    - Si min_required no se cumple: score = 0
    """
    required = rules.get("required", [])
    optional = rules.get("optional", [])
    disqualifiers = rules.get("disqualifiers", [])
    must_have_any = rules.get("must_have_any", [])
    min_required = rules.get("min_required", 1)

    # Verificar campos requeridos
    found_required = [f for f in required if f in detected_semantics]
    found_optional = [f for f in optional if f in detected_semantics]
    found_disqualifiers = [f for f in disqualifiers if f in detected_semantics]
    found_must_have = [f for f in must_have_any if f in detected_semantics]

    # Si no se cumplen los mínimos requeridos, score = 0
    if len(found_required) < min_required:
        return 0.0, f"No cumple mínimo de campos requeridos ({len(found_required)}/{min_required})."

    # Calcular score base
    required_score = (len(found_required) / max(len(required), 1)) * 0.6
    optional_score = (len(found_optional) / max(len(optional), 1)) * 0.3 if optional else 0.0
    disqualifier_penalty = len(found_disqualifiers) * 0.4
    must_have_bonus = 0.2 if (must_have_any and found_must_have) else 0.0
    must_have_penalty = -0.3 if (must_have_any and not found_must_have) else 0.0

    score = required_score + optional_score - disqualifier_penalty + must_have_bonus + must_have_penalty
    score = max(0.0, score)

    # Construir razonamiento
    reasoning_parts = []
    if found_required:
        reasoning_parts.append(f"Campos requeridos detectados: {', '.join(found_required)}.")
    if found_optional:
        reasoning_parts.append(f"Campos opcionales: {', '.join(found_optional)}.")
    if found_disqualifiers:
        reasoning_parts.append(f"Campos que penalizan: {', '.join(found_disqualifiers)}.")
    if must_have_any and found_must_have:
        reasoning_parts.append(f"Campos clave presentes: {', '.join(found_must_have)}.")
    elif must_have_any and not found_must_have:
        reasoning_parts.append(f"Faltan campos clave: {', '.join(must_have_any)}.")

    reasoning = " ".join(reasoning_parts) if reasoning_parts else "Sin justificación."

    return score, reasoning


# ---------------------------------------------------------------------------
# UTILIDAD: HINT POR NOMBRE DE ARCHIVO
# ---------------------------------------------------------------------------

def get_type_hint_from_filename(file_name: str, sheet_name: str = None) -> str:
    """
    Intenta inferir el tipo de tabla a partir del nombre del archivo o hoja.
    Retorna el tipo sugerido o "" si no hay hint claro.

    Esto se usa como contexto adicional, no como clasificación definitiva.
    """
    name = (sheet_name or file_name).lower()

    hints = {
        "Maestro de Productos": ["maestro", "productos", "articulos", "items", "catalogo", "material"],
        "Stock": ["stock", "inventario", "existencia", "saldo"],
        "Recepciones": ["recepcion", "recibo", "ingreso", "entrada", "compra"],
        "Pedidos": ["pedido", "orden", "venta", "factura", "egreso", "salida"],
        "Preparaciones": ["preparacion", "picking", "despacho", "preparado"],
        "Transferencias": ["transferencia", "traslado", "movimiento", "transfer"],
        "Devoluciones Cliente": ["devolucion", "devcliente", "retorno"],
        "Devoluciones Proveedor": ["devproveedor", "devolprov", "ncredito"],
        "Ajustes": ["ajuste", "ajustes", "inventario_ajuste", "discrepancia"],
        "Clientes": ["cliente", "clientes", "customer"],
        "Proveedores": ["proveedor", "proveedores", "vendor", "supplier"],
        "Depósitos": ["deposito", "almacen", "warehouse", "sucursal"],
    }

    for table_type, keywords in hints.items():
        for kw in keywords:
            if kw in name:
                return table_type

    return ""
