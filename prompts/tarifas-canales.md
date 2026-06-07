# Prompt programado — Tarifas por canal (rate shopping)

Ejecuta el Skill **`tarifas-canales`** de este repositorio.

Pasos:
1. Lee `CLAUDE.md` y `config/tarifas-publicas.yaml`.
2. Sigue el playbook de `.claude/skills/tarifas-canales/SKILL.md`:
   - Ejecuta `scripts/scrape-tarifas.py` (Playwright, vista pública sin login) →
     `reports/YYYY-MM-DD-tarifas.csv`.
   - Ejecuta `scripts/generar-tabla.py` sobre ese CSV → `reports/YYYY-MM-DD-tarifas.xlsx`.
3. Escribe `reports/YYYY-MM-DD-tarifas.md` con los hallazgos (paridad, posición vs
   competencia, sitios bloqueados).
4. Haz commit de las salidas en la branch del repo.

Requiere que el environment tenga Playwright instalado (`playwright install chromium`).
Uso responsable y a baja frecuencia. Responde en español de Chile.
