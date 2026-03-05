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

# ---------------- GUIDE ----------------
with st.expander("📘 Guide d'annotation (Obligatoire)"):
    st.markdown("""
### Objectif
Cette plateforme sert à annoter des commentaires pour un mémoire de recherche en NLP.
Votre rôle est d'identifier si un commentaire est abusif et, si oui, préciser son type et son intensité.

### Abusive / Non abusive
- **abusive** : le commentaire contient une attaque dirigée contre une personne ou un groupe.
- **non abusive** : commentaire neutre, informatif ou critique sans attaque personnelle.

### Types d'abus (à choisir uniquement si "abusive")
- **Insulte** : mot offensant ou dégradant visant une personne  
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

# ---------------- SESSION STATE SIMPLIFIÉ ----------------
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

# ---------------- FONCTIONS DATA ----------------
@st.cache_data
def load_data():
    if not os.path.exists(DATA_FILE):
        st.error(f"❌ Fichier {DATA_FILE} manquant. Ajoutez-le à la racine.")
        st.stop()
    
    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    if "text" not in df.columns:
        st.error("❌ CSV doit contenir colonne 'text'")
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

def save_annotation_local(row):
    """Sauvegarde locale (Sheets OFF)"""
    annotations = load_annotations()
    new_row = pd.DataFrame([row])
    annotations = pd.concat([annotations, new_row], ignore_index=True)
    annotations.to_csv(ANNOT_FILE, index=False, encoding="utf-8")

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

# Mode local (Sheets OFF pour l'instant)
st.warning("🟡 **MODE LOCAL** - Google Sheets désactivé (API à activer)")

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
    
    langue = st.multiselect(
        "Langue", ["Français", "Wolof", "Français-Wolof"],
        key=f"langue_{st.session_state.langue_key}"
    )
    
    label = st.selectbox(
        "Ce commentaire est-il abusif ?",
        ["Choisir...", "abusive", "non abusive"],
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
            "Intensité", ["faible", "moyenne", "élevée"],
            key=f"intensite_{st.session_state.intensite_key}"
        )
    
    if st.button("💾 Enregistrer et suivant", use_container_width=True):
        if label == "Choisir...":
            st.error("❌ Choisissez si abusive ou non abusive")
            st.stop()
        if not langue:
            st.error("❌ Sélectionnez au moins une langue")
            st.stop()
        if "Français-Wolof" in langue and len(langue) > 1:
            st.error("❌ Français-Wolof = pas d'autres langues")
            st.stop()
        
        save_annotation_local({
            "comment_id": row["comment_id"],
            "email": email,
            "label": label,
            "type_abus": ", ".join(type_abus) if label == "abusive" else "",
            "intensite": ", ".join(intensite) if label == "abusive" else "",
            "langue": ", ".join(langue)
        })
        
        # Reset keys et next
        st.session_state.label_key += 1
        st.session_state.type_key += 1
        st.session_state.intensite_key += 1
        st.session_state.langue_key += 1
        st.session_state.idx += 1
        
        st.success("✅ Annotation enregistrée localement !")
        st.rerun()

# ---------------- ADMIN ----------------
st.markdown("---")
if email in ADMIN_EMAILS:
    st.subheader("🔐 Zone Admin")
    
    if st.button("🔄 Recharger données"):
        st.cache_data.clear()
        st.rerun()
    
    annotations = load_annotations()
    data_admin = load_data()
    
    if annotations.empty:
        st.info("Aucune annotation")
    else:
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
            if st.button("🗑️ Reset annotations"):
                if os.path.exists(ANNOT_FILE):
                    os.remove(ANNOT_FILE)
                    st.success("Reset OK")
                    st.rerun()

st.markdown("---")
st.caption("👨‍💻 Moussa Cissé - Mémoire NLP Annotation (Mode Local)")
