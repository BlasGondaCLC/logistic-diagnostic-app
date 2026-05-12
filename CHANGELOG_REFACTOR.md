# Cambios realizados

## Archivos creados

- `models/table_profile.py`: dataclasses y propiedades necesarias para el pipeline.
- `templates/base_prompt_logistico_flexible.txt`: documento base conceptual usado como referencia.
- `CHANGELOG_REFACOTR.md`: resumen de cambios.

## Archivos editados

### `backend/prompt_generator.py`
Refactor completo. Ahora genera un prompt dinámico y flexible para Claude + Power BI MCP. Incluye protocolo de ejecución, bloques candidatos, matriz de factibilidad, estrategia de reporte, tareas Power Query/DAX y checklist.

### `config.py`
Se agregó `ANALYSIS_BLOCKS`, `REPORT_GENERATION_MODES` y `REPORT_FOCUS_OPTIONS`.

### `backend/feasibility_engine.py`
Se corrigió la evaluación de análisis que requieren combinar Stock + Movimientos y se agregaron condiciones parciales más logísticas.

### `app.py`
Se agregaron opciones de estrategia del prompt en el sidebar y se pasan al generador de prompt.

### `README.md`
Se agregó documentación de la versión flexible.

## Validación técnica realizada

- `python -m compileall -q .`
- Import de módulos principales.
- Prueba sintética de `run_feasibility_analysis()` y `generate_mcp_prompt()`.
