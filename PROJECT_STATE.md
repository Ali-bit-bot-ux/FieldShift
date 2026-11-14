# PROJECT_STATE.md — FieldShift

Date: 2026-11-14
Repo owner: Ali
Roles: 1 Frontend Lead + 3 Backend Leads
Status: repository scaffold committed; parallel implementation can start.

## Current implementation

- Contract copied and frozen: docs/features/fieldshift/00_CONTRACT.md.
- AgriCascade dataset copied: 16 crops, 7 soils, 17 drought practices, decision matrix.
- Minimal Streamlit shell runs on docs/features/fieldshift/fixtures/contract_response.json.
- Role stubs created:
  - modules/m6_rotation_planner.py
  - pipeline/gee_client.py
  - modules/fieldshift_facade.py
  - scripts/prefetch_nasa_climate.py
- Starter rotation rules: dataset/rotation_rules.json.

## Ownership

See AGENTS.md. File ownership is strict to avoid merge conflicts.

## Next actions

- Frontend: replace fixture rendering with the full planner UI.
- Backend 1: implement NASA GLDAS/IMERG access and offline cache.
- Backend 2: implement rotation rules, Soil Health Score, weighted optimizer.
- Backend 3: implement facade, integration tests, edge cases and offline smoke.

## Verification

python -m unittest discover -s tests -v
streamlit run dashboard/app.py
