# Tareas-Almasur · Stack de Automatización Diaria

Base de operaciones de un asistente diario para **Marcelo Ruiz** (Gerente Comercial y de
Tecnología, **Inversiones Almasur**). Orquesta los conectores de Claude Code (Asana,
Microsoft 365, web, Canva) mediante **Skills** reutilizables (a demanda) y **prompts
programados** (automáticos), y deja un registro versionado de los reportes en `reports/`.

> Repositorio **exclusivamente laboral**. Salidas en **español de Chile (es-CL)**, zona
> horaria **America/Santiago**.

## Cómo está organizado

```
CLAUDE.md            Contexto + reglas que se cargan en cada sesión.
config/              Fuente de verdad (YAML): perfil, proyectos Asana, destinatarios,
                     sitios web, tarifas públicas. Editar aquí, no en los Skills.
.claude/skills/      Rutinas (playbooks) que invoca el usuario o las sesiones programadas.
.claude/settings.json  Allowlist de herramientas de solo lectura + hook de conectores.
prompts/             Prompts cortos para las Scheduled sessions (invocan los Skills).
scripts/             Código propio: crear-borrador (Graph), scrape-tarifas (Playwright),
                     generar-tabla (openpyxl).
reports/             Salidas generadas: YYYY-MM-DD-<rutina>.md / .csv / .xlsx.
```

## Las rutinas (Skills)

| Skill | Qué hace | Estado |
|---|---|---|
| `reporte-matinal` | Pendientes de Asana (míos + vencidos/del día) + correos del día. Resumen priorizado por área en `reports/`. **Solo lectura.** | ✅ Listo |
| `triage-correo` | Correo de Outlook de últimas 24 h: muestra **solo lo accionable** + respuesta sugerida. No escribe nada. | ✅ Listo |
| `tarifas-canales` | *Rate shopping* público vía **MCP de viajes** (Booking/Trivago/Tripadvisor/Expedia) → CSV + Excel comparativo y paridad por canal. | ✅ Listo (requiere configurar hoteles) |
| `reporte-terceros` | Arma un reporte y lo deja como **borrador** en Outlook (nunca envía). | 🟡 Andamiaje (definir reportes) |
| `descarga-web` | Descarga datos de sitios públicos; deriva a Playwright los que tengan login/JS. | 🟡 Andamiaje (definir sitios) |

**Invocación a demanda:** en una sesión, escribe `/reporte-matinal`, `/triage-correo`,
`/tarifas-canales`, etc.

## Regla de oro (seguridad)

**Nunca se ejecutan acciones de escritura o salientes sin confirmación**, salvo que el
Skill lo autorice. En concreto: el correo solo se deja en **borrador** en Outlook (jamás
se envía solo); las escrituras en Asana (`create_tasks`, `update_tasks`,
`create_project_status_update`) siempre piden vista previa y confirmación.

## Puesta en marcha

### 1. Dependencias de los scripts

```bash
pip install -r scripts/requirements.txt
playwright install chromium    # solo para scrape-tarifas.py
```

### 2. Sesiones programadas (Scheduled sessions)

