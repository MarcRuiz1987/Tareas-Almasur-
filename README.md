# Tareas-Almasur — Generación de leads

Herramienta para buscar empresas de un rubro, obtener sus contactos y una descripción, y **refinar si
encajan o no con el perfil de las empresas que buscas**, retroalimentándose de tu cartera de clientes
actuales.

El proyecto tiene **tres versiones que conviven** y se ejecutan de forma independiente:

| | **v1 — scraping (gratuita)** | **v2 — herramientas de pago (mejorada)** | **v3 — completar planilla** |
|---|---|---|---|
| Carpeta | [`v1-scraping/`](v1-scraping/) | [`v2-leadgen/`](v2-leadgen/) | [`v3-enrich/`](v3-enrich/) |
| Punto de partida | Rubro + comuna | Rubro + comuna | **Planilla que ya tienes** (nombres de empresa) |
| Descubrimiento | Scraping de Google Maps (Scrapling) | **Google Places API** (oficial, estable) | — (la lista ya existe) |
| Contactos | Regex sobre el sitio + LinkedIn vía Google | **Hunter** (descubrir) → **FullEnrich** (email + teléfono) | **Hunter → FullEnrich** |
| RUT (Chile) | ❌ | ❌ | ✅ proveedor configurable |
| Titular + rep. legal (SEIA) | ❌ | ❌ | ✅ registro público (gratis, sin clave) |
| Descripción de empresa | ❌ | ✅ **Claude** (Haiku) | ❌ |
| Calificación ICP / ajuste | ❌ | ✅ **Claude** (Sonnet) con tus clientes como referencia | ❌ |
| Costo | Gratis | APIs de pago (ver abajo) | APIs de pago (sólo las que uses) |
| Fiabilidad | Frágil (bloqueos, CAPTCHAs) | Alta (APIs oficiales) | Alta (APIs oficiales) |
| Claves requeridas | Ninguna | Google Places, Hunter, FullEnrich, Anthropic | Google Places, Hunter, FullEnrich, RUT |

**¿Cuál usar?** La **v3** cuando **ya tienes la lista de empresas** (p. ej. un listado del SEIA) y sólo
necesitas **rellenar los datos que faltan** (RUT, web, contactos y, gratis, el titular + representante
legal del SEIA con su contacto). La **v2** para descubrir empresas nuevas desde cero con descripción y
calificación de ajuste. La **v1** como alternativa gratuita o para una exploración rápida sin claves.

## Documentación

[`docs/MODELOS.md`](docs/MODELOS.md) describe cada modelo, herramienta y módulo del sistema, cómo adaptarlo
a un nuevo rubro y cómo portarlo a otro LLM.

## Inicio rápido (v2)

```bash
cd v2-leadgen
pip install -r requirements.txt
cp .env.example .env          # completa tus claves de API
python cli.py --rubro logistica --comuna "Pudahuel, Santiago" --max 50 \
    --clientes clients/clientes.csv
```

## Inicio rápido (v3 — completar una planilla)

```bash
cd v3-enrich
pip install -r requirements.txt
python cli.py --entrada ejemplo_planilla.csv   # crea el .env la 1ª vez; pega tus claves y reintenta
python cli.py --entrada gtc_leads.xlsx --salida gtc_leads_completa.xlsx
```

## Inicio rápido (v1)

```bash
cd v1-scraping
pip install -r requirements.txt
scrapling install
python procentro_leads.py --rubro logistica --max 30
```
