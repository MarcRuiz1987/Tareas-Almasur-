---
name: reporte-matinal
description: >-
  Genera el reporte matinal de pendientes de Marcelo: lee sus tareas de Asana
  (incluidas vencidas y del día) y los correos del día en Outlook, y produce un
  resumen priorizado agrupado por área. Úsalo al empezar la jornada o cuando el
  usuario pida "reporte matinal", "mis pendientes de hoy" o similar.
---

# Skill: Reporte matinal

Resumen priorizado de pendientes para empezar el día. **Solo para Marcelo**: se
muestra en pantalla y se guarda en `reports/`. **No** envía correo ni escribe nada.

## Insumos

- **Asana** (mis tareas + vencidas/del día) sobre los proyectos de
  `config/proyectos-asana.yaml`.
- **Outlook** (correos del día / no leídos que requieren acción).
- **No** se consulta Calendario ni Teams en esta rutina.

## Pasos

1. **Carga el contexto.** Lee `config/perfil.yaml` (zona horaria America/Santiago,
   idioma es-CL) y `config/proyectos-asana.yaml` (proyectos y sus áreas).

2. **Tareas asignadas.** Llama `get_my_tasks` para obtener las tareas abiertas de
   Marcelo (GID en `perfil.yaml: usuario.asana_gid`). Quédate con las incompletas.

3. **Tareas vencidas / del día por proyecto.** Para cada proyecto de
   `proyectos-asana.yaml`, usa `search_tasks` (o `get_tasks` del proyecto) para
   detectar tareas con `due_on` <= hoy (vencidas y que vencen hoy). Crúzalas con las de
   `get_my_tasks` para no duplicar.

4. **Correos del día.** Llama `outlook_email_search` acotado a hoy
   (p. ej. `afterDateTime` = inicio del día CLT) y/o no leídos. Identifica los que
   **requieren acción** (preguntas directas, solicitudes, plazos). Resume en una línea
   cada uno; no listes lo meramente informativo.

5. **Prioriza y agrupa.** Arma el reporte agrupado **por área/proyecto**
   (Tecnología, Comercial, Hotel) y, dentro de cada grupo, por urgencia:
   - **🔴 Vencido** — `due_on` < hoy.
   - **🟡 Hoy** — vence hoy o requiere acción hoy.
   - **🟢 Esta semana** — vence en los próximos 7 días.
   Incluye al final una sección **"Correos que requieren acción"**.

6. **Entrega.**
   - Muestra el reporte en pantalla.
   - Guárdalo en `reports/YYYY-MM-DD-matinal.md` (fecha en CLT). Usa el formato de
     abajo.

## Formato de salida (`reports/YYYY-MM-DD-matinal.md`)

```markdown
# Reporte matinal — {fecha larga en es-CL}

## 🔴 Vencido
- **[Área]** {tarea} — venció {fecha} · [Asana]({url})

## 🟡 Hoy
- **[Área]** {tarea} — vence hoy · [Asana]({url})

## 🟢 Esta semana
- **[Área]** {tarea} — vence {fecha} · [Asana]({url})

## 📧 Correos que requieren acción
- {remitente} — {asunto}: {resumen en una línea}

## Resumen
{1-2 líneas: cuántos vencidos, foco sugerido del día}
```

## Reglas

- Idioma **es-CL**, fechas en zona **America/Santiago**.
- Esta rutina es **solo lectura**: no crees ni edites tareas, no redactes borradores.
- Si un conector (Asana u Outlook) falla, indícalo en el reporte y continúa con el resto.
