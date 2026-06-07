# Prompt programado — Reporte matinal

Ejecuta el Skill **`reporte-matinal`** de este repositorio para hoy.

Pasos:
1. Lee el contexto del proyecto (`CLAUDE.md`) y los archivos de `config/`.
2. Sigue el playbook de `.claude/skills/reporte-matinal/SKILL.md`:
   - Tareas de Asana (mías + vencidas/del día) sobre los proyectos de
     `config/proyectos-asana.yaml`.
   - Correos del día en Outlook que requieran acción.
3. Genera el resumen priorizado agrupado por área y guárdalo en
   `reports/YYYY-MM-DD-matinal.md` (zona horaria America/Santiago).
4. Haz commit del reporte en la branch del repo y deja el resumen como salida.

Esta rutina es **solo lectura**: no crees ni edites tareas, ni redactes correos.
Responde en español de Chile.
