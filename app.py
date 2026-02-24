import streamlit as st
import pandas as pd
import os

# ---------------- CONFIG ----------------
DATA_FILE = "data.csv"
ANNOT_FILE = "annotations.csv"
MAX_ANNOT = 3
ADMIN_EMAIL = "cissemoussa681@gmail.com"

st.set_page_config(page_title="Plateforme d’annotation", layout="centered")
st.title("📝 Plateforme d'annotation")

# ---------------- GUIDE ----------------
with st.expander("📘 Guide d’annotation (Obligatoire)"):
    st.markdown("Lisez attentivement les consignes avant d’annoter.")

guide_ok = st.checkbox("J’ai lu et compris le guide d’annotation")

# ---------------- SESSION STATE ----------------
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "last_email" not in st.session_state:
    st.session_state.last_email = ""
if "label_key" not in st.session_state:
    st.session_state.label_key = 0
if "type_key" not in st.session_state:
    st.session_state.type_key = 0
if "intensite_key" not in st.session_state:
    st.session_state.intensite_key = 0
if "langue_key" not in st.session_state:
    st.session_state.langue_key = 0

# ---------------- LOAD DATA ----------------
@st.cache_data
def load_data():
    if not os.path.exists(DATA_FILE):
        st.error("data.csv introuvable.")
        st.stop()

    df = pd.read_csv(DATA_FILE, encoding="utf-8")

    if "text" not in df.columns:
        st.error("Le fichier CSV doit contenir une colonne 'text'")
        st.stop()

    df["text"] = df["text"].astype(str)
    df = df[df["text"].str.split().str.len() >= 3]
    df = df.reset_index(drop=True)
    df["comment_id"] = df.index.astype(str)

    return df

# ---------------- LOAD ANNOTATIONS ----------------
def load_annotations():
    if os.path.exists(ANNOT_FILE):
        df = pd.read_csv(ANNOT_FILE, encoding="utf-8")
        return df
    else:
        return pd.DataFrame(
            columns=["comment_id", "email", "label", "type_abus", "intensite", "langue"]
        )

# ---------------- SAVE ----------------
def save_annotation(row):
    ann = load_annotations()
    ann = pd.concat([ann, pd.DataFrame([row])], ignore_index=True)
    ann.to_csv(ANNOT_FILE, index=False, encoding="utf-8")

# ---------------- LOGIC ----------------
def get_available_comments(data, annotations, email):

    if annotations.empty:
        return data

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
    st.warning("Vous devez lire et accepter le guide.")
    st.stop()

data = load_data()
annotations = load_annotations()

available = get_available_comments(data, annotations, email)

if available.empty:
    st.success("🎉 Tous les commentaires ont atteint 3 annotations.")
    row = None
else:
    if st.session_state.idx >= len(available):
        st.success("🎉 Annotation terminée pour vous.")
        row = None
    else:
        row = available.iloc[st.session_state.idx]

# ---------------- AFFICHAGE COMMENTAIRE ----------------
if row is not None:

    st.markdown("### 💬 Commentaire")
    st.write(row["text"])

    langue = st.multiselect(
        "Langue du commentaire",
        ["Français", "Wolof", "Français-Wolof"],
        key=f"langue_{st.session_state.langue_key}"
    )

    label = st.selectbox(
        "Ce commentaire est-il abusif ?",
        ["Choisir une option", "abusive", "non abusive"],
        key=f"label_{st.session_state.label_key}"
    )

    type_abus = None
    intensite = None

    if label == "abusive":
        type_abus = st.multiselect(
            "Type(s) d’abus",
            ["Insulte", "Haine", "Menace", "Harcèlement", "Discrimination", "Autre"],
            key=f"type_{st.session_state.type_key}"
        )

        intensite = st.selectbox(
            "Intensité",
            ["faible", "moyenne", "élevée"],
            key=f"intensite_{st.session_state.intensite_key}"
        )

    if st.button("💾 Enregistrer et suivant"):

        if label == "Choisir une option":
            st.warning("Veuillez choisir une option.")
            st.stop()

        if not langue:
            st.warning("Veuillez sélectionner la langue.")
            st.stop()

        save_annotation({
            "comment_id": row["comment_id"],
            "email": email,
            "label": label,
            "type_abus": ", ".join(type_abus) if label == "abusive" else None,
            "intensite": intensite if label == "abusive" else None,
            "langue": ", ".join(langue)
        })

        st.session_state.label_key += 1
        st.session_state.type_key += 1
        st.session_state.intensite_key += 1
        st.session_state.langue_key += 1
        st.session_state.idx += 1

        st.rerun()

# ---------------- ADMIN SECTION ----------------
st.markdown("---")

if email == ADMIN_EMAIL:

    st.subheader("🔐 Zone Admin – Résumé Annotation")

    annotations = load_annotations()
    data_admin = load_data()

    if annotations.empty:
        st.info("Aucune annotation enregistrée.")
    else:

        annotations["comment_id"] = annotations["comment_id"].astype(str)
        data_admin["comment_id"] = data_admin["comment_id"].astype(str)

        summary_list = []

        grouped = annotations.groupby("comment_id")

        for cid, group in grouped:

            tweet_text = data_admin.loc[
                data_admin["comment_id"] == cid, "text"
            ].values[0]

            count_na = len(group[group["label"] == "non abusive"])
            count_a = len(group[group["label"] == "abusive"])
            final_class = 1 if count_a > count_na else 0

            intensite_finale = (
                group["intensite"].dropna().value_counts().idxmax()
                if not group["intensite"].dropna().empty else ""
            )

            langue_finale = (
                group["langue"].dropna().value_counts().idxmax()
                if not group["langue"].dropna().empty else ""
            )

            summary_list.append({
                "Nbr-NA": count_na,
                "Nbr-A": count_a,
                "Class": final_class,
                "Intensite": intensite_finale,
                "Langue": langue_finale,
                "Commentaires": tweet_text
            })

        summary_df = pd.DataFrame(summary_list)
        st.dataframe(summary_df)

        st.download_button(
            label="⬇️ Télécharger Annotation.csv",
            data=summary_df.to_csv(index=False, encoding="utf-8"),
            file_name="Annotation_format.csv",
            mime="text/csv"
        )
