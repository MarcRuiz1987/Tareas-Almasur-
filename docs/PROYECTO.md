# Proyecto Tareas-Almasur — Generación de Leads B2B

> **Documento maestro para revisión externa (consultor).**
> Vista completa y autocontenida del proyecto: qué es, para qué sirve, cómo funciona, cada
> componente y herramienta, qué hace cada script y por qué se tomaron las decisiones de diseño.
> Incluye estado actual, costos, limitaciones conocidas y preguntas abiertas para el revisor.
>
> Última actualización: 2026-06-25 · Rama de referencia: `main` + PR #4.

---

## 0. Índice

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [El problema y el objetivo](#2-el-problema-y-el-objetivo)
3. [Las dos versiones (v1 vs v2)](#3-las-dos-versiones-v1-vs-v2)
4. [Arquitectura general (pipeline de 5 fases)](#4-arquitectura-general-pipeline-de-5-fases)
5. [Estructura completa de carpetas y archivos](#5-estructura-completa-de-carpetas-y-archivos)
6. [Herramientas externas (APIs y librerías)](#6-herramientas-externas-apis-y-librerías)
7. [Módulos internos de la v2 — detalle por archivo](#7-módulos-internos-de-la-v2--detalle-por-archivo)
8. [La v1 (scraping) — detalle por archivo](#8-la-v1-scraping--detalle-por-archivo)
9. [Modelos de datos](#9-modelos-de-datos)
10. [Decisiones de diseño y por qué](#10-decisiones-de-diseño-y-por-qué)
11. [Cómo se ejecuta](#11-cómo-se-ejecuta)
12. [Costos](#12-costos)
13. [Estado actual y hallazgos recientes](#13-estado-actual-y-hallazgos-recientes)
14. [Seguridad y manejo de claves](#14-seguridad-y-manejo-de-claves)
15. [Limitaciones conocidas y riesgos](#15-limitaciones-conocidas-y-riesgos)
16. [Panorama de ramas del repositorio](#16-panorama-de-ramas-del-repositorio)
17. [Preguntas y áreas de mejora para el consultor](#17-preguntas-y-áreas-de-mejora-para-el-consultor)

---

## 1. Resumen ejecutivo

**Qué es:** una herramienta de **generación de leads B2B** orientada a Chile. Dado un **rubro**
(ej. logística) y una **zona** (comuna), produce una lista de empresas con:

- **contactos nominados** (nombre + cargo),
- **email verificado y teléfono**,
- una **descripción** de la empresa, y
- un **veredicto de ajuste** al perfil de cliente ideal (sí / quizás / no), aprendido de **tu
  propia cartera de clientes actuales**.

**Origen / caso de uso:** nació para **Procentro** (arriendo/venta de bodegas en Santiago). De ahí
los rubros objetivo: empresas que necesitan almacenamiento y operación logística (logística,
e-commerce, distribución, importadores, manufactura, exportadores, servicios técnicos).

**Cómo lo hace:** un **pipeline de 5 fases** donde cada fase usa la mejor herramienta para su tarea
(Google Places para descubrir, Hunter para encontrar personas, FullEnrich para verificar email +
teléfono, Claude para describir y calificar) y exporta a CSV/Excel.

**Estado:** la **v2** (de pago) es el producto principal. El descubrimiento (Google Places) y el
descubrimiento de contactos (Hunter) funcionan; FullEnrich quedó recién corregido a su API actual;
las fases con IA (descripción y calificación ICP) están **pendientes** de activar la clave de
Anthropic y de cargar la cartera real de clientes.

---

## 2. El problema y el objetivo

El punto de partida del usuario es: **"tengo el rubro y la zona, pero no tengo los contactos ni sé
cuáles empresas realmente me sirven"**. Un listado de empresas crudo (ej. Google Maps) no basta:
falta a quién contactar, su email/teléfono real, y un criterio para **priorizar** las que se parecen
a los clientes que ya funcionan.

El objetivo del sistema es cerrar esas tres brechas:

| Brecha | Cómo la resuelve |
|---|---|
| "¿Qué empresas existen del rubro X en la zona Y?" | Descubrimiento vía Google Places API |
| "¿A quién le escribo y cuál es su email/teléfono?" | Hunter (descubre personas) → FullEnrich (verifica email + teléfono) |
| "¿Cuáles priorizo?" | Descripción con IA + calificación de ajuste (ICP) aprendida de tu cartera |

El resultado es una planilla **priorizada por score**, lista para prospección comercial.

---

## 3. Las dos versiones (v1 vs v2)

El repositorio contiene **dos implementaciones que conviven** y se ejecutan de forma independiente:

| | **v1 — scraping (gratuita)** | **v2 — herramientas de pago (principal)** |
|---|---|---|
| Carpeta | `v1-scraping/` | `v2-leadgen/` |
| Descubrimiento | Scraping de Google Maps (Scrapling/Playwright) | **Google Places API** (oficial, estable) |
| Contactos | Regex sobre el sitio + LinkedIn vía Google | **Hunter** (descubrir) → **FullEnrich** (email + teléfono) |
| Descripción de empresa | ❌ | ✅ **Claude Haiku** |
| Calificación ICP / ajuste | ❌ | ✅ **Claude Sonnet** (con tus clientes como referencia) |
| Costo | Gratis | APIs de pago |
| Fiabilidad | Frágil (bloqueos, CAPTCHAs, cambios de HTML) | Alta (APIs oficiales) |
| Claves requeridas | Ninguna | Google Places, Hunter, FullEnrich, Anthropic |
| Reproducibilidad | Baja | Alta |

**Criterio de uso:** la **v2** para trabajo real; la **v1** como alternativa gratuita / exploración
rápida sin claves. La v1 se conserva como respaldo y porque su lógica de regex se **reutiliza** como
*fallback* en la v2 (cuando Hunter no devuelve nada).

---

## 4. Arquitectura general (pipeline de 5 fases)

```
            ┌──────────────┐
 rubro +    │ 1. discovery │  Google Places API → empresas (nombre, web, teléfono, reseñas)
 comuna ───▶│              │
            └──────┬───────┘
                   ▼
            ┌──────────────┐
            │ 2. describe  │  Scrapling baja el sitio → Claude (Haiku) → descripción estructurada
            └──────┬───────┘
                   ▼
            ┌──────────────┐
            │ 3. enrich    │  Hunter (descubrir personas por dominio) → FullEnrich (email + teléfono)
            └──────┬───────┘
                   ▼
            ┌──────────────┐   clientes.csv ─┐
            │ 4. icp       │  ◀──────────────┘  resolver a dominio + describir → perfil ICP (Sonnet)
            │              │  calificar cada empresa contra el perfil (sí/quizás/no + score + razón)
            └──────┬───────┘
                   ▼
            ┌──────────────┐
            │ 5. score     │  scoring combinado (ICP + completitud de contacto) → CSV / Excel
            └──────────────┘
```

**Principio rector:** cada fase es independiente y pasa/recibe estructuras de datos neutrales
(`Empresa`, `Contacto`). Esto permite **activar, desactivar o reordenar fases** sin tocar el resto —
de hecho, hoy se corren solo las fases 1, 3 y 5 mientras no hay clave de Anthropic (ver
`run_sin_claude.py`).

---

## 5. Estructura completa de carpetas y archivos

```
Tareas-Almasur-/
├── README.md                      # Visión general + inicio rápido de ambas versiones
├── .gitignore                     # Excluye secretos (.env), salidas (leads-*.csv), caché ICP, __pycache__
│
├── docs/
│   ├── MODELOS.md                 # Referencia técnica de modelos/herramientas/módulos (cómo adaptar y portar)
│   └── PROYECTO.md                # ESTE documento (vista completa para revisión)
│
├── v1-scraping/                   # ── VERSIÓN 1: scraping gratuito ──
│   ├── README.md                  # Qué hace, limitaciones, uso
│   ├── requirements.txt           # scrapling[all]
│   ├── procentro_leads.py         # Pipeline completo de scraping (7 rubros + enriquecimiento web/LinkedIn)
│   ├── scrape_leads_logistica.py  # Versión simple: solo logística, solo descubrimiento
│   └── scrapling-mcp-setup.md     # Guía para usar Scrapling como MCP en Claude Desktop (Windows)
│
└── v2-leadgen/                    # ── VERSIÓN 2: APIs de pago (principal) ──
    ├── .env.example               # Plantilla de claves de API
    ├── .env                       # (local, NO versionado) claves reales
    ├── requirements.txt           # requests, anthropic, pydantic, python-dotenv, openpyxl, mcp, scrapling[all]
    ├── cli.py                     # Entrypoint para corridas masivas (exige las 4 claves)
    ├── mcp_server.py              # Entrypoint MCP: expone el pipeline como herramientas a Claude Desktop
    ├── run_sin_claude.py          # Runner parcial: discovery + enrich + score, SIN fases de Claude (NUEVO)
    │
    ├── clients/
    │   └── clientes.csv           # Cartera de clientes (columna 'nombre') para construir el ICP
    │   └── icp_profile.json       # (local, NO versionado) caché del perfil ICP construido
    │
    └── leadgen/                   # ── El paquete principal ──
        ├── __init__.py            # Metadatos del paquete; reexporta config
        ├── config.py              # Claves, rubros, comunas, IDs de modelo, rutas, gate de claves
        ├── models.py              # Dataclasses neutrales: Empresa, Contacto
        ├── llm.py                 # ÚNICA capa del LLM: cliente Claude, prompts y schemas Pydantic
        ├── discovery.py           # Google Places API (búsqueda de empresas, resolución de dominio)
        ├── website.py             # Scrapling: bajar sitio + regex de contacto (fallback)
        ├── enrich.py              # Cadena de contactos: Hunter → FullEnrich → fallback web
        ├── describe.py            # Descripción de empresa con Claude (Haiku)
        ├── icp.py                 # Cargar clientes, construir/cachear perfil ICP, calificar
        ├── score.py               # Scoring combinado (ICP + completitud de contacto)
        ├── export.py              # Exportación a CSV / Excel
        └── pipeline.py            # Orquestador de las 5 fases
```

**Archivos NO versionados (por `.gitignore`, a propósito):** `v2-leadgen/.env` (secretos),
`v2-leadgen/clients/icp_profile.json` (caché de datos de clientes), `leads-*.csv` / `*.xlsx`
(salidas generadas) y `__pycache__/`.

---

## 6. Herramientas externas (APIs y librerías)

Cada capa usa la herramienta más adecuada para su tarea. Las cuatro claves se configuran en
`v2-leadgen/.env`.

### 6.1 Google Places API — descubrimiento (`GOOGLE_PLACES_API_KEY`)
- **Qué hace:** Text Search (API "New") busca empresas por texto libre + sesgo por país.
- **Entrada:** `"empresa logística en Pudahuel, Santiago"` + `regionCode=cl`.
- **Salida:** nombre, dirección, teléfono nacional, sitio web, rating, nº de reseñas, tipo, estado.
- **Por qué:** reemplaza el scraping frágil de Google Maps por una API oficial y estable con buena
  cobertura en Chile.
- **Control de costo:** *field masking* (`X-Goog-FieldMask`) → se paga solo por los campos pedidos.
- **Módulo:** `leadgen/discovery.py`.

### 6.2 Hunter.io — Domain Search (`HUNTER_API_KEY`)
- **Qué hace:** a partir de **solo el dominio**, devuelve personas con email público de la empresa.
- **Salida:** lista de emails con `first_name`, `last_name`, `position`, `confidence`.
- **Por qué:** es el único eslabón que **descubre personas sin saber a priori a quién buscar**.
  Reemplaza el "LinkedIn vía Google" de la v1.
- **Módulo:** `leadgen/enrich.py` → `HunterProvider`.

### 6.3 FullEnrich — Waterfall enrichment (`FULLENRICH_API_KEY`)
- **Qué hace:** consulta 15+ proveedores en cascada (Apollo, Dropcontact, Prospeo, RocketReach…) y
  devuelve el primer acierto con **email verificado + teléfono**.
- **Entrada:** `firstname + lastname + domain` (y `linkedin_url` si se tiene) por contacto.
- **Por qué:** sube la tasa de aciertos y agrega teléfonos, que Hunter no entrega. **No descubre
  desde cero**: necesita el nombre que aporta Hunter.
- **Naturaleza:** **asíncrono** — se encola un lote (`/bulk`) y se consulta el resultado por polling.
- **Módulo:** `leadgen/enrich.py` → `FullEnrichProvider`.

### 6.4 Anthropic Claude — descripción + calificación (`ANTHROPIC_API_KEY`)
- **Qué hace:** genera la descripción estructurada de la empresa, infiere el perfil ICP desde tus
  clientes y califica cada empresa candidata.
- **Modelos:**
  | Uso | Modelo | ID | Por qué |
  |---|---|---|---|
  | Descripción (volumen) | Claude Haiku 4.5 | `claude-haiku-4-5` | Barato y rápido; tarea simple a gran escala |
  | Perfil ICP + calificación | Claude Sonnet 4.6 | `claude-sonnet-4-6` | Más capaz; aquí la calidad del juicio importa |
- **Detalles:** salida estructurada con `client.messages.parse(..., output_format=SchemaPydantic)`
  (sin parseo manual de JSON); se revisa `stop_reason == "refusal"`.
- **Módulo:** `leadgen/llm.py` (única dependencia del LLM en todo el proyecto).

### 6.5 Librerías de soporte
- **Scrapling** (Playwright/Chromium): scraping de la v1 y *fallback* de contacto en la v2; también
  se usa como **servidor MCP** para extraer listas de clientes desde directorios web.
- **requests**: cliente HTTP para las tres APIs REST.
- **pydantic v2**: schemas de salida estructurada del LLM.
- **python-dotenv**: carga de claves desde `.env`.
- **openpyxl**: exportación opcional a Excel.
- **mcp (FastMCP)**: expone el pipeline como herramientas conversacionales en Claude Desktop.

---

## 7. Módulos internos de la v2 — detalle por archivo

> Resumen de responsabilidades. La lógica del LLM vive **solo** en `llm.py`; el resto del pipeline es
> agnóstico del proveedor.

### `leadgen/config.py` — configuración central
- Carga las 4 claves desde `.env`.
- Define `RUBROS` (slug → nombre + término de búsqueda), `COMUNAS_DEFAULT` (5 comunas de Santiago),
  IDs de modelo, parámetros (`MIN_RESENAS=3`, `DEFAULT_MAX=50`, `REGION_CODE=cl`, `LANGUAGE_CODE=es`)
  y rutas (`CLIENTS_DIR`, `ICP_CACHE`).
- **Funciones:** `resolver_rubro(slug)` (slug → nombre, query; lanza error si no existe) y
  `claves_faltantes()` (reporta qué claves faltan — base del "gate" del CLI).

### `leadgen/models.py` — estructuras de datos neutrales
- `Contacto`: nombre, cargo, email, teléfono, linkedin_url, confianza (0-100).
- `Empresa`: ficha completa de un lead (datos de Google + descripción + contactos + veredicto ICP +
  score). Propiedad `contacto_principal` (el de mayor confianza). `to_dict()` para exportar.
- Son `@dataclass` puras, sin dependencia de ningún proveedor ni del LLM.

### `leadgen/llm.py` — capa aislada del LLM (la superficie a reescribir para portar a otro modelo)
- **Schemas Pydantic:** `DescripcionEmpresa`, `PerfilICP`, `Calificacion`.
- **Cliente perezoso:** importa `anthropic` solo al usarse (no exige la dependencia si no se llama).
- **Funciones públicas:** `describir_empresa(nombre, texto_web)`, `construir_perfil_icp(clientes)`,
  `calificar_empresa(empresa, perfil, ejemplos)`.
- Prompts en español; calificación con `thinking={"type": "adaptive"}`; manejo de `refusal`.

### `leadgen/discovery.py` — Google Places
- `buscar_empresas(rubro_query, comuna, rubro_nombre, max)`: Text Search con paginación
  (`nextPageToken`), filtra por `businessStatus == OPERATIONAL` y `userRatingCount ≥ MIN_RESENAS`,
  deriva el dominio del sitio web.
- `resolver_dominio_de_nombre(nombre)`: resuelve un nombre de empresa a su ficha (se usa para
  perfilar clientes en la fase ICP).

### `leadgen/website.py` — acceso al sitio web (Scrapling)
- `texto_de_sitio(website)`: concatena texto de home + páginas de contacto/nosotros (alimenta a
  Claude para la descripción).
- `extraer_contacto_de_sitio(website)`: *fallback* por regex → (email, nombre, cargo). Importa
  Scrapling de forma perezosa. Reutiliza la lógica de la v1.

### `leadgen/enrich.py` — cadena de contactos *(corregido en PR #4)*
- `ContactProvider` (interfaz abstracta) → `HunterProvider` y `FullEnrichProvider`.
- `HunterProvider.descubrir(dominio)`: domain-search → lista de `Contacto`.
- `FullEnrichProvider.enriquecer(contactos, dominio, empresa)`: encola un lote `/bulk`, hace
  **polling** hasta `FINISHED`, y mapea email + teléfono de vuelta a cada contacto.
- `enriquecer_empresa(empresa, top_contactos=3)`: orquesta Hunter → prioriza por cargo+email →
  toma los mejores 3 → FullEnrich; si Hunter no devuelve nada, cae al *fallback* web (regex).

### `leadgen/describe.py` — descripción con Claude
- `describir(empresa)`: baja el sitio (`website.texto_de_sitio`) y llama a `llm.describir_empresa`;
  rellena descripcion/sector/tamaño/señales. Tolerante a fallos (si algo falla, deja la empresa intacta).

### `leadgen/icp.py` — perfil de cliente ideal y calificación
- `cargar_clientes(csv)`: lee nombres de clientes (columna `nombre` o la primera).
- `construir_o_cargar_icp(nombres)`: resuelve cada cliente a dominio + lo describe + Claude resume el
  conjunto en un `PerfilICP`. **Cachea** en `clients/icp_profile.json` para no re-pagar.
- `calificar(empresa, perfil, ejemplos)`: clasifica la empresa (sí/quizás/no + score + razón).

### `leadgen/score.py` — scoring combinado
- `score(empresa)`: combina el ajuste al ICP (lo que más pesa: hasta 50 pts del `score_icp` + 20 si
  "sí" / 5 si "quizás") con la completitud de contacto (nombre 10, email 8, teléfono 7), el sitio web
  (2) y la tracción por reseñas (1-3).

### `leadgen/export.py` — exportación
- `a_csv(empresas, path)`: CSV en `utf-8-sig` (abre bien en Excel en español). `a_excel(...)` opcional
  (requiere openpyxl). Aplana el contacto principal a columnas planas.

### `leadgen/pipeline.py` — orquestador
- `generar_leads(rubro, comunas, max, clientes_csv)`: corre las 5 fases en orden, deduplica
  (`deduplicar`, por dominio o nombre normalizado), y devuelve los leads ordenados por score.

### `cli.py` — entrypoint de corridas masivas
- Argumentos: `--rubro`, `--comuna` (repetible), `--max`, `--clientes`, `--sin-icp`, `--salida`,
  `--excel`. **Gate:** si falta alguna de las 4 claves, aborta con un aviso. Imprime resumen + top 5.

### `mcp_server.py` — entrypoint MCP (Claude Desktop)
- Expone el pipeline como **herramientas conversacionales** vía FastMCP: `buscar_empresas`,
  `describir_empresa`, `enriquecer_contactos`, `cargar_clientes`, `construir_icp`, `calificar_lead`.
- Permite usar las piezas "por chat" en vez de en lote.

### `run_sin_claude.py` — runner parcial *(NUEVO, PR #4)*
- Corre **discovery → enrich → score → export** llamando a los módulos directamente, **sin** importar
  `llm.py` ni pasar por el gate de 4 claves del CLI. Pensado para operar **mientras no hay clave de
  Anthropic**. Sondea Hunter antes del lote (circuit-breaker si la cuenta está restringida), limita
  contactos por empresa (~3) y aísla errores por empresa para no abortar la corrida.

---

## 8. La v1 (scraping) — detalle por archivo

### `procentro_leads.py` — pipeline de scraping completo
- **Fase 1 — Google Maps:** con `StealthyFetcher` (Chromium anti-bot) abre la búsqueda, acepta
  cookies, hace scroll del feed y recolecta URLs de fichas; luego visita cada ficha y extrae
  teléfono, sitio web, nombre, calificación, reseñas y dirección (selectores CSS + regex).
- **Fase 2A — enriquecimiento web:** baja home + páginas de contacto y extrae email/nombre/cargo por
  regex (`mailto:`, patrones de nombre+cargo).
- **Fase 2B — LinkedIn vía Google:** busca `site:linkedin.com/in "<empresa>" (<cargos>) Chile` y
  parsea los `<h3>` de resultados para un contacto nominado (sin cuenta de LinkedIn).
- **Dedup + scoring + CSV:** deduplica por nombre, puntúa (contacto 35, email 25, teléfono 15, web 5,
  reseñas/rating bonus) y exporta a `~/Desktop/leads-procentro-santiago-<fecha>.csv`.
- Flags: `--rubro`, `--max`, `--solo-empresas`, `--sin-linkedin`.

### `scrape_leads_logistica.py` — scraping simple
- Versión reducida: solo logística, solo descubrimiento (sin enriquecimiento). Misma técnica de
  scroll + extracción de ficha. Exporta a `~/Desktop/leads-operaciones-logistica-<ciudad>.csv`.
- Flags: `--ciudad`, `--max`.

### `scrapling-mcp-setup.md`
- Guía paso a paso (Windows) para instalar Scrapling y registrarlo como **MCP en Claude Desktop**,
  usado para extraer listas de clientes desde directorios web.

> **Nota de continuidad:** las constantes y la lógica de regex de la v1 (`CONTACT_PATHS`,
> `CARGO_KEYWORDS`, `EMAIL_RE`, extracción de contacto) se **reutilizan** en `v2-leadgen/website.py`
> como *fallback*.

---

## 9. Modelos de datos

**Estructuras internas** (`leadgen/models.py`):

```python
@dataclass
class Contacto:
    nombre: str; cargo: str; email: str; telefono: str
    linkedin_url: str; confianza: int            # 0-100

@dataclass
class Empresa:
    nombre: str; rubro: str; comuna: str; direccion: str; telefono: str
    sitio_web: str; dominio: str; calificacion: str; resenas: int; place_id: str
    descripcion: str; sector: str; tamano_estimado: str; senales: list[str]   # ← describe
    contactos: list[Contacto]                                                  # ← enrich
    ajuste_icp: str; score_icp: int; razon_icp: str                           # ← icp
    score: int                                                                 # ← score
```

**Schemas del LLM** (`leadgen/llm.py`, Pydantic):

```python
class DescripcionEmpresa: descripcion, sector, tamano_estimado, senales[]
class PerfilICP:          rubros[], tamano, senales_clave[], criterios_exclusion[], resumen
class Calificacion:       ajuste ("si"|"quizas"|"no"), score_icp (0-100), razon
```

**Columnas del CSV de salida:** `nombre, rubro, comuna, descripcion, sector, tamano_estimado,
nombre_contacto, cargo_contacto, email, telefono, sitio_web, ajuste_icp, score_icp, razon_icp, score`.

---

## 10. Decisiones de diseño y por qué

1. **Dos versiones que conviven.** La v2 (pago) da calidad; la v1 (gratis) es respaldo/exploración y
   fuente de la lógica de *fallback*. Permite operar con o sin presupuesto.
2. **Pipeline de 5 fases desacopladas.** Cada fase consume/produce dataclasses neutrales → se pueden
   activar/desactivar/reordenar sin tocar el resto (clave para correr hoy sin Claude).
3. **Interfaz `ContactProvider`.** Hunter y FullEnrich viven tras una interfaz común → se pueden
   reordenar, desactivar uno o sumar otro proveedor sin tocar el pipeline.
4. **Cadena Hunter → FullEnrich (no competidores).** Hunter *descubre* a quién contactar; FullEnrich
   *enriquece* a esas personas con datos verificados. Roles complementarios.
5. **Toda la dependencia del LLM en un solo archivo (`llm.py`).** Para portar a otro proveedor
   (OpenAI/Gemini/local) se reescribe **solo** ese archivo, manteniendo las 3 firmas públicas.
6. **Salida estructurada con Pydantic** (`messages.parse`) → instancias validadas, sin parseo manual
   de JSON ni *prompt-engineering* frágil de formato.
7. **Field masking en Google** → se paga solo por los campos necesarios.
8. **Caché del ICP** (`icp_profile.json`) → no re-pagar la descripción de los clientes en cada corrida.
9. **Dos modelos según la tarea:** Haiku para descripción a volumen (barato), Sonnet para el juicio de
   ajuste (calidad). Optimiza costo vs. calidad.
10. **Scoring combinado** (ICP + completitud de contacto + tracción) → ordena por valor comercial real.
11. **Dedup por dominio-o-nombre** → evita repetidos entre comunas/listados.
12. **CSV en `utf-8-sig`** → abre correcto en Excel en español (acentos).
13. **`.env` + `.gitignore`** → secretos y salidas fuera del control de versiones.
14. **Dos entrypoints:** `cli.py` (lotes) y `mcp_server.py` (conversacional en Claude Desktop).
15. **Imports perezosos** (anthropic, scrapling) → no exigir dependencias pesadas si esa ruta no se usa.
16. **Tolerancia a fallos** en describe/icp (try/except que no aborta la corrida) y aislamiento por
    empresa en `run_sin_claude.py`.

---

## 11. Cómo se ejecuta

**v2 — corrida completa (requiere las 4 claves):**
```bash
cd v2-leadgen
pip install -r requirements.txt
cp .env.example .env          # completar claves
python cli.py --rubro logistica --comuna "Pudahuel, Santiago" --max 50 \
    --clientes clients/clientes.csv
```

**v2 — sin clave de Anthropic (solo descubrimiento + contactos):**
```bash
cd v2-leadgen
python run_sin_claude.py --rubro logistica --max-total 50
```

**v2 — como MCP en Claude Desktop:** registrar `mcp_server.py` en `claude_desktop_config.json`.

**v1 — scraping gratuito:**
```bash
cd v1-scraping
pip install -r requirements.txt && scrapling install
python procentro_leads.py --rubro logistica --max 30
```

**Adaptar a nuevo rubro / zona / país / clientes** (todo en `config.py`):
- Nuevo rubro: agregar a `RUBROS`. Nuevas zonas: editar `COMUNAS_DEFAULT` o pasar `--comuna`.
- Otra cartera: reemplazar `clients/clientes.csv` y **borrar** `clients/icp_profile.json`.
- Otro país: cambiar `REGION_CODE`/`LANGUAGE_CODE` (ojo: Hunter/FullEnrich rinden mejor en EE.UU./Europa).

---

## 12. Costos

| Herramienta | Costo de referencia | Notas |
|---|---|---|
| Google Places (Text Search) | ~USD 32 / 1.000 búsquedas | Con field masking; ~1-2 búsquedas por comuna |
| Hunter.io | Free 50 búsquedas/mes; pago desde ~USD 49/mes (500) | 1 búsqueda = 1 dominio |
| FullEnrich | desde ~USD 29/mes (500 créditos, ~USD 0,058 c/u) | Cobra por acierto; el no-match cuesta 0 |
| Claude Haiku 4.5 | USD 1 / 5 por millón de tokens (in/out) | Descripción a volumen |
| Claude Sonnet 4.6 | USD 3 / 15 por millón de tokens (in/out) | Perfil ICP + calificación |

**Orden de magnitud para 50 leads:** descubrimiento Google ≈ USD 0,2-0,3; Hunter ≈ 50 búsquedas;
FullEnrich ≈ hasta 150 enriquecimientos (3/empresa) pero solo cobra los aciertos; Claude ≈ unos pocos
centavos a USD para describir + calificar 50 empresas. El cuello de costo/volumen es **Hunter**
(cuota) y, en menor medida, **FullEnrich** (créditos por acierto).

---

## 13. Estado actual y hallazgos recientes

- **Google Places:** ✅ funciona; corrida real devolvió 50 empresas de logística en las 5 comunas.
- **Hunter:** ✅ funciona (plan **Free**, 50 búsquedas/mes). Se observó un episodio **transitorio** de
  `restricted_account` (probablemente por exposición de la clave) que se resolvió solo.
- **FullEnrich:** 🔧 **corregido** (PR #4). El código asumía la forma de una API anterior:
  - `enrich_fields` usaba `contact_email`/`contact_phone` → la API responde **HTTP 400**; lo válido es
    `contact.emails`/`contact.phones`.
  - Los resultados se leían planos; en realidad vienen anidados en `datas[].contact`
    (`most_probable_email`/`most_probable_phone` + listas `emails`/`phones`).
  - Verificado end-to-end (POST 200 → polling `IN_PROGRESS`→`FINISHED`).
- **Corrida de 50 leads (logística):** 50 empresas, **35 con email** (de Hunter), **39 con teléfono**
  (de Google Places). **FullEnrich no devolvió teléfonos** chilenos (cobertura LATAM débil).
- **Pendiente:** activar `ANTHROPIC_API_KEY` para las fases de **descripción** (Haiku) y
  **calificación ICP** (Sonnet), y reemplazar `clients/clientes.csv` con la cartera real de clientes.

---

## 14. Seguridad y manejo de claves

- Las 4 claves viven en `v2-leadgen/.env`, ignorado por git (`*.env`). `.env.example` documenta el formato.
- Salidas y caché de datos de clientes también están en `.gitignore` (no se versionan).
- **Pendiente operativo:** rotar las claves de Google / Hunter / FullEnrich, ya que quedaron expuestas
  en conversaciones de trabajo.
- Tráfico de las APIs sobre HTTPS. El MCP de la v1/v2 corre local.

---

## 15. Limitaciones conocidas y riesgos

1. **Cobertura LATAM de Hunter/FullEnrich.** Menor que en EE.UU./Europa; en esta corrida FullEnrich no
   aportó teléfonos chilenos. Los teléfonos provienen mayormente de Google Places.
2. **Hunter Free = 50 búsquedas/mes.** Una corrida de 50 empresas agota la cuota. Para volumen real se
   requiere plan de pago.
3. **Calidad de datos de Hunter.** Devuelve también emails genéricos (`info@`, `contacto@`) y ocasional
   ruido (ej. un email de `instagram.com` para una empresa sin sitio propio).
4. **Fragilidad y ToS del scraping (v1).** Google Maps/LinkedIn cambian HTML, ponen CAPTCHAs y su
   scraping puede chocar con términos de servicio. La v1 es respaldo, no la vía principal.
5. **Dedup imperfecto.** La clave es dominio-o-nombre; una misma empresa listada dos veces (una sin
   sitio web) puede colarse como dos registros.
6. **FullEnrich es lento por empresa.** El diseño actual encola **un job async por empresa** (polling
   ~80s c/u); para 50 empresas la corrida es larga. Oportunidad: **batch** (el `/bulk` admite hasta
   100 contactos en un job).
7. **Sin pruebas automatizadas** ni CI en el repo.
8. **IDs de modelo y parámetros hardcodeados** en `config.py` (sin override por entorno salvo claves).
9. **Entorno efímero.** `.env` y CSV generados viven solo en el contenedor de trabajo; deben
   resguardarse aparte.
10. **El `score` sin ICP es bajo y poco discriminante** (solo pondera completitud de contacto); su
    valor real aparece al activar la calificación ICP.

---

## 16. Panorama de ramas del repositorio

| Rama | Contenido | ¿En `main`? |
|---|---|---|
| `main` | Proyecto canónico: v1 + v2 + docs | — |
| `claude/kind-hamilton-d44gyi` (**PR #4**) | Fix de FullEnrich + `run_sin_claude.py` | abierto |
| `claude/lead-generation-paid-tools-ibw8me` | La v2 antes de fusionarse | ya en `main` |
| `claude/charming-gates-f2zfyr` | La v1 ("Procentro") | representada en `main` |
| `claude/spreadsheet-data-v3-3xvnu5` | **v3**: contactos por dominio del SEIA + checkpoints reanudables | ❌ no fusionada |
| `claude/daily-task-automation-stack-RozCD` | Stack de automatización diaria | ❌ no fusionada |

> Existen **dos líneas de trabajo no fusionadas** (una "v3" basada en datos del SEIA y un stack de
> automatización diaria). No están en `main`; conviene decidir si se integran, se documentan o se
> archivan.

---

## 17. Preguntas y áreas de mejora para el consultor

> Puntos abiertos donde la opinión externa aporta más valor. No son conclusiones, son temas a discutir.

**Estrategia de datos y calidad**
- ¿Conviene **verificar/limpiar** los emails de Hunter (genéricos vs. nominados, descartar ruido)
  antes de enriquecer con FullEnrich, para no gastar créditos en basura?
- ¿Vale la pena un proveedor con mejor **cobertura de teléfonos en Chile/LATAM** (o una fuente local)?
- ¿El **ICP aprendido de la cartera** es el enfoque correcto, o conviene complementarlo con reglas
  duras (tamaño, comuna, señales como "tiene bodega")?

**Costo y rendimiento**
- **Batch de FullEnrich** (un job `/bulk` con ~100 contactos en vez de uno por empresa) para reducir
  tiempo de ~1 hora a minutos y simplificar el manejo de créditos. ¿Prioritario?
- Estrategia de **cuotas** (Hunter Free vs. pago) y *caching* de dominios ya consultados.

**Arquitectura y mantenibilidad**
- Falta de **pruebas automatizadas / CI**: ¿qué cobertura mínima tendría sentido (parsers de Google,
  mapeo de FullEnrich, scoring)?
- ¿Consolidar v1/v2/v3 o separar en repos/paquetes? ¿Qué hacer con las ramas no fusionadas?
- **Observabilidad**: logging estructurado, conteo de créditos consumidos, métricas de cobertura.

**Producto e integración**
- Integración con **CRM** (HubSpot/Pipedrive) en vez de CSV; deduplicación contra registros existentes.
- **Deliverability**: validación de email (MX/SMTP), supresión de bajas, cumplimiento de no contactar.
- **Cumplimiento legal**: GDPR/uso de datos personales y términos de servicio de las fuentes (en
  especial el scraping de la v1).

**Calidad del lead**
- Revisar la **fórmula de scoring** (pesos de ICP vs. contacto vs. tracción) y validar con resultados
  reales de prospección (¿qué leads efectivamente convirtieron?).

---

*Fin del documento. Para detalle de implementación por módulo y guía de portabilidad a otro LLM, ver
también `docs/MODELOS.md`.*
