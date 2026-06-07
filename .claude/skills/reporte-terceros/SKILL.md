---
name: reporte-terceros
description: >-
  [ANDAMIAJE — pendiente de definir insumos y destinatarios] Arma un reporte para
  terceros a partir de Asana y Microsoft 365 y lo deja como BORRADOR en Outlook
  (nunca lo envía). Úsalo cuando el usuario pida preparar/redactar un reporte para
  enviar a alguien.
---

# Skill: Reporte a terceros (BORRADOR en Outlook)

> **Estado: ANDAMIAJE.** La estructura está lista; faltan por definir los insumos, el
> enfoque y los destinatarios de cada reporte en `config/destinatarios.yaml`. Los pasos
> marcados con `TODO` se completan al definir cada reporte.

Reúne datos, redacta el reporte y lo deja como **borrador nativo en Outlook** (carpeta
"Borradores"). **Nunca envía.** Marcelo revisa y envía a mano.

## Insumos

- **Asana** (`get_project`, `get_tasks`, `create_project_status_update` como insumo).
- **Microsoft 365** (búsquedas de Outlook/SharePoint para datos de apoyo).
- `config/destinatarios.yaml` — define a quién, asunto, formato, frecuencia.
- `config/proyectos-asana.yaml` — `reportes_recurrentes` lista candidatos detectados.

## Pasos

1. **Carga contexto.** Lee `config/perfil.yaml` y `config/destinatarios.yaml`.
   Pregunta a Marcelo **qué reporte** quiere preparar (o recíbelo como argumento).

2. **Reúne los datos.** `TODO` por reporte: definir las fuentes exactas (qué proyectos/
   tareas de Asana, qué archivos de SharePoint, qué tablas web). Consolida los datos.

3. **(Opcional) Tabla/visual.** Si el reporte lleva tabla, genera el `.xlsx` con
   `scripts/generar-tabla.py` y/o un gráfico con el **MCP de Canva**.

4. **Redacta** asunto y cuerpo según el `formato` del reporte (`html`/`markdown`),
   en es-CL, con tono profesional.

5. **Vista previa + confirmación.** Muestra a Marcelo el asunto, destinatarios y cuerpo.
   **Espera su confirmación explícita** antes de crear el borrador.

6. **Crea el borrador** llamando a `scripts/crear-borrador.py` con asunto, cuerpo,
   destinatarios (To/CC) y adjuntos. El script crea el mensaje con `isDraft=true`
   (**no envía**).

7. **Guarda copia** del reporte en `reports/YYYY-MM-DD-<id-reporte>.md` para historial.
   Opcional: publicar el avance como *status update* en Asana
   (`create_project_status_update`) **previa confirmación**.

## Reglas

- **Nunca enviar.** Solo borrador en Outlook. El envío lo hace Marcelo.
- Pedir confirmación antes de crear el borrador y antes de cualquier escritura en Asana.
- Idioma es-CL.

## TODO para activar cada reporte

- [ ] Completar la entrada del reporte en `config/destinatarios.yaml` (destinatarios,
      asunto, formato, frecuencia, fuente).
- [ ] Definir y cablear las fuentes de datos exactas del paso 2.
- [ ] Validar el flujo de borrador con `scripts/crear-borrador.py` (requiere secretos de
      Microsoft Graph cargados — ver README).
