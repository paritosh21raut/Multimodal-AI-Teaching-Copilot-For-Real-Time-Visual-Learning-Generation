from __future__ import annotations

import os
from pathlib import Path
import html

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from app.dashboard.dashboard_state import dashboard_state


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="AI Teaching Copilot",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# AUTO REFRESH
# ============================================================

st_autorefresh(
    interval=1000,
    key="dashboard_refresh",
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
<style>
html, body {
    background-color: #0b0f14;
}

[data-testid="stAppViewContainer"] {
    background-color: #0b0f14;
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stToolbar"] {
    display: none;
}

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}


/* ============================================================
   MAIN CONTAINER
   ============================================================ */

.main .block-container {
    max-width: 1500px;
    padding-top: 2rem;
    padding-bottom: 1.5rem;
    padding-left: 3rem;
    padding-right: 3rem;
}


/* ============================================================
   HEADER
   ============================================================ */

.app-header {
    text-align: left;
    padding-bottom: 1.1rem;
    border-bottom: 1px solid #292f37;
}

.app-title {
    color: #f5f7fa;
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.15;
    margin: 0;
}

.app-subtitle {
    color: #858e99;
    font-size: 0.85rem;
    margin-top: 0.4rem;
}


/* ============================================================
   SLIDE TITLE / TOPIC
   ============================================================ */

.slide-heading {
    text-align: center;

    color: #f5f7fa;

    font-size: 2rem;
    font-weight: 700;

    line-height: 1.25;

    max-width: 1050px;

    margin: 1.7rem auto 1.6rem auto;
}


/* ============================================================
   MAIN CONTENT AREA
   ============================================================ */

.main-content {
    padding-top: 0.5rem;
}


/* ============================================================
   LEFT SIDE
   ============================================================ */

.bullets-container {
    padding: 0.3rem 0.5rem 0 0.2rem;
}

.bullet-item {
    color: #e1e6eb;

    font-size: 1.18rem;
    font-weight: 400;

    line-height: 1.55;

    margin-bottom: 1rem;

    padding-left: 1.25rem;

    position: relative;
}

.bullet-item::before {
    content: "•";

    position: absolute;

    left: 0;
    top: 0;

    color: #e1e6eb;

    font-size: 1.15rem;
}


/* ============================================================
   IMAGE AREA
   ============================================================ */

.image-wrapper {
    width: 100%;

    min-height: 390px;

    display: flex;

    align-items: center;
    justify-content: center;

    background: #10161d;

    border: 1px solid #29323c;

    border-radius: 12px;

    overflow: hidden;
}

.image-placeholder {
    color: #737d88;

    font-size: 1rem;

    text-align: center;
}

[data-testid="stImage"] {
    width: 100%;
}

[data-testid="stImage"] img {
    width: 100%;

    max-height: 430px;

    object-fit: contain;

    border-radius: 12px;
}


/* ============================================================
   LIVE TRANSCRIPT
   ============================================================ */

.transcript-section {
    margin-top: 1.8rem;

    padding-top: 1.2rem;

    border-top: 1px solid #292f37;
}

.transcript-heading {
    color: #f2f4f6;

    font-size: 1.15rem;

    font-weight: 650;

    margin-bottom: 0.7rem;
}

.transcript-box {
    width: 100%;

    background: #10161d;

    border: 1px solid #29323c;

    border-radius: 10px;

    padding: 1rem 1.2rem;
}

.transcript-text {
    color: #dce2e8;

    font-size: 1rem;

    line-height: 1.55;
}

.transcript-empty {
    color: #737d88;

    font-size: 0.95rem;
}


/* ============================================================
   RESPONSIVE
   ============================================================ */

@media (max-width: 900px) {

    .main .block-container {
        padding-left: 1.2rem;
        padding-right: 1.2rem;
    }

    .app-title {
        font-size: 1.6rem;
    }

    .slide-heading {
        font-size: 1.55rem;
    }

    .bullet-item {
        font-size: 1rem;
    }

    .image-wrapper {
        min-height: 280px;
    }
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# READ DASHBOARD STATE
# ============================================================

state = dashboard_state.snapshot()

title = state.title.strip() if state.title else ""
bullets = list(state.bullets)

transcript = (
    state.transcript.strip()
    if state.transcript
    else ""
)

image_path = state.image


# ============================================================
# TEXT ESCAPING
# ============================================================

def safe_text(value) -> str:
    return html.escape(str(value))


# ============================================================
# RESOLVE IMAGE PATH
# ============================================================

def resolve_image_path(path_value: str) -> str | None:

    if not path_value:
        return None

    path = Path(path_value)

    # Direct path
    if path.is_file():
        return str(path.resolve())

    # Relative to project root
    project_root = Path(__file__).resolve().parents[2]

    candidate = project_root / path

    if candidate.is_file():
        return str(candidate.resolve())

    # Try normalized Windows path
    try:

        candidate = Path(
            os.path.normpath(path_value)
        )

        if candidate.is_file():
            return str(candidate.resolve())

    except Exception:
        pass

    return None


resolved_image = resolve_image_path(image_path)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="app-header">'
    '<div class="app-title">AI Teaching Copilot</div>'
    '<div class="app-subtitle">'
    'Real-Time Visual Learning Generation'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# MAIN SLIDE TITLE
# ============================================================

# IMPORTANT:
# We intentionally use the generated PPT title here.
#
# state.topic can sometimes contain a long transcript-like
# value depending on the topic detector.
#
# The PPT title is the reliable slide-level topic/title.

display_title = (
    title
    if title
    else "Waiting for lecture..."
)

st.markdown(
    '<div class="slide-heading">'
    + safe_text(display_title)
    + '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# MAIN CONTENT
# ============================================================

left_column, right_column = st.columns(
    [1, 1],
    gap="large",
)


# ============================================================
# LEFT: BULLET POINTS
# ============================================================

with left_column:

    st.markdown(
        '<div class="bullets-container">',
        unsafe_allow_html=True,
    )

    valid_bullets = [
        str(bullet).strip()
        for bullet in bullets
        if bullet and str(bullet).strip()
    ]

    if valid_bullets:

        for bullet in valid_bullets:

            st.markdown(
                '<div class="bullet-item">'
                + safe_text(bullet)
                + '</div>',
                unsafe_allow_html=True,
            )

    else:

        st.markdown(
            '<div class="transcript-empty">'
            'Waiting for lecture content...'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# RIGHT: GENERATED IMAGE
# ============================================================

with right_column:

    if resolved_image:

        st.image(
            resolved_image,
            use_container_width=True,
        )

    else:

        st.markdown(
            '<div class="image-wrapper">'
            '<div class="image-placeholder">'
            'Waiting for visual generation...'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )


# ============================================================
# LIVE TRANSCRIPT
# ============================================================

st.markdown(
    '<div class="transcript-section">',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="transcript-heading">'
    'Live Transcript'
    '</div>',
    unsafe_allow_html=True,
)

if transcript:

    st.markdown(
        '<div class="transcript-box">'
        '<div class="transcript-text">'
        + safe_text(transcript)
        + '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

else:

    st.markdown(
        '<div class="transcript-box">'
        '<div class="transcript-empty">'
        'Waiting for speech...'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown(
    '</div>',
    unsafe_allow_html=True,
)