# CLAUDE.md — Stack de Automatización Diaria · Inversiones Almasur

Este repositorio es la **base de operaciones** de un asistente diario para Marcelo Ruiz.
Cuando trabajes en una sesión sobre este repo, sigue este contexto y estas reglas.

## Quién

- **Usuario:** Marcelo Ruiz — `Marcelo.ruiz@ialmasur.cl`
- **Cargo:** Gerente Comercial y de Tecnología
- **Empresa:** **Inversiones Almasur** (www.ialmasur.cl), holding de **rentas
  inmobiliarias** con participación en:
  - Hotelería — **Almasur Hoteles**
  - Estacionamientos — **Bluepark**
  - Bodegas industriales — **Procentro**
  - Concesiones y licitaciones — **Centro Metropolitano de Vehículos Retirados de
    Circulación** y **Movilidad Urbana**
  - Edificios **multifamily**
  - **Rentas comerciales**
- El foco diario cruza lo **comercial (hotelería)** y **tecnología**.
- Este repositorio es **exclusivamente laboral**.

## Salida (idioma y formato)

- Responde y redacta **en español de Chile (es-CL)**.
- Zona horaria: **America/Santiago (CLT)**. Las fechas de los reportes usan ese huso.
- Los reportes generados se guardan en `reports/` con el patrón `YYYY-MM-DD-<rutina>.md`
  (y `.csv` / `.xlsx` cuando aplique).

## Herramientas disponibles (MCP y nativas)

Estos conectores deben estar activos en la sesión:

- **Asana** (lectura **y** escritura): `get_my_tasks`, `get_tasks`, `search_tasks`,
  `get_projects`, `get_project`, `create_tasks`, `update_tasks`,
  `create_project_status_update`, `get_me`.
- **Microsoft 365** (solo lectura/búsqueda): `outlook_email_search`,
  `outlook_calendar_search`, `find_meeting_availability`, `chat_message_search` (Teams),
  `sharepoint_search`, `sharepoint_folder_search`, `read_resource`.
- **Web nativo:** `WebFetch`, `WebSearch` (solo HTML estático / público).
- **Viajes/hoteles (MCP)** — para *rate shopping* de tarifas públicas (vista de cliente),
  sin scraping. Referidos por su **nombre base** (el prefijo del servidor cambia por sesión):
  - **Booking** → `accommodations_search` (precio exacto por hotel/fecha; respeta `currency`).
  - **Trivago** → `trivago-search-suggestions`, `trivago-accommodation-search`,
    `trivago-accommodation-radius-search` (metabuscador: precio **y canal/OTA** por hotel).
  - **Tripadvisor** → `hotel_details`, `compare_hotels`, `search_hotels` (precio + reviews).
  - **Expedia-like** → `search_hotels` (gateway).
- **Canva** (MCP) — para gráficos/infografías de reportes.
- **Microsoft Learn docs** (MCP) — para consultar documentación oficial al implementar.
- **GitHub** (MCP) — operaciones de repositorio.

Scripts propios (en `scripts/`):

- `crear-borrador.py` — crea correos como **BORRADOR** en Outlook vía Microsoft Graph.
- `generar-tabla.py` — openpyxl, arma Excel con formato desde un CSV.
- `scrape-tarifas.py` — **respaldo** Playwright (sin login) para tarifas públicas de
  Booking/Expedia, solo si los MCP de viajes no están disponibles en la sesión.

## Fuente de verdad: `config/`

No cablees datos en los Skills. Lee siempre de `config/`:

- `config/perfil.yaml` — datos del usuario/empresa, zona horaria, idioma.
- `config/proyectos-asana.yaml` — proyectos Asana relevantes (GIDs reales).
- `config/destinatarios.yaml` — reportes a terceros (a quién, asunto, formato, frecuencia).
- `config/sitios-web.yaml` — sitios recurrentes a descargar.
- `config/tarifas-publicas.yaml` — hoteles/competidores a monitorear en Booking/Expedia.

## Skills (rutinas) — en `.claude/skills/`

- `reporte-matinal` — resumen priorizado de pendientes (Asana) + correos del día (Outlook).
- `triage-correo` — clasifica el correo de las últimas 24 h y sugiere respuestas.
- `reporte-terceros` — arma un reporte y lo deja como **borrador** en Outlook (plantilla).
- `descarga-web` — extrae datos de sitios públicos (deriva a Playwright si hay login/JS).
- `tarifas-canales` — *rate shopping* público vía MCP de viajes (Booking/Trivago/
  Tripadvisor/Expedia) → tabla comparativa de tarifas y paridad por canal.

## Regla de oro (seguridad de acciones)

> **Nunca ejecutes acciones de escritura o salientes sin confirmación explícita del
> usuario**, salvo que el Skill en curso lo autorice de forma explícita.

Esto incluye:

- **Asana:** `create_tasks`, `update_tasks`, `create_project_status_update` → siempre
  muestra una vista previa y pide confirmación antes de ejecutar.
- **Correo:** solo se crean **borradores** en Outlook (`crear-borrador.py`). **Nunca**
  se envía un correo automáticamente. El usuario revisa y envía a mano.
- Las herramientas de **solo lectura** (búsquedas Asana/Outlook/Teams/SharePoint,
  `WebFetch`, `WebSearch`) sí pueden usarse sin pedir permiso (están en el allowlist de
  `.claude/settings.json`).

## Convenciones

- Reportes legibles, concisos, con encabezados y agrupados por **proyecto/área** y luego
  por **urgencia** cuando aplique.
- Marca claramente lo **vencido** y lo **urgente**.
- Si un conector o sitio falla, repórtalo en el output y continúa con el resto.
