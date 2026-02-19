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

with st.expander("📘 Guide d’annotation (Obligatoire)"):
    st.markdown("""
### 🎯 Objectif
Cette plateforme sert à annoter des commentaires pour un projet de recherche en NLP.

### 🏷 Abusive / Non abusive
- abusive : contient une insulte, menace, harcèlement, haine ou discrimination.
- non abusive : commentaire normal ou critique sans attaque.

### 🔥 Intensité
- faible : attaque légère
- moyenne : attaque claire
- élevée : attaque grave ou violente

### 🌍 Langue
- Français
- Wolof
- Français-Wolof (mélange)

⚠ Basez-vous uniquement sur le texte affiché.
""")

guide_ok = st.checkbox("✅ J’ai lu et compris le guide d’annotation")



# ---------------- SESSION STATE INIT ----------------
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
    df = pd.read_csv(DATA_FILE, encoding="utf-8", engine="python")

    if "text" not in df.columns:
        st.error("Le fichier CSV doit contenir une colonne 'text'")
        st.stop()

    df["text"] = df["text"].astype(str)
    df = df[df["text"].str.split().str.len() >= 3]
    df = df.reset_index(drop=True)
    df["comment_id"] = df.index.astype(str)

    return df


def load_annotations():
    if os.path.exists(ANNOT_FILE):
        df = pd.read_csv(ANNOT_FILE, encoding="utf-8")

        # 🔥 Ajouter la colonne langue si elle n'existe pas
        if "langue" not in df.columns:
            df["langue"] = None

        return df

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
st.title("📝 Plateforme d'annotation")

email = st.text_input("📧 Entrez votre email")

if st.session_state.last_email != email:
    st.session_state.idx = 0
    st.session_state.last_email = email

if not email:
    st.info("Veuillez entrer votre email pour commencer.")
    st.stop()
if not guide_ok:
    st.warning("Vous devez lire et accepter le guide avant de commencer l’annotation.")
    st.stop()

data = load_data()
annotations = load_annotations()

available = get_available_comments(data, annotations, email)

if available.empty:
    st.success("🎉 Tous les commentaires ont atteint 3 annotations ou vous avez tout annoté.")
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



    comment_id = row["comment_id"]

    label = st.radio(
        "Ce commentaire est-il abusif ?",
        ["abusive", "non abusive"],
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

        intensite = st.multiselect(
            "Intensité",
            ["faible", "moyenne", "élevée"],
            key=f"intensite_{st.session_state.intensite_key}"
        )

    if st.button("💾 Enregistrer et suivant"):

        # Vérification cohérence langue
        if "Français-Wolof" in langue and len(langue) > 1:
            st.warning("Si vous choisissez 'Français-Wolof', ne sélectionnez pas d'autres options.")
            st.stop()
    
        if not langue:
            st.warning("Veuillez sélectionner au moins une langue.")
            st.stop()
    
        save_annotation({
            "comment_id": comment_id,
            "email": email,
            "label": label,
            "type_abus": ", ".join(type_abus) if label == "abusive" else None,
            "intensite": ", ".join(intensite) if label == "abusive" else None,
            "langue": ", ".join(langue)
        })
    
        st.session_state.label_key += 1
        st.session_state.type_key += 1
        st.session_state.intensite_key += 1
        st.session_state.langue_key += 1
    
        st.rerun()





# ---------------- ADMIN SECTION ----------------
st.markdown("---")

if email == ADMIN_EMAIL:

    st.subheader("🔐 Zone Admin – Résumé AnnDoom")

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

            annot_count = len(group)
            count_na = len(group[group["label"] == "non abusive"])
            count_a = len(group[group["label"] == "abusive"])

            final_class = 1 if count_a > count_na else 0

            labels = group["label"].tolist()
            

            ann1 = labels[0] if len(labels) > 0 else ""
            ann2 = labels[1] if len(labels) > 1 else ""
            ann3 = labels[2] if len(labels) > 2 else ""

            intensites = group["intensite"].dropna()

            if not intensites.empty:
                intensite_finale = intensites.value_counts().idxmax()
            else:
                intensite_finale = ""


            langues = group["langue"].dropna()

            if not langues.empty:
                langue_finale = langues.value_counts().idxmax()
            else:
                langue_finale = ""



            summary_list.append({
                "Annotateur": annot_count,
                "Nbr-NA": count_na,
                "Nbr-A": count_a,
                "Class": final_class,
                "Annotation1": ann1,
                "Annotation2": ann2,
                "Annotation3": ann3,
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

    if st.button("🗑 Supprimer toutes les annotations"):
        if os.path.exists(ANNOT_FILE):
            os.remove(ANNOT_FILE)

            st.session_state.idx = 0
            st.session_state.label_key = 0
            st.session_state.type_key = 0
            st.session_state.intensite_key = 0

            st.success("Annotations supprimées ✅")
            st.rerun()
        else:
            st.info("Aucun fichier à supprimer.")
