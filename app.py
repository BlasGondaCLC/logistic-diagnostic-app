"""
app.py
======
Aplicación principal — Streamlit.
Asistente de Diagnóstico Logístico Previo a Power BI.

Flujo de 4 pasos:
  Paso 1 → Carga de archivos
  Paso 2 → Revisión y corrección (semi-automática)
  Paso 3 → Diagnóstico completo
  Paso 4 → Generación y descarga del prompt MCP

Para correr: streamlit run app.py
"""

import os
import sys
import logging
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Asegurar que el directorio raíz esté en el path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

# Cargar variables de entorno (.env)
load_dotenv(ROOT_DIR / ".env")

# Importar módulos del backend
from backend.file_loader import load_files
from backend.schema_profiler import profile_tables
from backend.semantic_column_detector import detect_column_semantics
from backend.table_classifier import classify_tables, get_type_hint_from_filename
from backend.data_quality_engine import run_quality_checks
from backend.feasibility_engine import run_feasibility_analysis
from backend.llm_analyzer import llm_enrich_all, llm_generate_prompt_context
from backend.prompt_generator import generate_mcp_prompt
from backend.export_utils import export_diagnostic_txt, export_technical_profile_json
from config import ALL_TABLE_TYPES, ALL_SEMANTIC_TYPES, REPORT_GENERATION_MODES, REPORT_FOCUS_OPTIONS

