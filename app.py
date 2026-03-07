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

# créer fichier annotation si absent
if not os.path.exists(ANNOT_FILE):
    pd.DataFrame(columns=[
        "comment_id",
        "email",
        "label",
        "type_abus",
        "intensite",
        "langue"
    ]).to_csv(ANNOT_FILE, index=False)

st.title("📝 Plateforme d'annotation")

# ---------------- GUIDE ----------------
with st.expander("📘 Guide d’annotation (Obligatoire)"):
    st.markdown("""
###  Objectif
Cette plateforme sert à annoter des commentaires pour un memoire de recherche en NLP.
Votre rôle est d’identifier si un commentaire est abusif et, si oui, préciser son type et son intensité.

---

###  Abusive / Non abusive

- *abusive* : le commentaire contient une attaque dirigée contre une personne ou un groupe.
- *non abusive* : commentaire neutre, informatif ou critique sans attaque personnelle.

---

###  Types d’abus (à choisir uniquement si "abusive")

Choisissez le type correspondant au contenu du commentaire :

- *Insulte* : mot offensant ou dégradant visant une personne  
  (ex: idiot, imbécile, nul, etc.)

- *Menace* : expression d’une intention de nuire physiquement ou moralement  
  (ex: je vais te frapper, tu vas payer, etc.)

- *Harcèlement* : attaques répétées, intimidation ou pression continue contre une personne

- *Haine* : discours visant un groupe basé sur la religion, l’ethnie, la nationalité, le genre, etc.

- *Discrimination* : exclusion, traitement injuste ou dévalorisation d’un groupe ou individu à cause de son identité

- *Autre* : abus qui ne correspond à aucune des catégories ci-dessus

 Si plusieurs types apparaissent dans le même commentaire, vous pouvez en sélectionner plusieurs.

---

###  Intensité

- *faible* : attaque légère ou indirecte
- *moyenne* : attaque claire et explicite
- *élevée* : attaque grave, violente ou très agressive

---

###  Langue

- Français
- Wolof
- Français-Wolof (mélange des deux)

 Si vous choisissez "Français-Wolof", ne sélectionnez pas d’autre langue.

---

 Important : Basez-vous uniquement sur le texte affiché.
Ne tenez pas compte de votre opinion personnelle.
""")

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
def load_data():

    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig", engine="python")

    if "text" not in df.columns:
        st.error("Le fichier CSV doit contenir une colonne 'text'")
        st.stop()

    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.split().str.len() >= 3]
    df = df.reset_index(drop=True)

    df["comment_id"] = df["text"].apply(
        lambda x: hashlib.md5(x.encode()).hexdigest()
    )

    return df


# ---------------- LOAD ANNOTATIONS ----------------
def load_annotations():

    if not os.path.exists(ANNOT_FILE):
        return pd.DataFrame(columns=[
            "comment_id","email","label","type_abus","intensite","langue"
        ])

    if os.path.getsize(ANNOT_FILE) == 0:
        return pd.DataFrame(columns=[
            "comment_id","email","label","type_abus","intensite","langue"
        ])

    try:
        return pd.read_csv(ANNOT_FILE, encoding="utf-8")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=[
            "comment_id","email","label","type_abus","intensite","langue"
        ])


# ---------------- SAVE ----------------
def save_annotation(row):

    df = pd.DataFrame([row])

    if not os.path.exists(ANNOT_FILE) or os.path.getsize(ANNOT_FILE) == 0:
        df.to_csv(ANNOT_FILE, index=False, encoding="utf-8")
    else:
        df.to_csv(
            ANNOT_FILE,
            mode="a",
            header=False,
            index=False,
            encoding="utf-8"
        )


# ---------------- LOGIC ----------------
def get_available_comments(data, annotations, email):

    if annotations.empty:
        return data

    annotations["comment_id"] = annotations["comment_id"].astype(str)

    total_count = annotations["comment_id"].value_counts()

    user_annotated = annotations[
        annotations["email"] == email
    ]["comment_id"].unique()

    mask = (
        data["comment_id"].map(total_count).fillna(0) < MAX_ANNOT
    ) & (
        ~data["comment_id"].isin(user_annotated)
    )

    return data[mask]


# ---------------- UI ----------------
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

    label = st.selectbox(
        "Ce commentaire est-il abusif ?",
        ["Choisir une option", "abusive", "non abusive"],
        key=f"label_{st.session_state.label_key}"
    )

    type_abus = []
    intensite = []

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

        if label == "Choisir une option":
            st.warning("Veuillez choisir une option.")
            st.stop()

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
            "type_abus": ", ".join(type_abus) if label == "abusive" else "",
            "intensite": ", ".join(intensite) if label == "abusive" else "",
            "langue": ", ".join(langue)
        })

        st.session_state.idx += 1
        st.session_state.label_key += 1
        st.session_state.type_key += 1
        st.session_state.intensite_key += 1
        st.session_state.langue_key += 1

        st.rerun()


# ---------------- ADMIN ----------------
st.markdown("---")

ADMIN_EMAILS = ["cissemoussa681@gmail.com","kdrame@univ-zig.sn"]

if email in ADMIN_EMAILS:

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

            match = data_admin.loc[
                data_admin["comment_id"] == cid, "text"
            ]

            tweet_text = match.values[0] if not match.empty else ""

            annot_count = len(group)
            count_na = len(group[group["label"] == "non abusive"])
            count_a = len(group[group["label"] == "abusive"])

            final_class = 1 if count_a > count_na else 0

            labels = group["label"].tolist()
            intensites = group["intensite"].tolist()
            langues = group["langue"].tolist()
            abus = group["type_abus"].tolist()

            summary_list.append({
                "Annotateur": annot_count,
                "Nbr-NA": count_na,
                "Nbr-A": count_a,
                "Class": final_class,
                "Ann1": labels[0] if len(labels)>0 else "",
                "Ann2": labels[1] if len(labels)>1 else "",
                "Ann3": labels[2] if len(labels)>2 else "",
                "Int1": intensites[0] if len(intensites)>0 else "",
                "Int2": intensites[1] if len(intensites)>1 else "",
                "Int3": intensites[2] if len(intensites)>2 else "",
                "L1": langues[0] if len(langues)>0 else "",
                "L2": langues[1] if len(langues)>1 else "",
                "L3": langues[2] if len(langues)>2 else "",
                "Abus1": abus[0] if len(abus)>0 else "",
                "Abus2": abus[1] if len(abus)>1 else "",
                "Abus3": abus[2] if len(abus)>2 else "",
                "Commentaires": tweet_text
            })

        summary_df = pd.DataFrame(summary_list)

        st.dataframe(summary_df)

        st.download_button(
            label="⬇️ Télécharger Annotation_format.csv",
            data=summary_df.to_csv(index=False),
            file_name="Annotation_format.csv",
            mime="text/csv"
        )

    if st.button("🗑 Supprimer toutes les annotations"):

        if os.path.exists(ANNOT_FILE):
            os.remove(ANNOT_FILE)
            st.success("Annotations supprimées")
            st.rerun()
