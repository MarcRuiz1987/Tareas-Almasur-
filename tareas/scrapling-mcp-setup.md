# Scrapling MCP — Setup para extracción de listas de clientes

**Ejecución:** Manual (en tu máquina local)  
**Librería:** [Scrapling by D4Vinci](https://github.com/D4Vinci/Scrapling) v0.4.9  
**Objetivo:** Usar Scrapling como servidor MCP en Claude Desktop para sacar listas de clientes desde directorios web.

---

## Estado de preparación (hecho en servidor remoto)

| Paso | Estado | Notas |
|------|--------|-------|
| Python 3.11.15 | ✅ | Requiere 3.10+ |
| uv 0.8.17 | ✅ | Gestor de paquetes |
| `scrapling[all]` 0.4.9 | ✅ | Con playwright, patchright, curl-cffi |
| Browsers (Playwright/Patchright) | ⚠️ | Requiere tu máquina local (ver Paso 3) |
| Comando MCP confirmado | ✅ | `scrapling mcp` |
| Config Claude Desktop | 📋 | Aplícala tú (ver Paso 5) |

---

## Pasos a ejecutar en tu máquina local (macOS)

### Paso 1 — Verificar Python y uv

```bash
python3 --version   # Necesitas 3.10+
uv --version
```

Si falta Python 3.10+:
```bash
brew install python@3.11
```

Si falta uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

### Paso 2 — Instalar Scrapling

```bash
uv pip install "scrapling[all]"
```

O si no tienes venv activo:
```bash
uv pip install "scrapling[all]" --system
```

Verifica la instalación:
```bash
scrapling --version
# Esperado: Scrapling, version 0.4.9
```

---

### Paso 3 — Instalar navegadores

Este paso **requiere tu máquina local** (el entorno remoto bloquea la descarga desde cdn.playwright.dev).

```bash
scrapling install
```

Esto instala:
- Chromium (vía Patchright — versión anti-detección)
- Chromium (vía Playwright — estándar)
- Camoufox (Firefox anti-fingerprint) si está disponible

Si falla algún browser individualmente, puedes instalar solo el que necesitas:
```bash
python -m patchright install chromium
python -m playwright install chromium
```

---

### Paso 4 — Comando MCP confirmado

El comando correcto (verificado en v0.4.9) es:

```bash
scrapling mcp          # stdio (para Claude Desktop)
scrapling mcp --http   # HTTP stream (para uso remoto)
```

**No existe** `scrapling-mcp` como binario separado — todo va por `scrapling mcp`.

---

### Paso 5 — Configurar Claude Desktop

Abre o crea el archivo:
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Si el archivo ya existe con otros MCPs**, agrega SOLO el bloque `"scrapling"` dentro de `"mcpServers"`:

```json
{
  "mcpServers": {
    "scrapling": {
      "command": "scrapling",
      "args": ["mcp"]
    }
  }
}
```

> Si `scrapling` no está en tu PATH, usa la ruta completa. Encuéntrala con:
> ```bash
> which scrapling
> ```
> Resultado típico en macOS: `/usr/local/bin/scrapling` o `/opt/homebrew/bin/scrapling`

Con ruta absoluta:
```json
{
  "mcpServers": {
    "scrapling": {
      "command": "/usr/local/bin/scrapling",
      "args": ["mcp"]
    }
  }
}
```

Si ya tienes otros MCPs configurados, el archivo se vería así:
```json
{
  "mcpServers": {
    "otro-mcp-existente": {
      "command": "...",
      "args": [...]
    },
    "scrapling": {
      "command": "scrapling",
      "args": ["mcp"]
    }
  }
}
```

---

### Paso 6 — Probar extracción

Prueba básica de funcionamiento (ejecutar en terminal):

```python
# test_scrapling.py
from scrapling.fetchers import Fetcher, StealthyFetcher

# Sin browser (rápido, curl-cffi)
page = Fetcher().get('https://es.wikipedia.org/wiki/Odontolog%C3%ADa')
print('Status:', page.status)
print('Título:', page.css('h1')[0].text)

# Con browser stealth (más potente para sitios anti-bot)
page2 = StealthyFetcher().fetch(
    'https://www.doctoralia.com.mx/buscar?filters[0]=doctor&q=dentista&loc=Ciudad+de+Mexico',
    headless=True,
    network_idle=True
)
nombres = page2.css('[class*="doctor-name"], h3 a')[:3]
for n in nombres:
    print('-', n.text.strip())
```

```bash
python test_scrapling.py
```

---

### Paso 7 — Usar desde Claude Desktop

1. **Reinicia Claude Desktop** completamente (Cmd+Q, no solo cerrar ventana)
2. Abre una conversación nueva
3. Verifica que el MCP aparece en la lista de herramientas disponibles
4. Usa prompts como:

```
Usa Scrapling para extraer los primeros 10 dentistas de CDMX 
desde Doctoralia. Dame: nombre, especialidad, dirección, teléfono.
```

---

## Fetchers disponibles en Scrapling 0.4.9

| Fetcher | Velocidad | Anti-bot | Requiere browser |
|---------|-----------|----------|-----------------|
| `Fetcher` | ⚡ Rápido | Básico (curl-cffi) | No |
| `StealthyFetcher` | 🐢 Medio | Alto (Patchright) | Sí (Chromium) |
| `DynamicFetcher` | 🐢 Medio | Estándar (Playwright) | Sí (Chromium) |

Para listas de clientes desde directorios públicos: **`StealthyFetcher`** es la mejor opción.

---

## Notas técnicas

- Los buscadores (Google, Bing, DuckDuckGo) bloquean IPs de datacenter. En tu máquina local con IP residencial, el scraping de resultados de búsqueda funciona normalmente.
- Scrapling 0.4.9 muestra warnings sobre `Fetcher.configure()` — son deprecation warnings, no errores. El código sigue funcionando.
- Para scraping a escala, considera rotar User-Agents y añadir delays entre requests.
