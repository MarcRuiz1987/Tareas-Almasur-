# Tareas-Almasur — Generación de leads

Herramienta para buscar empresas de un rubro, obtener sus contactos y una descripción, y **refinar si
encajan o no con el perfil de las empresas que buscas**, retroalimentándose de tu cartera de clientes
actuales.

El proyecto tiene **dos versiones que conviven** y se ejecutan de forma independiente:

| | **v1 — scraping (gratuita)** | **v2 — herramientas de pago (mejorada)** |
|---|---|---|
| Carpeta | [`v1-scraping/`](v1-scraping/) | [`v2-leadgen/`](v2-leadgen/) |
| Descubrimiento | Scraping de Google Maps (Scrapling) | **Google Places API** (oficial, estable) |
| Contactos | Regex sobre el sitio + LinkedIn vía Google | **Hunter** (descubrir) → **FullEnrich** (email + teléfono) |
| Descripción de empresa | ❌ | ✅ **Claude** (Haiku) |
| Calificación ICP / ajuste | ❌ | ✅ **Claude** (Sonnet) con tus clientes como referencia |
| Costo | Gratis | APIs de pago (ver abajo) |
| Fiabilidad | Frágil (bloqueos, CAPTCHAs) | Alta (APIs oficiales) |
| Claves requeridas | Ninguna | Google Places, Hunter, FullEnrich, Anthropic |

**¿Cuál usar?** La **v2** para trabajo serio: datos confiables, descripción y calificación de ajuste.
La **v1** como alternativa gratuita o para una exploración rápida sin claves.

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

## Inicio rápido (v1)

```bash
cd v1-scraping
pip install -r requirements.txt
scrapling install
python procentro_leads.py --rubro logistica --max 30
```
