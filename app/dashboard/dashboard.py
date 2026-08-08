from __future__ import annotations

import streamlit as st

from app.dashboard.dashboard_state import dashboard_state
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="AI Teaching Copilot",
    layout="wide",
)

st.title("🎓 AI Teaching Copilot")

st.caption("Live AI Lecture Generation")

left, right = st.columns([2, 1])

with dashboard_state.lock:
    topic = dashboard_state.topic
    title = dashboard_state.title
    transcript = dashboard_state.transcript
    bullets = list(dashboard_state.bullets)

with left:

    st.header(topic)

    st.subheader(title)

    if bullets:
        for bullet in bullets:
            st.markdown(f"• {bullet}")
    else:
        st.info("Waiting for lecture...")

with right:

    st.subheader("Live Transcript")

    st.code(transcript if transcript else "Waiting for speech...")

st.divider()

st.caption("Dashboard refreshes automatically every second.")

st_autorefresh(
    interval=1000,
    key="dashboard_refresh",
)
