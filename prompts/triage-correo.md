# Prompt programado — Triage de correo

Ejecuta el Skill **`triage-correo`** de este repositorio.

Pasos:
1. Lee `CLAUDE.md` y `config/perfil.yaml`.
2. Sigue el playbook de `.claude/skills/triage-correo/SKILL.md`:
   - Correo de Outlook de las últimas 24 h.
   - Muestra **solo lo accionable**, con resumen y respuesta sugerida por hilo.
3. Entrega el resultado como salida. Si se pide explícitamente, guarda copia en
   `reports/YYYY-MM-DD-triage.md`.

**No** crees tareas en Asana ni borradores de correo automáticamente.
Responde en español de Chile.
