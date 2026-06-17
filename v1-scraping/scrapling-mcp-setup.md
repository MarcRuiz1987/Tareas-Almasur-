# Scrapling MCP — Setup para extracción de listas de clientes

**Plataforma:** Windows  
**Ejecución:** Manual (en tu máquina local)  
**Librería:** [Scrapling by D4Vinci](https://github.com/D4Vinci/Scrapling) v0.4.9  
**Objetivo:** Usar Scrapling como servidor MCP en Claude Desktop para sacar listas de clientes desde directorios web.

---

## Pasos a ejecutar en tu máquina (Windows)

### Paso 1 — Verificar Python y uv

Abre **PowerShell** (o CMD) y ejecuta:

```powershell
python --version   # Necesitas 3.10+
uv --version
```

**Si falta Python 3.11+:**
```powershell
winget install Python.Python.3.11
```
O descárgalo desde https://www.python.org/downloads/ (marca "Add to PATH" durante la instalación).

**Si falta uv:**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
Cierra y reabre PowerShell después de instalar uv.

---

### Paso 2 — Instalar Scrapling

```powershell
uv pip install "scrapling[all]"
```

Si da error de entorno virtual:
```powershell
uv pip install "scrapling[all]" --system
```

Verifica:
```powershell
scrapling --version
# Esperado: Scrapling, version 0.4.9
```

---

### Paso 3 — Instalar navegadores

```powershell
scrapling install
```

Esto descarga e instala Chromium (Patchright + Playwright). Si falla alguno individualmente:
```powershell
python -m patchright install chromium
python -m playwright install chromium
```

---

### Paso 4 — Comando MCP confirmado

El comando correcto (verificado en v0.4.9):

```powershell
scrapling mcp          # stdio — para Claude Desktop
scrapling mcp --http   # HTTP stream — para uso remoto
```

No existe `scrapling-mcp.exe` separado — todo va por `scrapling mcp`.

---

### Paso 5 — Configurar Claude Desktop

La ubicación del archivo en Windows:
```
%APPDATA%\Claude\claude_desktop_config.json
```

Para abrirlo rápido, pega esto en el Explorador de archivos o en Ejecutar (Win+R):
```
%APPDATA%\Claude\claude_desktop_config.json
```

Primero encuentra la ruta exacta de scrapling:
```powershell
where scrapling
```
Resultado típico en Windows:
```
C:\Users\TuUsuario\AppData\Local\Programs\Python\Python311\Scripts\scrapling.exe
```

**Contenido del archivo** (si no existe, créalo):
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

Si `scrapling` no está en PATH (el `where scrapling` no encontró nada), usa la ruta completa con barras invertidas escapadas:
```json
{
  "mcpServers": {
    "scrapling": {
      "command": "C:\\Users\\TuUsuario\\AppData\\Local\\Programs\\Python\\Python311\\Scripts\\scrapling.exe",
      "args": ["mcp"]
    }
  }
}
```

**Si ya tienes otros MCPs configurados**, agrega solo el bloque `"scrapling"` dentro de `"mcpServers"`, sin tocar lo demás:
```json
{
  "mcpServers": {
    "otro-mcp-existente": {
      "command": "...",
      "args": ["..."]
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

Crea un archivo `test_scrapling.py` y ejecútalo:

```python
from scrapling.fetchers import Fetcher, StealthyFetcher

# Sin browser (rápido)
page = Fetcher().get('https://es.wikipedia.org/wiki/Odontolog%C3%ADa')
print('Status:', page.status)
print('Título:', page.css('h1')[0].text)

# Con browser stealth (para sitios anti-bot)
page2 = StealthyFetcher().fetch(
    'https://www.doctoralia.com.mx/buscar?filters[0]=doctor&q=dentista&loc=Ciudad+de+Mexico',
    headless=True,
    network_idle=True
)
nombres = page2.css('[class*="doctor-name"], h3 a')[:3]
for n in nombres:
    print('-', n.text.strip())
```

```powershell
python test_scrapling.py
```

---

### Paso 7 — Usar desde Claude Desktop

1. **Cierra Claude Desktop completamente** (botón derecho en la bandeja del sistema → Salir)
2. Vuelve a abrirlo
3. Abre una conversación nueva
4. El MCP de Scrapling aparecerá en las herramientas disponibles
5. Prueba con un prompt como:

```
Usa Scrapling para extraer los primeros 10 dentistas de CDMX 
desde Doctoralia. Dame: nombre, especialidad, dirección, teléfono.
```

---

## Fetchers disponibles

| Fetcher | Velocidad | Anti-bot | Requiere browser |
|---------|-----------|----------|-----------------|
| `Fetcher` | ⚡ Rápido | Básico (curl-cffi) | No |
| `StealthyFetcher` | Medio | Alto (Patchright/Chromium) | Sí |
| `DynamicFetcher` | Medio | Estándar (Playwright) | Sí |

Para listas de clientes desde directorios: **`StealthyFetcher`** es la mejor opción.

---

## Notas

- Scrapling 0.4.9 muestra warnings sobre `Fetcher.configure()` — son deprecation warnings, no errores.
- Los buscadores (Google, Bing) pueden bloquear si haces muchas peticiones seguidas. Usa delays entre requests.
- Si el MCP no aparece en Claude Desktop después de reiniciar, verifica que el JSON esté bien formado (sin comas extra, sin comillas simples).
