import streamlit as st
import pandas as pd
import os
import hashlib

DATA_FILE = "data.csv"   # ton vrai fichier
ANNOT_FILE = "annotations.csv"
MAX_ANNOTATIONS = 3

st.set_page_config(page_title="Plateforme d'annotation", layout="centered")
st.title("📝 Plateforme d'annotation de commentaires")

# ---------- Chargement données ----------
@st.cache_data
def load_data():
    df = pd.read_csv(DATA_FILE)

    # ID STABLE PAR COMMENTAIRE
    df["comment_id"] = df.apply(
    lambda row: hashlib.md5(
        f"{row['video_id']}_{row['author']}_{row['published']}".encode()
    ).hexdigest(),
    axis=1
)



    return df

data = load_data()

# ---------- Annotations ----------
if os.path.exists(ANNOT_FILE):
    annotations = pd.read_csv(ANNOT_FILE)
else:
    annotations = pd.DataFrame(
        columns=["comment_id", "text", "abusif", "intensite", "email"]
    )

# ---------- Email ----------
email = st.text_input("📧 Votre email")

if email.strip() == "":
    st.info("Veuillez entrer votre email pour commencer.")
    st.stop()

# ---------- Commentaires encore annotables ----------
def get_remaining_comments():
    if annotations.empty:
        return data.copy()

    counts = annotations.groupby("comment_id").size()
    valid_ids = counts[counts < MAX_ANNOTATIONS].index

    return data[data["comment_id"].isin(valid_ids)].reset_index(drop=True)

remaining = get_remaining_comments()

# ---------- Session ----------
if "index" not in st.session_state:
    st.session_state.index = 0

if remaining.empty:
    st.success("🎉 Tous les commentaires ont atteint 3 annotations.")
    st.stop()

if st.session_state.index >= len(remaining):
    st.session_state.index = 0

row = remaining.iloc[st.session_state.index]

# ---------- Interface ----------
st.markdown("### 💬 Commentaire")
st.info(row["text"])

abusif = st.radio(
    "Ce commentaire est-il abusif ?",
    ["non abusive", "abusive"]
)

intensite = ""
if abusif == "abusive":
    intensite = st.radio(
        "Intensité",
        ["faible", "moyenne", "élevée"]
    )

# ---------- Sauvegarde ----------
if st.button("💾 Enregistrer et continuer"):

    # ❌ empêcher double annotation par même email
    already_done = annotations[
        (annotations["comment_id"] == row["comment_id"]) &
        (annotations["email"] == email)
    ]

    if not already_done.empty:
        st.warning("⚠️ Vous avez déjà annoté ce commentaire.")
        st.stop()

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

    # 👉 passage automatique
    st.session_state.index += 1
    st.experimental_rerun()
