# FieldShift sprint roadmap

## Sprint goal

Deliver an explainable crop-rotation decision tool for NASA Space Apps 2026 — Field Shift.

## Branches

- feat/frontend-ui — Frontend Lead
- feat/nasa-data — Backend 1
- feat/agro-engine — Backend 2
- feat/integration-qa — Backend 3
- main — protected; merge via PR after integration tests

## Phase 0 — Setup: done

- Contract copied and frozen.
- Dataset copied from AgriCascade.
- Minimal Streamlit shell with contract fixture.
- Role stubs and ownership recorded.

## Phase 1 — Parallel implementation

### Frontend Lead
- Parameter panel: region, soil, area, four priority weights.
- Three strategy cards.
- Plotly: water demand vs precipitation.
- Plotly: soil health score dynamics.
- Explainable rationale in KK/RU.
- Replace fixture with facade when Backend 3 is ready.

### Backend 1 — NASA Data
- Implement GLDAS evapotranspiration/root-zone extraction.
- Implement IMERG precipitation extraction.
- Prefetch and cache four regions.
- Implement get_nasa_climate_summary(region) returning exact contract keys.

### Backend 2 — Agro Engine
- Implement rotation rules.
- Implement Soil Health Score dynamics.
- Implement weighted optimizer.
- Generate three contract strategies.

### Backend 3 — Integrator
- Implement facade.
- Contract-validation tests.
- Replace frontend fixture with facade.
- Edge cases: zero weights, area 0.1/50000 ha, all soils, offline mode.

## Phase 2 — Hardening

- Full unittest run.
- Offline smoke test.
- KK/RU text review.
- README/requirements cleanup.
- Streamlit Cloud smoke test.

## Definition of done

- python -m unittest discover -s tests -v passes.
- streamlit run dashboard/app.py runs with no unhandled exceptions.
- Offline mode returns cached NASA data.
- Contract fixture is no longer used in final UI.
- All UI strings exist in both KK and RU.
