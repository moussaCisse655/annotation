import streamlit as st
import pandas as pd
import os
import hashlib
import gspread
from google.oauth2 import service_account

# ---------------- CONFIG ----------------
DATA_FILE = "data.csv" 
ANNOT_FILE = "annotations.csv"
MAX_ANNOT = 3
ADMIN_EMAILS = ["cissemoussa681@gmail.com", "kdrame@univ-zig.sn"]

st.set_page_config(page_title="Plateforme d'annotation", layout="centered")
st.title("📝 Plateforme d'annotation")

# ---------------- GOOGLE SHEETS ----------------
SHEETS_OK = False
sheet = None
client = None

try:
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"]
    )
    scoped_credentials = credentials.with_scopes([
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    client = gspread.authorize(scoped_credentials)
    SHEETS_OK = True
except Exception as e:
    st.warning(f"🟡 Google Sheets OFF (API non activée): {str(e)[:80]}")
    st.info("Activez Google Drive API + Sheets API dans GCP")

# ---------------- GUIDE ----------------
with st.expander("📘 Guide d'annotation (Obligatoire)"):
    st.markdown("""
### Objectif
Cette plateforme sert à annoter des commentaires pour un memoire de recherche en NLP.
Votre rôle est d'identifier si un commentaire est abusif et, si oui, préciser son type et son intensité.

### Abusive / Non abusive
- **abusive** : le commentaire contient une attaque dirigée contre une personne ou un groupe.
- **non abusive** : commentaire neutre, informatif ou critique sans attaque personnelle.

### Types d'abus
- **Insulte**, **Menace**, **Harcèlement**, **Haine**, **Discrimination**, **Autre**

### Intensité
- **faible**, **moyenne**, **élevée**

### Langue
- Français, Wolof, Français-Wolof
""")

guide_ok = st.checkbox("J'ai lu et compris le guide d'annotation")

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
    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig", engine="python")
    if "text" not in df.columns:
        st.error("Le fichier CSV doit contenir une colonne 'text'")
        st.stop()
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.split().str.len() >= 3].reset_index(drop=True)
    df["comment_id"] = df["text"].apply(lambda x: hashlib.md5(x.encode()).hexdigest())
    return df

# ---------------- GOOGLE SHEETS FUNCTIONS ----------------
def get_or_create_sheet(name, cols):
    try:
        ws = client.open("Annotations").worksheet(name)
    except gspread.WorksheetNotFound:
        ws = client.open("Annotations").add_worksheet(title=name, rows="1000", cols=str(len(cols)))
        ws.update([cols])
    return ws

# ---------------- SAVE ANNOTATION ----------------
def save_annotation(row):

    # LOCAL
    if os.path.exists(ANNOT_FILE):
        annotations = pd.read_csv(ANNOT_FILE, encoding="utf-8")
    else:
        annotations = pd.DataFrame()

    annotations = pd.concat([annotations, pd.DataFrame([row])], ignore_index=True)
    annotations.to_csv(ANNOT_FILE, index=False, encoding="utf-8")

    if not SHEETS_OK or not client:
        return

    try:
        raw_cols = ["comment_id","email","label","type_abus","intensite","langue"]
        raw_sheet = get_or_create_sheet("Brut", raw_cols)

        records = raw_sheet.get_all_records()
        df_raw = pd.DataFrame(records) if records else pd.DataFrame(columns=raw_cols)

        exists = df_raw[(df_raw["comment_id"]==row["comment_id"]) & (df_raw["email"]==row["email"])]

        if exists.empty:
            df_raw = pd.concat([df_raw, pd.DataFrame([row])], ignore_index=True)
        else:
            df_raw.loc[
                (df_raw["comment_id"]==row["comment_id"]) &
                (df_raw["email"]==row["email"]),
                ["label","type_abus","intensite","langue"]
            ] = row["label"], row["type_abus"], row["intensite"], row["langue"]

        raw_sheet.clear()
        raw_sheet.update([df_raw.columns.tolist()] + df_raw.values.tolist())

    except Exception as e:
        st.warning(f"Erreur Google Sheets : {str(e)[:80]}")

# ---------------- LOAD ANNOTATIONS ----------------
@st.cache_data(ttl=5)
def load_annotations():

    local_df = pd.read_csv(ANNOT_FILE, encoding="utf-8") if os.path.exists(ANNOT_FILE) else pd.DataFrame()

    if SHEETS_OK and client:
        try:
            raw_sheet = get_or_create_sheet(
                "Brut",
                ["comment_id","email","label","type_abus","intensite","langue"]
            )

            records = raw_sheet.get_all_records()
            sheets_df = pd.DataFrame(records)

            if not sheets_df.empty:
                combined = pd.concat([sheets_df, local_df], ignore_index=True)
                return combined.drop_duplicates(subset=["comment_id","email"])

        except:
            pass

    return local_df

# ---------------- AVAILABLE COMMENTS ----------------
def get_available_comments(data, annotations, email):

    if annotations.empty:
        return data.reset_index(drop=True)

    user_done = annotations[annotations["email"] == email]["comment_id"]

    counts = annotations.groupby("comment_id").size()

    valid_ids = counts[counts < MAX_ANNOT].index

    available = data[
        (~data["comment_id"].isin(user_done)) &
        (
            ~data["comment_id"].isin(counts.index) |
            data["comment_id"].isin(valid_ids)
        )
    ]

    return available.reset_index(drop=True)

# ---------------- UI ----------------
email = st.text_input("📧 Entrez votre email")

if st.session_state.last_email != email:
    st.session_state.idx = 0
    st.session_state.last_email = email

if not email:
    st.info("Veuillez entrer votre email pour commencer.")
    st.stop()

if not guide_ok:
    st.warning("Vous devez lire et accepter le guide avant de commencer l'annotation.")
    st.stop()

data = load_data()
annotations = load_annotations()

available = get_available_comments(data, annotations, email)

if available.empty:
    st.success("🎉 Tous les commentaires ont atteint 3 annotations ou vous avez tout annoté.")
    row = None
else:
    row = available.iloc[0]

# ---------------- COMMENT ----------------
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
            "Type(s) d'abus",
            ["Insulte","Haine","Menace","Harcèlement","Discrimination","Autre"],
            key=f"type_{st.session_state.type_key}"
        )

        intensite = st.multiselect(
            "Intensité",
            ["faible","moyenne","élevée"],
            key=f"intensite_{st.session_state.intensite_key}"
        )

    if st.button("💾 Enregistrer et suivant"):

        if label == "Choisir une option":
            st.warning("Veuillez choisir si le commentaire est abusive ou non abusive.")
            st.stop()

        if "Français-Wolof" in langue and len(langue)>1:
            st.warning("Si vous choisissez 'Français-Wolof', ne sélectionnez pas d'autres options.")
            st.stop()

        if not langue:
            st.warning("Veuillez sélectionner au moins une langue.")
            st.stop()

        save_annotation({
            "comment_id": comment_id,
            "email": email,
            "label": label,
            "type_abus": ", ".join(type_abus) if label=="abusive" else "",
            "intensite": ", ".join(intensite) if label=="abusive" else "",
            "langue": ", ".join(langue)
        })

        st.session_state.label_key += 1
        st.session_state.type_key += 1
        st.session_state.intensite_key += 1
        st.session_state.langue_key += 1

        st.success("✅ Sauvegardé !" + (" (Google Sheets)" if SHEETS_OK else " (local)"))

        st.cache_data.clear()

        st.rerun()

# ---------------- ADMIN ----------------
st.markdown("---")

if email in ADMIN_EMAILS:

    st.subheader("🔐 Zone Admin – Résumé Annotation")

    annotations = load_annotations()

    if annotations.empty:
        st.info("Aucune annotation disponible.")
    else:
        st.dataframe(annotations)

        st.download_button(
            label="⬇️ Télécharger Annotation_format.csv",
            data=annotations.to_csv(index=False, encoding="utf-8"),
            file_name="Annotation_format.csv",
            mime="text/csv"
        )
