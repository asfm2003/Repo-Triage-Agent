"""
Streamlit demo UI for the Repo Triage Agent.
White + emerald green palette, minimal layout, no emojis.
Run with: streamlit run streamlit_app.py
"""
import asyncio
import datetime
import streamlit as st

from agent_core import run_agent_investigation

st.set_page_config(page_title="Repo Triage Agent", layout="centered")

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif;
    background-color: #ffffff;
}

#MainMenu, footer, header {visibility: hidden;}

.block-container {
    max-width: 800px;
    padding-top: 2rem;
}

.top-bar {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    border-bottom: 1px solid #e3f5ec;
    padding-bottom: 1.2rem;
    margin-bottom: 2.5rem;
}

.top-bar-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #047857;
}

.top-bar-sub {
    font-size: 0.85rem;
    color: #9ca3af;
    margin-top: 2px;
}

.top-bar-nav {
    font-size: 0.85rem;
    color: #10b981;
    letter-spacing: 0.02em;
}

.headline {
    font-size: 2.6rem;
    line-height: 1.15;
    font-weight: 800;
    color: #064e3b;
    margin-bottom: 0.4rem;
}

.headline .accent {
    color: #10b981;
}

.subcopy {
    color: #6b7280;
    font-size: 1rem;
    margin-bottom: 2.5rem;
    max-width: 560px;
}

.section-label {
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.72rem;
    color: #10b981;
    font-weight: 700;
    margin-bottom: 0.6rem;
}

div.stButton > button {
    background-color: #10b981;
    color: #fff;
    border-radius: 8px;
    border: none;
    padding: 0.55rem 1.4rem;
    font-weight: 600;
    font-size: 0.9rem;
}

div.stButton > button:hover {
    background-color: #059669;
    color: #fff;
}

div[data-testid="stNumberInput"] input {
    border-radius: 8px;
    border: 1px solid #d1fae5;
}

.status-line {
    font-size: 0.85rem;
    color: #6b7280;
    margin-bottom: 1.5rem;
}

.diagnosis-box {
    border: 1px solid #d1fae5;
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
    background-color: #f0fdf4;
    color: #064e3b;
    font-size: 0.95rem;
    line-height: 1.6;
}

.diagnosis-box-warning {
    border: 1px solid #fde68a;
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
    background-color: #fffbeb;
    color: #92400e;
    font-size: 0.9rem;
    line-height: 1.6;
}

.stExpander {
    border: 1px solid #d1fae5 !important;
    border-radius: 10px !important;
}

hr {
    border-color: #d1fae5;
}

.footer-note {
    color: #9ca3af;
    font-size: 0.8rem;
    margin-top: 2.5rem;
    border-top: 1px solid #e3f5ec;
    padding-top: 1.2rem;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

now_str = datetime.datetime.now().strftime("%d %b — %H:%M")

st.markdown(
    f"""
    <div class="top-bar">
        <div>
            <div class="top-bar-title">Repo Triage Agent</div>
            <div class="top-bar-sub">{now_str} · MCP + Gemini</div>
        </div>
        <div class="top-bar-nav">Docs&nbsp;&nbsp;&nbsp;GitHub</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="headline">
        Agent investigating <span class="accent">GitHub issues</span><br>
        from bug report to <span class="accent">grounded</span><br>
        diagnosis.
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="subcopy">
    Give it an issue number. It plans its own investigation — reading the report,
    searching the codebase, inspecting the relevant logic — and cites the exact
    file and line behind its conclusion.
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("**About this agent**")
    st.markdown(
        "Connects to a live GitHub repo and a local code clone via an MCP "
        "server. Gemini acts as the reasoning engine and decides which tools "
        "to call — there is no fixed pipeline.\n\n"
        "**Tools available:**\n"
        "- `get_issue`\n"
        "- `search_code`\n"
        "- `list_similar_issues`\n"
        "- `read_code_context`\n\n"
        "**Safety design:** the agent only diagnoses. It never auto-writes or "
        "merges code. A planned PR-drafting step will always require explicit "
        "human approval first."
    )
    st.markdown(
        "<div class='status-line'>Free-tier Gemini quota is limited — "
        "each run costs several API calls.</div>",
        unsafe_allow_html=True,
    )

st.markdown('<div class="section-label">Run investigation</div>', unsafe_allow_html=True)

col1, col2 = st.columns([3, 1])
with col1:
    issue_number = st.number_input(
        "Issue number", min_value=1, value=2, step=1, label_visibility="collapsed"
    )
with col2:
    run_clicked = st.button("Investigate", type="primary", use_container_width=True)

if run_clicked:
    status_placeholder = st.empty()
    status_placeholder.markdown(
        '<div class="status-line">Connecting to MCP server and starting investigation...</div>',
        unsafe_allow_html=True,
    )

    with st.spinner(""):
        trace = asyncio.run(run_agent_investigation(int(issue_number)))

    status_placeholder.empty()

    st.markdown('<div class="section-label">Investigation trace</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="status-line">Tools available: {", ".join(trace["tools_loaded"])}</div>',
        unsafe_allow_html=True,
    )

    for r in trace["rounds"]:
        with st.expander(f"Round {r['round']} — {r['tool']}({r['args']})", expanded=False):
            st.code(r["result"], language="text")

    st.markdown('<div class="section-label">Diagnosis</div>', unsafe_allow_html=True)

    if trace["final_diagnosis"]:
        st.markdown(
            f'<div class="diagnosis-box">{trace["final_diagnosis"]}</div>',
            unsafe_allow_html=True,
        )
    elif trace["stopped_without_answer"]:
        st.markdown(
            '<div class="diagnosis-box-warning">Agent hit its round limit without '
            "concluding. This can happen when the issue needs more investigation "
            "than the round budget allows, or when the model gets stuck "
            "re-searching instead of inspecting a hit.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.error("No diagnosis produced — check the terminal or agent_run_log.txt for errors.")

st.markdown(
    '<div class="footer-note">Built with the official MCP Python SDK and the '
    "Gemini API. Source: github.com/asfm2003/Repo-Triage-Agent</div>",
    unsafe_allow_html=True,
)