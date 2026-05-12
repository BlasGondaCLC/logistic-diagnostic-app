"""
config.py
=========
Configuración central de la aplicación.
Contiene todos los patrones de detección de columnas, tipos de tabla,
reglas de factibilidad y constantes.

Para extender el motor de detección, modificá las listas de este archivo.
"""

# ---------------------------------------------------------------------------
# PATRONES SEMÁNTICOS DE COLUMNAS
# ---------------------------------------------------------------------------
# Formato: { "SemanticType": ["patron1", "patron2", ...] }
# Los patrones se comparan contra el nombre de columna normalizado
# (lowercase, sin espacios, sin guiones, sin underscores).

COLUMN_SEMANTIC_PATTERNS: dict = {
    "SKU": [
        "sku", "codArticulo", "codarticulo", "cod_articulo", "codigoproducto",
        "codigo_producto", "articulo", "item", "producto", "material",
        "codproducto", "cod_producto", "idproducto", "productoid",
        "codigoarticulo", "codigomaterial", "itemcode", "itemid",
        "productcode", "part", "partno", "partnumber", "referencia",
        "ref", "codref", "coditem", "iditem", "idsku",
    ],
    "Descripcion": [
        "descripcion", "descripcionproducto", "descripcionarticulo",
        "descproducto", "descarticulo", "nombre", "nombreproducto",
        "nombrematerial", "description", "productname", "productdesc",
        "itemdesc", "itemdescription", "detalle", "detalleproducto",
        "nombremercaderia", "mercaderia",
    ],
    "Fecha": [
        "fecha", "fechapedido", "fechadocumento", "fechafactura",
        "fechamovimiento", "fechaingreso", "fechaegreso", "fechaemision",
        "fechaentrega", "fechaenvio", "fecharegistro", "date", "createddate",
        "orderdate", "invoicedate", "movdate", "fecmov", "fec_mov",
        "fechacreacion", "fecha_creacion", "fechamod", "fecha_modificacion",
        "transactiondate", "docdate", "fechaoperacion",
    ],
    "Cantidad": [
        "cantidad", "cantidades", "cant", "unidades", "qty", "quantity",
        "movimiento", "monto_unidades", "cantidadunidades", "unidadesstock",
        "cantstock", "bultos", "cajas", "items", "units",
        "cantidadpedida", "cantidadrecibida", "cantidadpreparada",
        "cantidadtransferida", "cantidaddevuelta", "cantidadajuste",
    ],
    "Documento": [
        "documento", "nrodocumento", "numerodocumento", "ndocumento",
        "factura", "nrofactura", "numerofactura", "nfactura",
        "pedido", "nropedido", "numeropedido", "npedido", "idpedido",
        "remito", "nroremito", "numeroremito", "nremito",
        "orden", "ordencompra", "nroorden", "numeroorden",
        "docid", "id", "transactionid", "invoiceid", "orderid",
        "referencia", "nroreferenciadoc", "comprobante",
        "codoperacion", "operacion",
    ],
    "Cliente": [
        "cliente", "clientes", "codcliente", "codigocliente", "idcliente",
        "customer", "customername", "customerid", "razonsocial",
        "razon_social", "nombrecli", "nombrecliente", "cuentacliente",
        "cliente_id", "numcliente", "codcli",
    ],
    "Proveedor": [
        "proveedor", "proveedores", "codproveedor", "codigoproveedor",
        "idproveedor", "vendor", "vendorname", "vendorid", "supplier",
        "suppliername", "supplierid", "nombreproveedor", "nomproveedor",
        "codpro", "cuentaproveedor",
    ],
    "Deposito": [
        "deposito", "depositos", "almacen", "almacenes", "sucursal",
        "sucursales", "warehouse", "warehouseid", "warehousename",
        "ubicacion", "location", "codalm", "coddeposito",
        "iddeposito", "codsucursal", "tienda", "local", "sede",
        "planta", "centro", "hub",
    ],
    "Origen": [
        "origen", "depositoorigen", "almacenorigen", "sucursalorigen",
        "from", "from_location", "origenlocation", "origendep",
        "warehousefrom", "almacenorig", "deposito_origen",
    ],
    "Destino": [
        "destino", "depositodestino", "almacendestino", "sucursaldestino",
        "to", "to_location", "destinolocation", "destinodep",
        "warehouseto", "almacendest", "deposito_destino",
    ],
    "Familia": [
        "familia", "familias", "categoria", "categorias", "grupo",
        "grupos", "rubro", "rubros", "segmento", "segmentos",
        "linea", "lineas", "tipo", "subtipo", "clasificacion",
        "division", "departamento", "seccion", "category",
        "groupname", "familyname",
    ],
    "Subfamilia": [
        "subfamilia", "subfamilias", "subcategoria", "subcategorias",
        "subgrupo", "subgrupos", "subrubro", "sublínea",
        "subcategory", "subgroup", "subfamilyname",
    ],
    "TipoMovimiento": [
        "tipomovimiento", "tipo_movimiento", "movtype", "movementtype",
        "tipooperacion", "tipo_operacion", "operacion", "operationtype",
        "tipotransaccion", "tiporegistro", "clase", "clasemov",
        "tipoajuste", "motivoajuste", "signo",
    ],
    "Stock": [
        "stock", "stockactual", "stockfinal", "stockinicial",
        "stockdisponible", "existencia", "existencias",
        "inventario", "saldostock", "saldo", "cantidadstock",
        "stockfisico", "stocklogico", "onhand", "available",
    ],
    "Costo": [
        "costo", "costos", "costopromedio", "costounitario",
        "precio", "preciounitario", "preciocompra", "precioproveedor",
        "cost", "unitcost", "avgcost", "costorepuesicion",
    ],
    "Valor": [
        "valor", "valores", "importe", "importes", "total",
        "totales", "monto", "montos", "amount", "totalamount",
        "valorstock", "valortotal", "subtotal",
    ],
}

