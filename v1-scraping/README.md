# v1 — Generación de leads por scraping (gratuita)

Versión original del generador de leads. **No requiere claves de pago.** Usa
[Scrapling](https://github.com/D4Vinci/Scrapling) (Playwright/Chromium) para raspar Google Maps,
los sitios web de las empresas y perfiles públicos de LinkedIn vía Google.

> Si buscas calidad de datos, descripción de empresa y calificación de ajuste (ICP) con
> retroalimentación desde tus clientes, usa la **v2** (`../v2-leadgen/`), que reemplaza el scraping
> por APIs de pago. Esta v1 se conserva como alternativa gratuita y reproducible.

## Qué hace

- **`procentro_leads.py`** — descubre empresas en Google Maps por 7 rubros, enriquece contactos
  desde el sitio web (regex) y busca un contacto nominado en LinkedIn vía Google. Hace scoring,
  deduplica y exporta un CSV al Escritorio.
- **`scrape_leads_logistica.py`** — versión más simple, sólo logística, sin enriquecimiento.

## Limitaciones conocidas

- El scraping de Google Maps / LinkedIn es **frágil** (cambios de HTML, CAPTCHAs, bloqueos) y depende
  de los términos de servicio de cada sitio.
- La extracción de email/contacto por regex tiene **cobertura y precisión limitadas**.
- No genera descripción de empresa ni calificación de ajuste al perfil de cliente.

## Instalación

```bash
pip install -r requirements.txt
scrapling install   # descarga Chromium (Patchright + Playwright)
```

Para usar Scrapling como servidor MCP en Claude Desktop (Windows), ver `scrapling-mcp-setup.md`.

## Uso

```bash
# Todos los rubros, 50 leads c/u, con enriquecimiento web + LinkedIn
python procentro_leads.py

# Un solo rubro, 30 leads
python procentro_leads.py --rubro logistica --max 30

# Sólo descubrimiento de empresas (rápido, sin enriquecimiento)
python procentro_leads.py --solo-empresas

# Scraping simple de logística en otra ciudad
python scrape_leads_logistica.py --ciudad "Montevideo" --max 30
```

El CSV resultante se guarda en el Escritorio (`~/Desktop/leads-*.csv`).