En **Claude Code en la web** (https://code.claude.com/docs/en/claude-code-on-the-web):

1. Abre este repositorio y la branch de trabajo.
2. Crea una *Scheduled session* y apúntala al prompt deseado, p. ej.
   `prompts/reporte-matinal.md` (lun–vie 08:00 CLT) o `prompts/tarifas-canales.md`.
3. El resultado se entrega y los reportes se commitean en `reports/`.

Las herramientas de **solo lectura** (búsquedas Asana/Outlook, WebFetch/WebSearch) y la
ejecución de los scripts de scraping/Excel están en el allowlist de
`.claude/settings.json` para que las sesiones no se bloqueen pidiendo permisos. La
creación de borradores (`crear-borrador.py`) está en `ask` para que siempre confirmes.

### 3. Borradores en Outlook (Microsoft Graph) — configuración única

`scripts/crear-borrador.py` crea el correo como **borrador** (`isDraft=true`, vía
`POST /users/{mailbox}/messages`). **Nunca** llama a `/sendMail`.

Registro de aplicación en **Microsoft Entra ID** (Azure AD):

1. *Azure Portal → Microsoft Entra ID → App registrations → New registration.*
2. En **API permissions** agrega **Microsoft Graph → Application permissions →
   `Mail.ReadWrite`** y otorga **Grant admin consent**.
   - Se usa `Mail.ReadWrite` (no `Mail.Send`) a propósito: permite crear/editar
     borradores pero **no enviar**. El envío queda 100% en manos de Marcelo.
3. En **Certificates & secrets** crea un *client secret*.
4. Carga estas variables como **secretos del environment** de Claude Code web (no como
   archivo, no se commitean): `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET`,
   `MAILBOX=Marcelo.ruiz@ialmasur.cl`. Ver nombres en `scripts/.env.example`.

Documentación oficial: consultable con el MCP de **Microsoft Learn** al implementar.

Prueba:

```bash
python3 scripts/crear-borrador.py --asunto "Prueba" --para Marcelo.ruiz@ialmasur.cl \
  --cuerpo "Hola, esto es un borrador de prueba." --formato markdown
# Debe aparecer en la carpeta "Borradores" de Outlook, sin enviarse.
```

### 4. Rate shopping de tarifas públicas (vía MCP de viajes)

La vía **principal** usa los **conectores MCP de viajes** —datos estructurados, sin
scraping, sin anti-bot ni problemas de ToS. Validado con Almasur Providencia: Booking
devuelve la tarifa exacta en CLP; Trivago entrega el set competitivo **con el canal/OTA de
cada precio**; Tripadvisor añade precio + reviews.

1. Completa `config/tarifas-publicas.yaml`: hoteles propios (nombre de búsqueda,
   coordenadas, ids), competidores, fechas (`offsets_dias`) y ocupaciones.
2. En una sesión con los MCP de viajes activos, invoca el Skill **`/tarifas-canales`** (o
   programa `prompts/tarifas-canales.md`). El Skill:
   - consulta Booking/Trivago/Tripadvisor, normaliza moneda a CLP (registrando la de
     origen), escribe `reports/YYYY-MM-DD-tarifas.csv`, y
   - ejecuta `generar-tabla.py` para el `.xlsx` y arma el resumen de paridad.

```bash
# El Excel comparativo se genera desde el CSV que produce el Skill:
python3 scripts/generar-tabla.py reports/AAAA-MM-DD-tarifas.csv   # → .xlsx con formato
```

**Conectores MCP** (nombres base; el prefijo del servidor cambia por sesión): Booking
`accommodations_search`; Trivago `trivago-search-suggestions` +
`trivago-accommodation-radius-search`; Tripadvisor `hotel_details` / `compare_hotels`;
Expedia-like `search_hotels`.

#### Respaldo: Playwright (solo si no hay MCP de hoteles)

Si en la sesión **no** hay conectores de viajes, existe `scripts/scrape-tarifas.py`
(Playwright, vista pública) que lee las URLs de `plataformas.*` del config:

```bash
pip install -r scripts/requirements.txt && playwright install chromium
python3 scripts/scrape-tarifas.py     # → reports/YYYY-MM-DD-tarifas.csv
```

**Uso responsable del respaldo:** Booking/Expedia detectan automatización (captcha,
bloqueos, límites). El scraper respeta pausas, reintenta y, si lo bloquean, marca la fila
como `bloqueado` y sigue. Úsalo a baja frecuencia y conforme a los términos de cada sitio.
Los selectores de precio pueden requerir ajuste si cambia el DOM (depura con `--headful`).

## Estado y próximos pasos

- Completar `config/destinatarios.yaml` y el flujo de `reporte-terceros` cuando se
  definan los reportes a terceros (insumos, destinatarios, formato).
- Completar `config/sitios-web.yaml` para activar `descarga-web`.
- Cargar los secretos de Graph para habilitar los borradores en Outlook.
