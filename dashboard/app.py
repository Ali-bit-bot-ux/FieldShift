import streamlit as st
from dashboard.rotation_planner_tab import render_rotation_planner_tab

st.set_page_config(page_title="FieldShift", page_icon=None, layout="wide")

st.title("FieldShift — Crop Rotation Planner")
render_rotation_planner_tab()
