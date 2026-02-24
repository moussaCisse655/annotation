import streamlit as st
import pandas as pd
import os
import hashlib

# ---------------- CONFIG ----------------
DATA_FILE = "data.csv"
ANNOT_FILE = "annotations.csv"
MAX_ANNOT = 3
ADMIN_EMAIL = "cissemoussa681@gmail.com"

st.set_page_config(page_title="Plateforme d’annotation", layout="centered")
st.title("📝 Plateforme d'annotation")

# ---------------- GUIDE ----------------
with st.expander("📘 Guide d’annotation (Obligatoire)"):
    st.markdown("""
### Objectif
Annoter des commentaires pour un mémoire de recherche en NLP.

### abusive / non abusive
- abusive : attaque contre personne ou groupe
- non abusive : neutre ou critique sans attaque

### Types d’abus
Insulte, Menace, Harcèlement, Haine, Discrimination, Autre

### Intensité
faible, moyenne, élevée

### Langue
Français, Wolof, Français-Wolof
""")

guide_ok = st.checkbox("J’ai lu et compris le guide d’annotation")

# ---------------- SESSION STATE ----------------
if "idx" not in st.session_state:
    st.session_state.idx = 0

if "last_email" not in st.session_state:
    st.session_state.last_email = ""

if "form_key" not in st.session_state:
    st.session_state.form_key = 0

# ---------------- LOAD DATA ----------------
def load_data():
    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig", engine="python")

    if "text" not in df.columns:
        st.error("Le fichier CSV doit contenir une colonne 'text'")
        st.stop()

    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.split().str.len() >= 3]
    df = df.reset_index(drop=True)

    # ID basé sur hash du texte (robuste)
    df["comment_id"] = df["text"].apply(
        lambda x: hashlib.md5(x.encode()).hexdigest()
    )

    return df

# ---------------- LOAD ANNOTATIONS ----------------
def load_annotations():
    if os.path.exists(ANNOT_FILE):
        return pd.read_csv(ANNOT_FILE, encoding="utf-8")
    else:
        return pd.DataFrame(
            columns=["comment_id", "email", "label", "type_abus", "intensite", "langue"]
        )

# ---------------- SAVE ----------------
def save_annotation(row):
    ann = load_annotations()
    ann = pd.concat([ann, pd.DataFrame([row])], ignore_index=True)
    ann.to_csv(ANNOT_FILE, index=False, encoding="utf-8")

# ---------------- FILTER COMMENTS ----------------
def get_available_comments(data, annotations, email):

    annotations["comment_id"] = annotations["comment_id"].astype(str)
    data["comment_id"] = data["comment_id"].astype(str)

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
email = st.text_input("📧 Entrez votre email")

if st.session_state.last_email != email:
    st.session_state.idx = 0
    st.session_state.last_email = email

if not email:
    st.info("Veuillez entrer votre email pour commencer.")
    st.stop()

if not guide_ok:
    st.warning("Vous devez accepter le guide.")
    st.stop()

data = load_data()
annotations = load_annotations()

# 🔥 Supprime automatiquement les annotations d’un ancien dataset
if not annotations.empty:
    annotations = annotations[
        annotations["comment_id"].isin(data["comment_id"])
    ]
    annotations.to_csv(ANNOT_FILE, index=False, encoding="utf-8")

available = get_available_comments(data, annotations, email)

if available.empty:
    st.success("🎉 Tous les commentaires ont été annotés.")
    row = None
else:
    if st.session_state.idx >= len(available):
        st.success("🎉 Annotation terminée pour vous.")
        row = None
    else:
        row = available.iloc[st.session_state.idx]

# ---------------- DISPLAY COMMENT ----------------
if row is not None:

    st.markdown("### 💬 Commentaire")
    st.write(row["text"])

    langue = st.multiselect(
        "Langue",
        ["Français", "Wolof", "Français-Wolof"],
        key=f"lang_{st.session_state.form_key}"
    )

    label = st.selectbox(
        "Ce commentaire est-il abusif ?",
        ["Choisir une option", "abusive", "non abusive"],
        key=f"label_{st.session_state.form_key}"
    )

    type_abus = []
    intensite = []

    if label == "abusive":
        type_abus = st.multiselect(
            "Type(s) d’abus",
            ["Insulte", "Haine", "Menace", "Harcèlement", "Discrimination", "Autre"],
            key=f"type_{st.session_state.form_key}"
        )

        intensite = st.multiselect(
            "Intensité",
            ["faible", "moyenne", "élevée"],
            key=f"int_{st.session_state.form_key}"
        )

    if st.button("💾 Enregistrer et suivant"):

        if label == "Choisir une option":
            st.warning("Veuillez choisir une option.")
            st.stop()

        if "Français-Wolof" in langue and len(langue) > 1:
            st.warning("Ne combinez pas Français-Wolof avec d'autres.")
            st.stop()

        if not langue:
            st.warning("Sélectionnez une langue.")
            st.stop()

        save_annotation({
            "comment_id": row["comment_id"],
            "email": email,
            "label": label,
            "type_abus": ", ".join(type_abus) if label == "abusive" else "",
            "intensite": ", ".join(intensite) if label == "abusive" else "",
            "langue": ", ".join(langue)
        })

        st.session_state.form_key += 1
        st.rerun()

# ---------------- ADMIN ----------------
st.markdown("---")

if email == ADMIN_EMAIL:

    st.subheader("🔐 Zone Admin")

    annotations = load_annotations()

    if annotations.empty:
        st.info("Aucune annotation.")
    else:
        summary = annotations.groupby("comment_id").agg(
            total_annotations=("label", "count"),
            abusive_count=("label", lambda x: (x == "abusive").sum()),
            non_abusive_count=("label", lambda x: (x == "non abusive").sum())
        ).reset_index()

        summary["final_class"] = summary.apply(
            lambda x: 1 if x["abusive_count"] > x["non_abusive_count"] else 0,
            axis=1
        )

        summary = summary.merge(
            data[["comment_id", "text"]],
            on="comment_id",
            how="left"
        )

        st.dataframe(summary)

        st.download_button(
            label="⬇️ Télécharger Annotation_format.csv",
            data=summary.to_csv(index=False),
            file_name="Annotation_format.csv",
            mime="text/csv"
        )

    if st.button("🗑 Supprimer toutes les annotations"):
        if os.path.exists(ANNOT_FILE):
            os.remove(ANNOT_FILE)
            st.success("Annotations supprimées.")
            st.rerun()
