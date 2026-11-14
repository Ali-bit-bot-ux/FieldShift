"""FieldShift UI. Frontend Lead owns this file.

The current version renders the contract fixture so the shell is usable
before Backend 1/2 and the facade are integrated.
"""
import json
from pathlib import Path

import streamlit as st

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "docs/features/fieldshift/fixtures/contract_response.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def render_rotation_planner_tab() -> None:
    payload = _load_fixture()

    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        c1.selectbox("Область", ["sko", "kostanay", "akmola", "pavlodar"], key="fixture_region")
        c2.selectbox("Тип почвы", ["chernozem_southern_ordinary"], key="fixture_soil")
        c3.number_input("Площадь, га", min_value=0.1, max_value=50000.0, value=400.0, key="fixture_area")
        c4.selectbox("Срок ротации", [3, 4], index=1, key="fixture_years")

    st.info("Development fixture from 00_CONTRACT.md. Replace with get_fieldshift_recommendation(payload).")

    cards = st.columns(3)
    for col, strategy in zip(cards, payload["strategies"]):
        with col:
            st.subheader(strategy["title_ru"])
            st.metric("Summary score", f"{strategy['summary_score']:.1f}")
            st.metric("Water saved", f"{strategy['water_saved_percent']:.1f}%")
            st.metric("Soil health", strategy["soil_health_delta"])

    st.subheader("Rotation years")
    selected_id = st.selectbox(
        "Strategy",
        [s["strategy_id"] for s in payload["strategies"]],
        format_func=lambda value: next(s["title_ru"] for s in payload["strategies"] if s["strategy_id"] == value),
        key="fixture_strategy",
    )
    strategy = next(s for s in payload["strategies"] if s["strategy_id"] == selected_id)
    st.dataframe(strategy["rotation_years"], use_container_width=True, hide_index=True)

    st.subheader("Climate context")
    st.json(payload["climate_context"])
