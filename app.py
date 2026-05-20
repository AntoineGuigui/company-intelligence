"""
app.py — Streamlit interface for the Defence Company Intelligence Generator.
Output: DataBase.xlsm-compatible Excel (same schema as Company Profile Generator).

Each analysis adds/updates a row in the shared Excel database, which can then
be used directly by the Company Profile Generator to produce PPTX slides.
"""

import os
import re
import streamlit as st
from pathlib import Path

from pipeline.collector import collect
from pipeline.extractor import extract
from pipeline.excel_generator import generate_excel

# -------------------------------------------------------
# CONFIG
# -------------------------------------------------------
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Excel database — same format as Company Profile Generator
EXCEL_PATH = OUTPUT_DIR / "DataBase.xlsx"

st.set_page_config(
    page_title="Defence Intelligence Generator",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Configuration")
    st.markdown("---")

    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-...",
    )

    model = st.selectbox(
        "Modèle LLM",
        ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
        index=0,
        help="gpt-4o-mini = moins cher (~0.02€) | gpt-4o = meilleure qualité (~0.10€)",
    )

    st.markdown("---")
    st.markdown("### 📊 Format DataBase.xlsm")
    st.markdown("""
    Chaque analyse **ajoute une ligne** dans le même format
    que `DataBase.xlsm`, compatible avec le 
    **Company Profile Generator** (Flask → PPTX).
    
    **6 feuilles :**
    - `DataBase` — infos générales (14 colonnes)
    - `Revenue` — revenus par FY
    - `EBIT` — EBIT par FY
    - `Net Profit` — résultat net par FY
    - `EBIT Margin` — marge EBIT % par FY
    - `Net Profit Margin` — marge nette % par FY
    """)

    st.markdown("---")
    if EXCEL_PATH.exists():
        with open(EXCEL_PATH, "rb") as f:
            st.download_button(
                "⬇️ Télécharger DataBase.xlsx",
                f,
                file_name="DataBase.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        if st.button("🗑️ Réinitialiser la base", use_container_width=True):
            EXCEL_PATH.unlink()
            st.success("Base réinitialisée.")
            st.rerun()

    st.markdown("---")
    st.markdown("### 💡 Exemples")
    st.markdown("""
    - `Thales` · France · `HO.PA`
    - `Rheinmetall` · Germany · `RHM.DE`
    - `MBDA` · France · *(privé)*
    - `BAE Systems` · UK · `BA.L`
    - `Leonardo` · Italy · `LDO.MI`
    - `Safran` · France · `SAF.PA`
    """)

# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
st.title("🛡️ Defence Company Intelligence Generator")
st.markdown("*Web scraping + GPT-4o → DataBase.xlsm → Company Profile Generator*")
st.markdown("---")

col1, col2, col3 = st.columns([2, 1.5, 1])
with col1:
    company = st.text_input("🏢 Entreprise", placeholder="ex: Thales, MBDA, Rheinmetall...")
with col2:
    country = st.text_input("🌍 Pays", placeholder="ex: France, Germany, UK...")
with col3:
    ticker = st.text_input("📈 Ticker *(optionnel)*", placeholder="ex: HO.PA")

st.markdown("")
generate_btn = st.button(
    "🔍 Analyser et ajouter à la base",
    type="primary",
    disabled=not (company and country and api_key),
)

if not api_key:
    st.info("👈 Entre ta clé API OpenAI dans la sidebar pour commencer.")

if generate_btn and company and country and api_key:

    # -------------------------------------------------------
    # ÉTAPE 1 — Collecte
    # -------------------------------------------------------
    with st.status("🔎 Collecte des données...", expanded=True) as status:
        st.write("Recherche DuckDuckGo + Yahoo Finance...")
        try:
            raw_data = collect(company, country, ticker)
            n_sources = sum(1 for v in raw_data.values() if v)
            st.write(f"✅ {n_sources} sources collectées")
            status.update(label="✅ Données collectées", state="complete")
        except Exception as e:
            st.error(f"❌ Erreur collecte : {e}")
            st.stop()

    # -------------------------------------------------------
    # ÉTAPE 2 — Extraction LLM
    # -------------------------------------------------------
    with st.status("🧠 Extraction structurée...", expanded=True) as status:
        st.write(f"Analyse via {model}...")
        try:
            structured_data = extract(company, country, raw_data, api_key, model)
            st.write("✅ Données structurées extraites")
            status.update(label="✅ Analyse terminée", state="complete")
        except Exception as e:
            st.error(f"❌ Erreur LLM : {e}")
            st.stop()

    # -------------------------------------------------------
    # ÉTAPE 3 — Écriture Excel (format DataBase.xlsm)
    # -------------------------------------------------------
    with st.status("📊 Écriture dans DataBase...", expanded=True) as status:
        try:
            generate_excel(structured_data, str(EXCEL_PATH))
            st.write("✅ Ligne ajoutée/mise à jour dans DataBase.xlsx")
            status.update(label="✅ Excel mis à jour", state="complete")
        except Exception as e:
            st.error(f"❌ Erreur Excel : {e}")
            st.stop()

    # -------------------------------------------------------
    # RÉSULTATS
    # -------------------------------------------------------
    st.success(f"🎉 **{company}** ({country}) ajouté à la base !")
    st.markdown("---")

    dl_col, preview_col = st.columns([1, 2])

    with dl_col:
        st.markdown("### 📥 Télécharger")
        with open(EXCEL_PATH, "rb") as f:
            st.download_button(
                label="⬇️ DataBase.xlsx",
                data=f,
                file_name="DataBase.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary",
            )
        st.caption(
            "Ce fichier est directement compatible avec le "
            "Company Profile Generator (Flask → PPTX)."
        )

    with preview_col:
        st.markdown("### 📋 Aperçu")
        kf = structured_data.get("key_facts", {})
        fin = structured_data.get("financials", {})

        # Find most recent FY with data
        latest_fy = None
        for fy in sorted(fin.keys(), reverse=True):
            if isinstance(fin[fy], dict) and any(v for v in fin[fy].values()):
                latest_fy = fy
                break

        latest = fin.get(latest_fy, {}) if latest_fy else {}

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Employés", structured_data.get("employees", "N/A"))
        with c2:
            rev = latest.get("revenues")
            st.metric(
                f"Revenus {latest_fy or ''}",
                f"{rev:,.0f} M€" if rev else "N/A",
            )
        with c3:
            margin = latest.get("ebit_margin")
            st.metric(
                f"Marge EBIT {latest_fy or ''}",
                f"{margin:.1f}%" if margin else "N/A",
            )
        with c4:
            ci = structured_data.get("confidence_index", "?")
            st.metric("Confiance", f"{'⭐' * int(ci)}" if str(ci).isdigit() else ci)

        st.markdown(
            f"**Fondée :** {structured_data.get('founded', 'N/A')}  |  "
            f"**Siège :** {structured_data.get('locations', 'N/A')}  |  "
            f"**Ownership :** {structured_data.get('type_ownership', 'N/A')}"
        )
        st.info(structured_data.get("synthetic_comment", ""))

    with st.expander("🔍 JSON complet extrait"):
        st.json(structured_data)

# -------------------------------------------------------
# FOOTER
# -------------------------------------------------------
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:gray;font-size:12px'>"
    "Defence Intelligence Generator · DuckDuckGo + Yahoo Finance + GPT-4o → DataBase.xlsm"
    "</div>",
    unsafe_allow_html=True,
)
