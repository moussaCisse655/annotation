import streamlit as st
import pandas as pd
import os

# ---------------- CONFIG ----------------
DATA_FILE = "data.csv"          # nom de ton CSV
ANNOT_FILE = "annotations.csv"
MAX_ANNOT = 3
ADMIN_EMAIL = "cissemoussa681@gmail.com"   # 🔴 METS TON EMAIL ICI

st.set_page_config(
    page_title="Plateforme d’annotation",
    layout="centered"
)

# ---------------- LOAD DATA ----------------
@st.cache_data
def load_data():
    df = pd.read_csv(DATA_FILE)

    if "text" not in df.columns:
        st.error("❌ Le fichier CSV doit contenir une colonne 'text'")
        st.stop()

    # 🔥 ID unique par commentaire (même si video_id est identique)
    df = df.reset_index(drop=True)
    df["comment_id"] = df.index.astype(str)

    return df


def load_annotations():
    if os.path.exists(ANNOT_FILE):
        return pd.read_csv(ANNOT_FILE)
    return pd.DataFrame(
        columns=["comment_id", "email", "label", "intensite"]
    )

# ---------------- SAVE ----------------
def save_annotation(row):
    ann = load_annotations()
    ann = pd.concat([ann, pd.DataFrame([row])], ignore_index=True)
    ann.to_csv(ANNOT_FILE, index=False)

# ---------------- LOGIC ----------------
def get_available_comments(data, annotations, email):
    # nombre total d’annotations par commentaire
    total_count = annotations.groupby("comment_id").size()

    def is_available(cid):
        total = total_count.get(cid, 0)

        already_by_user = (
            (annotations["comment_id"] == cid) &
            (annotations["email"] == email)
        ).any()

        return total < MAX_ANNOT and not already_by_user

    return data[data["comment_id"].apply(is_available)]

# ---------------- UI ----------------
st.title("📝 Plateforme d'annotation de commentaires")

email = st.text_input("📧 Entrez votre email")

if not email:
    st.info("Veuillez entrer votre email pour commencer.")
    st.stop()

data = load_data()
annotations = load_annotations()

available = get_available_comments(data, annotations, email)

if available.empty:
    st.success(
        "🎉 Tous les commentaires ont atteint 3 annotations "
        "ou vous avez tout annoté."
    )
    st.stop()

# 👉 Toujours prendre le PREMIER commentaire disponible
row = available.iloc[0]

st.markdown("### 💬 Commentaire")
st.write(row["text"])

label = st.radio(
    "Ce commentaire est-il abusif ?",
    ["abusive", "non abusive"]
)

intensite = None
if label == "abusive":
    intensite = st.selectbox(
        "Intensité",
        ["faible", "moyenne", "élevée"]
    )

if st.button("💾 Enregistrer et suivant"):
    save_annotation({
        "comment_id": row["comment_id"],
        "email": email,
        "label": label,
        "intensite": intensite if label == "abusive" else None
    })

    # 🔁 passage automatique
    st.rerun()

# ---------------- ADMIN SECTION ----------------
st.markdown("---")

if email == ADMIN_EMAIL:
    st.subheader("🔐 Zone Admin – Annotations")

    annotations = load_annotations()

    if annotations.empty:
        st.info("Aucune annotation enregistrée pour le moment.")
    else:
        st.dataframe(annotations, use_container_width=True)

        st.download_button(
            label="⬇️ Télécharger toutes les annotations",
            data=annotations.to_csv(index=False).encode("utf-8"),
            file_name="annotations_finales.csv",
            mime="text/csv"
        )
