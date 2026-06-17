# MODELOS — Cómo funciona el sistema de generación de leads (v2)

Documento de referencia para entender qué hace cada pieza, adaptar la herramienta a un **nuevo rubro** o
**portarla a otro LLM**. Pensado tanto para una persona como para un modelo de lenguaje al que se le entregue
este proyecto.

---

## 1. Visión general

El objetivo: dado un **rubro** y una **zona**, devolver empresas con **contactos nominados**, **email
verificado y teléfono**, una **descripción** de la empresa, y un **veredicto de ajuste** al perfil de las
empresas que buscas (sí / quizás / no), donde ese perfil se aprende de tu **cartera de clientes actuales**.

El pipeline tiene 5 fases:

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
            │ 4. icp       │  ◀──────────────┘  resolver a dominio + describir → perfil ICP (Claude/Sonnet)
            │              │  calificar cada empresa contra el perfil (sí/quizás/no + score + razón)
            └──────┬───────┘
                   ▼
            ┌──────────────┐
            │ 5. score     │  scoring combinado (ICP + completitud de contacto) → CSV / Excel
            └──────────────┘
```

---

## 2. Modelos de datos / herramientas externas

Cada capa usa una herramienta de pago distinta. Todas se configuran con su clave en `.env`
(ver `v2-leadgen/.env.example`).

### Google Places API (descubrimiento) — `GOOGLE_PLACES_API_KEY`
- **Qué hace:** busca lugares/empresas por texto (Text Search, "API New").
- **Entrada:** texto tipo `"empresa logística en Pudahuel, Santiago"` + `regionCode=cl`.
- **Salida:** nombre, dirección, teléfono nacional, sitio web, rating, nº de reseñas, tipo, estado.
- **Por qué:** reemplaza el scraping frágil de Google Maps por una API oficial y estable con excelente
  cobertura en Chile.
- **Costo:** ~USD 32 por 1.000 búsquedas Text Search. Se usa *field masking* (`X-Goog-FieldMask`) para pagar
  sólo por los campos pedidos.
- **Módulo:** `leadgen/discovery.py`.

### Hunter.io — Domain Search (descubrir contactos) — `HUNTER_API_KEY`
- **Qué hace:** a partir de **sólo el dominio** devuelve las personas con email público de esa empresa.
- **Entrada:** `domain` (ej. `empresa.cl`).
- **Salida:** lista de emails con `first_name`, `last_name`, `position`, `confidence`.
- **Por qué:** es el único de la cadena que **descubre personas sin saber a quién buscar**. Encaja con el
  punto de partida ("tengo la empresa, no los contactos"). Reemplaza el LinkedIn-vía-Google de la v1.
- **Costo:** desde ~USD 49/mes (500 búsquedas).
- **Módulo:** `leadgen/enrich.py` → `HunterProvider`.

### FullEnrich — Waterfall enrichment (enriquecer contactos) — `FULLENRICH_API_KEY`
- **Qué hace:** consulta 15+ proveedores en cascada (Apollo, Dropcontact, Hunter, Prospeo, RocketReach…) y
  devuelve el primer acierto, con **email verificado + teléfono móvil**.
- **Entrada:** `firstname + lastname + domain` (y `linkedin_url` si se tiene) por contacto. **No descubre
  desde cero**: necesita el nombre, que aporta Hunter.
- **Salida:** email verificado y teléfono por contacto.
- **Por qué:** sube la tasa de aciertos (~65-90% vs ~35-45% de un solo proveedor) y agrega teléfonos, que
  Hunter no entrega. Es **asíncrono**: se encola un lote (`/bulk`) y se consulta el resultado por polling.
- **Costo:** desde ~USD 29/mes (500 créditos, ~USD 0,058 c/u).
- **Módulo:** `leadgen/enrich.py` → `FullEnrichProvider`.

**Por qué la cadena Hunter → FullEnrich:** no son competidores. Hunter *descubre* a quién contactar a partir
del dominio; FullEnrich *enriquece* a esas personas con datos verificados. Ambos viven tras la interfaz
`ContactProvider`, así que puedes reordenarlos, desactivar uno (p. ej. sólo Hunter) o sumar otro proveedor
sin tocar el resto del pipeline. Si Hunter no devuelve nada, hay un **fallback** que raspa el sitio web con
regex (heredado de la v1).

### Claude API (Anthropic) — descripción + calificación — `ANTHROPIC_API_KEY`
- **Qué hace:** genera la descripción estructurada de la empresa, infiere el perfil ICP desde tus clientes y
  califica cada empresa candidata.
- **Módulo:** `leadgen/llm.py` (única dependencia del LLM en todo el proyecto).

---

## 3. Modelos de lenguaje (LLM)

| Uso | Modelo | ID exacto | Costo (in / out por millón de tokens) | Por qué |
|---|---|---|---|---|
| Descripción de empresa (volumen) | Claude Haiku 4.5 | `claude-haiku-4-5` | USD 1 / 5 | Barato y rápido; la tarea es simple y se corre para muchas empresas. |
| Perfil ICP + calificación de ajuste | Claude Sonnet 4.6 | `claude-sonnet-4-6` | USD 3 / 15 | Más capaz; aquí la calidad del juicio importa. |

Detalles de implementación (en `leadgen/llm.py`):
- Salida estructurada con `client.messages.parse(..., output_format=SchemaPydantic)` → devuelve instancias
  validadas, sin parseo manual de JSON.
- En la calificación se usa `thinking={"type": "adaptive"}` (no usar `budget_tokens`).
- Se revisa `stop_reason == "refusal"` antes de leer la respuesta.

Para controlar costos antes de una corrida grande: `client.messages.count_tokens(...)`.

---

## 4. Módulos internos (`v2-leadgen/leadgen/`)

| Archivo | Responsabilidad | Funciones públicas |
|---|---|---|
| `config.py` | Claves, rubros, comunas, IDs de modelo, rutas. | `resolver_rubro`, `claves_faltantes` |
| `models.py` | Estructuras de datos neutrales. | `Empresa`, `Contacto` |
| `llm.py` | **Única** capa del LLM: cliente, prompts, schemas. | `describir_empresa`, `construir_perfil_icp`, `calificar_empresa` |
| `discovery.py` | Google Places API. | `buscar_empresas`, `resolver_dominio_de_nombre` |
| `website.py` | Scrapling: bajar sitio + regex (fallback). | `texto_de_sitio`, `extraer_contacto_de_sitio` |
| `enrich.py` | Cadena de contactos Hunter → FullEnrich. | `enriquecer_empresa`, `HunterProvider`, `FullEnrichProvider` |
| `describe.py` | Descripción de empresa con Claude. | `describir` |
| `icp.py` | Cargar clientes, perfil ICP, calificar. | `cargar_clientes`, `construir_o_cargar_icp`, `calificar` |
| `score.py` | Scoring combinado (ICP + contacto). | `score` |
| `export.py` | Export a CSV / Excel. | `a_csv`, `a_excel` |
| `pipeline.py` | Orquesta las 5 fases. | `generar_leads`, `deduplicar` |

Entrypoints: `cli.py` (corridas masivas) y `mcp_server.py` (herramientas para Claude Desktop).

---

## 5. Schemas estructurados

Definidos en `leadgen/llm.py` como modelos Pydantic:

```python
class DescripcionEmpresa(BaseModel):
    descripcion: str        # qué hace, 1-3 frases
    sector: str
    tamano_estimado: str    # micro | pequeña | mediana | grande
    senales: list[str]      # ej: ["tiene bodega", "exporta", "e-commerce"]

