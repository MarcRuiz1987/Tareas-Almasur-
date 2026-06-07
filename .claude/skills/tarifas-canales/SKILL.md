---
name: tarifas-canales
description: >-
  Rate shopping de las tarifas PÚBLICAS (vista de cliente, sin login) en Booking.com
  y Expedia para los hoteles de config/tarifas-publicas.yaml, y arma una tabla
  comparativa en reports/. Úsalo cuando el usuario pida "comparar tarifas", "rate
  shopping", "tarifas de la competencia" o el monitoreo diario de tarifas por canal.
---

# Skill: Tarifas por canal (rate shopping público)

Captura la **tarifa pública mostrada al cliente** en Booking.com y Expedia (sin login,
sin extranet) para los hoteles configurados, y produce una tabla comparativa.

## Insumos

- `config/tarifas-publicas.yaml` — hoteles (propios y/o competidores), URLs por
  plataforma, fechas/ocupaciones a consultar y parámetros de cortesía (pausas).

## Pasos

1. **Carga** `config/perfil.yaml` y `config/tarifas-publicas.yaml`.

2. **Captura tarifas.** Ejecuta `scripts/scrape-tarifas.py`, que con **Playwright**
   (Chromium headless, **sin login**) navega la vista pública de cada hotel/plataforma
   para cada combinación de fecha y ocupación, y escribe un CSV:
   `reports/YYYY-MM-DD-tarifas.csv` (columnas: plataforma, hotel, propio, check_in,
   check_out, ocupacion, habitacion, tarifa, moneda, url, estado).

3. **Genera la tabla.** Ejecuta `scripts/generar-tabla.py` sobre ese CSV para producir
   `reports/YYYY-MM-DD-tarifas.xlsx` con formato (resalta tarifa más baja por
   hotel/fecha, compara propio vs competencia).

4. **(Opcional) Gráfico.** Si Marcelo lo pide, arma un gráfico con el **MCP de Canva**
   a partir de los datos.

5. **Resumen.** Escribe `reports/YYYY-MM-DD-tarifas.md` con los hallazgos clave:
   diferencias de paridad, dónde estamos por encima/debajo de la competencia, y sitios
   que no se pudieron leer (bloqueos/anti-bot).

## Reglas

- **Solo vista pública.** Nunca login ni extranet.
- Uso **responsable y a baja frecuencia**; respeta pausas (`consulta.pausa_segundos`) y
  los términos de cada sitio. Si un sitio bloquea (captcha/anti-bot), regístralo en el
  CSV con `estado=bloqueado` y continúa con el resto.
- Idioma es-CL; fechas en zona America/Santiago.

## Requisitos técnicos

- Dependencias: `playwright`, `openpyxl` (ver `scripts/requirements.txt`).
- Una vez en el environment: `playwright install chromium` (ver README).
