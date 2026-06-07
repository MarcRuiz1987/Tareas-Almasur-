#!/usr/bin/env bash
# Hook SessionStart (opcional): recuerda en el contexto qué conectores deben estar
# activos para este repo, para fallar temprano y claro si falta alguno.
# Se registra en .claude/settings.json (sección "hooks"). No bloquea la sesión.

cat <<'EOF'
[Almasur] Conectores esperados en esta sesión:
  - Asana (lectura+escritura): get_my_tasks, search_tasks, get_project, create_tasks, update_tasks
  - Microsoft 365 (solo lectura): outlook_email_search, outlook_calendar_search, chat_message_search, sharepoint_search
  - Web nativo: WebFetch, WebSearch
  - Canva (MCP) y Microsoft Learn (MCP) disponibles si se necesitan.
Si falta Asana o M365, avísalo antes de ejecutar las rutinas. Fuente de verdad: config/.
EOF