# ---------------------------------------------------------------------------
# INDICADORES POR TIPO DE TABLA
# ---------------------------------------------------------------------------
# Para cada tipo de tabla: campos requeridos (score alto) y opcionales (score bajo)

TABLE_TYPE_INDICATORS: dict = {
    "Maestro de Productos": {
        "required": ["SKU", "Descripcion"],
        "optional": ["Familia", "Subfamilia", "Costo", "Valor"],
        "disqualifiers": ["Fecha", "Documento", "Cliente"],  # si tiene estos, probablemente no es maestro
        "min_required": 2,
    },
    "Stock": {
        "required": ["SKU", "Stock"],
        "optional": ["Deposito", "Fecha", "Familia", "Valor"],
        "disqualifiers": [],
        "min_required": 2,
    },
    "Recepciones": {
        "required": ["SKU", "Cantidad", "Fecha"],
        "optional": ["Documento", "Proveedor", "Deposito", "Familia"],
        "disqualifiers": ["Cliente"],
        "min_required": 2,
    },
    "Pedidos": {
        "required": ["SKU", "Cantidad", "Fecha"],
        "optional": ["Documento", "Cliente", "Deposito", "Familia"],
        "disqualifiers": ["Proveedor"],
        "min_required": 2,
    },
    "Preparaciones": {
        "required": ["SKU", "Cantidad", "Fecha"],
        "optional": ["Documento", "Cliente", "Deposito"],
        "disqualifiers": [],
        "min_required": 2,
    },
    "Transferencias": {
        "required": ["SKU", "Cantidad"],
        "optional": ["Origen", "Destino", "Deposito", "Fecha", "Documento"],
        "must_have_any": ["Origen", "Destino"],  # al menos uno de estos
        "disqualifiers": [],
        "min_required": 2,
    },
    "Devoluciones Cliente": {
        "required": ["SKU", "Cantidad"],
        "optional": ["Cliente", "Fecha", "Documento", "Familia"],
        "disqualifiers": ["Proveedor"],
        "min_required": 2,
    },
    "Devoluciones Proveedor": {
        "required": ["SKU", "Cantidad"],
        "optional": ["Proveedor", "Fecha", "Documento", "Familia"],
        "disqualifiers": ["Cliente"],
        "min_required": 2,
    },
    "Ajustes": {
        "required": ["SKU", "Cantidad"],
        "optional": ["TipoMovimiento", "Fecha", "Deposito", "Documento"],
        "disqualifiers": [],
        "min_required": 2,
    },
    "Clientes": {
        "required": ["Cliente"],
        "optional": ["Documento", "Deposito"],
        "disqualifiers": ["SKU", "Cantidad", "Fecha"],
        "min_required": 1,
    },
    "Proveedores": {
        "required": ["Proveedor"],
        "optional": ["Documento"],
        "disqualifiers": ["SKU", "Cantidad", "Fecha"],
        "min_required": 1,
    },
    "Depósitos": {
        "required": ["Deposito"],
        "optional": [],
        "disqualifiers": ["SKU", "Cantidad", "Fecha"],
        "min_required": 1,
    },
}

