# Guía de Deploy — Streamlit Community Cloud

Seguí estos pasos para publicar la app y compartirla con tu compañero de trabajo.  
No requiere servidor propio ni conocimientos de infraestructura.

---

## Requisitos previos

- Cuenta en **GitHub** (gratuita) → https://github.com
- Cuenta en **Streamlit Community Cloud** (gratuita) → https://share.streamlit.io
- Tu **Anthropic API key** (`sk-ant-...`)

---

## Paso 1 — Crear repositorio en GitHub

1. Abrí https://github.com/new
2. Nombre del repo: `logistic-diagnostic-app` (o el que prefieras)
3. Dejalo en **Public** (necesario para el plan gratuito de Streamlit Cloud)
4. No inicialices con README ni .gitignore (ya los tenemos)
5. Hacé clic en **Create repository**

---

## Paso 2 — Subir el código

Abrí una terminal en la carpeta del proyecto y ejecutá:

```bash
git init
git add .
git commit -m "Initial commit — Diagnóstico Logístico"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/logistic-diagnostic-app.git
git push -u origin main
```

> Reemplazá `TU_USUARIO` con tu nombre de usuario de GitHub.

Si ya tenés el repo creado de antes, simplemente:
```bash
git add .
git commit -m "Actualización CLC theme + LLM analyzer"
git push
```

---

## Paso 3 — Conectar con Streamlit Community Cloud

1. Andá a https://share.streamlit.io y hacé login con tu cuenta de GitHub.
2. Hacé clic en **New app**.
3. Completá los campos:
   - **Repository:** `TU_USUARIO/logistic-diagnostic-app`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Hacé clic en **Advanced settings** (importante para el siguiente paso).

---

## Paso 4 — Configurar la API key (secreto)

En la sección **Secrets** del panel Advanced settings, pegá esto:

```toml
ANTHROPIC_API_KEY = "sk-ant-TU_KEY_REAL_AQUI"
```

> Reemplazá con tu key real. Este valor queda cifrado en Streamlit Cloud  
> y nunca aparece en el repositorio.

---

## Paso 5 — Deploy

1. Hacé clic en **Deploy!**
2. Streamlit Cloud instala las dependencias de `requirements.txt` automáticamente.
3. En 1-3 minutos la app estará disponible en una URL del tipo:  
   `https://TU_USUARIO-logistic-diagnostic-app-app-XXXXX.streamlit.app`

---

## Paso 6 — Compartir con tu compañero

Simplemente compartí la URL pública. No necesita cuenta de GitHub ni de Streamlit.  
Solo necesita el link y puede usarla desde cualquier navegador.

Si querés restringir el acceso solo a personas de tu organización, podés activar  
**Viewer authentication** en la configuración de la app en Streamlit Cloud  
(requiere que tu compañero tenga una cuenta de GitHub o Google).

---

## Actualizaciones futuras

Cada vez que hagas cambios al código, simplemente:

```bash
git add .
git commit -m "Descripción del cambio"
git push
```

Streamlit Cloud detecta el push automáticamente y redespliega la app en ~1 minuto.

---

## Resolución de problemas comunes

| Problema | Solución |
|----------|----------|
| `ModuleNotFoundError` | Verificar que el paquete esté en `requirements.txt` |
| `API key not found` | Verificar el secreto en App settings → Secrets |
| La app tarda en cargar | Normal en el primer acceso del día (cold start ~30 seg) |
| Error de encoding en CSV | La app detecta encoding automáticamente con `chardet` |
| Excel con macros no carga | Guardar como `.xlsx` estándar sin macros |

---

## Estructura de archivos que se suben a GitHub

```
logistic_diagnostic_app/
├── app.py
├── config.py
├── requirements.txt
├── .gitignore
├── README.md
├── DEPLOY.md
├── .streamlit/
│   ├── config.toml          ← tema CLC (se sube)
│   └── secrets.toml.example ← template sin keys (se sube)
├── models/
│   ├── __init__.py
│   └── table_profile.py
└── backend/
    ├── __init__.py
    ├── file_loader.py
    ├── schema_profiler.py
    ├── semantic_column_detector.py
    ├── table_classifier.py
    ├── data_quality_engine.py
    ├── feasibility_engine.py
    ├── llm_analyzer.py
    ├── prompt_generator.py
    └── export_utils.py
```

> **NO se suben:** `.env`, `.streamlit/secrets.toml`, archivos Excel/CSV de prueba, `venv/`
> (todos están en `.gitignore`)
