# Prompt programado — Tarifas por canal (rate shopping vía MCP)

Ejecuta el Skill **`tarifas-canales`** de este repositorio.

Pasos:
1. Lee `CLAUDE.md` y `config/tarifas-publicas.yaml`.
2. Sigue el playbook de `.claude/skills/tarifas-canales/SKILL.md`:
   - Tarifa de cada hotel propio con el MCP de **Booking** (`accommodations_search`).
   - Set competitivo y canal/OTA por precio con el MCP de **Trivago**
     (`trivago-accommodation-radius-search`).
   - Valida/enriquece con **Tripadvisor** (`hotel_details` / `compare_hotels`) si aplica.
   - Normaliza moneda a CLP (registrando la de origen) y escribe
     `reports/YYYY-MM-DD-tarifas.csv`.
3. Ejecuta `python3 scripts/generar-tabla.py reports/YYYY-MM-DD-tarifas.csv`
   → `reports/YYYY-MM-DD-tarifas.xlsx`.
4. Escribe `reports/YYYY-MM-DD-tarifas.md` con tarifas, paridad y posición vs competencia.
5. Haz commit de las salidas en la branch del repo.

Requiere los conectores MCP de viajes activos en la sesión. Si no lo están, usa el
respaldo `scripts/scrape-tarifas.py` (Playwright). Responde en español de Chile.
