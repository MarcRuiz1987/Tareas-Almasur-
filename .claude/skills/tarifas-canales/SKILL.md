---
name: tarifas-canales
description: >-
  Rate shopping de tarifas públicas (vista de cliente) usando los conectores MCP de
  viajes (Booking, Trivago, Tripadvisor, Expedia) para los hoteles de
  config/tarifas-publicas.yaml, y arma una tabla comparativa en reports/. Úsalo cuando
  el usuario pida "comparar tarifas", "rate shopping", "tarifas de la competencia" o el
  monitoreo de tarifas por canal.
---

# Skill: Tarifas por canal (rate shopping vía MCP)

Captura la **tarifa pública (vista de cliente)** de los hoteles propios y de la
competencia usando los **conectores MCP de viajes** —datos estructurados, sin scraping,
sin anti-bot ni problemas de ToS— y produce una tabla comparativa.

## Conectores MCP (vía principal)

Refiérete a ellos por su **nombre base** (el prefijo del servidor MCP cambia por sesión):

| Fuente | Tool | Uso |
|---|---|---|
| **Booking** | `accommodations_search` | Precio exacto por hotel/fecha/ocupación. Usa `hotel_names` para un hotel concreto; respeta `currency` (devuelve CLP). |
| **Trivago** | `trivago-search-suggestions` → `trivago-accommodation-radius-search` (o `-accommodation-search`) | **Set competitivo + CANAL/OTA de cada precio** (paridad). Radius search alrededor de las coordenadas del hotel propio. |
| **Tripadvisor** | `hotel_details` (un hotel) · `compare_hotels` (varios) | Precio en vivo + rating/reviews. `includePricing: true`, `pricingMode: QUICK`. |
| **Expedia-like** | `search_hotels` (gateway) | Alternativa/validación; ordena por más barato. |

> No es obligatorio llamar a las cuatro. Para la tarifa del **hotel propio** basta
> **Booking** (es la más exacta y en CLP). Para **competencia/paridad** usa **Trivago**.
> Tripadvisor/Expedia sirven para validar o enriquecer (reviews, segundo precio).

## Insumos

- `config/tarifas-publicas.yaml` — hoteles propios (nombre, coordenadas, ids),
  competidores, fechas (`offsets_dias`), ocupaciones y `moneda` objetivo (CLP).
- `config/perfil.yaml` — idioma/zona horaria.

## Pasos

1. **Carga config.** Lee `config/perfil.yaml` y `config/tarifas-publicas.yaml`.
   Calcula los check-in/out: por cada `offset` en `offsets_dias`, `check_in = hoy + offset`
   (zona America/Santiago) y `check_out = check_in + noches`.

2. **Tarifa de cada hotel propio (Booking).** Para cada hotel de `hoteles_propios` y cada
   fecha/ocupación, llama `accommodations_search` con `hotel_names: [nombre_busqueda]`,
   `checkin_date`, `checkout_date`, `number_of_adults`, `number_of_rooms`,
   `currency: CLP`, `user_country_code: cl`, `user_locale: es-cl`. Toma `price.book` y
   `price.currency`.

3. **Set competitivo y paridad (Trivago).** Para cada hotel propio con `coordenadas`,
   usa `trivago-accommodation-radius-search` (lat, lon, `radius` = `radio_competencia_km`
   en metros, arrival/departure, adults, rooms). Por cada alojamiento devuelto guarda
   `accommodation_name`, `price_per_night`, **`advertisers` (el canal/OTA)**, `currency`,
   `review_rating`. Si no hay coordenadas, usa `trivago-search-suggestions` con la ciudad
   para obtener `ns`/`id` y luego `trivago-accommodation-search`.

4. **Competidores explícitos (opcional).** Para los de `competidores`, usa
   `accommodations_search` (`hotel_names`) o `compare_hotels` de Tripadvisor
   (`locations: [...]`, mínimo 2) para una comparación directa con el hotel propio.

5. **Normaliza moneda.** La moneda objetivo es CLP. Booking suele devolver CLP; Trivago
   puede devolver EUR y Tripadvisor USD. Convierte a CLP con un tipo de cambio razonable
   (puedes obtenerlo con `WebSearch`/`WebFetch`) y **registra siempre la moneda de origen**
   en la columna `moneda_origen` para trazabilidad.

6. **Escribe el CSV** `reports/YYYY-MM-DD-tarifas.csv` con estas columnas (las consume
   `scripts/generar-tabla.py`):

   `fuente,hotel,propio,canal,check_in,check_out,ocupacion,tarifa,moneda,tarifa_clp,moneda_origen,rating,url,estado`

   - `fuente`: booking | trivago | tripadvisor | expedia
   - `propio`: si | no
   - `canal`: el OTA/anunciante (relevante en filas de Trivago; vacío en Booking directo)
   - `estado`: ok | sin_precio | error

7. **Genera la tabla.** Ejecuta:
   `python3 scripts/generar-tabla.py reports/YYYY-MM-DD-tarifas.csv`
   → `reports/YYYY-MM-DD-tarifas.xlsx` (resalta la tarifa más baja por hotel/fecha).

8. **(Opcional) Gráfico.** Si Marcelo lo pide, arma una infografía con el **MCP de Canva**
   a partir de los datos.

9. **Resumen** en `reports/YYYY-MM-DD-tarifas.md`:
   - Tarifa del/los hotel(es) propio(s) por fecha.
   - **Paridad:** ¿el precio propio coincide entre canales? ¿algún OTA lo muestra distinto?
   - **Posición vs competencia:** por encima/debajo y por cuánto.
   - Fuentes/fechas sin dato y por qué.

## Reglas

- Solo lectura: ninguna reserva ni acción saliente. Es monitoreo de tarifas públicas.
- Idioma es-CL; fechas en zona America/Santiago.
- Si un conector falla o no está disponible en la sesión, regístralo y continúa con los
  demás. **Respaldo:** si NINGÚN MCP de hoteles está disponible, usa
  `scripts/scrape-tarifas.py` (Playwright, vista pública) con las URLs de
  `plataformas.*` — ver nota de uso responsable en su encabezado y en el README.

## Requisitos

- Conectores MCP de viajes activos en la sesión (Booking/Trivago/Tripadvisor/Expedia).
- `scripts/generar-tabla.py` requiere `openpyxl` (`pip install -r scripts/requirements.txt`).
