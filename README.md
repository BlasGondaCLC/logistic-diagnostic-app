# Diagnóstico Logístico → Power BI MCP

Asistente de diagnóstico logístico previo a Power BI.
Cargá archivos Excel/CSV, analizá la estructura automáticamente y generá un prompt personalizado para Claude conectado a Power BI mediante MCP.

---

## Instalación rápida

### Requisitos

- Python 3.10 o superior
- pip

### Pasos

```bash
# 1. Clonar o descomprimir el proyecto
cd logistic_diagnostic_app

# 2. Crear entorno virtual (recomendado)
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Mac/Linux

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar API key
copy .env.example .env
# Editar .env y poner tu Anthropic API key

# 5. Correr la app
streamlit run app.py
```

La app abre en `http://localhost:8501` en el navegador.

---

## Flujo de uso

### Paso 1 — Carga de archivos
- Cargá uno o varios archivos Excel (.xlsx, .xls) o CSV (.csv).
- En Excel con múltiples hojas, cada hoja se procesa como tabla separada.
- La app detecta automáticamente separador, encoding y formato de fechas.

### Paso 2 — Revisión y corrección
- Revisás la clasificación automática de cada tabla (Pedidos, Stock, Recepciones, etc.).
- Podés corregir el tipo de tabla si la clasificación no es correcta.
- Podés ajustar el mapeo de columnas (qué columna corresponde a SKU, Fecha, Cantidad, etc.).
- Podés excluir tablas del análisis si no son relevantes.

### Paso 3 — Diagnóstico completo
- Ves la calidad de datos de cada tabla: nulos, fechas inválidas, negativos, duplicados.
- Ves la matriz de factibilidad: qué análisis son posibles, parciales o imposibles.
- Podés descargar el diagnóstico como TXT y el perfil técnico como JSON.

### Paso 4 — Prompt para MCP
- La app genera un prompt completo personalizado para Claude + Power BI MCP.
- El prompt incluye: contexto, archivos, mapeo, análisis posibles, Power Query, DAX, visuales y checklist.
- Descargás el prompt como TXT y lo pegás en Claude conectado a Power BI.

---

## Configuración de API key

La app usa Claude (claude-haiku) para detectar columnas con nombres ambiguos.
Sin API key, usa solo heurísticas (funciona bien en la mayoría de los casos).

Opciones para configurar la key:
1. **Archivo .env** (recomendado): crear `.env` con `ANTHROPIC_API_KEY=sk-ant-...`
2. **Desde la UI**: ingresar la key en el campo del sidebar al correr la app.

---

## Estructura del proyecto

```
logistic_diagnostic_app/
├── app.py                          ← Streamlit principal (4 pasos)
├── config.py                       ← Patrones de detección y reglas
├── requirements.txt
├── .env.example                    ← Template de configuración
├── README.md
├── models/
│   ├── __init__.py
│   └── table_profile.py            ← Dataclasses (ColumnProfile, TableProfile, etc.)
└── backend/
    ├── __init__.py
    ├── file_loader.py              ← Carga Excel/CSV con tolerancia a errores
    ├── schema_profiler.py          ← Perfila cada tabla
    ├── semantic_column_detector.py ← Detecta semántica de columnas (heurísticas + LLM)
    ├── table_classifier.py         ← Clasifica tipo de tabla
    ├── data_quality_engine.py      ← Calidad: nulos, fechas, duplicados, negativos
    ├── feasibility_engine.py       ← Motor de factibilidad por análisis
    ├── prompt_generator.py         ← Genera prompt final para MCP
    └── export_utils.py             ← Exporta TXT y JSON
```

---

## Cómo extender el motor de factibilidad

### Agregar un nuevo análisis

Editá `config.py`, sección `FEASIBILITY_RULES`. Agregá una nueva entrada:

```python
"Nombre del Análisis": {
    "description": "Qué hace este análisis.",
    "required_tables": ["Pedidos"],       # Tipos de tabla necesarios
    "required_fields": ["SKU", "Fecha"],  # Campos semánticos mínimos
    "partial_if": [
        "Falta columna de Cliente.",      # Condiciones que lo hacen parcial
    ],
    "impossible_if": [
        "No existe tabla de Pedidos.",    # Condiciones que lo hacen imposible
    ],
    "notes": "Texto adicional para el usuario.",
},
```

No necesitás tocar ningún otro archivo. El motor lo detecta automáticamente.

### Agregar nuevos patrones de columnas

Editá `config.py`, sección `COLUMN_SEMANTIC_PATTERNS`. Agregá variantes al tipo existente:

```python
"SKU": [
    "sku", "codarticulo", ...,
    "nuevavariante",      # ← agregar acá
],
```

### Agregar un nuevo tipo de tabla