# ---------------------------------------------------------------------------
# REGLAS DE FACTIBILIDAD
# ---------------------------------------------------------------------------
# Para cada análisis posible, se definen:
#   - required_any: necesita al menos uno de estos conjuntos de campos
#   - required_for_full: campos que hacen el análisis "completo" (vs "básico")
#   - required_tables: tipos de tabla que deben existir
#   - description: qué hace este análisis
#   - partial_condition: condición que lo hace parcial

FEASIBILITY_RULES: dict = {
    "Información Recibida": {
        "description": "Resumen de archivos cargados, cobertura de datos y calidad general.",
        "required_tables": [],  # siempre posible si hay al menos un archivo
        "required_fields": [],
        "partial_if": [],
        "impossible_if": [],
        "notes": "Siempre posible con al menos un archivo cargado.",
    },
    "Balance de Masa": {
        "description": "Reconstrucción del stock final a partir del stock inicial + movimientos.",
        "required_tables": ["Stock"],
        "required_fields": ["SKU", "Cantidad", "Fecha"],
        "requires_stock": True,
        "partial_if": [
            "Faltan tablas de ajustes o transferencias.",
            "No se puede identificar signo de algunos movimientos.",
        ],
        "impossible_if": [
            "No existe tabla de stock inicial ni final.",
        ],
        "notes": "Requiere stock + movimientos fechados con signo o tipo.",
    },
    "Evolución de Stock": {
        "description": "Cómo evoluciona el inventario en el tiempo.",
        "required_tables": ["Stock"],
        "required_fields": ["SKU", "Stock"],
        "partial_if": [
            "El stock es solo snapshot actual (sin historial temporal).",
        ],
        "impossible_if": [
            "No existe tabla de stock.",
        ],
        "notes": "Posible completo si hay stock histórico por fecha. Parcial con stock actual.",
    },
    "Perfil de Recepciones": {
        "description": "Volumen, frecuencia y distribución de ingresos de mercadería.",
        "required_tables": ["Recepciones"],
        "required_fields": ["SKU", "Cantidad", "Fecha"],
        "partial_if": [
            "Falta columna de Documento (no se pueden calcular líneas por documento).",
            "Falta columna de Proveedor.",
        ],
        "impossible_if": [
            "No existe tabla de recepciones.",
        ],
        "notes": "Básico con SKU+Cantidad+Fecha. Completo con Documento+Proveedor+Familia.",
    },
    "Evolución de Recepciones": {
        "description": "Tendencia mensual/diaria de recepciones.",
        "required_tables": ["Recepciones"],
        "required_fields": ["Fecha", "Cantidad"],
        "partial_if": [
            "Falta columna de Familia para segmentación.",
        ],
        "impossible_if": [
            "No existe tabla de recepciones.",
            "No existen fechas en recepciones.",
        ],
        "notes": "Requiere recepciones con fechas.",
    },
    "Análisis de Proveedores": {
        "description": "Volumen, variedad y frecuencia por proveedor.",
        "required_tables": ["Recepciones"],
        "required_fields": ["Proveedor", "SKU", "Cantidad", "Fecha"],
        "partial_if": [
            "No hay campo Proveedor en recepciones (análisis solo por SKU).",
        ],
        "impossible_if": [
            "No existe tabla de recepciones.",
        ],
        "notes": "Requiere columna Proveedor en recepciones.",
    },
    "Perfil de Pedidos": {
        "description": "Volumen, frecuencia y distribución de pedidos/egresos.",
        "required_tables": ["Pedidos", "Preparaciones"],
        "required_fields": ["SKU", "Cantidad", "Fecha"],
        "partial_if": [
            "Falta columna de Documento.",
            "Falta columna de Cliente.",
        ],
        "impossible_if": [
            "No existe tabla de pedidos ni preparaciones.",
        ],
        "notes": "Básico con SKU+Cantidad+Fecha. Completo con Documento+Cliente+Familia.",
    },
    "Evolución de Pedidos": {
        "description": "Tendencia mensual/diaria de pedidos.",
        "required_tables": ["Pedidos", "Preparaciones"],
        "required_fields": ["Fecha", "Cantidad"],
        "partial_if": [
            "Falta columna de Familia para segmentación.",
        ],
        "impossible_if": [
            "No existe tabla de pedidos ni preparaciones.",
            "No existen fechas en pedidos.",
        ],
        "notes": "Requiere pedidos con fechas.",
    },
    "Análisis de Clientes": {
        "description": "Volumen, variedad y frecuencia por cliente.",
        "required_tables": ["Pedidos", "Preparaciones"],
        "required_fields": ["Cliente", "SKU", "Cantidad", "Fecha"],
        "partial_if": [
            "No hay campo Cliente en pedidos.",
        ],
        "impossible_if": [
            "No existe tabla de pedidos ni preparaciones.",
        ],
        "notes": "Requiere columna Cliente en pedidos/preparaciones.",
    },
    "Pedidos Global (con Transferencias)": {
        "description": "Carga operativa total sumando pedidos y transferencias.",
        "required_tables": ["Pedidos"],
        "required_fields": ["Cantidad", "Fecha"],
        "partial_if": [
            "No existe tabla de transferencias (solo pedidos).",
        ],
        "impossible_if": [
            "No existe tabla de pedidos ni transferencias.",
        ],
        "notes": "Completo con Pedidos + Transferencias. Parcial solo con uno.",
    },
    "Transferencias": {
        "description": "Flujo de mercadería entre depósitos/sucursales.",
        "required_tables": ["Transferencias"],
        "required_fields": ["SKU", "Cantidad", "Fecha"],
        "partial_if": [
            "Existen depósitos pero no Origen/Destino separados.",
        ],
        "impossible_if": [
            "No existe tabla de transferencias.",
        ],
        "notes": "Completo con Origen+Destino+SKU+Cantidad+Fecha.",
    },
    "Devoluciones": {
        "description": "Tasa y distribución de devoluciones de clientes y/o a proveedores.",
        "required_tables": ["Devoluciones Cliente", "Devoluciones Proveedor"],
        "required_fields": ["SKU", "Cantidad", "Fecha"],
        "partial_if": [
            "Solo hay un tipo de devolución (cliente o proveedor, no ambas).",
            "No hay base comparativa para calcular tasa.",
        ],
        "impossible_if": [
            "No existe tabla de devoluciones de ningún tipo.",
        ],
        "notes": "Tasa requiere base comparativa (pedidos o recepciones).",
    },
    "Ajustes": {
        "description": "Impacto de ajustes manuales de inventario.",
        "required_tables": ["Ajustes"],
        "required_fields": ["SKU", "Cantidad", "Fecha"],
        "partial_if": [
            "No hay campo de motivo de ajuste.",
            "No se puede distinguir ajuste positivo de negativo.",
        ],
        "impossible_if": [
            "No existe tabla de ajustes.",
        ],
        "notes": "Mejora con TipoMovimiento o columna de signo.",
    },
    "Edad de Stock": {
        "description": "Días de cobertura por SKU según stock actual y consumo histórico.",
        "required_tables": ["Stock"],
        "required_fields": ["SKU", "Stock", "Cantidad"],
        "requires_stock_and_movement": True,
        "partial_if": [
            "El consumo histórico es muy corto (menos de 30 días).",
        ],
        "impossible_if": [
            "No existe tabla de stock.",
            "No existe tabla de pedidos/preparaciones para calcular consumo.",
        ],
        "notes": "Requiere stock actual + consumo histórico (pedidos/preparaciones).",
    },
    "Pareto de Preparación / Picking": {
        "description": "Concentración de actividad por SKU, cliente o proveedor.",
        "required_tables": ["Pedidos", "Preparaciones", "Recepciones"],
        "required_fields": ["SKU", "Cantidad"],
        "partial_if": [
            "Solo hay unidades (sin Documento, no se pueden calcular líneas).",
            "Falta columna de Familia para segmentación ABC.",
        ],
        "impossible_if": [
            "No existe SKU en ninguna tabla de movimientos.",
        ],
        "notes": "Por líneas requiere Documento+SKU. Por unidades solo necesita SKU+Cantidad.",
    },
}

