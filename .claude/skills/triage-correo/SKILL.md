---
name: triage-correo
description: >-
  Hace triage del correo de Outlook de las últimas 24 horas: muestra SOLO lo
  accionable, lo resume y sugiere una respuesta para cada hilo. No crea tareas ni
  borradores automáticamente. Úsalo cuando el usuario pida "revisar correo",
  "triage", "qué correos necesitan respuesta" o similar.
---

# Skill: Triage de correo

Revisa el correo reciente y deja a la vista **solo lo que requiere acción**, con un
resumen y una respuesta sugerida por hilo. **No** escribe en Asana ni crea borradores
de forma automática (eso queda a decisión del usuario).

## Insumos

- **Outlook**, últimas 24 horas. (Por ahora **sin** Teams ni SharePoint.)

## Pasos

1. **Carga contexto.** Lee `config/perfil.yaml` (idioma es-CL, zona horaria).

2. **Trae el correo.** Llama `outlook_email_search` acotado a las últimas 24 h
   (`afterDateTime` = ahora − 24 h, en CLT). Prioriza no leídos.

3. **Clasifica cada hilo:**
   - **Requiere acción** — pide una respuesta, decisión, aprobación o tiene un plazo.
   - **Para leer** — relevante pero sin acción inmediata.
   - **Informativo** — newsletters, notificaciones, copias FYI.

4. **Filtra.** **Oculta** lo Informativo. Muestra los "Requiere acción" y, de forma
   colapsada/breve, los "Para leer".

5. **Por cada "Requiere acción":**
   - Resume el hilo en 1–2 líneas (quién pide qué y para cuándo).
   - **Sugiere una respuesta** (borrador de texto, en es-CL), lista para que Marcelo
     copie/ajuste. No la envíes ni la guardes como borrador en Outlook.

6. **Entrega.** Muestra todo en pantalla. (Opcional: si Marcelo lo pide explícitamente,
   se puede guardar copia en `reports/YYYY-MM-DD-triage.md`.)

## Formato de salida (pantalla)

```markdown
# Triage de correo — últimas 24 h ({fecha})

## ✅ Requiere acción ({n})
### {remitente} — {asunto}
- **Qué piden:** {resumen}
- **Plazo:** {si aplica}
- **Respuesta sugerida:**
  > {texto sugerido en es-CL}

## 👀 Para leer ({n})
- {remitente} — {asunto}: {1 línea}

_(Informativos ocultos: {n})_
```

## Reglas

- Idioma **es-CL**.
- **No** crear tareas en Asana ni borradores en Outlook automáticamente. Si Marcelo
  pide convertir un correo en tarea o en borrador, **pídele confirmación** y recién ahí
  usa `create_tasks` (Asana) o el Skill `reporte-terceros` / `scripts/crear-borrador.py`.
- Si Outlook falla, indícalo y continúa.