Editá `config.py`, sección `TABLE_TYPE_INDICATORS`. Agregá un nuevo tipo:

```python
"Nuevo Tipo": {
    "required": ["SKU", "Fecha"],
    "optional": ["Cantidad", "Documento"],
    "disqualifiers": ["Cliente"],
    "min_required": 2,
},
```

---

## Formatos de entrada soportados

| Formato | Notas |
|---------|-------|
| .xlsx | Excel moderno. Múltiples hojas. |
| .xls | Excel legacy. |
| .csv (;) | Separador punto y coma (común en Argentina/LATAM). |
| .csv (,) | Separador coma (estándar internacional). |
| Decimal , | Formato 1.234,56 → se convierte automáticamente. |
| Decimal . | Formato 1,234.56 → se convierte automáticamente. |
| Fecha DD/MM/YYYY | Formato local. |
| Fecha YYYY-MM-DD | ISO. |

---

## Output del análisis

### Diagnóstico (.txt)
- Resumen ejecutivo.
- Lista de archivos con tipo, filas, fechas y calidad.
- Mapeo de columnas original → estándar.
- Matriz de factibilidad completa.
- Supuestos sugeridos.

### Perfil técnico (.json)
- Todos los metadatos del análisis en formato JSON estructurado.
- Útil para versionado, auditoría o integración con otras herramientas.

### Prompt para MCP (.txt)
- Prompt completo para pegar en Claude + Power BI MCP.
- Incluye: contexto, data, mapeo, análisis, Power Query, DAX, visuales y checklist.

---

## Ejemplo de output esperado

**Resumen ejecutivo:**
```
Se cargaron 4 tabla(s) con un total de 128,450 filas.
Tipos detectados: Stock, Recepciones, Pedidos, Maestro de Productos.
Análisis viables: 9/14 posibles, 3 parciales, 2 no posibles.
Viabilidad general del diagnóstico: 75%.
```

**Matriz de factibilidad:**
```
✅ Posible      Información Recibida
✅ Posible      Perfil de Recepciones
✅ Posible      Evolución de Recepciones
⚠️ Parcial     Balance de Masa (falta validar ajustes)
⚠️ Parcial     Análisis de Proveedores (falta campo Proveedor)
❌ No posible  Devoluciones (no existe tabla de devoluciones)
❌ No posible  Transferencias (no existe tabla de transferencias)
```

---

## Notas de versión

**v1.0.0**
- Detección automática de semántica con heurísticas + Claude API.
- Motor de factibilidad para 14 tipos de análisis logístico.
- Calidad de datos: nulos, fechas, negativos, duplicados, cross-table.
- Prompt generator completo para Claude + Power BI MCP.
- Exportación a TXT y JSON.
- UI Streamlit en 4 pasos.
- Soporte Excel (.xlsx, .xls) y CSV con auto-detección de formato.

---

## Cambios de la versión refactor flexible

Esta versión incorpora el enfoque del documento base `templates/base_prompt_logistico_flexible.txt` como lógica conceptual para el prompt MCP.

### Cambios principales

- Se agregó `models/table_profile.py` con las dataclasses necesarias para que el pipeline funcione de punta a punta.
- Se refactorizó `backend/prompt_generator.py` para generar un prompt flexible y consultivo, no un layout rígido de Power BI.
- Se agregó en `config.py` la capa `ANALYSIS_BLOCKS`, con objetivos, preguntas de negocio, KPIs sugeridos, visuales recomendados y visuales alternativos por bloque de análisis.
- Se mejoró `backend/feasibility_engine.py` para evaluar mejor análisis que combinan stock + movimientos, como Balance de Masa y Edad de Stock.
- Se agregaron controles en `app.py` para definir:
  - Nivel de detalle del prompt: Ejecutivo, Operativo o Técnico completo.
  - Foco del reporte: diagnóstico general, pedidos/picking, stock/cobertura, recepciones, balance de masa o calidad de datos.
  - Si Claude debe proponer un plan antes de ejecutar cambios.
  - Si Claude puede crear visuales directamente o solo proponerlos.

### Nueva lógica del prompt

El prompt final ya no le pide a Claude que cree siempre las mismas páginas. Ahora genera bloques candidatos de análisis. Para cada bloque indica:

- Estado: posible, parcial o no posible.
- Fuentes detectadas.
- Campos encontrados.
- Campos faltantes.
- Preguntas que puede responder.
- KPIs sugeridos.
- Visuales recomendados.
- Visuales alternativos.
- Limitaciones.
- Instrucciones específicas para Claude.

Claude debe inspeccionar primero el modelo real mediante MCP, validar nombres reales de tablas y columnas, proponer un plan de reporte y recién después crear Power Query, DAX, tablas auxiliares o visuales.
