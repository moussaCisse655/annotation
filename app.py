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
    st.warning("🟡 Google Sheets OFF")
    client = None


# ---------------- CACHE DATA ----------------
@st.cache_data
def load_data():
    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    df["text"] = df["text"].astype(str).str.strip()

    df = df[df["text"].str.split().str.len() >= 3]

    df["comment_id"] = df["text"].apply(
        lambda x: hashlib.md5(x.encode()).hexdigest()
    )

    return df.reset_index(drop=True)


@st.cache_data(ttl=5)
def load_annotations():

    if os.path.exists(ANNOT_FILE):
        df = pd.read_csv(ANNOT_FILE)
    else:
        df = pd.DataFrame(
            columns=["comment_id","email","label","type_abus","intensite","langue"]
        )

    return df


# ---------------- GOOGLE SHEETS ----------------
def get_or_create_sheet(name, cols):

    try:
        ws = client.open("Annotations").worksheet(name)

    except:
        ws = client.open("Annotations").add_worksheet(
            title=name,
            rows="1000",
            cols=str(len(cols))
        )

        ws.append_row(cols)

    return ws


# ---------------- SAVE ANNOTATION ----------------
def save_annotation(row):

    # ---------- LOCAL ----------
    if os.path.exists(ANNOT_FILE):
        annotations = pd.read_csv(ANNOT_FILE)
    else:
        annotations = pd.DataFrame()

    annotations = pd.concat(
        [annotations, pd.DataFrame([row])],
        ignore_index=True
    )

    annotations.to_csv(ANNOT_FILE, index=False)

    # ---------- GOOGLE SHEETS ----------
    if not SHEETS_OK:
        return

    try:

        raw_cols = [
            "comment_id","email",
            "label","type_abus",
            "intensite","langue"
        ]

        raw_sheet = get_or_create_sheet("Brut", raw_cols)

        raw_sheet.append_row([
            row["comment_id"],
            row["email"],
            row["label"],
            row["type_abus"],
            row["intensite"],
            row["langue"]
        ])

    except Exception as e:
        st.warning("Erreur Google Sheets")


# ---------------- AVAILABLE COMMENTS ----------------
def get_available_comments(data, annotations, email):

    if annotations.empty:
        return data.copy()

    user_done = annotations[
        annotations["email"] == email
    ]["comment_id"]

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


# ---------------- GUIDE ----------------
with st.expander("📘 Guide d'annotation (Obligatoire)"):

    st.markdown("""
### Objectif
Cette plateforme sert à annoter des commentaires pour un mémoire de recherche en NLP.

### Abusive / Non abusive
- abusive
- non abusive

### Types d'abus
- Insulte
- Menace
- Harcèlement
- Haine
- Discrimination
- Autre

### Intensité
- faible
- moyenne
- élevée

### Langue
- Français
- Wolof
- Français-Wolof
""")

guide_ok = st.checkbox("J'ai lu et compris le guide")


# ---------------- SESSION STATE ----------------
if "idx" not in st.session_state:
    st.session_state.idx = 0

if "last_email" not in st.session_state:
    st.session_state.last_email = ""


# ---------------- EMAIL ----------------
email = st.text_input("📧 Entrez votre email")

if st.session_state.last_email != email:
    st.session_state.idx = 0
    st.session_state.last_email = email

if not email:
    st.info("Veuillez entrer votre email")
    st.stop()

if not guide_ok:
    st.warning("Veuillez lire le guide")
    st.stop()


# ---------------- LOAD DATA ----------------
data = load_data()
annotations = load_annotations()

available = get_available_comments(data, annotations, email)


# ---------------- COMMENT ----------------
if available.empty:

    st.success(
        "🎉 Tous les commentaires ont atteint 3 annotations."
    )

else:

    row = available.iloc[0]

    st.markdown("### 💬 Commentaire")
    st.write(row["text"])

    langue = st.multiselect(
        "Langue",
        ["Français","Wolof","Français-Wolof"]
    )

    label = st.selectbox(
        "Ce commentaire est-il abusif ?",
        ["Choisir","abusive","non abusive"]
    )

    type_abus = []
    intensite = []

    if label == "abusive":

        type_abus = st.multiselect(
            "Type d'abus",
            [
                "Insulte",
                "Haine",
                "Menace",
                "Harcèlement",
                "Discrimination",
                "Autre"
            ]
        )

        intensite = st.multiselect(
            "Intensité",
            ["faible","moyenne","élevée"]
        )

    if st.button("💾 Enregistrer et suivant"):

        if label == "Choisir":
            st.warning("Choisir abusive ou non abusive")
            st.stop()

        if not langue:
            st.warning("Choisir une langue")
            st.stop()

        save_annotation({
            "comment_id": row["comment_id"],
            "email": email,
            "label": label,
            "type_abus": ", ".join(type_abus),
            "intensite": ", ".join(intensite),
            "langue": ", ".join(langue)
        })

        st.success("✅ Sauvegardé")

        st.cache_data.clear()

        st.rerun()


# ---------------- ADMIN ----------------
st.markdown("---")

if email in ADMIN_EMAILS:

    st.subheader("🔐 Zone Admin")

    if os.path.exists(ANNOT_FILE):

        df = pd.read_csv(ANNOT_FILE)

        st.write("Nombre total d'annotations :", len(df))

        st.dataframe(df)

        st.download_button(
            "⬇️ Télécharger annotations",
            df.to_csv(index=False),
            "annotations.csv"
        )
