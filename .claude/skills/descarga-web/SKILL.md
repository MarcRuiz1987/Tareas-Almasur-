---
name: descarga-web
description: >-
  [ANDAMIAJE — pendiente de definir sitios] Descarga información de los sitios web
  recurrentes listados en config/sitios-web.yaml, consolida en una tabla/resumen en
  reports/. Usa WebFetch para sitios públicos estáticos y deriva a Playwright los que
  tienen login/JS. Úsalo cuando el usuario pida "descargar/actualizar datos web".
---

# Skill: Descarga de información web

> **Estado: ANDAMIAJE.** Estructura lista; faltan por definir los sitios reales en
> `config/sitios-web.yaml`.

Recorre los sitios configurados y consolida la información en `reports/`.

## Insumos

- `config/sitios-web.yaml` — sitios con `url`, `extraer`, `login`, `js_pesado`,
  `frecuencia`.

## Pasos

1. **Carga** `config/sitios-web.yaml` y `config/perfil.yaml`.

2. **Por cada sitio:**
   - Si `login: false` y `js_pesado: false` → usa **`WebFetch`** (y `WebSearch` si hace
     falta localizar la página) para extraer lo indicado en `extraer`.
   - Si `js_pesado: true` (sin login) → derívalo a un script **Playwright** (mismo
     patrón que `scripts/scrape-tarifas.py`). Para tarifas de Booking/Expedia usa
     directamente el Skill `tarifas-canales`.
   - Si `login: true` → **no** es accesible por `WebFetch`. Márcalo como pendiente y
     anótalo; requiere un script Playwright dedicado con credenciales en secretos del
     environment (patrón a extender). `TODO`.

3. **Consolida** los datos extraídos en una tabla/resumen.

4. **Entrega.** Guarda en `reports/YYYY-MM-DD-descarga-web.md` (y `.csv` si conviene una
   tabla). Lista al final los sitios que **no** se pudieron leer y por qué.

## Reglas

- Solo lectura; no envía ni escribe nada externo.
- Respeta los términos de cada sitio; frecuencia razonable.
- Idioma es-CL. Si un sitio falla, repórtalo y continúa con el resto.

## TODO para activar

- [ ] Completar `config/sitios-web.yaml` con los sitios reales.
- [ ] Para sitios con login, definir el script Playwright dedicado y sus secretos.
