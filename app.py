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
    sheet = client.open("Annotations").sheet1
    SHEETS_OK = True
    
except Exception as e:
    st.warning(f"🟡 Google Sheets OFF (API non activée): {str(e)[:80]}")
    st.info("Activez Google Drive API + Sheets API dans GCP")

with st.expander("📘 Guide d'annotation (Obligatoire)"):
    st.markdown("""
###  Objectif
Cette plateforme sert à annoter des commentaires pour un memoire de recherche en NLP.
Votre rôle est d'identifier si un commentaire est abusif et, si oui, préciser son type et son intensité.

###  Abusive / Non abusive
- **abusive** : le commentaire contient une attaque dirigée contre une personne ou un groupe.
- **non abusive** : commentaire neutre, informatif ou critique sans attaque personnelle.

###  Types d'abus (à choisir uniquement si "abusive")
- **Insulte** : mot offensant ou dégradant visant une personne  
- **Menace** : expression d'une intention de nuire physiquement ou moralement  
- **Harcèlement** : attaques répétées, intimidation ou pression continue
- **Haine** : discours visant un groupe basé sur la religion, l'ethnie, etc.
- **Discrimination** : exclusion, traitement injuste basé sur l'identité
- **Autre** : abus qui ne correspond à aucune catégorie

###  Intensité
- **faible** : attaque légère ou indirecte
- **moyenne** : attaque claire et explicite
- **élevée** : attaque grave, violente ou très agressive

###  Langue
- Français
- Wolof
- Français-Wolof (mélange des deux)
""")

guide_ok = st.checkbox("J'ai lu et compris le guide d'annotation")

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
def load_data():
    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig", engine="python")
    if "text" not in df.columns:
        st.error("Le fichier CSV doit contenir une colonne 'text'")
        st.stop()
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.split().str.len() >= 3]
    df = df.reset_index(drop=True)
    df["comment_id"] = df["text"].apply(lambda x: hashlib.md5(x.encode()).hexdigest())
    return df

# ✅ FONCTION MODIFIÉE : Lit Google Sheets COMME la partie admin
def load_annotations():
    if os.path.exists(ANNOT_FILE):
        local_df = pd.read_csv(ANNOT_FILE, encoding="utf-8")
    else:
        local_df = pd.DataFrame()
    
    # Récupérer Google Sheets comme dans save_annotation()
    if SHEETS_OK and sheet:
        try:
            records = sheet.get_all_records()
            if records:
                sheets_df = pd.DataFrame(records)
                # Ignorer les lignes avec en-têtes "Annotateur" (format résumé)
                sheets_df = sheets_df[~sheets_df.apply(lambda row: row.astype(str).str.contains("Annotateur").any(), axis=1)]
                if not sheets_df.empty and "comment_id" in sheets_df.columns:
                    sheets_df = sheets_df[['comment_id', 'email', 'label', 'type_abus', 'intensite', 'langue']]
                    # Fusionner local + sheets
                    combined = pd.concat([sheets_df, local_df], ignore_index=True)
                    return combined.drop_duplicates(subset=['comment_id', 'email'])
        except:
            pass
    
    return local_df

def get_available_comments(data, annotations, email):
    if annotations.empty:
        return data.reset_index(drop=True)

    annotations["comment_id"] = annotations["comment_id"].astype(str)
    data["comment_id"] = data["comment_id"].astype(str)

    user_done = annotations[annotations["email"] == email]["comment_id"].tolist()

    counts = annotations.groupby("comment_id").size()

    valid_ids = counts[counts < MAX_ANNOT].index.tolist()

    never_annotated = data[~data["comment_id"].isin(counts.index)]

    available = pd.concat([
        data[data["comment_id"].isin(valid_ids)],
        never_annotated
    ])

    available = available[~available["comment_id"].isin(user_done)]

    return available.reset_index(drop=True)

