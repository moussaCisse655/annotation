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
Annoter des commentaires pour un mémoire NLP.

### Abusive / Non abusive
- **abusive** : attaque dirigée contre une personne ou un groupe.
- **non abusive** : commentaire neutre ou critique sans attaque.

### Types d'abus (si "abusive")
- Insulte, Menace, Harcèlement, Haine, Discrimination, Autre

### Intensité
- faible, moyenne, élevée

### Langue
- Français, Wolof, Français-Wolof
""")
guide_ok = st.checkbox("J'ai lu et compris le guide d'annotation")

# ---------------- SESSION STATE ----------------
if "idx" not in st.session_state: st.session_state.idx = 0
if "last_email" not in st.session_state: st.session_state.last_email = ""
if "label_key" not in st.session_state: st.session_state.label_key = 0
if "type_key" not in st.session_state: st.session_state.type_key = 0
if "intensite_key" not in st.session_state: st.session_state.intensite_key = 0
if "langue_key" not in st.session_state: st.session_state.langue_key = 0
if "data" not in st.session_state: st.session_state.data = None
if "annotations" not in st.session_state: st.session_state.annotations = None

# ---------------- LOAD DATA ----------------
def load_data():
    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig", engine="python")
    if "text" not in df.columns:
        st.error("Le fichier CSV doit contenir une colonne 'text'")
        st.stop()
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.split().str.len() >= 3].reset_index(drop=True)
    df["comment_id"] = df["text"].apply(lambda x: hashlib.md5(x.encode()).hexdigest())
    return df

# ---------------- GOOGLE SHEETS ----------------
def get_or_create_sheet(name, cols):
    try:
        ws = client.open("Annotations").worksheet(name)
    except gspread.WorksheetNotFound:
        ws = client.open("Annotations").add_worksheet(title=name, rows="1000", cols=str(len(cols)))
        ws.update([cols])
    return ws

def save_annotation(row):
    # --- LOCAL SAVE ---
    if os.path.exists(ANNOT_FILE):
        annotations = pd.read_csv(ANNOT_FILE, encoding="utf-8")
    else:
        annotations = pd.DataFrame()
    annotations = pd.concat([annotations, pd.DataFrame([row])], ignore_index=True)
    annotations.to_csv(ANNOT_FILE, index=False, encoding="utf-8")

    # --- GOOGLE SHEETS SAVE (append only) ---
    if SHEETS_OK and client:
        try:
            raw_cols = ["comment_id","email","label","type_abus","intensite","langue"]
            raw_sheet = get_or_create_sheet("Brut", raw_cols)
            raw_sheet.append_row([row[c] for c in raw_cols])
        except Exception as e:
            st.warning(f"Erreur Google Sheets append : {str(e)[:80]}")

# ---------------- LOAD ANNOTATIONS ----------------
def load_annotations():
    if st.session_state.annotations is not None:
        return st.session_state.annotations
    local_df = pd.read_csv(ANNOT_FILE, encoding="utf-8") if os.path.exists(ANNOT_FILE) else pd.DataFrame()
    if SHEETS_OK and client:
        try:
            raw_sheet = get_or_create_sheet("Brut", ["comment_id","email","label","type_abus","intensite","langue"])
            records = raw_sheet.get_all_records()
            sheets_df = pd.DataFrame(records)
            if not sheets_df.empty:
                combined = pd.concat([sheets_df, local_df], ignore_index=True)
                st.session_state.annotations = combined.drop_duplicates(subset=["comment_id","email"])
                return st.session_state.annotations
        except:
            pass
    st.session_state.annotations = local_df
    return local_df

# ---------------- GET AVAILABLE COMMENTS ----------------
def get_available_comments(data, annotations, email):
    if annotations.empty:
        return data.reset_index(drop=True)
    user_done = annotations.loc[annotations["email"]==email, "comment_id"]
    counts = annotations.groupby("comment_id").size()
    counts.name = "nb_annot"
    merged = data.merge(counts, how="left", left_on="comment_id", right_index=True)
    merged["nb_annot"] = merged["nb_annot"].fillna(0)
    available = merged[(merged["nb_annot"] < MAX_ANNOT) & (~merged["comment_id"].isin(user_done))]
    return available.reset_index(drop=True)

# ---------------- LOAD SUMMARY ----------------
def load_summary_from_sheets():
    if not SHEETS_OK or not client:
        return pd.DataFrame()
    summary_cols = ["Annotateur","Nbr-NA","Nbr-A","Class",
                    "Ann1","Ann2","Ann3",
                    "Int1","Int2","Int3",
                    "L1","L2","L3",
                    "Abus1","Abus2","Abus3",
                    "Commentaires"]
    try:
        summary_sheet = get_or_create_sheet("Résumé", summary_cols)
        records = summary_sheet.get_all_records()
        if not records:
            return pd.DataFrame(columns=summary_cols)
        df = pd.DataFrame(records)
        for col in summary_cols:
            if col not in df.columns:
                df[col] = ""
        return df[summary_cols]
    except Exception as e:
        st.warning(f"Erreur Google Sheets : {str(e)[:80]}")
        return pd.DataFrame(columns=summary_cols)

# ---------------- UI ----------------
email = st.text_input("📧 Entrez votre email")
if st.session_state.last_email != email:
    st.session_state.idx = 0
    st.session_state.last_email = email
if not email:
    st.info("Veuillez entrer votre email pour commencer.")
    st.stop()
if not guide_ok:
    st.warning("Vous devez lire et accepter le guide avant de commencer.")
    st.stop()

# --- LOAD DATA ONCE ---
if st.session_state.data is None:
    st.session_state.data = load_data()
data = st.session_state.data

annotations = load_annotations()
available = get_available_comments(data, annotations, email)

if available.empty:
    st.success("🎉 Tous les commentaires ont atteint 3 annotations ou vous avez tout annoté.")
    row = None
else:
    row = available.iloc[0]

# --- COMMENT DISPLAY ---
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

        row_data = {
            "comment_id": comment_id,
            "email": email,
            "label": label,
            "type_abus": ", ".join(type_abus) if label=="abusive" else "",
            "intensite": ", ".join(intensite) if label=="abusive" else "",
            "langue": ", ".join(langue)
        }

        save_annotation(row_data)

        st.session_state.label_key += 1
        st.session_state.type_key += 1
        st.session_state.intensite_key += 1
        st.session_state.langue_key += 1

        # Update session annotations
        st.session_state.annotations = pd.concat([st.session_state.annotations, pd.DataFrame([row_data])], ignore_index=True)

        st.success("✅ Sauvegardé !" + (" (Google Sheets)" if SHEETS_OK else " (local)"))
        st.experimental_rerun()

# ---------------- ADMIN ----------------
st.markdown("---")
if email in ADMIN_EMAILS:
    st.subheader("🔐 Zone Admin – Résumé Annotation")
    summary_df = load_summary_from_sheets()
    if summary_df.empty:
        st.info("Aucune annotation disponible dans Google Sheets.")
    else:
        st.dataframe(summary_df)
        st.download_button(
            label="⬇️ Télécharger Annotation_format.csv",
            data=summary_df.to_csv(index=False, encoding="utf-8"),
            file_name="Annotation_format.csv",
            mime="text/csv"
        )