class PerfilICP(BaseModel):
    rubros: list[str]
    tamano: str
    senales_clave: list[str]
    criterios_exclusion: list[str]
    resumen: str

class Calificacion(BaseModel):
    ajuste: str             # "si" | "quizas" | "no"
    score_icp: int          # 0-100
    razon: str
```

Ejemplo de calificación devuelta:

```json
{ "ajuste": "si", "score_icp": 82,
  "razon": "Distribuidora con bodega propia en Santiago, igual que la mayoría de tus clientes." }
```

---

## 6. Cómo adaptar a un nuevo rubro o zona

Todo se controla desde `leadgen/config.py`:

1. **Nuevo rubro:** agrega una entrada a `RUBROS` con `slug → (nombre, término de búsqueda)`. Ejemplo:
   ```python
   RUBROS["alimentos"] = ("Alimentos", "empresa de alimentos")
   ```
   Luego: `python cli.py --rubro alimentos --comuna "Quilicura, Santiago"`.
2. **Nuevas zonas:** edita `COMUNAS_DEFAULT` o pasa `--comuna` (repetible) en el CLI.
3. **Otra cartera de clientes:** reemplaza `clients/clientes.csv` (columna `nombre`) y **borra
   `clients/icp_profile.json`** para forzar la reconstrucción del perfil ICP.
4. **Otro país:** cambia `REGION_CODE` y `LANGUAGE_CODE` en `config.py` (Google Places se sesga por región).
   Ten presente que Hunter/FullEnrich tienen mejor cobertura en EE.UU./Europa que en LATAM.

---

## 7. Cómo portar a otro LLM

Toda la dependencia del LLM está en **un solo archivo**: `leadgen/llm.py`. El resto del pipeline pasa y
recibe `dict`/dataclasses, sin saber qué proveedor responde.

Para cambiar de proveedor (OpenAI, Gemini, un modelo local, etc.), reescribe **sólo** `llm.py` manteniendo:

- Las tres funciones públicas con su firma y su tipo de retorno (`DescripcionEmpresa`, `PerfilICP`,
  `Calificacion`).
- Los schemas Pydantic (puedes conservarlos; sólo cambia cómo los llenas).

En la práctica: cambiar el cliente, traducir los prompts (los `system`/`prompt` están en español dentro de
`llm.py`) y adaptar la llamada de salida estructurada al mecanismo del nuevo proveedor (function calling /
JSON mode / etc.). No hace falta tocar `discovery`, `enrich`, `describe`, `icp`, `score`, `pipeline`, `cli`
ni `mcp_server`.

---

## 8. v1 vs v2 vs v3 — cuándo usar cada una

| Criterio | v1 (scraping) | v2 (pago) | v3 (completar planilla) |
|---|---|---|---|
| Punto de partida | Rubro + comuna | Rubro + comuna | Planilla con nombres de empresa |
| Costo | Gratis | APIs de pago | APIs de pago (sólo las que uses) |
| Fiabilidad | Frágil (bloqueos/CAPTCHAs) | Alta (APIs oficiales) | Alta (APIs oficiales) |
| Email/teléfono | Baja cobertura (regex) | Verificado (Hunter + FullEnrich) | Verificado (Hunter + FullEnrich) |
| RUT (Chile) | No | No | Sí (proveedor configurable) |
| Descripción / ICP | No | Sí | No |
| Reproducibilidad | Baja | Alta | Alta |

Usa **v3** cuando ya tienes la lista (p. ej. del SEIA) y sólo faltan datos; **v2** para descubrir
empresas nuevas con descripción y calificación; **v1** para una exploración rápida sin claves.

### v3 — completar planillas (`v3-enrich/`)

Parte de una planilla `.xlsx`/`.csv` existente y **rellena sólo las celdas vacías**, columna a columna:

- **RUT** (`rut.py`) — razón social → RUT vía un proveedor HTTP **configurable** (`RUT_API_URL` con el
  marcador `{q}` y `RUT_API_JSON_PATH`). No hay una API pública única de *nombre → RUT* en Chile, por eso
  se deja abierto a SimpleAPI / Boostr / LibreDTE u otro.
- **Web / teléfono / dirección** (`lugar.py`) — Google Places Text Search, reutilizando el *field masking*
  de la v2 pero resolviendo **una empresa conocida** en vez de buscar por rubro.
- **Contactos** (`contactos.py`) — la misma cadena Hunter → FullEnrich de la v2, reducida a devolver el
  **mejor contacto** por dominio.

La detección de columnas (`sheet.py`) es tolerante a mayúsculas, acentos y alias (`config.ALIAS_COLUMNAS`);
las columnas que faltan se crean con su encabezado canónico y nunca se borra nada existente. No usa LLM.
