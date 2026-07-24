import sys
from pathlib import Path

# Allow "services", "models", etc. to be imported from the project root.
# Needed on Streamlit Community Cloud: Streamlit puts the directory
# containing the entry script (app/) on sys.path, not the project root,
# so anything outside app/ (services/, models/, importers/, utils/)
# isn't importable without this. This only needs to run ONCE, here, in
# the entry point — sys.path is shared by the whole process, so every
# page (app/pages/*.py) inherits it too. It does NOT belong in each
# page file individually.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

st.set_page_config(
    page_title="Journal Intelligence",
    page_icon="📚",
    layout="centered",
)

# ==========================================================
# Header
# ==========================================================

header_left, header_right = st.columns([8, 1])

with header_left:
    st.title("📚 Journal Intelligence")

with header_right:
    st.selectbox(
        label="Language",
        options=["English"],
        index=0,
        disabled=True,
        label_visibility="collapsed",
        help="Multi-language support is planned for a future release.",
    )

st.write("### Find the right journal.")
st.write("Learn the publication process.")
st.write("Publish with confidence.")

st.write("")

# ==========================================================
# Workflow Selection
# ==========================================================

st.header("Choose your workflow")

st.write(
    "Select the workflow that best matches your current stage of research."
)

# ----------------------------------------------------------
# Planning
# ----------------------------------------------------------

with st.container(border=True):

    left, right = st.columns([6, 2])

    with left:
        st.subheader("🌱 Planning")

    with right:
        st.caption("🚧 Coming Soon")

    st.write(
        "Still planning or writing your manuscript?\n\n"
        "Discover suitable journals before you begin writing so you can "
        "align your manuscript with the right audience, scope, and author "
        "guidelines from the start."
    )

    if st.button(
        "🌱 Start Planning",
        use_container_width=True,
    ):

        st.info(
            "The Planning workflow is currently under development."
        )

        st.markdown("""
### Planned Features

- Discover suitable journals before writing
- Download journal templates
- Browse author guidelines
- Explore journal aims and scope
- Receive journal-specific writing recommendations
""")

# ----------------------------------------------------------
# Submission
# ----------------------------------------------------------

with st.container(border=True):

    st.subheader("🚀 Submission")

    st.write(
        "Already have a completed manuscript?\n\n"
        "Analyze your title, abstract, and keywords to discover journals "
        "that best match your research."
    )

    if st.button(
        "🚀 Start Submission Search",
        use_container_width=True,
    ):
        st.switch_page("pages/1_Submission_Search.py")

st.write("")

# ==========================================================
# Publication Academy
# ==========================================================

st.header("🎓 Need a quick refresher?")

st.write(
    "Whether you're publishing your first paper or exploring a new indexing "
    "system, Publication Academy explains important publishing concepts in "
    "clear, practical language."
)

if st.button(
    "🎓 Explore Publication Academy",
    use_container_width=True,
):
    st.switch_page("pages/2_Publication_Academy.py")

st.info(
    "💡 Publishing terms such as APC, Scopus, SINTA, Quartiles, Open Access, "
    "and Peer Review will be explained throughout the application."
)

st.divider()

st.caption(
    "🔒 Privacy-first • No account required • Built for researchers"
)