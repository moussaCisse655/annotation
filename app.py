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

# ---------------- GOOGLE SHEETS (OPTIMISÉ) ----------------
@st.cache_resource
def init_sheets():
    """Initialise la connexion Google Sheets une seule fois"""
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"]
    )
    
    scoped_credentials = credentials.with_scopes([
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    
    client = gspread.authorize(scoped_credentials)
    sheet = client.open("Annotations").sheet1
    
    # Vérifier les headers
    headers = ["comment_id", "email", "label", "type_abus", "intensite", "langue", "timestamp"]
    current_headers = sheet.row_values(1)
    if current_headers != headers:
        sheet.clear()
        sheet.append_row(headers)
    
    return sheet

# Initialiser Sheets
try:
    sheet = init_sheets()
    SHEETS_OK = True
except Exception as e:
    st.error(f"❌ Erreur Google Sheets: {str(e)[:100]}...")
    st.info("💡 Vérifiez que le service account a accès au Sheet 'Annotations'")
    SHEETS_OK = False

st.title("📝 Plateforme d'annotation")

with st.expander("📘 Guide d'annotation (Obligatoire)"):
    st.markdown("""
### Objectif
Cette plateforme sert à annoter des commentaires pour un mémoire de recherche en NLP.
Votre rôle est d'identifier si un commentaire est abusif et, si oui, préciser son type et son intensité.

### Abusive / Non abusive
- **abusive** : le commentaire contient une attaque dirigée contre une personne ou un groupe.
- **non abusive** : commentaire neutre, informatif ou critique sans attaque personnelle.

### Types d'abus (à choisir uniquement si "abusive")
- **Insulte** : mot offensant ou dégradant visant une personne (ex: idiot, imbécile, nul, etc.)
- **Menace** : expression d'une intention de nuire physiquement ou moralement
- **Harcèlement** : attaques répétées, intimidation ou pression continue
- **Haine** : discours visant un groupe basé sur la religion, l'ethnie, etc.
- **Discrimination** : exclusion, traitement injuste basé sur l'identité
- **Autre** : abus qui ne correspond à aucune catégorie

### Intensité
- **faible** : attaque légère ou indirecte
- **moyenne** : attaque claire et explicite  
- **élevée** : attaque grave, violente ou très agressive

### Langue
- Français
- Wolof  
- Français-Wolof (mélange des deux)
    """)

guide_ok = st.checkbox("J'ai lu et compris le guide d'annotation")

# ---------------- SESSION STATE ----------------
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "last_email" not in st.session_state:
    st.session_state.last_email = ""
if "keys" not in st.session_state:
    st.session_state.keys = {"label": 0, "type": 0, "intensite": 0, "langue": 0}

# ---------------- LOAD DATA ----------------
@st.cache_data
def load_data():
    if not os.path.exists(DATA_FILE):
        st.error(f"Fichier {DATA_FILE} manquant")
        st.stop()
    
    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    if "text" not in df.columns:
        st.error("CSV doit contenir colonne 'text'")
        st.stop()
    
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.split().str.len() >= 3].reset_index(drop=True)
    df["comment_id"] = df["text"].apply(lambda x: hashlib.md5(x.encode()).hexdigest())
    return df

@st.cache_data
def load_annotations():
    if os.path.exists(ANNOT_FILE):
        return pd.read_csv(ANNOT_FILE, encoding="utf-8")
    return pd.DataFrame(columns=["comment_id", "email", "label", "type_abus", "intensite", "langue"])

def save_annotation(row):
    if not SHEETS_OK:
        # Sauvegarde locale si Sheets KO
        annotations = load_annotations()
        new_row = pd.DataFrame([row])
        annotations = pd.concat([annotations, new_row], ignore_index=True)
        annotations.to_csv(ANNOT_FILE, index=False, encoding="utf-8")
        return
    
    sheet.append_row([
        row["comment_id"], row["email"], row["label"], 
        row["type_abus"], row["intensite"], row["langue"],
        pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    ])

def get_available_comments(data, annotations, email):
    if annotations.empty:
        return data
    
    annotations["comment_id"] = annotations["comment_id"].astype(str)
    total_count = annotations["comment_id"].value_counts()
    user_annotated = annotations[annotations["email"] == email]["comment_id"].unique()
    
    mask = (
        data["comment_id"].map(total_count).fillna(0) < MAX_ANNOT &
        ~data["comment_id"].isin(user_annotated)
    )
    return data[mask]

# ---------------- UI PRINCIPALE ----------------
email = st.text_input("📧 Entrez votre email")

if st.session_state.last_email != email:
    st.session_state.idx = 0
    st.session_state.last_email = email

if not email:
    st.info("👆 Entrez votre email pour commencer")
    st.stop()

if not guide_ok:
    st.warning("📖 Lisez et acceptez le guide avant de commencer")
    st.stop()

data = load_data()
annotations = load_annotations()

# Nettoyage annotations obsolètes
if not annotations.empty:
    annotations["comment_id"] = annotations["comment_id"].astype(str)
    data["comment_id"] = data["comment_id"].astype(str)
    annotations = annotations[annotations["comment_id"].isin(data["comment_id"])]
    annotations.to_csv(ANNOT_FILE, index=False, encoding="utf-8")

available = get_available_comments(data, annotations, email)

if available.empty:
    st.success("🎉 Tous les commentaires ont 3 annotations ou vous avez tout terminé !")
    row = None
else:
    if st.session_state.idx >= len(available):
        st.success("🎉 Votre session d'annotation est terminée !")
        row = None
    else:
        row = available.iloc[st.session_state.idx]

# ---------------- ANNOTATION ----------------
if row is not None:
    st.markdown("---")
    st.markdown("### 💬 Commentaire à annoter")
    st.info(row["text"])
    
    with st.form("annotation_form"):
        langue = st.multiselect(
            "Langue", ["Français", "Wolof", "Français-Wolof"],
            key=f"langue_{st.session_state.keys['langue']}"
        )
        
        label = st.selectbox(
            "Ce commentaire est-il abusif ?",
            ["Choisir...", "abusive", "non abusive"],
            key=f"label_{st.session_state.keys['label']}"
        )
        
        type_abus = st.multiselect(
            "Type(s) d'abus", 
            ["Insulte", "Haine", "Menace", "Harcèlement", "Discrimination", "Autre"],
            key=f"type_{st.session_state.keys['type']}"
        )
        
        intensite = st.multiselect(
            "Intensité", ["faible", "moyenne", "élevée"],
            key=f"intensite_{st.session_state.keys['intensite']}"
        )
        
        submit = st.form_submit_button("💾 Enregistrer et suivant", use_container_width=True)
        
        if submit:
            if label == "Choisir...":
                st.error("❌ Choisissez si abusive ou non abusive")
                st.stop()
            if not langue:
                st.error("❌ Sélectionnez au moins une langue")
                st.stop()
            if "Français-Wolof" in langue and len(langue) > 1:
                st.error("❌ Français-Wolof = pas d'autres langues")
                st.stop()
            
            save_annotation({
                "comment_id": row["comment_id"],
                "email": email,
                "label": label,
                "type_abus": ", ".join(type_abus) if label == "abusive" else "",
                "intensite": ", ".join(intensite) if label == "abusive" else "",
                "langue": ", ".join(langue)
            })
            
            # Incrémenter keys et index
            for key in st.session_state.keys:
                st.session_state.keys[key] += 1
            st.session_state.idx += 1
            
            st.success("✅ Annotation enregistrée !")
            st.rerun()

# ---------------- ADMIN ----------------
st.markdown("---")
if email in ADMIN_EMAILS:
    st.subheader("🔐 Zone Admin")
    
    if st.button("🔄 Recharger données", key="refresh"):
        st.cache_data.clear()
        st.rerun()
    
    annotations = load_annotations()
    data_admin = load_data()
    
    if annotations.empty:
        st.info("Aucune annotation")
    else:
        # Résumé complet
        summary_list = []
        grouped = annotations.groupby("comment_id")
        
        for cid, group in grouped:
            match = data_admin[data_admin["comment_id"] == cid]["text"]
            text = match.values[0] if len(match) > 0 else "Introuvable"
            
            count_na = len(group[group["label"] == "non abusive"])
            count_a = len(group[group["label"] == "abusive"])
            final_class = 1 if count_a > count_na else 0
            
            summary_list.append({
                "Annotations": len(group), "Non-abusive": count_na, 
                "Abusive": count_a, "Classe": final_class,
                "Commentaire": text[:100] + "..." if len(text) > 100 else text
            })
        
        summary_df = pd.DataFrame(summary_list)
        st.dataframe(summary_df, use_container_width=True)
        
        csv = summary_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "⬇️ Télécharger rapport CSV", csv, "rapport_annotations.csv", "text/csv"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Supprimer annotations locales"):
                if os.path.exists(ANNOT_FILE):
                    os.remove(ANNOT_FILE)
                    st.success("Local supprimé")
                    st.rerun()
        
        with col2:
            if SHEETS_OK and st.button("🔄 Synchroniser Sheets → Local"):
                # Récupérer depuis Sheets
                all_rows = sheet.get_all_records()
                if all_rows:
                    df_sheets = pd.DataFrame(all_rows)
                    df_sheets.to_csv(ANNOT_FILE, index=False, encoding="utf-8")
                    st.success(f"Sync OK: {len(df_sheets)} lignes")
                    st.rerun()

st.markdown("---")
st.caption("👨‍💻 Moussa Cissé - Mémoire NLP Annotation")