# ✅ FONCTION MODIFIÉE : APPEND + résumé (garder votre logique)
def save_annotation(row):
    # Sauvegarde locale
    annotations = load_annotations()
    new_row = pd.DataFrame([row])
    annotations = pd.concat([annotations, new_row], ignore_index=True)
    annotations.to_csv(ANNOT_FILE, index=False, encoding="utf-8")

    if not SHEETS_OK or not sheet:
        return

    # Récupérer annotations existantes
    records = sheet.get_all_records()
    if records:
        df = pd.DataFrame(records)
        # Filtrer les lignes résumé (contenant "Annotateur")
        df = df[~df.apply(lambda row: row.astype(str).str.contains("Annotateur").any(), axis=1)]
    else:
        df = pd.DataFrame(columns=["comment_id","email","label","type_abus","intensite","langue"])

    # Ajouter nouvelle annotation
    new_row = pd.DataFrame([row])
    df = pd.concat([df, new_row], ignore_index=True)

    # Générer résumé (votre logique exacte)
    data_admin = load_data()
    summary_list = []
    grouped = df.groupby("comment_id")

    for cid, group in grouped:
        match = data_admin.loc[data_admin["comment_id"] == cid, "text"]
        tweet_text = match.values[0] if not match.empty else ""

        annot_count = len(group)
        count_na = len(group[group["label"] == "non abusive"])
        count_a = len(group[group["label"] == "abusive"])
        final_class = 1 if count_a > count_na else 0

        labels = group["label"].tolist()
        ann1 = labels[0] if len(labels) > 0 else ""
        ann2 = labels[1] if len(labels) > 1 else ""
        ann3 = labels[2] if len(labels) > 2 else ""

        intensites = group["intensite"].tolist()
        int1 = intensites[0] if len(intensites) > 0 else ""
        int2 = intensites[1] if len(intensites) > 1 else ""
        int3 = intensites[2] if len(intensites) > 2 else ""

        langues = group["langue"].tolist()
        l1 = langues[0] if len(langues) > 0 else ""
        l2 = langues[1] if len(langues) > 1 else ""
        l3 = langues[2] if len(langues) > 2 else ""

        abus = group["type_abus"].tolist()
        a1 = abus[0] if len(abus) > 0 else ""
        a2 = abus[1] if len(abus) > 1 else ""
        a3 = abus[2] if len(abus) > 2 else ""

        summary_list.append({
            "Annotateur": annot_count,
            "Nbr-NA": count_na,
            "Nbr-A": count_a,
            "Class": final_class,
            "Ann1": ann1,
            "Ann2": ann2,
            "Ann3": ann3,
            "Int1": int1,
            "Int2": int2,
            "Int3": int3,
            "L1": l1,
            "L2": l2,
            "L3": l3,
            "Abus1": a1,
            "Abus2": a2,
            "Abus3": a3,
            "Commentaires": tweet_text
        })

    summary_df = pd.DataFrame(summary_list)
    data_to_write = [summary_df.columns.tolist()] + summary_df.values.tolist()
    sheet.update("A1", data_to_write)

# ---------------- UI (INCHANGÉE) ----------------
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

if not annotations.empty:
    annotations["comment_id"] = annotations["comment_id"].astype(str)
    data["comment_id"] = data["comment_id"].astype(str)
    annotations = annotations[annotations["comment_id"].isin(data["comment_id"])]
    annotations.to_csv(ANNOT_FILE, index=False, encoding="utf-8")

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
            "Type(s) d'abus",
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
            st.warning("Veuillez choisir si le commentaire est abusive ou non abusive.")
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

        st.session_state.label_key += 1
        st.session_state.type_key += 1
        st.session_state.intensite_key += 1
        st.session_state.langue_key += 1
        st.session_state.idx += 1

        st.success("✅ Sauvegardé !" + (" (Google Sheets)" if SHEETS_OK else " (local)"))
        st.rerun()

# ---------------- ADMIN SECTION (INCHANGÉE) ----------------
st.markdown("---")

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
            match = data_admin.loc[data_admin["comment_id"] == cid, "text"]
            if not match.empty:
                tweet_text = match.values[0]
            else:
                tweet_text = "Commentaire introuvable (ID absent du dataset)"

            annot_count = len(group)
            count_na = len(group[group["label"] == "non abusive"])
            count_a = len(group[group["label"] == "abusive"])
            final_class = 1 if count_a > count_na else 0

            labels = group["label"].tolist()
            ann1 = labels[0] if len(labels) > 0 else ""
            ann2 = labels[1] if len(labels) > 1 else ""
            ann3 = labels[2] if len(labels) > 2 else ""

            intensites = group["intensite"].tolist()
            intensite1 = intensites[0] if len(intensites) > 0 else ""
            intensite2 = intensites[1] if len(intensites) > 1 else ""
            intensite3 = intensites[2] if len(intensites) > 2 else ""

            langues = group["langue"].tolist()
            langue1 = langues[0] if len(langues) > 0 else ""
            langue2 = langues[1] if len(langues) > 1 else ""
            langue3 = langues[2] if len(langues) > 2 else ""

            abus = group["type_abus"].tolist()
            abus1 = abus[0] if len(abus) > 0 else ""
            abus2 = abus[1] if len(abus) > 1 else ""
            abus3 = abus[2] if len(abus) > 2 else ""

            summary_list.append({
                "Annotateur": annot_count,
                "Nbr-NA": count_na,
                "Nbr-A": count_a,
                "Class": final_class,
                "Ann1": ann1,
                "Ann2": ann2,
                "Ann3": ann3,
                "Int1": intensite1,
                "Int2": intensite2,
                "Int3": intensite3,
                "L1": langue1,
                "L2": langue2,
                "L3": langue3,
                "Abus1": abus1,
                "Abus2": abus2,
                "Abus3": abus3,
                "Commentaires": tweet_text
            })
        
        summary_df = pd.DataFrame(summary_list)
        st.dataframe(summary_df)

        st.download_button(
            label="⬇️ Télécharger Annotation_format.csv",
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
            st.session_state.langue_key = 0
            st.success("Annotations supprimées ✅")
            st.rerun()
        else:
            st.info("Aucun fichier à supprimer.")
