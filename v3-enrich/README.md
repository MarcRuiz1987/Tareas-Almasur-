# v3 — Completar planillas (enriquecimiento)

Mientras la **v2** *descubre* empresas desde cero (rubro + comuna), la **v3** parte de una
**planilla que ya tienes** y **rellena las celdas vacías**. Pensada para listados como el del
**SEIA** (proyectos solares en Chile), donde tienes el nombre de cada empresa pero te faltan el
**RUT**, el **sitio web/teléfono** y los **contactos**.

## Qué completa

| Grupo (`--campos`) | Campos que rellena | Proveedor |
|---|---|---|
| `rut` | `RUT` | API de RUT chileno (configurable) |
| `web` | `Sitio Web`, `Dominio`, `Teléfono`, `Dirección` | Google Places API |
| `contactos` | `Contacto`, `Cargo`, `Email`, `Teléfono Contacto`, `LinkedIn` | Hunter → FullEnrich |

Reglas: **sólo rellena celdas vacías** (salvo `--sobrescribir`), **nunca borra** columnas ni filas,
y **crea** las columnas que falten con su encabezado canónico. La detección de columnas tolera
mayúsculas, acentos y nombres alternativos (`Empresa`/`Nombre`/`Razón social`, etc.).

## Inicio rápido

```bash
cd v3-enrich
pip install -r requirements.txt
cp .env.example .env          # completa sólo las claves que vayas a usar

# completar todo sobre una planilla del SEIA
python cli.py --entrada gtc_leads.xlsx --salida gtc_leads_completa.xlsx

# probar con las primeras 10 filas
python cli.py --entrada gtc_leads.xlsx --limite 10

# sólo web + contactos (sin RUT)
python cli.py --entrada empresas.xlsx --campos web,contactos
```

Hay una planilla de ejemplo en [`ejemplo_planilla.csv`](ejemplo_planilla.csv) con la misma
estructura del SEIA. Acepta `.xlsx` y `.csv`.

## Claves de API (`.env`)

Todas son opcionales: si falta una, ese grupo de campos se omite (se avisa al iniciar) y el resto
se completa igual.

- `GOOGLE_PLACES_API_KEY` — sitio web, dominio, teléfono y dirección.
- `HUNTER_API_KEY` + `FULLENRICH_API_KEY` — contactos nominados con email/teléfono verificados.
- `RUT_API_URL` (+ `RUT_API_KEY`, `RUT_API_JSON_PATH`) — RUT por razón social.

### Sobre el RUT

No existe una API pública única y gratuita de **nombre → RUT**, así que el proveedor es
**configurable**: define la URL con el marcador `{q}` (la consulta) y la ruta JSON donde viene el
RUT. Sirve para servicios chilenos como SimpleAPI, Boostr o LibreDTE.

```bash
RUT_API_URL=https://api.tu-proveedor.cl/empresas?nombre={q}
RUT_API_KEY=...                 # opcional (se envía como Bearer)
RUT_API_JSON_PATH=data.0.rut    # ruta con puntos; índices numéricos = listas
```

## Módulos (`v3-enrich/planilla/`)

| Archivo | Responsabilidad | Funciones públicas |
|---|---|---|
| `config.py` | Claves, alias de columnas, grupos de campos. | `claves_disponibles`, `avisos_de_claves` |
| `sheet.py` | Leer/escribir `.xlsx`/`.csv`, mapear columnas, rellenar sólo vacíos. | `Planilla` |
| `lugar.py` | Google Places: nombre → sitio web / teléfono / dirección. | `resolver`, `dominio_de_url` |
| `rut.py` | Razón social → RUT (proveedor HTTP configurable). | `buscar_rut`, `RutProvider` |
| `contactos.py` | Hunter (descubrir) → FullEnrich (verificar). | `mejor_contacto` |
| `completar.py` | Orquesta el recorrido fila a fila. | `completar_planilla` |

Entrypoint: `cli.py`.
