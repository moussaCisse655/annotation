import streamlit as st
import pandas as pd
import os

DATA_FILE = "data.csv"
ANNOT_FILE = "annotations.csv"
MAX_ANNOTATIONS = 3

# ------------------ INIT ------------------
st.set_page_config(page_title="Plateforme d'annotation", layout="centered")
st.title("📝 Plateforme d'annotation de commentaires")

@st.cache_data
def load_data():
    df = pd.read_csv(DATA_FILE)
    df["comment_id"] = df.index.astype(str)
    return df

data = load_data()

if os.path.exists(ANNOT_FILE):
    annotations = pd.read_csv(ANNOT_FILE)
else:
    annotations = pd.DataFrame(
        columns=["comment_id", "text", "abusif", "intensite", "email"]
    )

# ------------------ EMAIL ------------------
email = st.text_input("📧 Votre email", placeholder="exemple@email.com")

if email == "":
    st.warning("Veuillez entrer votre email pour commencer.")
    st.stop()

# ------------------ FILTRAGE ------------------
def get_remaining_comments():
    if annotations.empty:
        return data.copy()

    counts = annotations.groupby("comment_id").size()
    valid_ids = counts[counts < MAX_ANNOTATIONS].index

    remaining = data[data["comment_id"].isin(valid_ids)]

    # retirer ceux déjà annotés par cet email
    annotated_by_user = annotations[
        annotations["email"] == email
    ]["comment_id"]

    remaining = remaining[
        ~remaining["comment_id"].isin(annotated_by_user)
    ]

    return remaining.reset_index(drop=True)

remaining = get_remaining_comments()

# ------------------ SESSION ------------------
if "index" not in st.session_state:
    st.session_state.index = 0

# ------------------ FIN ------------------
if remaining.empty:
    st.success("🎉 Vous avez tout annoté ou tous les commentaires ont atteint 3 annotations.")
    st.stop()

if st.session_state.index >= len(remaining):
    st.session_state.index = 0

row = remaining.iloc[st.session_state.index]

# ------------------ INTERFACE ------------------
st.markdown("### 💬 Commentaire")
st.info(row["text"])

abusif = st.radio("Ce commentaire est-il abusif ?", ["non abusive", "abusive"])

intensite = ""
if abusif == "abusive":
    intensite = st.radio(
        "Intensité",
        ["faible", "moyenne", "élevée"]
    )

# ------------------ SAUVEGARDE ------------------
if st.button("💾 Enregistrer et continuer"):
    new_row = {
        "comment_id": row["comment_id"],
        "text": row["text"],
        "abusif": abusif,
        "intensite": intensite,
        "email": email
    }

    annotations = pd.concat(
        [annotations, pd.DataFrame([new_row])],
        ignore_index=True
    )

    annotations.to_csv(ANNOT_FILE, index=False)

    st.session_state.index += 1
    st.experimental_rerun()