# ---------------------------------------------------------------------------
# CONSTANTES GENERALES
# ---------------------------------------------------------------------------

# Umbral de confianza mínima para clasificación automática (sin pasar por LLM)
HEURISTIC_CONFIDENCE_THRESHOLD = 0.60

# Umbral bajo el cual se llama al LLM para enriquecer la detección
LLM_ENRICHMENT_THRESHOLD = 0.45

# Máximo de valores de muestra a mostrar por columna
MAX_SAMPLE_VALUES = 5

# Máximo de filas a cargar para el preview (no afecta el análisis completo)
PREVIEW_MAX_ROWS = 1000

# Umbral de nulos para marcar como advertencia
NULL_WARNING_THRESHOLD = 0.10   # 10%
NULL_ERROR_THRESHOLD = 0.50     # 50%

# Modelos de Claude a usar
LLM_MODEL_FAST = "claude-haiku-4-5-20251001"      # Para detección de columnas
LLM_MODEL_ANALYSIS = "claude-sonnet-4-6"           # Para análisis semántico complejo

# Tipos de archivo aceptados
ACCEPTED_FILE_TYPES = [".xlsx", ".xls", ".csv"]

# Todos los tipos de tabla posibles (para selector manual)
ALL_TABLE_TYPES = [
    "Maestro de Productos",
    "Stock",
    "Recepciones",
    "Pedidos",
    "Preparaciones",
    "Transferencias",
    "Devoluciones Cliente",
    "Devoluciones Proveedor",
    "Ajustes",
    "Clientes",
    "Proveedores",
    "Depósitos",
    "Otro",
]

