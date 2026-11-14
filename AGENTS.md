# AGENTS.md — FieldShift sprint rules

Read this file before any code change.

## Canonical contract

`docs/features/fieldshift/00_CONTRACT.md` is the data contract. If code and contract differ, code is wrong unless the integrator approves a contract update in a PR.

## Roles and owned files

### Frontend Lead
Owns:
- dashboard/rotation_planner_tab.py

Must not touch:
- pipeline/gee_client.py
- modules/m6_rotation_planner.py
- modules/fieldshift_facade.py
- ROADMAP.md

### Backend 1 — NASA Data
Owns:
- pipeline/gee_client.py
- scripts/prefetch_nasa_climate.py
- data/processed/nasa_cache/

Must not touch:
- dashboard/app.py
- modules/m6_rotation_planner.py
- dashboard/rotation_planner_tab.py

### Backend 2 — Agro Engine
Owns:
- dataset/rotation_rules.json
- modules/m6_rotation_planner.py
- tests/test_rotation_planner.py

Must not touch:
- dashboard/app.py
- pipeline/gee_client.py
- dashboard/rotation_planner_tab.py

### Backend 3 — Integrator / QA
Owns:
- modules/fieldshift_facade.py
- tests/test_fieldshift_integration.py
- dashboard/app.py after initial scaffold
- ROADMAP.md
- PROJECT_STATE.md

## Commands

python -m py_compile dashboard/*.py modules/*.py pipeline/*.py
python -m unittest discover -s tests -v
streamlit run dashboard/app.py

## Data rules

- Use only real IDs from dataset/soils.json and dataset/crops.json.
- Never invent NASA values. If network/GEE is unavailable, Backend 1 must return cached data.
- Do not replace real calculations with random values.
- Contract fixture is allowed only for frontend development and must be replaced by the facade before final integration.