# ---------------------------------------------------------------------------
# CONFIGURACIÓN DE LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CONFIGURACIÓN DE STREAMLIT
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Diagnóstico Logístico → Power BI",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# ESTILOS CUSTOM — Tema CLC (negro + cyan)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* ── Fuente global ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }

    /* ── Fondo principal ── */
    .main .block-container { padding-top: 2rem; }

    /* ── Header de paso ── */
    .step-header {
        border-left: 3px solid #00C8D7;
        color: #ffffff;
        padding: 10px 20px;
        margin-bottom: 24px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        background: transparent;
    }

    /* ── Tipografía ── */
    h1 { color: #00C8D7 !important; font-weight: 800 !important; letter-spacing: -0.5px; }
    h2, h3 { color: #e8edf2 !important; font-weight: 600 !important; }
    h3 { font-size: 0.95rem !important; letter-spacing: 1px; text-transform: uppercase; color: #8fa3b8 !important; }

    /* ── Métricas ── */
    .clc-metric {
        background: #0d1624;
        border-top: 2px solid #00C8D7;
        padding: 16px 12px;
        text-align: center;
    }
    .clc-metric .num {
        font-size: 2.2rem;
        font-weight: 800;
        color: #00C8D7;
        line-height: 1;
    }
    .clc-metric .lbl {
        font-size: 0.7rem;
        color: #8fa3b8;
        margin-top: 6px;
        text-transform: uppercase;
        letter-spacing: 1.2px;
    }

    /* ── Badges de estado ── */
    .badge-ok   { color: #00C8D7; font-size: 0.72rem; font-weight: 700;
                  letter-spacing: 1px; text-transform: uppercase; }
    .badge-warn { color: #e6a817; font-size: 0.72rem; font-weight: 700;
                  letter-spacing: 1px; text-transform: uppercase; }
    .badge-fail { color: #c94b4b; font-size: 0.72rem; font-weight: 700;
                  letter-spacing: 1px; text-transform: uppercase; }

    /* ── Expanders ── */
    div[data-testid="stExpander"] {
        border: 1px solid #1a2535 !important;
        border-radius: 0 !important;
        background: #0d1624 !important;
    }
    div[data-testid="stExpander"] summary {
        font-weight: 600; font-size: 0.88rem;
        color: #cdd8e3; letter-spacing: 0.3px;
    }

    /* ── Tabla de datos ── */
    div[data-testid="stDataFrame"] { border: 1px solid #1a2535; }

    /* ── Botón primario ── */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: #00C8D7 !important;
        color: #060d14 !important;
        border: none !important;
        font-weight: 700 !important;
        font-size: 0.82rem !important;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        border-radius: 2px !important;
        padding: 0.6rem 1.4rem !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: #00dce9 !important;
    }
    div[data-testid="stButton"] > button[kind="secondary"] {
        border: 1px solid #1a2535 !important;
        color: #8fa3b8 !important;
        border-radius: 2px !important;
        font-size: 0.8rem !important;
        letter-spacing: 1px;
        text-transform: uppercase;
    }

    /* ── Separadores ── */
    hr { border-color: #1a2535 !important; margin: 1.5rem 0 !important; }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: #060d14 !important;
        border-right: 1px solid #1a2535;
    }
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {
        color: #8fa3b8;
        font-size: 0.83rem;
    }
    section[data-testid="stSidebar"] label {
        font-size: 0.78rem !important;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        color: #5a7a96 !important;
    }

    /* ── Insight Claude ── */
    .clc-insight {
        background: #0a1722;
        border-left: 2px solid #00C8D7;
        padding: 12px 16px;
        color: #adc0d0;
        font-size: 0.88rem;
        line-height: 1.7;
        margin-top: 8px;
    }

    /* ── Resumen ejecutivo ── */
    .clc-summary {
        background: #0a1722;
        border-top: 2px solid #00C8D7;
        padding: 20px 24px;
        color: #cdd8e3;
        line-height: 1.8;
        font-size: 0.94rem;
    }
    .clc-summary strong { color: #00C8D7; }

    /* ── Pasos sidebar ── */
    .step-done    { color: #00C8D7; font-size: 0.8rem; letter-spacing: 0.8px; }
    .step-active  { color: #ffffff; font-weight: 700; font-size: 0.85rem; letter-spacing: 0.8px; }
    .step-pending { color: #2d4055; font-size: 0.8rem; letter-spacing: 0.8px; }

    /* ── File uploader ── */
    div[data-testid="stFileUploader"] {
        border: 1px dashed #1a2535 !important;
        border-radius: 0 !important;
        background: #0a1722 !important;
        padding: 12px;
    }
    div[data-testid="stFileUploader"]:hover { border-color: #00C8D7 !important; }

    /* ── Tabs ── */
    div[data-baseweb="tab-list"] {
        background: #0d1624 !important;
        border-radius: 0; gap: 2px;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: #00C8D7 !important;
        color: #060d14 !important;
        font-weight: 700 !important;
        border-radius: 0 !important;
        font-size: 0.78rem !important;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    button[data-baseweb="tab"] {
        font-size: 0.78rem !important;
        letter-spacing: 1px;
        text-transform: uppercase;
        color: #8fa3b8 !important;
    }

    /* ── Prompt textarea ── */
    div[data-testid="stTextArea"] textarea {
        font-family: 'Consolas', 'Courier New', monospace !important;
        font-size: 0.8rem !important;
        background: #060d14 !important;
        color: #8bbdd9 !important;
        border: 1px solid #1a2535 !important;
        border-radius: 0 !important;
    }

    /* ── Download buttons ── */
    div[data-testid="stDownloadButton"] > button {
        border: 1px solid #1a2535 !important;
        color: #8fa3b8 !important;
        border-radius: 2px !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    div[data-testid="stDownloadButton"] > button[kind="primary"] {
        border: 1px solid #00C8D7 !important;
        color: #00C8D7 !important;
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background: #00C8D710 !important;
        border-color: #00C8D7 !important;
        color: #00C8D7 !important;
    }

    /* ── Inputs ── */
    div[data-testid="stTextInput"] input,
    div[data-testid="stSelectbox"] div {
        border-radius: 2px !important;
        border-color: #1a2535 !important;
        background: #0a1722 !important;
    }

    /* ── Toggle ── */
    label[data-testid="stWidgetLabel"] p {
        font-size: 0.8rem !important;
        color: #8fa3b8 !important;
    }

    /* ── st.info / st.warning / st.success ── */
    div[data-testid="stAlert"] {
        border-radius: 0 !important;
        border-left-width: 3px !important;
    }

    /* ── Captions ── */
    div[data-testid="stCaptionContainer"] p {
        font-size: 0.72rem !important;
        letter-spacing: 0.5px;
        color: #3d5268 !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _resolve_api_key() -> str:
    """Resuelve la API key en orden de prioridad:
    1. st.secrets (Streamlit Community Cloud)
    2. Variable de entorno / .env (local)
    3. Cadena vacía → el usuario la ingresa manualmente
    """
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("ANTHROPIC_API_KEY", "")


# ---------------------------------------------------------------------------
# INICIALIZACIÓN DE SESSION STATE
# ---------------------------------------------------------------------------

def init_session_state():
    """Inicializa todas las variables del session state."""
    defaults = {
        "step": 1,
        "loaded_tables": [],           # List[(df, file_name, sheet_name)]
        "load_errors": [],             # Errores de carga
        "profiles": [],                # List[TableProfile]
        "diagnostic_report": None,     # DiagnosticReport
        "generated_prompt": "",        # Prompt final
        "project_name": "",            # Nombre del proyecto/cliente
        "api_key": "",                 # Anthropic API key
        "use_llm": True,               # Usar LLM para detección de columnas
        "use_llm_classification": True,  # Usar LLM para clasificar tablas
        "use_llm_insights": True,        # Usar LLM para insights de calidad
        "use_llm_summary": True,         # Usar LLM para resumen ejecutivo
        "report_mode": "Técnico completo",   # Nivel de detalle del prompt MCP
        "report_focus": "Diagnóstico general",  # Foco del reporte generado
        "force_plan_first": True,       # Claude debe proponer plan antes de ejecutar
        "allow_visual_creation": False, # Permitir creación directa de visuales
        "processing": False,           # Flag de procesamiento
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

init_session_state()


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------

def render_sidebar():
    with st.sidebar:
        st.markdown("""
<div style="padding:24px 0 8px 0;">
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 260 115" width="200">
    <defs>
      <clipPath id="ccut"><rect x="0" y="0" width="68" height="90"/></clipPath>
    </defs>
    <!-- CLC letras -->
    <text x="4" y="82" font-family="Arial Black,Impact,sans-serif" font-weight="900"
          font-size="82" fill="#ffffff" letter-spacing="-4" clip-path="url(#ccut)">C</text>
    <!-- diagonal slash sobre la C -->
    <line x1="6" y1="8" x2="56" y2="84" stroke="#00C8D7" stroke-width="3.5"/>
    <text x="58" y="82" font-family="Arial Black,Impact,sans-serif" font-weight="900"
          font-size="82" fill="#ffffff" letter-spacing="-4">LC</text>
    <!-- línea horizontal -->
    <line x1="4" y1="92" x2="256" y2="92" stroke="#ffffff" stroke-width="1.2" opacity="0.5"/>
    <!-- tagline -->
    <text x="4" y="106" font-family="Arial,sans-serif" font-weight="400"
          font-size="9.5" fill="#8fa3b8" letter-spacing="1.8">EXCELENCIA EN ASESORÍA Y CONSTRUCCIÓN LOGÍSTICA</text>
  </svg>
</div>
""", unsafe_allow_html=True)

        st.divider()

        # Progreso
        steps = ["01 — Carga", "02 — Revisión", "03 — Diagnóstico", "04 — Prompt MCP"]
        current = st.session_state.step - 1
        for i, step_label in enumerate(steps):
            if i < current:
                st.markdown(f'<p class="step-done">— {step_label}</p>', unsafe_allow_html=True)
            elif i == current:
                st.markdown(f'<p class="step-active">→ {step_label}</p>', unsafe_allow_html=True)
            else:
                st.markdown(f'<p class="step-pending">· {step_label}</p>', unsafe_allow_html=True)

        st.divider()

        # Configuración
        st.markdown("**CONFIGURACIÓN**")

        st.session_state.project_name = st.text_input(
            "Nombre del proyecto / cliente",
            value=st.session_state.project_name,
            placeholder="Ej: Empresa X - Análisis Q1 2025",
        )

        # API Key — prioridad: st.secrets (Streamlit Cloud) > .env > campo manual
        api_key_auto = _resolve_api_key()
        if api_key_auto:
            st.session_state.api_key = api_key_auto
            st.success("API key configurada")
        else:
            entered = st.text_input(
                "Anthropic API Key",
                type="password",
                value=st.session_state.api_key,
                placeholder="sk-ant-...",
                help="Necesaria para análisis con Claude. Sin key, usa solo heurísticas.",
            )
            if entered:
                st.session_state.api_key = entered

        llm_enabled = bool(st.session_state.api_key)

        st.markdown("**Análisis con Claude:**")

        st.session_state.use_llm = st.toggle(
            "Detección de columnas",
            value=st.session_state.use_llm and llm_enabled,
            disabled=not llm_enabled,
            help="Claude clasifica columnas con nombres ambiguos.",
        )
        st.session_state.use_llm_classification = st.toggle(
            "Clasificación de tablas",
            value=st.session_state.use_llm_classification and llm_enabled,
            disabled=not llm_enabled,
            help="Claude determina el tipo de cada tabla leyendo los datos reales.",
        )
        st.session_state.use_llm_insights = st.toggle(
            "Insights de calidad",
            value=st.session_state.use_llm_insights and llm_enabled,
            disabled=not llm_enabled,
            help="Claude analiza cada tabla y genera observaciones sobre calidad y contenido.",
        )
        st.session_state.use_llm_summary = st.toggle(
            "Resumen ejecutivo",
            value=st.session_state.use_llm_summary and llm_enabled,
            disabled=not llm_enabled,
            help="Claude escribe el resumen ejecutivo del diagnóstico en lenguaje natural.",
        )

        if not llm_enabled:
            st.caption("Ingresá una API key para activar los análisis con Claude.")

        st.divider()

        st.markdown("**ESTRATEGIA DEL PROMPT**")
        st.session_state.report_mode = st.selectbox(
            "Nivel de detalle",
            options=REPORT_GENERATION_MODES,
            index=REPORT_GENERATION_MODES.index(st.session_state.report_mode)
            if st.session_state.report_mode in REPORT_GENERATION_MODES else 2,
            help="Define si el prompt final prioriza resumen ejecutivo, análisis operativo o detalle técnico completo.",
        )
        st.session_state.report_focus = st.selectbox(
            "Foco del reporte",
            options=REPORT_FOCUS_OPTIONS,
            index=REPORT_FOCUS_OPTIONS.index(st.session_state.report_focus)
            if st.session_state.report_focus in REPORT_FOCUS_OPTIONS else 0,
            help="Ordena y prioriza los bloques de análisis del prompt final.",
        )
        st.session_state.force_plan_first = st.checkbox(
            "Pedir plan antes de ejecutar cambios",
            value=st.session_state.force_plan_first,
            help="Hace que Claude primero proponga la estructura del reporte antes de crear medidas o visuales.",
        )
        st.session_state.allow_visual_creation = st.checkbox(
            "Permitir creación directa de visuales",
            value=st.session_state.allow_visual_creation,
            help="Si está desactivado, el prompt le pide a Claude que proponga visuales antes de crearlos.",
        )

        st.divider()

        # Reset
        if st.button("Nuevo análisis", use_container_width=True, type="secondary"):
            for key in ["loaded_tables", "load_errors", "profiles", "diagnostic_report",
                        "generated_prompt"]:
                st.session_state[key] = [] if isinstance(st.session_state[key], list) else None if key != "generated_prompt" else ""
            st.session_state.step = 1
            st.rerun()

        st.divider()
        st.caption("v1.0 · CLC — Diagnóstico Logístico")


# ---------------------------------------------------------------------------
# PASO 1: CARGA DE ARCHIVOS
# ---------------------------------------------------------------------------

def render_step1():
    st.markdown('<div class="step-header">01 — Carga de archivos</div>', unsafe_allow_html=True)

    st.markdown("""
    Cargá uno o varios archivos de tu cliente. La app acepta:
    **Excel** (.xlsx, .xls) y **CSV** (.csv).
    En Excel con múltiples hojas, cada hoja se analiza por separado.
    """)

    uploaded_files = st.file_uploader(
        "Arrastrá o seleccioná archivos",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
        key="file_uploader",
        label_visibility="collapsed",
    )

    if not uploaded_files:
        st.info("Cargá al menos un archivo para comenzar.")
        _show_format_tips()
        return

    # Mostrar lista de archivos subidos
    st.markdown(f"**{len(uploaded_files)} archivo(s) seleccionado(s):**")
    for f in uploaded_files:
        size_kb = len(f.getvalue()) / 1024
        st.markdown(f"  📄 `{f.name}` ({size_kb:.0f} KB)")

    st.divider()

    col1, col2 = st.columns([2, 1])
    with col1:
        process_btn = st.button(
            "🚀 Cargar y procesar archivos",
            type="primary",
            use_container_width=True,
        )

    if process_btn:
        with st.spinner("Cargando y analizando archivos..."):
            _process_step1(uploaded_files)


def _process_step1(uploaded_files):
    """Ejecuta la carga y profiling de archivos."""

    # Resetear archivos subidos para reprocessarlos
    for f in uploaded_files:
        f.seek(0)

    # Paso 1.1: Cargar archivos
    loaded_tables, load_errors = load_files(uploaded_files)
    st.session_state.load_errors = load_errors

    if not loaded_tables:
        st.error("No se pudo cargar ningún archivo. Verificá los errores abajo.")
        for err in load_errors:
            st.error(err)
        return

    st.session_state.loaded_tables = loaded_tables

    # Paso 1.2: Perfilar tablas
    profiles = profile_tables(loaded_tables)

    # Paso 1.3: Detectar semánticas (heurísticas + LLM opcional)
    api_key = st.session_state.api_key if st.session_state.use_llm else None
    profiles = detect_column_semantics(
        profiles,
        api_key=api_key,
        use_llm=st.session_state.use_llm and bool(api_key),
    )

    # Paso 1.4: Clasificar tablas
    profiles = classify_tables(profiles)

    # Aplicar hint de nombre de archivo para mejorar clasificación
    for i, profile in enumerate(profiles):
        hint = get_type_hint_from_filename(profile.file_name, profile.sheet_name)
        if hint and profile.type_confidence < 0.7:
            # Si la confianza es baja, el hint del nombre puede ayudar
            profile.type_reasoning += f" (Hint por nombre: {hint})"
            if profile.type_confidence < 0.5:
                profile.table_type = hint
                profile.type_confidence = 0.55

    st.session_state.profiles = profiles

    # Mostrar errores de carga si los hay
    if load_errors:
        for err in load_errors:
            st.warning(err)

    st.success(f"{len(loaded_tables)} tabla(s) cargada(s) exitosamente.")
    st.session_state.step = 2
    st.rerun()


def _show_format_tips():
    with st.expander("Consejos de formato"):
        st.markdown("""
        **Excel (.xlsx, .xls)**
        - Cada hoja del archivo se analiza por separado.
        - El header debe estar en la fila 1 (la app intenta detectarlo si no es así).
        - No es necesario exportar a CSV, la app lee Excel directamente.

        **CSV**
        - Separador automático: punto y coma (;), coma (,) o tab.
        - Encoding automático: UTF-8, Latin-1, Windows-1252.
        - Decimales con coma (1.234,56) o punto (1,234.56).
        - Fechas DD/MM/YYYY o YYYY-MM-DD.

        **Nombres de columnas**
        - No es necesario que sean exactos. La app detecta variantes como:
          SKU, CodArticulo, Item, Producto, Material, etc.
        """)


# ---------------------------------------------------------------------------
# PASO 2: REVISIÓN Y CORRECCIÓN
# ---------------------------------------------------------------------------

def render_step2():
    st.markdown('<div class="step-header">02 — Revisión y corrección</div>', unsafe_allow_html=True)

    profiles = st.session_state.profiles
    if not profiles:
        st.warning("No hay archivos cargados. Volvé al Paso 1.")
        return

    st.markdown("""
    Revisá la clasificación automática de cada tabla y corregí si es necesario.
    Podés también ajustar el mapeo de columnas clave antes de generar el análisis.
    """)

    # Resumen de lo detectado
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tablas cargadas", len(profiles))
    with col2:
        high_conf = sum(1 for p in profiles if p.type_confidence >= 0.7)
        st.metric("Clasificación segura", f"{high_conf}/{len(profiles)}")
    with col3:
        total_rows = sum(p.row_count for p in profiles)
        st.metric("Total filas", f"{total_rows:,}")

    st.divider()

    # --- Panel de revisión por tabla ---
    for i, profile in enumerate(profiles):
        confidence_pct = profile.type_confidence * 100
        confidence_icon = "🟢" if confidence_pct >= 70 else "🟡" if confidence_pct >= 40 else "🔴"
        header = f"{confidence_icon} {profile.display_name}  ·  {profile.row_count:,} filas  ·  {profile.table_type}"

        with st.expander(header, expanded=(confidence_pct < 70)):
            col_left, col_right = st.columns([1, 2])

            with col_left:
                # Clasificación
                st.markdown("**Clasificación de tabla**")
                new_type = st.selectbox(
                    "Tipo de tabla",
                    options=ALL_TABLE_TYPES,
                    index=ALL_TABLE_TYPES.index(profile.table_type) if profile.table_type in ALL_TABLE_TYPES else len(ALL_TABLE_TYPES) - 1,
                    key=f"type_{i}",
                    label_visibility="collapsed",
                )
                profile.table_type = new_type

                st.caption(f"Confianza automática: {confidence_pct:.0f}%")
                if profile.type_reasoning:
                    st.caption(f"Razón: {profile.type_reasoning[:120]}...")

                st.divider()

                # Incluir/excluir del análisis
                profile.include_in_analysis = st.checkbox(
                    "Incluir en el análisis",
                    value=profile.include_in_analysis,
                    key=f"include_{i}",
                )

                st.divider()

                # Info de rango
                st.markdown("**Rango de fechas**")
                st.caption(profile.date_range_str)

            with col_right:
                st.markdown("**Mapeo de columnas** (editá lo que no sea correcto)")

                # Mostrar columnas detectadas con posibilidad de corrección
                mapping = profile.build_effective_mapping()

                # Columnas con semántica detectada
                detected_cols = [col for col in profile.columns if col.detected_semantic != "Desconocido"]
                unknown_cols = [col for col in profile.columns if col.detected_semantic == "Desconocido"]

                if detected_cols:
                    corrected_mapping = {}
                    col_a, col_b = st.columns(2)

                    with col_a:
                        st.caption("Columna original")
                    with col_b:
                        st.caption("Tipo semántico detectado")

                    for col in detected_cols:
                        c1, c2 = st.columns(2)
                        with c1:
                            conf_label = "·" if col.detection_confidence >= 0.7 else "?"
                            st.markdown(f"{conf_label} `{col.original_name}`")
                            if col.sample_values:
                                st.caption(f"Muestra: {', '.join(str(v) for v in col.sample_values[:3])}")
                        with c2:
                            corrected = st.selectbox(
                                "tipo",
                                options=ALL_SEMANTIC_TYPES,
                                index=ALL_SEMANTIC_TYPES.index(col.detected_semantic) if col.detected_semantic in ALL_SEMANTIC_TYPES else len(ALL_SEMANTIC_TYPES) - 1,
                                key=f"sem_{i}_{col.original_name}",
                                label_visibility="collapsed",
                            )
                            if corrected != col.detected_semantic:
                                corrected_mapping[corrected] = col.original_name
                                col.detected_semantic = corrected

                    # Actualizar mapping manual en el profile
                    if corrected_mapping:
                        profile.column_mapping.update(corrected_mapping)

                # Columnas sin detectar (opcional mostrarlas)
                if unknown_cols:
                    with st.expander(f"{len(unknown_cols)} columnas sin clasificar"):
                        for col in unknown_cols[:20]:
                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown(f"`{col.original_name}`")
                                if col.sample_values:
                                    st.caption(f"{', '.join(str(v) for v in col.sample_values[:2])}")
                            with c2:
                                assign = st.selectbox(
                                    "tipo",
                                    options=ALL_SEMANTIC_TYPES,
                                    index=len(ALL_SEMANTIC_TYPES) - 1,  # "Desconocido"
                                    key=f"unk_{i}_{col.original_name}",
                                    label_visibility="collapsed",
                                )
                                if assign != "Desconocido":
                                    col.detected_semantic = assign
                                    profile.column_mapping[assign] = col.original_name

    st.divider()

    col1, col2 = st.columns([2, 1])
    with col1:
        if st.button("Confirmar y generar análisis", type="primary", use_container_width=True):
            with st.spinner("Ejecutando análisis de calidad y factibilidad..."):
                _process_step2()


def _process_step2():
    """Ejecuta quality checks, feasibility analysis y enriquecimiento LLM."""
    profiles = st.session_state.profiles
    loaded_tables = st.session_state.loaded_tables
    api_key = st.session_state.api_key

    any_llm = (
        st.session_state.use_llm_classification or
        st.session_state.use_llm_insights or
        st.session_state.use_llm_summary
    )

    # Paso A: Quality checks (heurístico)
    with st.status("Verificando calidad de datos...", expanded=False):
        profiles, cross_warnings = run_quality_checks(profiles, loaded_tables)
        st.write(f"Calidad verificada en {len(profiles)} tablas.")

    # Paso B: Feasibility analysis (heurístico)
    with st.status("Calculando factibilidad de análisis...", expanded=False):
        report = run_feasibility_analysis(profiles)
        report.cross_table_issues = cross_warnings
        st.write(f"{len(report.possible_analyses)} posibles, {len(report.partial_analyses)} parciales, {len(report.impossible_analyses)} no posibles.")

    # Paso C: Enriquecimiento LLM (si hay API key y algún toggle activo)
    if api_key and any_llm:
        steps_llm = []
        if st.session_state.use_llm_classification:
            steps_llm.append("clasificación de tablas")
        if st.session_state.use_llm_insights:
            steps_llm.append("insights de calidad")
        if st.session_state.use_llm_summary:
            steps_llm.append("resumen ejecutivo")

        with st.status(f"Claude analizando: {', '.join(steps_llm)}...", expanded=True):
            st.write("Enviando datos a Claude API...")
            try:
                profiles, report = llm_enrich_all(
                    profiles=profiles,
                    loaded_tables=loaded_tables,
                    report=report,
                    api_key=api_key,
                    use_llm_classification=st.session_state.use_llm_classification,
                    use_llm_insights=st.session_state.use_llm_insights,
                    use_llm_summary=st.session_state.use_llm_summary,
                )
                st.write("✅ Análisis con Claude completado.")
            except Exception as e:
                st.warning(f"Enriquecimiento LLM tuvo errores: {e}. Se usarán los resultados heurísticos.")

    st.session_state.profiles = profiles
    st.session_state.diagnostic_report = report
    st.session_state.step = 3
    st.rerun()


def _get_prompt_options() -> dict:
    """Opciones de estrategia que se inyectan en el prompt MCP."""
    return {
        "report_mode": st.session_state.get("report_mode", "Técnico completo"),
        "report_focus": st.session_state.get("report_focus", "Diagnóstico general"),
        "force_plan_first": st.session_state.get("force_plan_first", True),
        "allow_visual_creation": st.session_state.get("allow_visual_creation", False),
    }


# ---------------------------------------------------------------------------
# PASO 3: DIAGNÓSTICO COMPLETO
# ---------------------------------------------------------------------------

def render_step3():
    st.markdown('<div class="step-header">03 — Diagnóstico completo</div>', unsafe_allow_html=True)

    report = st.session_state.diagnostic_report
    if report is None:
        st.warning("No hay diagnóstico generado. Volvé al Paso 2.")
        return

    # --- Resumen ejecutivo ---
    st.markdown("### Resumen ejecutivo")
    # Detectar si el resumen fue generado por Claude o por template
    is_llm_summary = not report.general_summary.startswith("Se cargaron")
    if is_llm_summary:
        st.markdown(
            f'<div style="background:#f0f7ff;border-left:4px solid #2d6099;padding:14px 18px;'
            f'border-radius:6px;color:#1a1a2e;line-height:1.6">'
            f'🤖 <strong>Análisis Claude:</strong><br>{report.general_summary}'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info(report.general_summary)

    # Métricas principales
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("✅ Análisis posibles", len(report.possible_analyses))
    with c2:
        st.metric("⚠️ Análisis parciales", len(report.partial_analyses))
    with c3:
        st.metric("No posibles", len(report.impossible_analyses))
    with c4:
        viab = report.overall_feasibility_percentage
        st.metric("Viabilidad general", f"{viab:.0f}%")

    st.divider()

    # --- Calidad de datos ---
    st.markdown("### 🔎 Calidad de datos por tabla")

    for table in report.active_tables:
        errors = [i for i in table.quality_issues if i.severity == "error"]
        warnings = [i for i in table.quality_issues if i.severity == "warning"]
        infos = [i for i in table.quality_issues if i.severity == "info"]

        label = f"{table.quality_label} — {table.display_name} ({table.table_type})"
        with st.expander(label, expanded=bool(errors)):
            cols = st.columns(4)
            cols[0].metric("Filas", f"{table.row_count:,}")
            cols[1].metric("Columnas", table.col_count)
            cols[2].metric("Período", table.date_range_str[:20] if len(table.date_range_str) > 20 else table.date_range_str)
            cols[3].metric("Tipo", table.table_type)

            if errors:
                st.markdown("**🔴 Errores críticos:**")
                for e in errors:
                    st.error(e.description)
            if warnings:
                st.markdown("**🟡 Advertencias:**")
                for w in warnings:
                    st.warning(w.description)
            if infos:
                st.markdown("**🔵 Información:**")
                for info in infos:
                    st.info(info.description)
            if not errors and not warnings and not infos:
                st.success("Sin problemas de calidad detectados.")

            # Insights de Claude (si están disponibles)
            llm_insights = table.__dict__.get("llm_insights", "")
            if llm_insights:
                st.markdown("**Análisis de Claude:**")
                st.markdown(
                    f'<div style="background:#f0f7ff;border-left:3px solid #2d6099;'
                    f'padding:10px 14px;border-radius:4px;color:#1a1a2e;font-size:0.93rem;line-height:1.6">'
                    f'{llm_insights}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # Mapeo de columnas
            mapping = table.build_effective_mapping()
            if mapping:
                st.markdown("**Mapeo efectivo:**")
                mapping_strs = [f"`{v}` → **{k}**" for k, v in mapping.items()]
                st.markdown("  |  ".join(mapping_strs))

    # Inconsistencias cross-tabla
    if report.cross_table_issues:
        st.markdown("### Inconsistencias entre tablas")
        for issue in report.cross_table_issues:
            st.warning(issue)

    st.divider()

    # --- Matriz de factibilidad ---
    st.markdown("### 📐 Matriz de factibilidad de análisis")

    tab_possible, tab_partial, tab_impossible = st.tabs([
        f"Posibles ({len(report.possible_analyses)})",
        f"Parciales ({len(report.partial_analyses)})",
        f"No posibles ({len(report.impossible_analyses)})",
    ])

    with tab_possible:
        if report.possible_analyses:
            for name in report.possible_analyses:
                result = next((r for r in report.feasibility_matrix if r.analysis_name == name), None)
                if result:
                    with st.expander(f"[POSIBLE] {name}"):
                        st.markdown(f"**Tablas fuente:** {', '.join(result.source_tables[:3])}")
                        st.markdown(f"**Campos:** {', '.join(result.found_fields)}")
                        st.markdown(f"**Razonamiento:** {result.reasoning}")
        else:
            st.info("No hay análisis completamente posibles con la data cargada.")

    with tab_partial:
        if report.partial_analyses:
            for name in report.partial_analyses:
                result = next((r for r in report.feasibility_matrix if r.analysis_name == name), None)
                if result:
                    with st.expander(f"[PARCIAL] {name}"):
                        st.markdown(f"**Razonamiento:** {result.reasoning}")
                        if result.missing_fields:
                            st.markdown(f"**Faltan:** {', '.join(result.missing_fields)}")
                        if result.partial_reasons:
                            for r in result.partial_reasons:
                                st.markdown(f"- {r}")
                        if result.proxy_available:
                            st.success(f"Proxy disponible: {result.proxy_description}")
                        if result.suggestions:
                            st.markdown("**Sugerencias:**")
                            for s in result.suggestions:
                                st.markdown(f"- {s}")
        else:
            st.info("No hay análisis parciales.")

    with tab_impossible:
        if report.impossible_analyses:
            for name in report.impossible_analyses:
                result = next((r for r in report.feasibility_matrix if r.analysis_name == name), None)
                if result:
                    with st.expander(f"[NO VIABLE] {name}"):
                        st.markdown(f"**Motivo:** {result.reasoning}")
                        if result.missing_fields:
                            st.markdown(f"**Datos faltantes:** {', '.join(result.missing_fields)}")
                        if result.suggestions:
                            st.markdown("**Para habilitarlo:**")
                            for s in result.suggestions:
                                st.markdown(f"- {s}")
        else:
            st.success("¡Todos los análisis son posibles!")

    st.divider()

    # Supuestos sugeridos
    if report.suggested_assumptions:
        st.markdown("### Supuestos sugeridos")
        for s in report.suggested_assumptions:
            st.info(f"- {s}")

    st.divider()

    # Advertencias globales
    if report.warnings:
        st.markdown("### Advertencias globales")
        for w in report.warnings:
            st.warning(w)

    st.divider()

    # Botones de acción
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Generar prompt para MCP", type="primary", use_container_width=True):
            with st.spinner("Generando prompt personalizado..."):
                prompt = generate_mcp_prompt(report, st.session_state.project_name, _get_prompt_options())
                # Enriquecer prompt con observaciones de Claude (insights por tabla)
                api_key = st.session_state.api_key
                if api_key and st.session_state.use_llm_insights:
                    extra_context = llm_generate_prompt_context(report, api_key)
                    if extra_context:
                        prompt += (
                            "\n\n================================================================================\n"
                            "O. OBSERVACIONES DE CLAUDE SOBRE LOS DATOS REALES\n"
                            "================================================================================\n\n"
                            "Las siguientes observaciones fueron generadas por Claude al analizar una "
                            "muestra real de cada tabla. Usarlas como contexto adicional para el modelado.\n\n"
                            + extra_context
                        )
                st.session_state.generated_prompt = prompt
                st.session_state.step = 4
                st.rerun()

    with col2:
        diagnostic_txt = export_diagnostic_txt(report, st.session_state.project_name)
        st.download_button(
            "Descargar diagnóstico (.txt)",
            data=diagnostic_txt.encode("utf-8"),
            file_name=f"diagnostico_{_safe_filename(st.session_state.project_name)}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    with col3:
        profile_json = export_technical_profile_json(report, st.session_state.project_name)
        st.download_button(
            "Descargar perfil técnico (.json)",
            data=profile_json.encode("utf-8"),
            file_name=f"perfil_tecnico_{_safe_filename(st.session_state.project_name)}.json",
            mime="application/json",
            use_container_width=True,
        )


# ---------------------------------------------------------------------------
# PASO 4: PROMPT MCP
# ---------------------------------------------------------------------------

def render_step4():
    st.markdown('<div class="step-header">04 — Prompt para Claude + Power BI MCP</div>', unsafe_allow_html=True)

    prompt = st.session_state.generated_prompt
    report = st.session_state.diagnostic_report

    if not prompt:
        st.warning("No hay prompt generado. Volvé al Paso 3.")
        return

    # Resumen rápido
    if report:
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Posibles", len(report.possible_analyses))
        col2.metric("⚠️ Parciales", len(report.partial_analyses))
        col3.metric("No posibles", len(report.impossible_analyses))

    st.divider()

    st.markdown("### Prompt generado para Claude + Power BI MCP")
    st.markdown("""
    Este prompt está listo para copiar y pegar directamente en **Claude conectado a Power BI mediante MCP**.
    Incluye toda la información del diagnóstico, mapeo de columnas, análisis posibles y tareas concretas.
    """)

    # Mostrar prompt en text area
    prompt_lines = prompt.count("\n")
    height = min(600, max(300, prompt_lines * 15))

    st.text_area(
        "Prompt completo",
        value=prompt,
        height=600,
        key="prompt_display",
        label_visibility="collapsed",
    )

    st.caption(f"Longitud del prompt: {len(prompt):,} caracteres · {prompt_lines:,} líneas")

    st.divider()

    # Botones de descarga
    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button(
            "Descargar prompt (.txt)",
            data=prompt.encode("utf-8"),
            file_name=f"prompt_mcp_{_safe_filename(st.session_state.project_name)}.txt",
            mime="text/plain",
            use_container_width=True,
            type="primary",
        )

    with col2:
        if report:
            diagnostic_txt = export_diagnostic_txt(report, st.session_state.project_name)
            st.download_button(
                "Descargar diagnóstico (.txt)",
                data=diagnostic_txt.encode("utf-8"),
                file_name=f"diagnostico_{_safe_filename(st.session_state.project_name)}.txt",
                mime="text/plain",
                use_container_width=True,
            )

    with col3:
        if report:
            profile_json = export_technical_profile_json(report, st.session_state.project_name)
            st.download_button(
                "Descargar perfil técnico (.json)",
                data=profile_json.encode("utf-8"),
                file_name=f"perfil_tecnico_{_safe_filename(st.session_state.project_name)}.json",
                mime="application/json",
                use_container_width=True,
            )

    st.divider()

    # Instrucciones de uso
    st.markdown("### Cómo usar el prompt")
    st.markdown("""
    1. **Abrí Claude** en tu computadora o en el navegador.
    2. **Asegurate de que Power BI esté abierto** con el archivo .pbix correspondiente.
    3. **Conectá el MCP de Power BI** siguiendo las instrucciones de tu configuración.
    4. **Copiá el prompt** completo usando el botón de arriba o descargándolo como .txt.
    5. **Pegalo en el chat de Claude** y envialo.
    6. Claude va a **inspeccionar el modelo real** en Power BI, validar nombres de tablas y columnas,
       y proponerte un plan antes de crear Power Query, DAX, tablas auxiliares o visuales.
    """)

    st.info(
        "**Nota:** Si el prompt incluye observaciones de Claude (sección O), "
        "esas observaciones fueron generadas al analizar una muestra real de tus datos "
        "y le dan contexto adicional a Claude para el modelado."
    )

    # Botón para volver y regenerar
    st.divider()
    if st.button("Volver al Paso 3 y regenerar", use_container_width=False):
        st.session_state.step = 3
        st.rerun()


# ---------------------------------------------------------------------------
# HELPER — nombre de archivo seguro
# ---------------------------------------------------------------------------

def _safe_filename(name: str) -> str:
    """Convierte un nombre de proyecto en un string válido para nombre de archivo."""
    import re
    safe = re.sub(r"[^\w\-_. ]", "", name)
    safe = safe.strip().replace(" ", "_")
    return safe or "proyecto"


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    init_session_state()
    render_sidebar()

    step = st.session_state.step

    if step == 1:
        render_step1()
    elif step == 2:
        render_step2()
    elif step == 3:
        render_step3()
    elif step == 4:
        render_step4()


if __name__ == "__main__":
    main()
