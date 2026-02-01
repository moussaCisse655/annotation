import streamlit as st
import pandas as pd
import os

# ---------------- CONFIG ----------------
DATA_FILE = "data.csv"
ANNOT_FILE = "annotations.csv"
MAX_ANNOT = 3
ADMIN_EMAIL = "cissemoussa681@gmail.com" 

st.set_page_config(page_title="Plateforme d’annotation", layout="centered")

# ---------------- LOAD DATA ----------------
@st.cache_data
def load_data():
    df = pd.read_csv(DATA_FILE, encoding="cp1252")
    if "text" not in df.columns:
        st.error("Le fichier CSV doit contenir une colonne 'text'")
        st.stop()

    # 🔥 Garder uniquement les commentaires avec au moins 3 mots
    df["text"] = df["text"].astype(str)
    df = df[df["text"].str.split().str.len() >= 3]

    # 🔥 Création automatique d’un ID UNIQUE par commentaire
    df = df.reset_index(drop=True)
    df["comment_id"] = df.index.astype(str)

    return df


def load_annotations():
    if os.path.exists(ANNOT_FILE):
        return pd.read_csv(ANNOT_FILE, encoding="utf-8", encoding_errors="replace")
    return pd.DataFrame(
        columns=["comment_id", "email", "label", "type_abus", "intensite"]
    )

# ---------------- SAVE ----------------
def save_annotation(row):
    ann = load_annotations()
    ann = pd.concat([ann, pd.DataFrame([row])], ignore_index=True)
    ann.to_csv(ANNOT_FILE, index=False, encoding="utf-8")

# ---------------- LOGIC ----------------
def get_available_comments(data, annotations, email):
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
st.title("📝 Plateforme d'annotation")

email = st.text_input("📧 Entrez votre email")
# 🔥 Réinitialiser l'index si nouvel email ou nouvelle session
if "last_email" not in st.session_state:
    st.session_state.last_email = email

if st.session_state.last_email != email:
    st.session_state.idx = 0
    st.session_state.last_email = email


if not email:
    st.info("Veuillez entrer votre email pour commencer.")
    st.stop()

data = load_data()
annotations = load_annotations()

available = get_available_comments(data, annotations, email)

if available.empty:
    st.success("🎉 Tous les commentaires ont atteint 3 annotations ou vous avez tout annoté.")
    st.stop()

# index en session
if "idx" not in st.session_state:
    st.session_state.idx = 0

if st.session_state.idx >= len(available):
    st.success("🎉 Annotation terminée pour vous.")
    st.stop()

row = available.iloc[st.session_state.idx]

st.markdown("### 💬 Commentaire")
st.write(row["text"])

label = st.radio(
    "Ce commentaire est-il abusif ?",
    ["abusive", "non abusive"]
)

type_abus = None
intensite = None

if label == "abusive":
    type_abus = st.multiselect(
        "Type(s) d’abus",
        [
            "Insulte",
            "Haine",
            "Menace",
            "Harcèlement",
            "Discrimination",
            "Autre"
        ]
    )

    intensite = st.selectbox(
        "Intensité",
        ["faible", "moyenne", "élevée"]
    )

if st.button("💾 Enregistrer et suivant"):
    save_annotation({
        "comment_id": row["comment_id"],
        "email": email,
        "label": label,
        "type_abus": ", ".join(type_abus) if label == "abusive" else None,
        "intensite": intensite if label == "abusive" else None
    })

    st.session_state.idx += 1
    st.rerun()

# ---------------- ADMIN SECTION ----------------
st.markdown("---")

if email == ADMIN_EMAIL:
    st.subheader("🔐 Zone Admin – Annotations")

    annotations = load_annotations()
    data_admin = load_data()

    if annotations.empty:
        st.info("Aucune annotation enregistrée pour le moment.")
    else:
        annotations["comment_id"] = annotations["comment_id"].astype(str)
        data_admin["comment_id"] = data_admin["comment_id"].astype(str)

        annotations_full = annotations.merge(
            data_admin[["comment_id", "text"]],
            on="comment_id",
            how="left"
        )

        st.dataframe(
            annotations_full[
                ["comment_id", "text", "email", "label", "type_abus", "intensite"]
            ]
        )

        st.download_button(
            label="⬇️ Télécharger toutes les annotations",
            data=annotations_full.to_csv(index=False).encode("utf-8"),
            file_name="annotations_finales_avec_commentaires.csv",
            mime="text/csv"
        )

    st.markdown("### 🗑️ Réinitialisation")
    if st.button("Supprimer toutes les annotations"):
        if os.path.exists(ANNOT_FILE):
            os.remove(ANNOT_FILE)
            st.success("Annotations supprimées avec succès.")
            st.rerun()
        else:
            st.info("Aucun fichier d’annotations à supprimer.")