# Todos los tipos semánticos de columnas (para selector manual)
ALL_SEMANTIC_TYPES = [
    "SKU",
    "Descripcion",
    "Fecha",
    "Cantidad",
    "Documento",
    "Cliente",
    "Proveedor",
    "Deposito",
    "Origen",
    "Destino",
    "Familia",
    "Subfamilia",
    "TipoMovimiento",
    "Stock",
    "Costo",
    "Valor",
    "Desconocido",
]

# ---------------------------------------------------------------------------
# BLOQUES FLEXIBLES DE ANÁLISIS PARA EL PROMPT MCP
# ---------------------------------------------------------------------------
# Esta capa NO decide la factibilidad. La factibilidad se calcula en
# FEASIBILITY_RULES/feasibility_engine. Estos bloques enriquecen el prompt final
# con preguntas de negocio, KPIs y opciones visuales según cada análisis.

ANALYSIS_BLOCKS: dict = {
    "Información Recibida": {
        "objective": "Entender qué archivos se cargaron, qué cubren y qué tan confiables son.",
        "business_questions": [
            "Qué información fue recibida y qué período cubre.",
            "Qué tablas parecen movimientos, maestros o snapshots.",
            "Qué campos son confiables y cuáles requieren limpieza o revisión.",
            "Qué análisis quedan habilitados, limitados o descartados.",
        ],
        "recommended_kpis": [
            "Cantidad de archivos/tablas", "Filas", "Columnas", "Rango de fechas",
            "SKUs detectados", "Documentos", "Clientes", "Proveedores", "Depósitos",
            "Errores y advertencias de calidad",
        ],
        "visual_options": [
            "Tabla resumen por archivo", "Matriz de campos encontrados vs requeridos",
            "Semáforo de calidad", "Tarjetas de cobertura", "Tabla de advertencias",
        ],
        "alternative_visuals": ["Página técnica de diagnóstico", "Resumen ejecutivo textual"],
    },
    "Balance de Masa": {
        "objective": "Evaluar si el stock final puede reconstruirse a partir del stock inicial y movimientos.",
        "business_questions": [
            "El balance es posible, parcial o no posible.",
            "Qué movimientos entran al cálculo y cuáles faltan.",
            "Qué supuestos se requieren para asignar signos.",
            "Dónde se concentran las diferencias por SKU, familia o depósito.",
        ],
        "recommended_kpis": [
            "Stock inicial", "Ingresos", "Egresos", "Ajustes", "Stock final calculado",
            "Stock final real", "Diferencia absoluta", "% diferencia vs stock", "% diferencia vs movimientos",
        ],
        "visual_options": [
            "Gráfico puente", "Ranking de diferencias por SKU", "Dispersión stock real vs calculado",
            "Tabla de diferencias", "Semáforo de confiabilidad",
        ],
        "alternative_visuals": ["Resumen de imposibilidad si falta stock o signo", "Tabla de supuestos"],
    },
    "Evolución de Stock": {
        "objective": "Entender comportamiento del inventario en el tiempo o validar si solo existe un snapshot.",
        "business_questions": [
            "Cómo evoluciona el stock por fecha, SKU, familia o depósito.",
            "Qué SKUs concentran inventario o presentan picos/quiebres.",
            "Si el stock es histórico o solo stock actual.",
        ],
        "recommended_kpis": ["Stock total", "Stock promedio", "Stock mínimo", "Stock máximo", "SKUs con stock", "Días con stock"],
        "visual_options": ["Línea/área temporal", "Ranking de SKUs", "Tabla min/prom/max", "Heatmap por fecha y familia"],
        "alternative_visuals": ["Análisis snapshot si no hay fecha", "Distribución de stock actual"],
    },
    "Perfil de Recepciones": {
        "objective": "Entender volumen, frecuencia, variedad y complejidad de ingresos.",
        "business_questions": [
            "Cuánto se recibe y con qué frecuencia.",
            "Qué días/meses tienen mayor carga.",
            "Qué SKUs, familias o proveedores concentran ingresos.",
            "Qué percentil usar para dimensionar capacidad.",
        ],
        "recommended_kpis": [
            "Unidades recibidas", "Documentos de recepción", "Líneas de recepción", "SKUs recibidos",
            "P90 unidades diarias", "P90 líneas diarias", "Proveedores activos",
        ],
        "visual_options": ["Serie diaria/mensual", "Histograma por documento", "Pareto de SKUs", "Ranking de proveedores", "P90 diario"],
        "alternative_visuals": ["Tabla por SKU si no hay proveedor", "Barras por familia si existe familia"],
    },
    "Evolución de Recepciones": {
        "objective": "Analizar tendencia temporal de ingresos y su composición.",
        "business_questions": [
            "Cómo cambia el volumen recibido en el tiempo.",
            "Qué familias/SKUs/proveedores explican la evolución.",
            "Si hay estacionalidad o picos atípicos.",
        ],
        "recommended_kpis": ["Unidades por mes", "SKUs activos", "Documentos por mes", "Proveedores activos"],
        "visual_options": ["Barras mensuales", "Línea de SKUs activos", "Barras apiladas por familia", "Ranking mensual"],
        "alternative_visuals": ["Tabla temporal si hay pocos meses", "Serie diaria si el período es corto"],
    },
    "Análisis de Proveedores": {
        "objective": "Medir concentración, variedad y frecuencia de ingresos por proveedor.",
        "business_questions": [
            "Qué proveedores explican mayor volumen.",
            "Qué proveedores generan mayor variedad de SKUs.",
            "Qué proveedores generan más frecuencia o documentos.",
        ],
        "recommended_kpis": ["Unidades", "SKUs", "Documentos", "Fechas activas", "Participación %"],
        "visual_options": ["Bubble chart volumen-variedad-frecuencia", "Ranking", "Pareto", "Tabla resumen"],
        "alternative_visuals": ["Análisis por SKU si falta proveedor"],
    },
    "Perfil de Pedidos": {
        "objective": "Entender demanda, egresos y carga operativa de preparación.",
        "business_questions": [
            "Cuánto se pide/prepara y con qué frecuencia.",
            "Cuántas líneas y documentos se procesan.",
            "Si predominan muchos pedidos chicos o pocos pedidos grandes.",
            "Qué SKUs generan mayor carga de picking.",
        ],
        "recommended_kpis": [
            "Unidades pedidas", "Documentos", "Líneas", "SKUs", "P90 unidades diarias",
            "P90 líneas diarias", "Unidades por línea", "Líneas por documento",
        ],
        "visual_options": ["Serie diaria", "Histograma de líneas por documento", "Histograma de unidades por línea", "Pareto de SKUs", "P90 diario"],
        "alternative_visuals": ["Análisis por documento si falta cliente", "Ranking por familia si existe familia"],
    },
    "Evolución de Pedidos": {
        "objective": "Analizar tendencia temporal de demanda/egresos.",
        "business_questions": [
            "Cómo evoluciona la demanda por día o mes.",
            "Qué SKUs/familias/clientes explican cambios.",
            "Qué nivel de carga sirve para dimensionamiento operativo.",
        ],
        "recommended_kpis": ["Unidades por período", "Líneas por período", "Documentos", "SKUs activos", "P90 carga diaria"],
        "visual_options": ["Barras mensuales", "Serie diaria", "Línea de SKUs activos", "Barras apiladas por familia"],
        "alternative_visuals": ["Tabla temporal si hay pocos datos"],
    },
    "Análisis de Clientes": {
        "objective": "Medir concentración de demanda y complejidad por cliente.",
        "business_questions": [
            "Qué clientes explican mayor volumen y líneas.",
            "Qué clientes generan más variedad de SKUs.",
            "Qué clientes concentran la operación.",
        ],
        "recommended_kpis": ["Unidades", "Líneas", "Documentos", "SKUs", "Fechas activas", "Participación %"],
        "visual_options": ["Bubble chart volumen-variedad-frecuencia", "Ranking", "Pareto", "Tabla resumen"],
        "alternative_visuals": ["Análisis por documento/SKU si falta cliente"],
    },
    "Pedidos Global (con Transferencias)": {
        "objective": "Sumar carga operativa de pedidos y transferencias cuando aplique.",
        "business_questions": [
            "Cuál es la carga total de egresos/preparación.",
            "Qué peso tienen transferencias sobre pedidos.",
            "Qué cambia al sumar movimientos internos.",
        ],
        "recommended_kpis": ["Unidades globales", "Documentos", "Líneas", "SKUs", "% transferencias"],
        "visual_options": ["Serie total", "Barras apiladas por tipo movimiento", "Tabla comparativa", "P90 carga global"],
        "alternative_visuals": ["Solo pedidos si no hay transferencias"],
    },
    "Transferencias": {
        "objective": "Entender flujos internos entre depósitos, tiendas o sucursales.",
        "business_questions": [
            "Desde dónde hacia dónde se mueve mercadería.",
            "Qué destinos reciben más carga.",
            "Qué SKUs/familias se transfieren.",
            "Cómo impactan en balance y preparación.",
        ],
        "recommended_kpis": ["Unidades transferidas", "Documentos", "Líneas", "SKUs", "Origenes", "Destinos"],
        "visual_options": ["Matriz origen-destino", "Ranking de destinos", "Serie temporal", "Sankey si aplica", "Histograma por documento"],
        "alternative_visuals": ["Tabla de transferencias si faltan origen/destino separados"],
    },
    "Devoluciones": {
        "objective": "Medir devoluciones de cliente y/o a proveedor y su tasa contra base comparativa.",
        "business_questions": [
            "Qué devoluciones existen y cuánto representan.",
            "Qué productos/clientes/proveedores concentran devoluciones.",
            "Si puede calcularse tasa o solo valores absolutos.",
        ],
        "recommended_kpis": ["Unidades devueltas", "% devolución vs pedidos", "% devolución a proveedor vs recepciones", "SKUs", "Documentos"],
        "visual_options": ["KPI de tasa", "Ranking de SKUs", "Evolución temporal", "Pareto", "Tabla por familia"],
        "alternative_visuals": ["Solo absolutos si falta base comparativa"],
    },
    "Ajustes": {
        "objective": "Entender impacto de ajustes manuales de inventario.",
        "business_questions": [
            "Cuánto ajusta la empresa y si es relevante.",
            "Qué SKUs/familias/depósitos concentran ajustes.",
            "Si los ajustes explican diferencias de stock.",
        ],
        "recommended_kpis": ["Ajuste neto", "Ajustes positivos", "Ajustes negativos", "SKUs ajustados", "% ajuste vs movimientos"],
        "visual_options": ["Ajuste neto por mes", "Positivos vs negativos", "Ranking de SKUs", "Tabla por motivo"],
        "alternative_visuals": ["Integrar en Balance de Masa si su peso es bajo"],
    },
    "Edad de Stock": {
        "objective": "Calcular días de cobertura según stock actual/final y consumo histórico.",
        "business_questions": [
            "Qué productos tienen sobrestock o baja cobertura.",
            "Qué productos tienen stock sin consumo.",
            "Qué familias concentran cobertura excesiva.",
            "Qué período de consumo se usó.",
        ],
        "recommended_kpis": ["Consumo promedio diario", "Días de cobertura", "SKUs >90 días", "SKUs >180 días", "SKUs sin consumo", "Baja cobertura"],
        "visual_options": ["Histograma de cobertura", "Ranking mayor/menor cobertura", "Matriz por familia", "Semáforo", "Stock vs consumo"],
        "alternative_visuals": ["Advertencia si no hay consumo suficiente", "Solo stock inmovilizado si no hay fechas"],
    },
    "Pareto de Preparación / Picking": {
        "objective": "Detectar concentración de carga operativa por SKU, cliente, proveedor o familia.",
        "business_questions": [
            "Qué SKUs explican la mayor parte de las líneas o unidades.",
            "Cuántos SKUs explican el 80% del movimiento.",
            "Qué productos deberían priorizarse para slotting.",
            "Qué parte del catálogo tiene baja o nula rotación.",
        ],
        "recommended_kpis": ["Líneas por SKU", "Unidades por SKU", "% participación", "% acumulado", "Ranking", "Clasificación ABC"],
        "visual_options": ["Pareto", "Tabla ABC", "Ranking", "Curva acumulada", "Matriz por familia"],
        "alternative_visuals": ["Pareto por unidades si no hay documento/líneas", "Alta rotación vs resto"],
    },
}

REPORT_GENERATION_MODES = ["Ejecutivo", "Operativo", "Técnico completo"]
REPORT_FOCUS_OPTIONS = [
    "Diagnóstico general",
    "Pedidos / Picking",
    "Stock / Cobertura",
    "Recepciones",
    "Balance de masa",
    "Calidad de datos",
]
