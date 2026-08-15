import streamlit as st
import json
import pandas as pd
import random
from google.oauth2 import service_account
from google.cloud import firestore
import plotly.express as px
from datetime import datetime
import os
import re
from datetime import datetime, timedelta

FEED_PATH = "feed_lega.json"

def load_feed():
    if os.path.exists(FEED_PATH):
        with open(FEED_PATH, "r") as f:
            return json.load(f)
    return []

def save_feed(data):
    with open(FEED_PATH, "w") as f:
        json.dump(data, f, indent=4)

def log_evento(nome_squadra, icona, testo):
    feed = load_feed()
    
    # --- FIX SICUREZZA: Se per errore il file JSON è un dizionario, forzalo a lista vuota ---
    if not isinstance(feed, list):
        feed = []
        
    orario = (datetime.utcnow() + timedelta(hours=2)).strftime("%d/%m %H:%M")    
    
    # Inserisce la nuova notizia in CIMA alla lista
    feed.insert(0, {"data": orario, "squadra": nome_squadra, "icona": icona, "testo": testo})
    save_feed(feed)

st.set_page_config(page_title="Osei Football League", layout="wide", initial_sidebar_state="expanded")

# --- CSS GLOBALE PER ALLUNGARE I MENU A TENDINA ---
st.markdown("""
<style>
/* Opzione Nucleare: Forza l'altezza massima delle tendine di Streamlit */
div[data-baseweb="popover"] > div {
    max-height: 500px !important;
}
div[data-baseweb="popover"] > div > div {
    max-height: 500px !important;
}
ul[role="listbox"] {
    max-height: 500px !important;
}
ul[data-baseweb="menu"] {
    max-height: 500px !important;
}
/* Bersaglia eventuali stili inline fissati a 300px dal motore React */
div[style*="max-height: 300px"], div[style*="max-height: 250px"] {
    max-height: 500px !important;
}
</style>
""", unsafe_allow_html=True)

# --- CONNESSIONE DATABASE FIRESTORE ---
@st.cache_resource
def get_db_connection():
    # Legge la chiave segreta dalla cassaforte di Streamlit, usando il nuovo formato [firebase]
    key_dict = json.loads(st.secrets["firebase"]["my_project_settings"])
    
    # Questo è l'unico "trucco" che serve per le chiavi in ambiente cloud
    if "\\n" in key_dict["private_key"]:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        
    creds = service_account.Credentials.from_service_account_info(key_dict)
    return firestore.Client(credentials=creds)

firestore_db = get_db_connection()

# --- FUNZIONI DATI E LOGICA ---
def load_data(doc_name):
    # Cerca il documento nel database Cloud
    doc_ref = firestore_db.collection("ofl_database").document(doc_name)
    doc = doc_ref.get()
    
    if doc.exists:
        # Trasforma i dati salvati di nuovo in formato Python
        return json.loads(doc.to_dict()["dati_json"])
    else:
        # Se il database è vuoto (la primissima volta), crea le liste vuote
        return {} if doc_name in ["squadre", "coppe"] else []

def save_data(data, doc_name):
    doc_ref = firestore_db.collection("ofl_database").document(doc_name)
    # Invia i dati al sicuro nel Cloud
    doc_ref.set({"dati_json": json.dumps(data, ensure_ascii=False)})

def init_bilancio():
    return {
        "ricavi": {"nuovo_capitale": 0.0, "premi_sportivi": 0.0, "sponsor": 0.0, "incassi_stadio": 0.0, "plusvalenze": 0.0},
        "costi": {"ammortamenti": 0.0, "monte_ingaggi": 0.0, "gestione_stadio": 0.0, "minusvalenze": 0.0, "costi_giocatori_ceduti": 0.0},
        "storico_movimenti": []
    }

def init_coppe():
    return {
        "ci": {"quarti": [], "semis": [], "finale": [], "perse_semis": [], "premi_dati": False},
        "cl": {
            "gir_A": [], "gir_B": [], 
            "punti_A": {}, "punti_B": {},
            "semis_andata": [], "semis_ritorno": [], 
            "finale": [], "perse_semis": [], "premi_dati": False
        }
    }

def genera_calendario_berger(squadre_lista, num_giornate):
    n = len(squadre_lista)
    squadre = list(squadre_lista)
    matchdays = []
    
    # Genera il girone di base (7 giornate)
    for i in range(n - 1):
        matchday = []
        for j in range(n // 2):
            home = squadre[j]
            away = squadre[n - 1 - j]
            if j == 0 and i % 2 == 1:
                home, away = away, home 
            matchday.append({"home": home, "away": away, "gol_home": 0, "gol_away": 0, "giocata": False, "incassi_assegnati": False})
        matchdays.append(matchday)
        squadre.insert(1, squadre.pop())
        
    # Costruisce il calendario fino al numero esatto di giornate richiesto
    full_calendar = []
    round_num = 0
    while len(full_calendar) < num_giornate:
        for md in matchdays:
            if len(full_calendar) < num_giornate:
                new_md = []
                for match in md:
                    # Inverte casa/trasferta a ogni nuovo girone
                    if round_num % 2 == 1: 
                        new_md.append({"home": match["away"], "away": match["home"], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi_assegnati": False})
                    else: 
                        new_md.append({"home": match["home"], "away": match["away"], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi_assegnati": False})
                full_calendar.append(new_md)
        round_num += 1
        
    return full_calendar

DB_PATH = "squadre"
CAL_PATH = "calendario"
COPPE_PATH = "coppe"

# --- GESTIONE ACCESSO ADMIN ---
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

st.sidebar.title("🔐 Accesso")
if not st.session_state.is_admin:
    pwd = st.sidebar.text_input("Password Admin", type="password")
    if pwd == "osei":
        st.session_state.is_admin = True
        st.rerun()
    elif pwd:
        st.sidebar.error("Password errata")
else:
    st.sidebar.success("👑 Modalità Admin")
    if st.sidebar.button("Logout"):
        st.session_state.is_admin = False
        st.rerun()

st.sidebar.divider()

# --- SIDEBAR NAVIGAZIONE ---
st.sidebar.title("⚽ OFL Manager")
menu = st.sidebar.radio("Navigazione", [
    "1. Setup Società", 
    "2. Dashboard & Rosa", 
    "3. Mercato (Definitivi)", 
    "4. Mercato (Prestiti)",
    "5. Calendario & Partite",
    "6. Classifica Campionato",
    "7. Coppe (Italia & CL)",
    "8. Chiusura Fiscale Bilancio",
    "9. Cronologia Ufficialità",
    "10. Regolamento Ufficiale"
])

# ==========================================
# --- CARICAMENTO DATI OTTIMIZZATO (CLOUD) ---
# ==========================================
# Impostiamo variabili vuote di default
db, calendario, coppe = {}, [], {}

# Scarica le SQUADRE (servono in quasi tutte le pagine, tranne il Regolamento)
if menu != "9. Regolamento Ufficiale":
    db = load_data(DB_PATH)
    for sq in db.values():
        if "costi_giocatori_ceduti" not in sq["bilancio"]["costi"]:
            sq["bilancio"]["costi"]["costi_giocatori_ceduti"] = 0.0

# Scarica il CALENDARIO (serve solo in queste due pagine)
if menu in ["5. Calendario & Partite", "6. Classifica Campionato"]:
    calendario = load_data(CAL_PATH)

# Scarica le COPPE (servono solo in queste due pagine)
if menu in ["5. Calendario & Partite", "7. Coppe (Italia & CL)"]:
    coppe = load_data(COPPE_PATH)
    if not coppe: coppe = init_coppe()

# Mettilo nella pagina principale, visibile sempre (o magari solo nel Menu 2 se preferisci)
ultimi_movimenti = []
for nome_sq, dati_sq in db.items():
    if dati_sq['bilancio'].get('storico_movimenti'):
        # Prende l'ultimo movimento della squadra e ci attacca il nome
        ultimo = dati_sq['bilancio']['storico_movimenti'][-1]
        ultimi_movimenti.append(f"**{nome_sq}**: {ultimo}")

# ==========================================
# 1. SETUP SOCIETÀ
# ==========================================
if menu == "1. Setup Società":
    st.header("🏢 Gestione Società")

    if not st.session_state.is_admin:
        st.error("🔒 Accesso riservato. Solo l'Amministratore della Lega può effettuare operazioni di mercato.")
    else:
        with st.form("crea_squadra"):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome Squadra")
            mister = c2.text_input("Allenatore")
            if st.form_submit_button("Iscrivi Squadra (Fondo 500M)"):
                if nome and mister and nome not in db:
                    db[nome] = {
                        "allenatore": mister, "cassa": 500.0,
                        "stadio": {"livello": None, "costo_annuo": 0, "base": 0, "pari": 0, "vittoria": 0},
                        "sponsor": {"nome": None, "valore": 0},
                        "rosa": [], "bilancio": init_bilancio()
                    }
                    save_data(db, DB_PATH)
                    st.success(f"Società {nome} creata!")
                elif nome in db:
                    st.error("Squadra già esistente!")

        st.divider()
        if db:
            sq_sel = st.selectbox("Seleziona Squadra", list(db.keys()))
            sq_dati = db[sq_sel]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Stadio")
                # CONTROLLO: Se lo stadio è già stato scelto, nasconde il menu e mostra l'info
                if sq_dati["stadio"].get("livello"):
                    st.info(f"✅ **Stadio Confermato:** Impianto da {sq_dati['stadio']['livello']} posti.")
                else:
                    stadi = {
                        "Categoria 1 (20.000 posti) - 7M Costo": {"livello": "20k", "costo": 7.0, "base": 0.2, "pari": 0.3, "vittoria": 0.6},
                        "Categoria 2 (50.000 posti) - 17M Costo": {"livello": "50k", "costo": 17.0, "base": 0.4, "pari": 0.7, "vittoria": 1.3},
                        "Categoria 3 (80.000 posti) - 28M Costo": {"livello": "80k", "costo": 28.0, "base": 0.8, "pari": 1.4, "vittoria": 2.1}
                    }
                    scelta = st.selectbox("Livello Stadio", list(stadi.keys()))
                    if st.button("Firma Contratto Stadio"):
                        costo_nuovo = stadi[scelta]["costo"]
                        costo_vecchio = sq_dati["bilancio"]["costi"]["gestione_stadio"]
                        
                        # Rimborsa l'eventuale stadio vecchio (se sta cambiando idea) e addebita il nuovo
                        sq_dati["cassa"] = round(sq_dati["cassa"] + costo_vecchio - costo_nuovo, 2)
                        
                        sq_dati["stadio"] = stadi[scelta]
                        sq_dati["bilancio"]["costi"]["gestione_stadio"] = costo_nuovo
                        
                        if costo_vecchio == 0:
                            sq_dati['bilancio']['storico_movimenti'].append(f"Affitto Stadio ({stadi[scelta]['livello']}): -{costo_nuovo}M")
                        
                        save_data(db, DB_PATH)
                        log_evento(sq_sel, "🏟️", f"ha ufficializzato il nuovo stadio ({stadi[scelta]['livello']}).")
                        st.toast(f"Stadio firmato! Pagato l'affitto annuale di {costo_nuovo}M.", icon="🏟️")
                        st.rerun() # Ricarica istantaneamente la pagina per mostrare il blocco ✅

            with col2:
                st.subheader("Sponsor")
                # CONTROLLO: Se lo sponsor ha già un nome, nasconde l'input e mostra l'info
                if sq_dati["sponsor"].get("nome"):
                    st.info(f"✅ **Sponsor Confermato:** Accordo siglato con {sq_dati['sponsor']['nome']}.")
                else:
                    ns = st.text_input("Nome Sponsor", value=sq_dati["sponsor"]["nome"] or "")
                    
                    if st.button("Firma Accordo Sponsor"):
                        if ns.strip(): # Evita che qualcuno firmi lasciando il nome vuoto
                            sq_dati["sponsor"] = {"nome": ns, "valore": 40.0}
                            # Accredita i 40M solo se la voce sponsor a bilancio è ancora a zero
                            if sq_dati["bilancio"]["ricavi"]["sponsor"] == 0.0:
                                sq_dati["bilancio"]["ricavi"]["sponsor"] = 40.0
                                sq_dati["cassa"] = round(sq_dati["cassa"] + 40.0, 2)
                                sq_dati['bilancio']['storico_movimenti'].append(f"Sponsor di Fondazione: +40.0M")
                            
                            save_data(db, DB_PATH)
                            log_evento(sq_sel, "💼", f"ha firmato il contratto di Sponsorizzazione Stagionale per **40.0 M**.")
                            st.toast(f"Sponsor {ns} firmato! 40 Milioni accreditati.", icon="💼")
                            st.rerun() # Ricarica istantaneamente la pagina per mostrare il blocco ✅
                        else:
                            st.warning("⚠️ Inserisci il nome dello sponsor prima di firmare!")

# ==========================================
# 2. DASHBOARD & ROSA (MODERN UI V5 - DEFINITIVA)
# ==========================================
elif menu == "2. Dashboard & Rosa":
    
    st.header("📊 Dashboard & Rosa") # <-- AGGIUNTO IL TITOLO!
    
    # --- CSS PER IL TEMA E LA TABELLA CUSTOM ---
    st.markdown("""
    <style>
    
    /* Stile per le metriche in alto */
    div[data-testid="metric-container"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03);
    }
    
    /* Stile per la tabella Roster Custom */
    .roster-table {
        width: 100%;
        border-collapse: collapse;
        background-color: #FFFFFF;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03);
        font-family: sans-serif;
    }
    .roster-table th {
        background-color: #F8FAFC;
        color: #64748B;
        font-weight: 600;
        font-size: 13px;
        text-align: left;
        padding: 12px 15px;
        border-bottom: 2px solid #E2E8F0;
    }
    .roster-table td {
        padding: 12px 15px;
        border-bottom: 1px solid #F1F5F9;
        color: #334155;
        font-size: 14px;
    }
    .roster-table tr:last-child td {
        border-bottom: none;
    }
    .roster-table tr:hover {
        background-color: #F8FAFC;
    }
    </style>
    """, unsafe_allow_html=True)

    if not db: 
        st.warning("Nessuna squadra presente.")
    else:
        sq_sel = st.selectbox("Seleziona Squadra", list(db.keys()))
        squadra = db[sq_sel]
        b = squadra['bilancio']
        
        # --- CALCOLI FINANZIARI & COSTI GIOCATORI ---
        tot_ammortamenti, tot_ingaggi = 0.0, 0.0
        giocatori_con_costo = [] 
        opportunita_rinnovo = [] 
        
        for g in squadra['rosa']:
            amm = g['ammortamento_annuo']
            stip = g['stipendio']
            anni_res = g['anni_contratto'] - g.get('anni_trascorsi', 0)
            # Se il numero è intero (es. 1.0), toglie il decimale trasformandolo in 1
            anni_res = int(anni_res) if anni_res % 1 == 0 else anni_res
            
            if g.get('acquistato_a_gennaio') and g['anni_trascorsi'] == 0:
                amm /= 2; stip /= 2
            elif g.get('rinnovato_a_gennaio') and g['anni_trascorsi'] == 0:
                amm = (g.get('vecchio_amm_gennaio', amm) / 2) + (g['ammortamento_annuo'] / 2)
                stip = (g.get('vecchio_stip_gennaio', stip) / 2) + (g['stipendio'] / 2)
                
            costo_reale_anno = 0
            
            # -----------------------------------------------
            # INIZIO NUOVO BLOCCO FINANZIARIO E TABELLE
            # -----------------------------------------------
            if g.get("prestato_a"):
                # 1. CEDUTO IN PRESTITO (Paga l'ammortamento totale + la quota stipendio che l'acquirente non paga)
                tot_ammortamenti += amm
                perc_nostra = 100 - g.get('perc_stipendio_pagato', 100)
                
                if g.get('prestato_a_gennaio'):
                    # La squadra madre l'ha avuto per 6 mesi interi, l'acquirente lo paga solo per l'altra metà
                    quota_stip = (stip / 2) + ((stip / 2) * (perc_nostra / 100))
                else:
                    quota_stip = stip * (perc_nostra / 100)
                    
                tot_ingaggi += quota_stip
                
            elif g.get("in_prestito_da"):
                # 2. PRESO IN PRESTITO (Paga 0 ammortamento, paga solo la percentuale pattuita dello stipendio)
                perc_loro_richiesta = g.get('perc_stipendio_pagato', 100)
                
                if g.get('prestato_a_gennaio'):
                    # L'ha preso a gennaio, paga la % solo su mezza stagione!
                    quota_stip = (stip / 2) * (perc_loro_richiesta / 100)
                else:
                    quota_stip = stip * (perc_loro_richiesta / 100)
                    
                tot_ingaggi += quota_stip
                costo_reale_anno += quota_stip
                anni_prestito = g.get('anni_prestito_rimanenti', 1)
                
                giocatori_con_costo.append({
                    "nome": f"{g['nome']} 🤝",
                    "ruolo": g['ruolo'], 
                    "anni_raw": anni_prestito, 
                    "anni_str": str(anni_prestito),
                    "acquisto": "Prestito", 
                    "amm": "0.00 M", 
                    "stip": f"{quota_stip:.2f} M", 
                    "val_res": "0.00 M", 
                    "costo_totale": f"{quota_stip:.2f} M"
                })
                
            else:
                # 3. GIOCATORE NORMALE DI PROPRIETÀ IN ROSA
                tot_ingaggi += stip
                tot_ammortamenti += amm
                costo_reale_anno = stip + amm
                
                giocatori_con_costo.append({
                    "nome": g['nome'], 
                    "ruolo": g['ruolo'], 
                    "anni_raw": anni_res,
                    "anni_str": str(anni_res),
                    "acquisto": f"{g['costo_acquisto']:.2f} M", 
                    "amm": f"{amm:.2f} M", 
                    "stip": f"{stip:.2f} M", 
                    "val_res": f"{g['valore_residuo']:.2f} M", 
                    "costo_totale": f"{costo_reale_anno:.2f} M"
                })

                # SIMULAZIONE RINNOVO
                if anni_res <= 2:
                    costo_attuale_regime = g['ammortamento_annuo'] + g['stipendio']
                    nuovo_stipendio = g['stipendio'] * 1.15
                    nuovo_ammortamento = g['valore_residuo'] / 3
                    nuovo_costo_regime = nuovo_stipendio + nuovo_ammortamento
                    risparmio = costo_attuale_regime - nuovo_costo_regime
                    
                    if risparmio > 0:
                        opportunita_rinnovo.append({
                            "nome": g['nome'], "anni_res": anni_res, "risparmio": risparmio
                        })
            # -----------------------------------------------
            # FINE BLOCCO
            # -----------------------------------------------

        b['costi']['ammortamenti'] = tot_ammortamenti
        b['costi']['monte_ingaggi'] = tot_ingaggi
        tot_ricavi = sum(b['ricavi'].values())
        tot_costi = sum(b['costi'].values())
        utile = tot_ricavi - tot_costi

        # ==========================================
        # RIGA 1: METRICHE CHIAVE
        # ==========================================
        # (Nel Menu 2, subito prima di m1, m2, m3, m4 = st.columns(4))
        
        # CHICCA: Calcolo Zavorra Futura (Ammortamenti bloccati per l'anno prossimo)
        zavorra_futura = sum([g['ammortamento_annuo'] for g in squadra['rosa'] if (g['anni_contratto'] - g.get('anni_trascorsi', 0)) > 1])

        # ==========================================
        # RIGA 1: METRICHE CHIAVE
        # ==========================================
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💰 Cassa", f"{squadra['cassa']:.2f} M")
        m2.metric("🟢 Ricavi", f"{tot_ricavi:.2f} M")
        m3.metric("🔴 Costi", f"{tot_costi:.2f} M")
        m4.metric("⚖️ Utile", f"{utile:.2f} M", delta="Bilancio Sano" if utile >= 0 else "Rischio Multa", delta_color="normal" if utile >= 0 else "inverse")
        st.write("") 

        # ==========================================
        # RIGA 2: ROSTER (sx) + WIDGETS MANAGERIALI (dx)
        # ==========================================
        col_sx, col_dx = st.columns([2.2, 1])

        with col_sx:
            # --- CONTEGGIO RUOLI DINAMICO ---
            conteggio = {"Portiere": 0, "Difensore": 0, "Centrocampista": 0, "Attaccante": 0}
            for g in squadra['rosa']:
                if not g.get("prestato_a"):
                    conteggio[g['ruolo']] += 1
            
            ruoli_str = f"POR: {conteggio['Portiere']}/3 &nbsp;|&nbsp; DIF: {conteggio['Difensore']}/8 &nbsp;|&nbsp; CEN: {conteggio['Centrocampista']}/8 &nbsp;|&nbsp; ATT: {conteggio['Attaccante']}/6"
            
            st.markdown(f"##### 📝 Rosa Attiva <span style='font-size: 13px; font-weight: 500; color: #64748B; float: right; margin-top: 5px;'>{ruoli_str}</span>", unsafe_allow_html=True)
            
            if giocatori_con_costo:
                # --- ORDINAMENTO PER RUOLO PRIMA DELLA STAMPA ---
                ordine_ruoli = {"Portiere": 1, "Difensore": 2, "Centrocampista": 3, "Attaccante": 4}
                giocatori_con_costo = sorted(giocatori_con_costo, key=lambda x: ordine_ruoli.get(x['ruolo'], 5))
                html_table = "<table class='roster-table'>"
                html_table += "<tr><th>Nome</th><th>Ruolo</th><th>Anni Residui</th><th>Costo Acquisto</th><th>Ammortamento</th><th>Stipendio</th><th>Costo Bilancio</th><th>Valore Residuo</th></tr>"
                
                # Definizione dei colori per i badge
                badge_color = {
                    "Portiere": "background-color: #F59E0B; color: white;",     # Giallo/Arancio
                    "Difensore": "background-color: #3B82F6; color: white;",    # Blu
                    "Centrocampista": "background-color: #10B981; color: white;", # Verde
                    "Attaccante": "background-color: #EF4444; color: white;"    # Rosso
                }
                
                for g in giocatori_con_costo:
                    # Creiamo il badge HTML per il ruolo
                    stile_ruolo = badge_color.get(g['ruolo'], "background-color: #64748B; color: white;")
                    badge_html = f"<span style='{stile_ruolo} padding: 4px 8px; border-radius: 6px; font-weight: bold; font-size: 12px;'>{g['ruolo'][:3].upper()}</span>"
                    
                    # Alert 1 anno (ora usa anni_raw per calcolare, ma stampa anni_str)
                    if g['anni_raw'] == 1:
                        anni_format = f"<span style='color: #EF4444; font-weight: bold;'>{g['anni_str']} ⚠️</span>"
                    else:
                        anni_format = f"{g['anni_str']}"

                    # QUI LA MAGIA: Togliamo tutti i :.2f perché i numeri sono già stati formattati nel blocco sopra
                    html_table += f"<tr><td><strong>{g['nome']}</strong></td><td>{badge_html}</td><td>{anni_format}</td><td>{g['acquisto']}</td><td>{g['amm']}</td><td>{g['stip']}</td><td style='color: #EF4444; font-weight: 600;'>{g['costo_totale']}</td><td><strong>{g['val_res']}</strong></td></tr>"

                html_table += "</table>"
                st.markdown(html_table, unsafe_allow_html=True)
            else:
                st.info("Nessun giocatore attualmente in rosa.")

            # --- TABELLA GIOCATORI IN PRESTITO ALTROVE ---
            giocatori_fuori = [g for g in squadra['rosa'] if g.get("prestato_a")]
            if giocatori_fuori:
                st.write("") # Aggiunge uno spazio pulito invece del <br> problematico
                st.markdown("##### ✈️ Giocatori in Prestito Altrove")
                
                # Tabella leggermente trasparente per far capire che non sono attivi
                html_fuori = "<table class='roster-table' style='opacity: 0.85;'>"
                html_fuori += "<tr><th>Nome</th><th>Ruolo</th><th>Prestato a</th><th>Anni Residui</th><th>Ammortamento</th><th>Stipendio</th><th>% Stipendio</th><th>Valore Residuo</th></tr>"
                
                for g in giocatori_fuori:
                    perc_pagata_da_loro = g.get('perc_stipendio_pagato', 100)
                    anni_res_fuori = g['anni_contratto'] - g.get('anni_trascorsi', 0)
                    
                    html_fuori += f"<tr><td><strong>{g['nome']}</strong></td><td>{g['ruolo'][:3].upper()}</td><td>{g['prestato_a']}</td><td>{anni_res_fuori}</td><td><span style='color: #EF4444;'>{g['ammortamento_annuo']:.2f} M</span></td><td>{g['stipendio']:.2f} M</td><td><span style='color: #10B981; font-weight: 600;'>{perc_pagata_da_loro}%</span></td><td><strong>{g['valore_residuo']:.2f} M</strong></td></tr>"
                    
                html_fuori += "</table>"
                st.markdown(html_fuori, unsafe_allow_html=True)

        with col_dx:
            # WIDGET 1: Dettaglio Voci
            st.markdown("##### 🔍 Dettaglio Voci")
            
            # --- NUOVO CALCOLO ZAVORRA FUTURA (Ammortamenti + Stipendi) ---
            amm_futuri = 0.0
            stip_futuri = 0.0
            
            for g in squadra['rosa']:
                anni_res = g['anni_contratto'] - g.get('anni_trascorsi', 0)
                
                # Contiamo solo i giocatori di nostra proprietà con più di 1 anno di contratto residuo
                if anni_res > 1 and not g.get('in_prestito_da'):
                    amm_futuri += g['ammortamento_annuo']
                    
                    # Se il giocatore è in prestito altrove ANCHE per l'anno prossimo, togliamo la percentuale pagata dagli altri
                    if g.get('prestato_a') and g.get('anni_prestito_rimanenti', 0) > 1:
                        stip_futuri += g['stipendio'] * ((100 - g.get('perc_stipendio_pagato', 0)) / 100)
                    else:
                        stip_futuri += g['stipendio']

            tot_zavorra = amm_futuri + stip_futuri

            html_voci = """
            <div style='background-color: white; border-radius: 12px; padding: 20px; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px rgba(0,0,0,0.03); font-size: 14px; margin-bottom: 20px;'>
                <strong style='color: #10B981;'>🟢 Valore Produzione</strong><br>
            """
            for k, v in b['ricavi'].items():
                html_voci += f"<span style='color: #64748B;'>{k.replace('_', ' ').title()}:</span> <span style='float: right; font-weight: bold;'>{v:.2f} M</span><br>"
            
            html_voci += "<br><strong style='color: #EF4444;'>🔴 Costi Produzione</strong><br>"
            for k, v in b['costi'].items():
                html_voci += f"<span style='color: #64748B;'>{k.replace('_', ' ').title()}:</span> <span style='float: right; font-weight: bold;'>{v:.2f} M</span><br>"
            
            # --- LA NUOVA SEZIONE ZAVORRA CON GLI STIPENDI ---
            html_voci += "<br><strong style='color: #F59E0B;'>⚓ Proiezione Prossima Stagione</strong><br>"
            html_voci += f"<span style='color: #64748B;'>Ammortamenti garantiti:</span> <span style='float: right; font-weight: bold;'>{amm_futuri:.2f} M</span><br>"
            html_voci += f"<span style='color: #64748B;'>Stipendi garantiti:</span> <span style='float: right; font-weight: bold;'>{stip_futuri:.2f} M</span><br>"
            
            html_voci += "</div>"
            st.markdown(html_voci, unsafe_allow_html=True)
                
            # WIDGET 3: Opportunità di Spalmatura
            st.markdown("##### ⏳ Opportunità di Rinnovo")
            if opportunita_rinnovo:
                opportunita_ordinate = sorted(opportunita_rinnovo, key=lambda x: x['risparmio'], reverse=True)[:3]
                
                html_opp = "<div style='background-color: white; border-radius: 12px; padding: 20px; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px rgba(0,0,0,0.03); font-size: 14px;'>"
                html_opp += "<div style='color: #64748B; margin-bottom: 10px; font-size: 12px;'>Spalmando il contratto a 3 anni risparmi:</div>"
                
                for g in opportunita_ordinate:
                    anni_testo = "anno" if g['anni_res'] == 1 else "anni"
                    html_opp += f"<div style='margin-bottom: 8px; border-bottom: 1px dashed #E2E8F0; padding-bottom: 5px;'>"
                    html_opp += f"<strong>{g['nome']}</strong> <span style='font-size: 11px; color: #94A3B8;'>(Scade tra {g['anni_res']} {anni_testo})</span><br>"
                    html_opp += f"<span style='color: #10B981; font-weight: bold;'>✨ +{g['risparmio']:.2f} M</span> a bilancio"
                    html_opp += "</div>"
                
                html_opp += "</div>"
                st.markdown(html_opp, unsafe_allow_html=True)
            else:
                st.info("Nessuna opzione vantaggiosa.")

# ==========================================
# 3. MERCATO (DEFINITIVI E RINNOVI)
# ==========================================
elif menu == "3. Mercato (Definitivi)":
    st.header("🛒 Acquisti, Cessioni, Svincoli e Rinnovi")

    if not st.session_state.is_admin:
        st.error("🔒 Accesso riservato. Solo l'Amministratore della Lega può effettuare operazioni di mercato.")
    else:
        if not db: st.warning("Crea una squadra.")
        else:
            sq_sel = st.selectbox("Seleziona Squadra", list(db.keys()))
            squadra = db[sq_sel]
            
            # --- 1. CREIAMO IL SEGNAPOSTO ---
            info_header = st.empty()
            # Lo riempiamo subito con i dati attuali
            info_header.write(f"💰 **Cassa:** {squadra['cassa']:.2f} MLN | 👥 **Rosa:** {len(squadra['rosa'])}/25")
            
            # --- ORDINAMENTO ROSA PER RUOLO ---
            ordine_ruoli = {"Portiere": 1, "Difensore": 2, "Centrocampista": 3, "Attaccante": 4}
            # Creiamo una lista della rosa ordinata in base al valore del dizionario sopra
            rosa_ordinata = sorted(squadra['rosa'], key=lambda x: ordine_ruoli.get(x['ruolo'], 5))
            
            t1, t2, t3, t4 = st.tabs(["Acquista", "Vendi", "Svincola", "Rinnovo"])
            
            with t1:
                # Sostituiamo st.form con st.container per avere l'aggiornamento in tempo reale!
                with st.container(border=True):
                    sessione_acq = st.radio("Sessione di Mercato", ["☀️ Estiva", "❄️ Invernale"], horizontal=True, key="sess_acq")
                    st.divider()
                    
                    col1, col2, col3 = st.columns(3)
                    n = col1.text_input("Calciatore")
                    r = col2.selectbox("Ruolo", ["Portiere", "Difensore", "Centrocampista", "Attaccante"])
                    c = col3.number_input("Prezzo Acquisto (MLN)", min_value=1.0, step=1.0)
                    anni = st.slider("Anni Contratto", 1, 5, 3)
                    
                    # Calcolo Stipendi (Aggiornato all'Opzione 2)
                    s_base = 1.0 if c <= 15 else (2.5 if c <= 45 else (4.5 if c <= 85 else (7.0 if c <= 130 else 11.0)))
                    
                    is_gennaio = True if "Invernale" in sessione_acq else False
                    anni_effettivi = anni - 0.5 if is_gennaio else anni
                    amm = c / anni_effettivi if anni_effettivi > 0 else c
                    
                    if is_gennaio:
                        st.info(f"💡 Durata Effettiva: {anni_effettivi} anni. | Stipendio Annuo Base: {s_base}M | Ammortamento Annuo Base: {amm:.2f}M.\n(Per i 6 mesi correnti pagherai la METÀ: {amm/2:.2f}M di ammortamento e {s_base/2:.2f}M di stipendio).")
                    else:
                        st.info(f"💡 Dati Contratto: Stipendio {s_base}M | Ammortamento {amm:.2f}M annui.")
                    
                    # Sostituiamo il form_submit_button con un normale button
                    if st.button("Conferma Acquisto", type="primary"):
                        if c > squadra['cassa']: 
                            st.error("Cassa insufficiente!")
                        elif not n:
                            st.warning("Inserisci il nome del calciatore prima di acquistare.")
                        else:
                            giocatore = {"nome": n, "ruolo": r, "costo_acquisto": c, "anni_contratto": anni_effettivi, "stipendio": s_base, "ammortamento_annuo": amm, "anni_trascorsi": 0, "valore_residuo": c, "acquistato_a_gennaio": is_gennaio}
                            squadra['rosa'].append(giocatore)
                            squadra['cassa'] = round(squadra['cassa'] - c, 2)
                            squadra['bilancio']['storico_movimenti'].append(f"Acquisto {n}: -{c}M")
                            save_data(db, DB_PATH)
                            log_evento(sq_sel, "✍️", f"ha acquistato **{n}** per **{c} M** ({anni_effettivi} anni di contratto).")
                            st.toast(f"Contratto firmato! {n} è un tuo giocatore.", icon="✍️")
                            
                            # AGGIORNIAMO IL SEGNAPOSTO
                            info_header.write(f"💰 **Cassa:** {squadra['cassa']:.2f} MLN | 👥 **Rosa:** {len(squadra['rosa'])}/25")
                            
            with t2:
                if rosa_ordinata:
                    with st.container(border=True):
                        sessione_ven = st.radio("Sessione di Mercato", ["☀️ Estiva", "❄️ Invernale"], horizontal=True, key="sess_ven")
                        st.divider()
                        
                        indice_a = st.selectbox(
                            "Seleziona da Vendere", 
                            options=range(len(rosa_ordinata)), 
                            format_func=lambda i: f"{rosa_ordinata[i]['nome']} ({rosa_ordinata[i]['ruolo'][:3].upper()})", 
                            key="vendita_idx"
                        )

                        g_obj = rosa_ordinata[indice_a]
                        
                        # CONTROLLO DI SICUREZZA: Esegue solo se g_obj non è vuoto
                        if g_obj:
                            if g_obj.get("prestato_a"):
                                st.error(f"❌ Impossibile vendere. {g_obj['nome']} è attualmente in prestito a {g_obj['prestato_a']}.")
                            elif g_obj.get("in_prestito_da"):
                                st.error(f"❌ Operazione Illegale. Non puoi vendere {g_obj['nome']} perché è di proprietà di: {g_obj['in_prestito_da']}.")
                            else:
                                if "Invernale" in sessione_ven:
                                    # Evita la doppia svalutazione se il giocatore è stato comprato o rinnovato IN QUESTA STESSA SESSIONE di Gennaio
                                    if (g_obj.get('rinnovato_a_gennaio') or g_obj.get('acquistato_a_gennaio')) and g_obj.get('anni_trascorsi', 0) == 0:
                                        val_res_effettivo = g_obj['valore_residuo']
                                    else:
                                        val_res_effettivo = g_obj['valore_residuo'] - (g_obj['ammortamento_annuo'] / 2)
                                else:
                                    val_res_effettivo = g_obj['valore_residuo']
                                st.write(f"📊 Valore Residuo Attuale: **{val_res_effettivo:.2f} M**")
                                
                                prezzo_v = st.number_input("Prezzo di Vendita (MLN)", min_value=0.0, step=1.0)
                                
                                # Bottone largo!
                                if st.button("Conferma Cessione", type="primary", key="btn_conferma_cessione"):
                                    if "Invernale" in sessione_ven:
                                        squadra['bilancio']['costi']['costi_giocatori_ceduti'] += (g_obj['ammortamento_annuo'] / 2) + (g_obj['stipendio'] / 2)
                                    
                                    diff = prezzo_v - val_res_effettivo
                                    squadra['cassa'] = round(squadra['cassa'] + prezzo_v, 2)
                                    if diff > 0: squadra['bilancio']['ricavi']['plusvalenze'] += diff
                                    else: squadra['bilancio']['costi']['minusvalenze'] += abs(diff)
                                    
                                    squadra['rosa'].remove(g_obj)
                                    save_data(db, DB_PATH)
                                    log_evento(sq_sel, "✈️", f"ha ceduto **{g_obj['nome']}** a titolo definitivo per **{prezzo_v} M**.")
                                    st.toast(f"{g_obj['nome']} ceduto definitivamente per {prezzo_v} M!", icon="✈️")
                                    st.rerun()
                else:
                    st.info("Nessun giocatore in rosa da vendere.")
                            
            with t3:
                if rosa_ordinata:
                    with st.container(border=True):
                        sessione_svin = st.radio("Sessione di Mercato", ["☀️ Estiva", "❄️ Invernale"], horizontal=True, key="sess_svin")
                        st.divider()
                        
                        indice_s = st.selectbox(
                            "Seleziona da Svincolare", 
                            options=range(len(rosa_ordinata)), 
                            format_func=lambda i: f"{rosa_ordinata[i]['nome']} ({rosa_ordinata[i]['ruolo'][:3].upper()})", 
                            key="svincolo_idx"
                        )

                        g_obj_s = rosa_ordinata[indice_s]
                        
                        # CONTROLLO DI SICUREZZA
                        if g_obj_s:
                            if g_obj_s.get("prestato_a"):
                                st.error(f"❌ Impossibile svincolare. {g_obj_s['nome']} è attualmente in prestito a {g_obj_s['prestato_a']}.")
                            elif g_obj_s.get("in_prestito_da"):
                                st.error(f"❌ Non puoi svincolare un giocatore in prestito. Proprietà: {g_obj_s['in_prestito_da']}.")
                            else:
                                if "Invernale" in sessione_svin:
                                    # Evita la doppia svalutazione se il giocatore è stato comprato o rinnovato IN QUESTA STESSA SESSIONE di Gennaio
                                    if (g_obj_s.get('rinnovato_a_gennaio') or g_obj_s.get('acquistato_a_gennaio')) and g_obj_s.get('anni_trascorsi', 0) == 0:
                                        val_res_effettivo_s = g_obj_s['valore_residuo']
                                    else:
                                        val_res_effettivo_s = g_obj_s['valore_residuo'] - (g_obj_s['ammortamento_annuo'] / 2)
                                else:
                                    val_res_effettivo_s = g_obj_s['valore_residuo']
                                st.error(f"⚠️ Svincolare azzera il valore residuo generando una minusvalenza di {val_res_effettivo_s:.2f}M.")
                                
                                # Bottone largo!
                                if st.button("Conferma Svincolo", type="primary", key="btn_conferma_svincolo"):
                                    if "Invernale" in sessione_svin:
                                        squadra['bilancio']['costi']['costi_giocatori_ceduti'] += (g_obj_s['ammortamento_annuo'] / 2) + (g_obj_s['stipendio'] / 2)
                                    
                                    squadra['bilancio']['costi']['minusvalenze'] += val_res_effettivo_s
                                    squadra['rosa'].remove(g_obj_s)
                                    save_data(db, DB_PATH)
                                    log_evento(sq_sel, "📄", f"ha rescisso il contratto di **{g_obj_s['nome']}**.")
                                    st.toast(f"{g_obj_s['nome']} è stato svincolato.", icon="📄")
                                    st.rerun()
                else:
                    st.info("Nessun giocatore in rosa da svincolare.")
                            
            with t4:
                if rosa_ordinata:
                    with st.container(border=True):
                        sessione_rin = st.radio("Sessione di Mercato", ["☀️ Estiva", "❄️ Invernale"], horizontal=True, key="sess_rin")
                        is_gen_rin = "Invernale" in sessione_rin
                        st.divider()
                        
                        # MODIFICA CHIAVE: Usiamo gli indici (numeri interi) invece dei dizionari 
                        # per evitare che Streamlit perda la memoria al click del bottone!
                        indice_r = st.selectbox(
                            "Seleziona da Rinnovare", 
                            options=range(len(rosa_ordinata)), 
                            format_func=lambda i: f"{rosa_ordinata[i]['nome']} ({rosa_ordinata[i]['ruolo'][:3].upper()})", 
                            key="rinnovo_idx"
                        )
                        
                        # Recuperiamo il dizionario del giocatore usando l'indice sicuro
                        g_obj_r = rosa_ordinata[indice_r]
                        
                        # CONTROLLO DI SICUREZZA
                        if g_obj_r:
                            if g_obj_r.get("prestato_a"):
                                st.error(f"❌ Impossibile rinnovare. {g_obj_r['nome']} è in prestito.")
                            elif g_obj_r.get("in_prestito_da"):
                                st.error(f"❌ Impossibile rinnovare. {g_obj_r['nome']} non è un tuo giocatore (Proprietà: {g_obj_r['in_prestito_da']}).")
                            else:
                                # CONTROLLO DI SICUREZZA
                                blocco_rinnovo = False
                                msg_blocco = ""
                                
                                # 1. Controllo acquisto recente (Esistente)
                                if g_obj_r.get('anni_trascorsi', 0) == 0:
                                    if not g_obj_r.get('acquistato_a_gennaio') and not is_gen_rin:
                                        blocco_rinnovo = True
                                        msg_blocco = "Hai appena firmato questo giocatore in questa Sessione Estiva. Le regole non permettono un rinnovo istantaneo."
                                    elif g_obj_r.get('acquistato_a_gennaio') and is_gen_rin:
                                        blocco_rinnovo = True
                                        msg_blocco = "Hai appena firmato questo giocatore in questa Sessione Invernale. Le regole non permettono un rinnovo istantaneo."
                                
                                # 2. NUOVO CONTROLLO: Anni rimanenti (Max 1 o 2 per rinnovare)
                                if not blocco_rinnovo: # Lo esegue solo se non è già bloccato dal controllo sopra
                                    anni_rimanenti = g_obj_r.get('anni_contratto', 1) - g_obj_r.get('anni_trascorsi', 0)
                                    if anni_rimanenti >= 3:
                                        blocco_rinnovo = True
                                        msg_blocco = f"Il giocatore ha ancora {anni_rimanenti} anni di contratto. Puoi rinnovarlo solo quando gli restano 1 o 2 anni."
                                
                                if blocco_rinnovo:
                                    st.warning(f"✋ **Operazione Bloccata.** {msg_blocco}")
                                else:
                                    st.write(f"📊 **Stipendio Attuale:** {g_obj_r['stipendio']:.3f} M | **Valore Residuo Attuale:** {g_obj_r['valore_residuo']:.2f} M")
                                    
                                    nuovi_anni = st.slider("Nuovi Anni di Contratto (Max 5)", 1, 5, 1, key="anni_rinnovo")
                                    
                                    # LA RIGA MAGICA: Sottrae 0.5 se siamo a gennaio!
                                    anni_effettivi = nuovi_anni - 0.5 if is_gen_rin else nuovi_anni
                                    
                                    nuovo_stipendio = g_obj_r['stipendio'] * 1.15
                                    
                                    if is_gen_rin:
                                        st.info(f"❄️ **Rinnovo Invernale:** Impatto pro-quota. Durata effettiva {anni_effettivi} anni.")
                                        vr_a_gennaio = g_obj_r['valore_residuo'] - (g_obj_r['ammortamento_annuo'] / 2)
                                        # Usiamo anni_effettivi per calcolare l'ammortamento corretto!
                                        nuovo_amm = vr_a_gennaio / anni_effettivi if anni_effettivi > 0 else 0
                                    else:
                                        st.info("☀️ **Rinnovo Estivo:** Nuovo contratto applicato all'intera stagione.")
                                        nuovo_amm = g_obj_r['valore_residuo'] / anni_effettivi if anni_effettivi > 0 else 0
                                        
                                    st.write(f"🔄 **Nuova Proiezione:** Stipendio **{nuovo_stipendio:.3f} M** | Ammortamento Annuo **{nuovo_amm:.2f} M**")
                                    
                                    # Bottone largo!
                                    if st.button("Conferma Rinnovo", type="primary", key="btn_conferma_rinnovo"):
                                        if is_gen_rin:
                                            g_obj_r['rinnovato_a_gennaio'] = True
                                            g_obj_r['vecchio_amm_gennaio'] = g_obj_r['ammortamento_annuo']
                                            g_obj_r['vecchio_stip_gennaio'] = g_obj_r['stipendio']
                                            g_obj_r['valore_residuo'] = vr_a_gennaio
                                            
                                        g_obj_r['stipendio'] = nuovo_stipendio
                                        g_obj_r['costo_acquisto'] = g_obj_r['valore_residuo']
                                        # Salviamo gli anni_effettivi e NON quelli dello slider nudo e crudo!
                                        g_obj_r['anni_contratto'] = anni_effettivi 
                                        g_obj_r['ammortamento_annuo'] = nuovo_amm
                                        g_obj_r['anni_trascorsi'] = 0
                                        
                                        save_data(db, DB_PATH)
                                        log_evento(sq_sel, "🤝", f"ha prolungato il contratto di **{g_obj_r['nome']}** per altri {anni_effettivi} anno/i.")
                                        st.toast(f"Contratto di {g_obj_r['nome']} rinnovato!", icon="🤝")
                                        st.rerun()
                else:
                    st.info("Nessun giocatore in rosa da rinnovare.")

# ==========================================
# 4. MERCATO (PRESTITI)
# ==========================================
elif menu == "4. Mercato (Prestiti)":
    st.header("🤝 Gestione Prestiti e Riscatti")

    if not st.session_state.is_admin:
        st.error("🔒 Accesso riservato. Solo l'Amministratore della Lega può effettuare operazioni di mercato.")
    else:
        if len(db) < 2: st.warning("Servono almeno 2 squadre per i prestiti.")
        else:
            c1, c2 = st.columns(2)
            sq_cedente = c1.selectbox("Società Cedente", list(db.keys()))
            sq_acquirente = c2.selectbox("Società Acquirente", [s for s in db.keys() if s != sq_cedente])
            
            rosa_cedente = [g for g in db[sq_cedente]['rosa'] if not g.get("prestato_a")]

            # --- ORDINAMENTO ROSA PER RUOLO ---
            ordine_ruoli = {"Portiere": 1, "Difensore": 2, "Centrocampista": 3, "Attaccante": 4}
            rosa_ordinata = sorted(rosa_cedente, key=lambda x: ordine_ruoli.get(x['ruolo'], 5))
            
            if not rosa_ordinata: st.info("Nessun giocatore disponibile.")
            else:
                # MODIFICA 1: Usiamo i numeri interi come opzioni per non perdere la memoria al click!
                indice_p = st.selectbox(
                    "Seleziona Giocatore da Prestare", 
                    options=range(len(rosa_ordinata)), 
                    format_func=lambda i: f"{rosa_ordinata[i]['nome']} ({rosa_ordinata[i]['ruolo'][:3].upper()})", 
                    key="prestito_out_idx"
                )
                
                # Recuperiamo il giocatore dalla lista temporanea ordinata
                g_selezionato = rosa_ordinata[indice_p]
                
                # MODIFICA 2: Troviamo il giocatore REALE dentro il database per modificarlo direttamente alla fonte
                g_obj = next(g for g in db[sq_cedente]['rosa'] if g['nome'] == g_selezionato['nome'])
                
                st.markdown("### 📝 Dettagli Contratto di Prestito")
                
                # ---> AGGIUNTA SESSIONE
                sessione_prestito = st.radio("Sessione di Mercato (Prestito)", ["☀️ Estiva", "❄️ Invernale"], horizontal=True, key="sess_prestito")
                is_gen_prestito = "Invernale" in sessione_prestito
                st.divider()
                
                col_dur, col_stip = st.columns(2)
                durata_prestito = col_dur.slider("Durata Prestito (Anni)", 1, 2, 1)
                perc_stipendio = col_stip.slider("% Stipendio a carico dell'Acquirente", 0, 100, 50, step=10)
                
                # Calcolo durata effettiva (-0.5 a gennaio)
                anni_effettivi_prestito = durata_prestito - 0.5 if is_gen_prestito else durata_prestito
                
                if is_gen_prestito:
                    st.info(f"❄️ **Prestito Invernale:** Durata effettiva {anni_effettivi_prestito} anni. Il {perc_stipendio}% di stipendio a carico dell'acquirente verrà calcolato **solo sui 6 mesi correnti**, mentre i primi 6 mesi restano interamente a carico della società cedente")
                else:
                    st.info(f"☀️ **Prestito Estivo:** Durata {anni_effettivi_prestito} anni. La percentuale si applica all'intera stagione.")
                
                col_on, col_tipo, col_cifra = st.columns(3)
                costo_prestito = col_on.number_input("Costo Prestito (Oneroso in MLN)", min_value=0.0, step=0.5, value=0.0)
                tipo_accordo = col_tipo.selectbox("Tipo di Accordo", ["Prestito Secco", "Diritto di Riscatto", "Obbligo di Riscatto"])
                
                cifra_riscatto = 0.0
                if tipo_accordo != "Prestito Secco":
                    cifra_riscatto = col_cifra.number_input("Cifra Riscatto Pattuita (MLN)", min_value=1.0, step=1.0, value=10.0)
                
                if st.button("Ufficializza Prestito"):
                    anni_rimanenti = g_obj['anni_contratto'] - g_obj.get('anni_trascorsi', 0)
                    
                    if anni_effettivi_prestito >= anni_rimanenti:
                        st.error(f"⚠️ Impossibile prestare. Il giocatore ha solo {anni_rimanenti} anno/i di contratto residui. Per questo prestito, servono almeno {anni_effettivi_prestito + 1} anni di contratto (rinnovalo prima di cederlo!).")
                    elif costo_prestito > db[sq_acquirente]['cassa']:
                        st.error("Cassa acquirente insufficiente per il prestito oneroso!")
                    else:
                        g_acq = g_obj.copy()
                        g_acq['in_prestito_da'], g_acq['perc_stipendio_pagato'] = sq_cedente, perc_stipendio
                        g_acq['accordo_riscatto'] = {"tipo": tipo_accordo, "cifra": cifra_riscatto}
                        g_acq['anni_prestito_rimanenti'] = anni_effettivi_prestito
                        g_acq['prestato_a_gennaio'] = is_gen_prestito # <--- NUOVO FLAG
                        db[sq_acquirente]['rosa'].append(g_acq)
                        
                        g_obj['prestato_a'], g_obj['perc_stipendio_pagato'] = sq_acquirente, perc_stipendio
                        g_obj['accordo_riscatto'] = {"tipo": tipo_accordo, "cifra": cifra_riscatto}
                        g_obj['anni_prestito_rimanenti'] = anni_effettivi_prestito
                        g_obj['prestato_a_gennaio'] = is_gen_prestito # <--- NUOVO FLAG
                        
                        if costo_prestito > 0:
                            db[sq_acquirente]['cassa'] = round(db[sq_acquirente]['cassa'] - costo_prestito, 2)
                            db[sq_cedente]['cassa'] = round(db[sq_cedente]['cassa'] + costo_prestito, 2)
                            db[sq_cedente]['bilancio']['ricavi']['plusvalenze'] += costo_prestito
                            db[sq_acquirente]['bilancio']['costi']['minusvalenze'] += costo_prestito
                            
                        save_data(db, DB_PATH)
                        log_evento(sq_cedente, "🧳", f"ha ceduto in prestito **{g_obj['nome']}** alla società **{sq_acquirente}**.")
                        st.toast(f"Prestito registrato!", icon="🧳")
                        st.rerun()
                        
            st.divider()
            st.subheader("🛒 Esercita Riscatto")
            in_prestito = [g for g in db[sq_acquirente]['rosa'] if g.get("in_prestito_da") == sq_cedente]
            if in_prestito:
                g_riscatto = st.selectbox("Calciatore da riscattare", [g['nome'] for g in in_prestito])
                g_r_obj = next(g for g in in_prestito if g['nome'] == g_riscatto)
                
                if "riscatto_prenotato" in g_r_obj:
                    st.warning(f"⏳ Riscatto già prenotato a {g_r_obj['riscatto_prenotato']['cifra']} M. Diventerà effettivo il 1° Luglio con la chiusura del bilancio.")
                else:
                    accordo = g_r_obj.get("accordo_riscatto", {"tipo": "Prestito Secco", "cifra": 0.0})
                    if accordo["tipo"] == "Obbligo di Riscatto":
                        st.error(f"⚠️ Questo giocatore ha un OBBLIGO di riscatto fissato a {accordo['cifra']} M.")
                        prezzo_r = st.number_input("Conferma Costo Riscatto (MLN)", min_value=0.0, value=float(accordo['cifra']))
                    elif accordo["tipo"] == "Diritto di Riscatto":
                        st.info(f"💡 Diritto di riscatto pattuito a {accordo['cifra']} M.")
                        prezzo_r = st.number_input("Costo del Riscatto (MLN)", min_value=0.0, value=float(accordo['cifra']))
                    else:
                        prezzo_r = st.number_input("Costo del Riscatto (MLN)", min_value=1.0)
                        
                    anni_nuovi = st.slider("Nuovi anni di contratto", 1, 5, 3)
                    
                    if st.button("Prenota Riscatto (Effettivo al 1° Luglio)"):
                        g_r_obj['riscatto_prenotato'] = {'cifra': prezzo_r, 'anni': anni_nuovi}
                        g_ced_obj = next(g for g in db[sq_cedente]['rosa'] if g['nome'] == g_riscatto)
                        g_ced_obj['riscatto_prenotato'] = {'cifra': prezzo_r, 'anni': anni_nuovi}
                        save_data(db, DB_PATH)
                        log_evento(sq_cedente, "💰", f"ha ufficializzato la cessione per riscatto di **{g_riscatto}** al **{sq_acquirente}** per **{prezzo_r} M**.")
                        st.toast(f"Riscatto di {g_riscatto} prenotato per fine anno!", icon="⏳")
                        st.rerun()

            st.divider()
            st.subheader("❌ Risoluzione Anticipata Prestito")
            if in_prestito:
                g_risoluzione = st.selectbox("Calciatore da far rientrare alla base", [g['nome'] for g in in_prestito], key="risoluzione")
                st.info("Interrompendo il prestito, il giocatore tornerà immediatamente attivo nella rosa della società proprietaria e l'eventuale accordo di riscatto verrà annullato.")
                
                if st.button("Interrompi Prestito Subito"):
                    # 1. Rimuoviamo il giocatore dalla rosa di chi l'aveva ricevuto
                    g_acq_obj = next(g for g in db[sq_acquirente]['rosa'] if g['nome'] == g_risoluzione)
                    db[sq_acquirente]['rosa'].remove(g_acq_obj)
                    
                    # 2. Ripuliamo tutti i vincoli di prestito dalla scheda originale della squadra madre
                    g_ced_obj = next(g for g in db[sq_cedente]['rosa'] if g['nome'] == g_risoluzione)
                    for key in ['prestato_a', 'perc_stipendio_pagato', 'accordo_riscatto', 'anni_prestito_rimanenti', 'riscatto_prenotato']:
                        g_ced_obj.pop(key, None)
                        
                    save_data(db, DB_PATH)
                    log_evento(sq_cedente, "🔙", f"ha richiamato **{g_risoluzione}** dal prestito. Il giocatore lascia il **{sq_acquirente}**.")
                    st.toast(f"Accordo interrotto. {g_risoluzione} torna alla base.", icon="🔙")
                    st.rerun()
            else:
                st.write("Nessun giocatore in prestito tra queste due squadre.")

# ==========================================
# 5. CALENDARIO E PARTITE
# ==========================================
elif menu == "5. Calendario & Partite":
    st.header("🗓️ Calendario")
    
    # --- CSS MAGICO PER GLI INPUT DEI GOL (V2.0) ---
    st.markdown("""
    <style>
    /* Nasconde i bottoni +/- nativi del browser */
    input[type=number]::-webkit-inner-spin-button, 
    input[type=number]::-webkit-outer-spin-button { 
        -webkit-appearance: none; 
        margin: 0; 
    }
    input[type=number] {
        -moz-appearance: textfield;
    }
    
    /* ANNIHILAZIONE DEI BOTTONI +/- DI STREAMLIT */
    [data-testid="stNumberInputStepDown"], 
    [data-testid="stNumberInputStepUp"] {
        display: none !important;
    }
    
    /* Forza il testo al centro in tutti i box dei gol */
    div[data-testid="stNumberInputContainer"] input {
        text-align: center !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    if not st.session_state.is_admin:
        st.error("🔒 Accesso riservato. Solo l'Amministratore della Lega può generare il calendario o inserire i risultati di una giornata.")
    else:
        if len(db) != 8:
            st.error(f"Per generare il calendario servono 8 squadre. Attualmente ce ne sono {len(db)}.")
        else:
            if not calendario:
                c_giornate, c_btn = st.columns([1, 3])
                num_g = c_giornate.number_input("Numero di Giornate", min_value=1, max_value=76, value=36)
                
                c_btn.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                
                if c_btn.button("🚀 Genera Calendario Ufficiale", type="primary"):
                    calendario = genera_calendario_berger(list(db.keys()), num_g)
                    save_data(calendario, CAL_PATH)
                    st.success(f"Calendario di {num_g} giornate generato con successo!")
                    st.rerun()
            
            if calendario:
                st.info("👇 Scorri per vedere tutte le giornate.")
                
                # ELIMINATO il menu a tendina! Ora facciamo un ciclo per mostrare TUTTE le giornate
                for giornata_idx, giornata_dati in enumerate(calendario):
                    
                    st.subheader(f"Partite Giornata {giornata_idx + 1}")
                    
                    # Controlliamo se la giornata è già stata giocata e salvata
                    # (Ci basta guardare la prima partita, perché le salviamo tutte insieme)
                    giornata_chiusa = False
                    if giornata_dati and giornata_dati[0].get("giocata", False):
                        giornata_chiusa = True
                    
                    if giornata_chiusa:
                        # ==========================================
                        # VISTA "LOCKED" (GIORNATA GIÀ GIOCATA E SALVATA)
                        # ==========================================
                        with st.container(border=True): # Mettiamo tutto in un bel box
                            for idx, match in enumerate(giornata_dati):
                                c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                                
                                c1.markdown(f"<div style='text-align: right; margin-top: 6px; font-weight: bold; font-size: 16px;'>{match['home']}</div>", unsafe_allow_html=True)
                                
                                # STILE CUSTOM PER I GOL SALVATI (Badge Verde brillante)
                                stile_badge = "background-color: #10B981; color: white; border-radius: 6px; padding: 6px 0; text-align: center; font-weight: bold; font-size: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);"
                                c2.markdown(f"<div style='{stile_badge}'>{match['gol_home']}</div>", unsafe_allow_html=True)
                                
                                c3.markdown("<div style='text-align: center; margin-top: 6px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                                
                                c4.markdown(f"<div style='{stile_badge}'>{match['gol_away']}</div>", unsafe_allow_html=True)
                                
                                c5.markdown(f"<div style='text-align: left; margin-top: 6px; font-weight: bold; font-size: 16px;'>{match['away']}</div>", unsafe_allow_html=True)
                                
                                st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True) # spaziatura tra le partite
                                
                            # IL MESSAGGIO CHE SOSTITUISCE IL BOTTONE
                            st.info(f"🔒 **Giornata {giornata_idx + 1} archiviata.** I risultati sono ufficiali e gli incassi stadio sono stati registrati a bilancio.")
                    
                    else:
                        # ==========================================
                        # VISTA "EDIT" (GIORNATA DA GIOCARE)
                        # ==========================================
                        with st.form(f"giornata_{giornata_idx}"):
                            for idx, match in enumerate(giornata_dati):
                                c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                                
                                c1.markdown(f"<div style='text-align: right; margin-top: 8px; font-weight: bold; font-size: 16px;'>{match['home']}</div>", unsafe_allow_html=True)
                                gol_h = c2.number_input("H", min_value=0, value=match["gol_home"], key=f"g{giornata_idx}_h_{idx}", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                                c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                                gol_a = c4.number_input("A", min_value=0, value=match["gol_away"], key=f"g{giornata_idx}_a_{idx}", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                                c5.markdown(f"<div style='text-align: left; margin-top: 8px; font-weight: bold; font-size: 16px;'>{match['away']}</div>", unsafe_allow_html=True)

                            if st.session_state.is_admin:
                                if st.form_submit_button(f"Salva Risultati & Assegna Incassi (G. {giornata_idx + 1})", type="primary"):
                                    gol_map = {}
                                    for idx, match in enumerate(giornata_dati):
                                        gh = st.session_state[f"g{giornata_idx}_h_{idx}"]
                                        ga = st.session_state[f"g{giornata_idx}_a_{idx}"]
                                        
                                        match["gol_home"] = gh
                                        match["gol_away"] = ga
                                        match["giocata"] = True

                                        gol_map[match["home"]] = gh
                                        gol_map[match["away"]] = ga
                                        
                                        if not match["incassi_assegnati"]:
                                            h_team = db[match["home"]]
                                            if h_team['stadio']['livello']:
                                                incasso = h_team['stadio']['vittoria'] if gh > ga else (h_team['stadio']['pari'] if gh == ga else h_team['stadio']['base'])
                                                h_team['bilancio']['ricavi']['incassi_stadio'] += incasso
                                                h_team['cassa'] += incasso 
                                                h_team['bilancio']['storico_movimenti'].append(f"Stadio G{giornata_idx + 1}: +{incasso}M")
                                            match["incassi_assegnati"] = True
                                    
                                    save_data(db, DB_PATH)
                                    save_data(calendario, CAL_PATH)
                                    
                                    log_evento("Lega", "📅", f"Risultati e incassi della **Giornata {giornata_idx + 1}** ufficializzati.")
                                    st.rerun() 
                    
                    # Divisore tra le giornate
                    st.divider()

# ==========================================
# 6. CLASSIFICA E PREMI CAMPIONATO
# ==========================================
elif menu == "6. Classifica Campionato":
    st.header("🏆 Classifica Campionato")
    if not calendario: st.warning("Nessun calendario trovato.")
    else:
        standings = {s: {"Punti": 0, "G": 0, "V": 0, "N": 0, "P": 0, "GF": 0, "GS": 0, "DR": 0} for s in db.keys()}
        for md in calendario:
            for m in md:
                if m["giocata"]:
                    h, a, gh, ga = m["home"], m["away"], m["gol_home"], m["gol_away"]
                    standings[h]["G"] += 1; standings[a]["G"] += 1
                    standings[h]["GF"] += gh; standings[h]["GS"] += ga
                    standings[a]["GF"] += ga; standings[a]["GS"] += gh
                    standings[h]["DR"] += (gh - ga); standings[a]["DR"] += (ga - gh)
                    if gh > ga: standings[h]["Punti"] += 3; standings[h]["V"] += 1; standings[a]["P"] += 1
                    elif gh == ga: standings[h]["Punti"] += 1; standings[a]["Punti"] += 1; standings[h]["N"] += 1; standings[a]["N"] += 1
                    else: standings[a]["Punti"] += 3; standings[a]["V"] += 1; standings[h]["P"] += 1
                        
        df_c = pd.DataFrame.from_dict(standings, orient='index').sort_values(by=["Punti", "DR", "GF"], ascending=[False, False, False])
        
        # --- TABELLA CLASSIFICA CUSTOM ---
        html_classifica = """
        <style>
        .tabella-classifica {
            border-collapse: collapse;
            background-color: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            font-family: sans-serif;
            margin-bottom: 20px;
            border: 1px solid #E2E8F0;
        }
        .tabella-classifica th {
            background-color: #F8FAFC;
            color: #64748B;
            padding: 12px 15px;
            font-size: 13px;
            text-align: center; /* Centriamo le colonne statistiche */
            border-bottom: 2px solid #E2E8F0;
        }
        .tabella-classifica td {
            padding: 12px 15px;
            font-size: 14px;
            color: #334155;
            text-align: center; /* Centriamo i valori */
            border-bottom: 1px solid #F1F5F9;
        }
        /* La prima colonna (Squadra) allineata a sinistra e più larga */
        .tabella-classifica th:first-child, .tabella-classifica td:first-child {
            text-align: left;
            width: 250px;
        }
        /* Colonne statistiche strette */
        .tabella-classifica th:not(:first-child), .tabella-classifica td:not(:first-child) {
            width: 70px;
        }
        .tabella-classifica tr:last-child td {
            border-bottom: none;
        }
        .tabella-classifica tr:hover {
            background-color: #F1F5F9;
        }
        </style>

        <table class="tabella-classifica">
            <tr>
                <th>Squadra</th><th>Punti</th><th>G</th><th>V</th><th>N</th><th>P</th><th>GF</th><th>GS</th><th>DR</th>
            </tr>
        """

        # Genera le righe della tabella pescando dal DataFrame ordinato
        for team, row in df_c.iterrows():
            # Niente spazi segreti usando le parentesi e le singole virgolette!
            html_classifica += (
                "<tr>"
                f"<td><strong>{team}</strong></td>"
                f"<td style='font-weight: bold; color: #2563EB;'>{row['Punti']}</td>"
                f"<td>{row['G']}</td>"
                f"<td>{row['V']}</td>"
                f"<td>{row['N']}</td>"
                f"<td>{row['P']}</td>"
                f"<td>{row['GF']}</td>"
                f"<td>{row['GS']}</td>"
                f"<td>{row['DR']}</td>"
                "</tr>"
            )

        html_classifica += "</table>"

        # Stampa la tabella a schermo
        st.markdown(html_classifica, unsafe_allow_html=True)

        st.divider()
        if not st.session_state.is_admin:
            st.error("🔒 Accesso riservato. Solo l'Amministratore della Lega può distribuire i premi e i ricavi da sponsor.")
        else:
            if st.button("🏆 Distribuisci Premi Campionato e Sponsor", type="primary"):
                squadre_ordinate = df_c.index.tolist()
                premi_sponsor = [70.0, 65.0, 60.0, 55.0, 50.0, 45.0, 42.0, 40.0]
                premi_campionato = [50.0, 52.0, 55.0, 58.0, 62.0, 65.0, 68.0, 70.0]
                
                # --- CONTEGGIO PARTITE IN CASA ---
                partite_in_casa = {s: 0 for s in db.keys()}
                for md in calendario:
                    for m in md:
                        partite_in_casa[m["home"]] += 1
                max_casa = max(partite_in_casa.values())
                
                for pos, nome_sq in enumerate(squadre_ordinate):
                    team = db[nome_sq]
                    p_spons = premi_sponsor[pos]
                    p_camp = premi_campionato[pos]
                    
                    # 1. PREMIO CAMPIONATO: Entra ORA in Cassa e Bilancio corrente
                    team['cassa'] = round(team['cassa'] + p_camp, 2)
                    team['bilancio']['ricavi']['premi_sportivi'] += p_camp
                    team['bilancio']['storico_movimenti'].append(f"Premio Campionato ({pos+1}°): +{p_camp}M")
                    
                    # 2. CONGUAGLIO STADIO: Rimborsa chi ha giocato meno partite in casa
                    diff_casa = max_casa - partite_in_casa[nome_sq]
                    if diff_casa > 0 and team['stadio']['livello']:
                        conguaglio = diff_casa * team['stadio']['base']
                        team['cassa'] = round(team['cassa'] + conguaglio, 2)
                        team['bilancio']['ricavi']['incassi_stadio'] += conguaglio
                        team['bilancio']['storico_movimenti'].append(f"Conguaglio Equità ({diff_casa} partite in meno in casa): +{conguaglio}M")
                    
                    # 3. PREMIO SPONSOR: Viene solo "prenotato" per la prossima stagione
                    team['sponsor_prenotato'] = p_spons
                    
                save_data(db, DB_PATH)
                st.success("Premi Campionato erogati! Calcolati i conguagli per gli Stadi e prenotati gli Sponsor per il prossimo anno.")

# ==========================================
# 7. COPPE UFFICIALI
# ==========================================
elif menu == "7. Coppe (Italia & CL)":
    st.header("🏆 Gestione Coppe")
    
    t_ci, t_cl = st.tabs(["🇮🇹 Coppa Italia", "🇪🇺 Champions League"])
    
    # ---------------- COPPA ITALIA ----------------
    with t_ci:
        st.subheader("🏆 Coppa Italia")
        
        # --- CSS MAGICO PER GLI INPUT DEI GOL (Applicato anche alle Coppe) ---
        st.markdown("""
        <style>
        input[type=number]::-webkit-inner-spin-button, 
        input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
        input[type=number] { -moz-appearance: textfield; }
        [data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] { display: none !important; }
        div[data-testid="stNumberInputContainer"] input { text-align: center !important; }
        </style>
        """, unsafe_allow_html=True)

        if not coppe["ci"]["quarti"]:
            if st.session_state.is_admin and st.button("Sorteggia Tabellone Quarti Coppa Italia", type="primary"):
                teams = list(db.keys())
                random.shuffle(teams)
                coppe["ci"]["quarti"] = [{"home": teams[i], "away": teams[i+1], "gol_home": 0, "gol_away": 0} for i in range(0, 8, 2)]
                save_data(coppe, COPPE_PATH)
                st.rerun()
        
        if coppe["ci"]["quarti"]:
            st.write("🔴 **Quarti di Finale**")
            
            # Leggiamo dal database se questa fase è già stata chiusa
            quarti_salvati = coppe["ci"].get("quarti_salvati", False)
            
            with st.container(border=True):
                for i, m in enumerate(coppe["ci"]["quarti"]):
                    c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                    c1.markdown(f"<div style='text-align: right; margin-top: 8px; font-weight: bold; font-size: 16px;'>{m['home']}</div>", unsafe_allow_html=True)
                    
                    if quarti_salvati:
                        # STILE BOX BLOCCATO NEUTRO (Grigio chiaro, non verde)
                        stile_box = "background-color: #F8FAFC; color: #334155; border: 1px solid #E2E8F0; border-radius: 6px; padding: 6px 0; text-align: center; font-size: 16px;"
                        c2.markdown(f"<div style='{stile_box}'>{m['gol_home']}</div>", unsafe_allow_html=True)
                        c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                        c4.markdown(f"<div style='{stile_box}'>{m['gol_away']}</div>", unsafe_allow_html=True)
                        c5.markdown(f"<div style='text-align: left; margin-top: 8px; font-weight: bold; font-size: 16px;'>{m['away']}</div>", unsafe_allow_html=True)
                        
                        _, c_passa, _ = st.columns([2.5, 2.5, 2.5])
                        # Menu a tendina sparito, sostituito da testo semplice
                        c_passa.markdown(f"<div style='text-align: center; margin-top: 8px; font-size: 14px; color: #64748B;'>Passa il turno: <b style='color: #0F172A;'>{m.get('vincente', '')}</b></div>", unsafe_allow_html=True)
                    else:
                        m['gol_home'] = c2.number_input("H", value=m.get('gol_home',0), key=f"ci_q_h_{i}", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                        c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                        m['gol_away'] = c4.number_input("A", value=m.get('gol_away',0), key=f"ci_q_a_{i}", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                        c5.markdown(f"<div style='text-align: left; margin-top: 8px; font-weight: bold; font-size: 16px;'>{m['away']}</div>", unsafe_allow_html=True)
                        
                        _, c_passa, _ = st.columns([2.5, 2.5, 2.5])
                        opzioni = ["-", m['home'], m['away']]
                        default_idx = opzioni.index(m.get('vincente')) if m.get('vincente') in opzioni else 0
                        scelta = c_passa.selectbox("Passa il turno:", opzioni, index=default_idx, key=f"ci_q_v_{i}", disabled=not st.session_state.is_admin)
                        m['vincente'] = scelta if scelta != "-" else None
                    
                    # Se NON è l'ultima partita, metti la riga
                    if i < len(coppe["ci"]["quarti"]) - 1:
                        st.divider()
                    # Se è l'ultima partita, metti solo uno spazio invisibile
                    else:
                        st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)
            
            if st.session_state.is_admin:
                if not quarti_salvati:
                    # Rinominato il bottone in "Archivia"
                    if st.button("Salva e Archivia Quarti Coppa Italia", type="primary"): 
                        vincitori = [m.get('vincente') for m in coppe["ci"]["quarti"]]
                        # Controllo di sicurezza: non ti fa archiviare se hai lasciato il trattino "-"
                        if None in vincitori:
                            st.error("⚠️ Seleziona chi passa il turno in tutte le partite prima di archiviare!")
                        else:
                            coppe["ci"]["quarti_salvati"] = True
                            save_data(coppe, COPPE_PATH)
                            st.rerun()
                else:
                    st.info("🔒 **Quarti di Finale archiviati.**")
                    if not coppe["ci"]["semis"] and st.button("Genera Semifinali Coppa Italia", type="primary"):
                        vincitori = [m.get('vincente') for m in coppe["ci"]["quarti"]]
                        coppe["ci"]["semis"] = [{"home": vincitori[0], "away": vincitori[1], "gol_home": 0, "gol_away": 0}, {"home": vincitori[2], "away": vincitori[3], "gol_home": 0, "gol_away": 0}]
                        save_data(coppe, COPPE_PATH)
                        st.rerun()

        if coppe["ci"]["semis"]:
            st.write("🟡 **Semifinali**")
            semis_salvate = coppe["ci"].get("semis_salvate", False)
            
            with st.container(border=True):
                for i, m in enumerate(coppe["ci"]["semis"]):
                    c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                    c1.markdown(f"<div style='text-align: right; margin-top: 8px; font-weight: bold; font-size: 16px;'>{m['home']}</div>", unsafe_allow_html=True)
                    
                    if semis_salvate:
                        stile_box = "background-color: #F8FAFC; color: #334155; border: 1px solid #E2E8F0; border-radius: 6px; padding: 6px 0; text-align: center; font-size: 16px;"
                        c2.markdown(f"<div style='{stile_box}'>{m['gol_home']}</div>", unsafe_allow_html=True)
                        c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                        c4.markdown(f"<div style='{stile_box}'>{m['gol_away']}</div>", unsafe_allow_html=True)
                        c5.markdown(f"<div style='text-align: left; margin-top: 8px; font-weight: bold; font-size: 16px;'>{m['away']}</div>", unsafe_allow_html=True)
                        
                        _, c_passa, _ = st.columns([2.5, 2.5, 2.5])
                        c_passa.markdown(f"<div style='text-align: center; margin-top: 8px; font-size: 14px; color: #64748B;'>Passa in Finale: <b style='color: #0F172A;'>{m.get('vincente', '')}</b></div>", unsafe_allow_html=True)
                    else:
                        m['gol_home'] = c2.number_input("H", value=m.get('gol_home',0), key=f"ci_s_h_{i}", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                        c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                        m['gol_away'] = c4.number_input("A", value=m.get('gol_away',0), key=f"ci_s_a_{i}", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                        c5.markdown(f"<div style='text-align: left; margin-top: 8px; font-weight: bold; font-size: 16px;'>{m['away']}</div>", unsafe_allow_html=True)
                        
                        _, c_passa, _ = st.columns([2.5, 2.5, 2.5])
                        opzioni = ["-", m['home'], m['away']]
                        default_idx = opzioni.index(m.get('vincente')) if m.get('vincente') in opzioni else 0
                        scelta = c_passa.selectbox("Passa in Finale:", opzioni, index=default_idx, key=f"ci_s_v_{i}", disabled=not st.session_state.is_admin)
                        m['vincente'] = scelta if scelta != "-" else None
                    
                    if i < len(coppe["ci"]["semis"]) - 1:
                        st.divider()
                    else:
                        st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)
            
            if st.session_state.is_admin:
                if not semis_salvate:
                    if st.button("Salva e Archivia Semifinali Coppa Italia", type="primary"): 
                        vincitori = [m.get('vincente') for m in coppe["ci"]["semis"]]
                        if None in vincitori:
                            st.error("⚠️ Seleziona chi passa in finale in tutte le partite prima di archiviare!")
                        else:
                            coppe["ci"]["semis_salvate"] = True
                            save_data(coppe, COPPE_PATH)
                            st.rerun()
                else:
                    st.info("🔒 **Semifinali archiviate.**")
                    if not coppe["ci"]["finale"] and st.button("Genera Finale Coppa Italia", type="primary"):
                        vincitori = [m.get('vincente') for m in coppe["ci"]["semis"]]
                        perdenti = [m['home'] if m.get('vincente') == m['away'] else m['away'] for m in coppe["ci"]["semis"]]
                        coppe["ci"]["finale"] = [{"home": vincitori[0], "away": vincitori[1], "gol_home": 0, "gol_away": 0}]
                        coppe["ci"]["perse_semis"] = perdenti
                        save_data(coppe, COPPE_PATH)
                        st.rerun()
                
        if coppe["ci"]["finale"]:
            st.write("🟢 **Finale**")
            finale_salvata = coppe["ci"].get("finale_salvata", False)
            
            with st.container(border=True):
                m = coppe["ci"]["finale"][0]
                c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                c1.markdown(f"<div style='text-align: right; margin-top: 8px; font-weight: bold; font-size: 16px;'>{m['home']}</div>", unsafe_allow_html=True)
                
                if finale_salvata:
                    stile_box = "background-color: #F8FAFC; color: #334155; border: 1px solid #E2E8F0; border-radius: 6px; padding: 6px 0; text-align: center; font-size: 16px;"
                    c2.markdown(f"<div style='{stile_box}'>{m['gol_home']}</div>", unsafe_allow_html=True)
                    c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                    c4.markdown(f"<div style='{stile_box}'>{m['gol_away']}</div>", unsafe_allow_html=True)
                    c5.markdown(f"<div style='text-align: left; margin-top: 8px; font-weight: bold; font-size: 16px;'>{m['away']}</div>", unsafe_allow_html=True)
                    
                    _, c_passa, _ = st.columns([2.5, 2.5, 2.5])
                    c_passa.markdown(f"<div style='text-align: center; margin-top: 8px; font-size: 14px; color: #64748B;'>VINCITORE: <b style='color: #0F172A;'>{m.get('vincente', '')}</b></div>", unsafe_allow_html=True)
                else:
                    m['gol_home'] = c2.number_input("H", value=m.get('gol_home',0), key="ci_f_h", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                    c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                    m['gol_away'] = c4.number_input("A", value=m.get('gol_away',0), key="ci_f_a", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                    c5.markdown(f"<div style='text-align: left; margin-top: 8px; font-weight: bold; font-size: 16px;'>{m['away']}</div>", unsafe_allow_html=True)
                    
                    _, c_passa, _ = st.columns([2.5, 2.5, 2.5])
                    opzioni = ["-", m['home'], m['away']]
                    default_idx = opzioni.index(m.get('vincente')) if m.get('vincente') in opzioni else 0
                    scelta = c_passa.selectbox("VINCITORE Coppa Italia:", opzioni, index=default_idx, key="ci_f_v", disabled=not st.session_state.is_admin)
                    m['vincente'] = scelta if scelta != "-" else None

                st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)
            
            if st.session_state.is_admin:
                if not finale_salvata:
                    if st.button("Salva e Archivia Finale Coppa Italia", type="primary"): 
                        vincente = m.get('vincente')
                        if not vincente:
                            st.error("⚠️ Seleziona il vincitore prima di archiviare!")
                        else:
                            coppe["ci"]["finale_salvata"] = True
                            save_data(coppe, COPPE_PATH)
                            st.rerun()
                else:
                    st.info("🔒 **Finale archiviata.**")
                    if not coppe["ci"]["premi_dati"] and st.button("🏆 Eroga Premi Coppa Italia", type="primary"):
                        vincente = m.get('vincente')
                        perdente = m['home'] if vincente == m['away'] else m['away']
                        db[vincente]['bilancio']['ricavi']['premi_sportivi'] += 35.0
                        db[vincente]['cassa'] += 35.0
                        db[perdente]['bilancio']['ricavi']['premi_sportivi'] += 20.0
                        db[perdente]['cassa'] += 20.0
                        for sq in coppe["ci"]["perse_semis"]: 
                            db[sq]['bilancio']['ricavi']['premi_sportivi'] += 10.0
                            db[sq]['cassa'] += 10.0
                        coppe["ci"]["premi_dati"] = True
                        save_data(db, DB_PATH); save_data(coppe, COPPE_PATH)
                        st.success("Premi Coppa Italia distribuiti!")
    
    # ---------------- CHAMPIONS LEAGUE ----------------
    with t_cl:
        st.subheader("🏆 Champions League")
        
        stile_box = "background-color: #F8FAFC; color: #334155; border: 1px solid #E2E8F0; border-radius: 6px; padding: 6px 0; text-align: center; font-size: 16px;"

        if not coppe["cl"]["gir_A"]:
            if st.session_state.is_admin and st.button("Sorteggia Gironi e Calendari Champions League", type="primary"):
                teams = list(db.keys())
                random.shuffle(teams)
                coppe["cl"]["gir_A"] = teams[:4]
                coppe["cl"]["gir_B"] = teams[4:]
                
                coppe["cl"]["cal_A"] = genera_calendario_berger(teams[:4], 6)
                coppe["cl"]["cal_B"] = genera_calendario_berger(teams[4:], 6)
                
                save_data(coppe, COPPE_PATH)
                st.rerun()
                
        if coppe["cl"]["gir_A"]:
            st.write("### Fase a Gironi")
            
            gironi_salvati = coppe["cl"].get("gironi_salvati", False)
            
            # --- CALCOLO DINAMICO PUNTI E STATISTICHE (DR, GF) ---
            stats_A = {t: {"Punti": 0, "GF": 0, "GS": 0, "DR": 0} for t in coppe["cl"]["gir_A"]}
            stats_B = {t: {"Punti": 0, "GF": 0, "GS": 0, "DR": 0} for t in coppe["cl"]["gir_B"]}
            
            def calcola_stats(calendario, dict_stats):
                for md in calendario:
                    for m in md:
                        if m.get("giocata", False):
                            gh = m["gol_home"]
                            ga = m["gol_away"]
                            
                            # Aggiunge Gol Fatti e Subiti
                            dict_stats[m["home"]]["GF"] += gh
                            dict_stats[m["home"]]["GS"] += ga
                            dict_stats[m["away"]]["GF"] += ga
                            dict_stats[m["away"]]["GS"] += gh
                            
                            # Calcola i Punti
                            if gh > ga: dict_stats[m["home"]]["Punti"] += 3
                            elif gh == ga: 
                                dict_stats[m["home"]]["Punti"] += 1
                                dict_stats[m["away"]]["Punti"] += 1
                            else: dict_stats[m["away"]]["Punti"] += 3
                            
                # Calcola Differenza Reti per ogni squadra
                for t, stats in dict_stats.items():
                    stats["DR"] = stats["GF"] - stats["GS"]
                            
            calcola_stats(coppe["cl"].get("cal_A", []), stats_A)
            calcola_stats(coppe["cl"].get("cal_B", []), stats_B)
            
            # Creazione Dataframe e Ordinamento Regolamento: Punti -> Differenza Reti -> Gol Fatti
            df_A = pd.DataFrame([{"Squadra": k, **v} for k, v in stats_A.items()]).sort_values(by=["Punti", "DR", "GF"], ascending=[False, False, False])
            df_B = pd.DataFrame([{"Squadra": k, **v} for k, v in stats_B.items()]).sort_values(by=["Punti", "DR", "GF"], ascending=[False, False, False])

            colA, colB = st.columns(2)
            
            with colA:
                st.markdown("#### 🔵 Girone A")
                # Mostriamo in classifica solo Squadra, Punti e DR (GF rimane nascosto ma lavora sull'ordinamento)
                st.dataframe(df_A[["Squadra", "Punti", "DR"]], hide_index=True, use_container_width=True)
                
                with st.expander("Calendario Girone A" if gironi_salvati else "Calendario Girone A"):
                    for g_idx, md in enumerate(coppe["cl"].get("cal_A", [])):
                        st.markdown(f"**Giornata {g_idx + 1}**")
                        for m_idx, m in enumerate(md):
                            c1, c2, c3, c4, c5, c6 = st.columns([3, 1, 0.5, 1, 3, 1])
                            c1.markdown(f"<div style='text-align: right; margin-top: 8px; font-weight: bold;'>{m['home']}</div>", unsafe_allow_html=True)
                            
                            # LA MAGIA: Se i gironi sono archiviati, OPPURE se questa singola partita ha la spunta, la blocchiamo!
                            partita_bloccata = gironi_salvati or m.get("giocata", False)
                            
                            if partita_bloccata:
                                c2.markdown(f"<div style='{stile_box}'>{m['gol_home']}</div>", unsafe_allow_html=True)
                                c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                                c4.markdown(f"<div style='{stile_box}'>{m['gol_away']}</div>", unsafe_allow_html=True)
                                c5.markdown(f"<div style='text-align: left; margin-top: 8px; font-weight: bold;'>{m['away']}</div>", unsafe_allow_html=True)
                                # Sostituiamo la checkbox interattiva con una semplice icona di conferma
                                c6.markdown("<div style='margin-top: 8px;' title='Giocata e Archiviata'>✅</div>", unsafe_allow_html=True)
                            else:
                                m["gol_home"] = c2.number_input("H", value=m.get("gol_home", 0), key=f"cl_a_gh_{g_idx}_{m_idx}", label_visibility="collapsed", disabled=not st.session_state.is_admin)
                                c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                                m["gol_away"] = c4.number_input("A", value=m.get("gol_away", 0), key=f"cl_a_ga_{g_idx}_{m_idx}", label_visibility="collapsed", disabled=not st.session_state.is_admin)
                                c5.markdown(f"<div style='text-align: left; margin-top: 8px; font-weight: bold;'>{m['away']}</div>", unsafe_allow_html=True)
                                m["giocata"] = c6.checkbox("✅", value=m.get("giocata", False), key=f"cl_a_g_{g_idx}_{m_idx}", disabled=not st.session_state.is_admin)
                        st.divider()
            
            with colB:
                st.markdown("#### 🔴 Girone B")
                # Il DataFrame df_B ora viene calcolato sopra insieme a df_A.
                # Qui ci limitiamo a stamparlo mostrando solo Squadra, Punti e DR!
                st.dataframe(df_B[["Squadra", "Punti", "DR"]], hide_index=True, use_container_width=True)
                
                with st.expander("Calendario Girone B" if gironi_salvati else "Calendario Girone B"):
                    for g_idx, md in enumerate(coppe["cl"].get("cal_B", [])):
                        st.markdown(f"**Giornata {g_idx + 1}**")
                        for m_idx, m in enumerate(md):
                            c1, c2, c3, c4, c5, c6 = st.columns([3, 1, 0.5, 1, 3, 1])
                            c1.markdown(f"<div style='text-align: right; margin-top: 8px; font-weight: bold;'>{m['home']}</div>", unsafe_allow_html=True)
                            
                            partita_bloccata = gironi_salvati or m.get("giocata", False)
                            
                            if partita_bloccata:
                                c2.markdown(f"<div style='{stile_box}'>{m['gol_home']}</div>", unsafe_allow_html=True)
                                c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                                c4.markdown(f"<div style='{stile_box}'>{m['gol_away']}</div>", unsafe_allow_html=True)
                                c5.markdown(f"<div style='text-align: left; margin-top: 8px; font-weight: bold;'>{m['away']}</div>", unsafe_allow_html=True)
                                c6.markdown("<div style='margin-top: 8px;' title='Giocata e Archiviata'>✅</div>", unsafe_allow_html=True)
                            else:
                                m["gol_home"] = c2.number_input("H", value=m.get("gol_home", 0), key=f"cl_b_gh_{g_idx}_{m_idx}", label_visibility="collapsed", disabled=not st.session_state.is_admin)
                                c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                                m["gol_away"] = c4.number_input("A", value=m.get("gol_away", 0), key=f"cl_b_ga_{g_idx}_{m_idx}", label_visibility="collapsed", disabled=not st.session_state.is_admin)
                                c5.markdown(f"<div style='text-align: left; margin-top: 8px; font-weight: bold;'>{m['away']}</div>", unsafe_allow_html=True)
                                m["giocata"] = c6.checkbox("✅", value=m.get("giocata", False), key=f"cl_b_g_{g_idx}_{m_idx}", disabled=not st.session_state.is_admin)
                        st.divider()

            if st.session_state.is_admin:
                if not gironi_salvati:
                    # Dividiamo lo spazio in due bottoni
                    btn_salva, btn_archivia = st.columns(2)
                    
                    # Bottone 1: Salva i progressi giornata per giornata
                    if btn_salva.button("💾 Salva Risultati Parziali", type="secondary", use_container_width=True, key="btn_salva_cl"):
                        save_data(coppe, COPPE_PATH)
                        st.success("Risultati parziali salvati!.")
                        st.rerun()
                        
                    # Bottone 2: Blocca tutto alla fine
                    if btn_archivia.button("🔒 Archivia Gironi Champions League", type="primary", use_container_width=True, key="btn_archivia_cl"):
                        coppe["cl"]["gironi_salvati"] = True
                        save_data(coppe, COPPE_PATH)
                        st.rerun()
                else:
                    st.info("🔒 **Gironi archiviati e classifiche definitive.**")
                    if not coppe["cl"]["semis_andata"] and st.button("Genera Semifinali CL", type="primary", use_container_width=True, key="btn_genera_semis_cl"):
                        a1, a2 = df_A.iloc[0]["Squadra"], df_A.iloc[1]["Squadra"]
                        b1, b2 = df_B.iloc[0]["Squadra"], df_B.iloc[1]["Squadra"]
                        coppe["cl"]["semis_andata"] = [{"home": a1, "away": b2, "gol_home": 0, "gol_away": 0}, {"home": b1, "away": a2, "gol_home": 0, "gol_away": 0}]
                        coppe["cl"]["semis_ritorno"] = [{"home": b2, "away": a1, "gol_home": 0, "gol_away": 0}, {"home": a2, "away": b1, "gol_home": 0, "gol_away": 0}]
                        save_data(coppe, COPPE_PATH)
                        st.rerun()

        if coppe["cl"]["semis_andata"]:
            st.divider()
            st.write("🟡 **Semifinali (Andata e Ritorno)**")
            semis_salvate = coppe["cl"].get("semis_salvate", False)
            
            with st.container(border=True):
                for i in range(2):
                    ma = coppe["cl"]["semis_andata"][i]
                    mr = coppe["cl"]["semis_ritorno"][i]
                    
                    st.markdown(f"<h5 style='text-align: center; color: #1E293B;'> {ma['home']} vs {ma['away']}</h5>", unsafe_allow_html=True)
                    
                    if semis_salvate:
                        # ANDATA BLOCCATA
                        c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                        c1.markdown(f"<div style='text-align: right; margin-top: 8px;'>✈️ Andata: <b style='font-size: 16px;'>{ma['home']}</b></div>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='{stile_box}'>{ma['gol_home']}</div>", unsafe_allow_html=True)
                        c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                        c4.markdown(f"<div style='{stile_box}'>{ma['gol_away']}</div>", unsafe_allow_html=True)
                        c5.markdown(f"<div style='text-align: left; margin-top: 8px;'><b style='font-size: 16px;'>{ma['away']}</b></div>", unsafe_allow_html=True)
                        
                        # RITORNO BLOCCATO
                        c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                        c1.markdown(f"<div style='text-align: right; margin-top: 8px;'>🏠 Ritorno: <b style='font-size: 16px;'>{mr['home']}</b></div>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='{stile_box}'>{mr['gol_home']}</div>", unsafe_allow_html=True)
                        c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                        c4.markdown(f"<div style='{stile_box}'>{mr['gol_away']}</div>", unsafe_allow_html=True)
                        c5.markdown(f"<div style='text-align: left; margin-top: 8px;'><b style='font-size: 16px;'>{mr['away']}</b></div>", unsafe_allow_html=True)
                        
                        _, c_passa, _ = st.columns([2.5, 2.5, 2.5])
                        c_passa.markdown(f"<div style='text-align: center; margin-top: 8px; font-size: 14px; color: #64748B;'>Passa in Finale: <b style='color: #0F172A;'>{mr.get('vincente', '')}</b></div>", unsafe_allow_html=True)
                    else:
                        # ANDATA EDITABILE
                        c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                        c1.markdown(f"<div style='text-align: right; margin-top: 8px;'>✈️ Andata: <b style='font-size: 16px;'>{ma['home']}</b></div>", unsafe_allow_html=True)
                        ma['gol_home'] = c2.number_input("H", value=ma.get('gol_home',0), key=f"cl_s_ah_{i}", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                        c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                        ma['gol_away'] = c4.number_input("A", value=ma.get('gol_away',0), key=f"cl_s_aa_{i}", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                        c5.markdown(f"<div style='text-align: left; margin-top: 8px;'><b style='font-size: 16px;'>{ma['away']}</b></div>", unsafe_allow_html=True)

                        # RITORNO EDITABILE
                        c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                        c1.markdown(f"<div style='text-align: right; margin-top: 8px;'>🏠 Ritorno: <b style='font-size: 16px;'>{mr['home']}</b></div>", unsafe_allow_html=True)
                        mr['gol_home'] = c2.number_input("H", value=mr.get('gol_home',0), key=f"cl_s_rh_{i}", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                        c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                        mr['gol_away'] = c4.number_input("A", value=mr.get('gol_away',0), key=f"cl_s_ra_{i}", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                        c5.markdown(f"<div style='text-align: left; margin-top: 8px;'><b style='font-size: 16px;'>{mr['away']}</b></div>", unsafe_allow_html=True)
                        
                        _, c_passa, _ = st.columns([2.5, 2.5, 2.5])
                        opzioni = ["-", ma['home'], ma['away']]
                        default_idx = opzioni.index(mr.get('vincente')) if mr.get('vincente') in opzioni else 0
                        scelta = c_passa.selectbox("Passa in Finale:", opzioni, index=default_idx, key=f"cl_s_v_{i}", disabled=not st.session_state.is_admin)
                        mr['vincente'] = scelta if scelta != "-" else None
                        
                    if i < 1:
                        st.divider()
                    else:
                        st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)

            if st.session_state.is_admin:
                if not semis_salvate:
                    if st.button("Salva e Archivia Semifinali Champions League", type="primary"):
                        vincitori = [coppe["cl"]["semis_ritorno"][0].get('vincente'), coppe["cl"]["semis_ritorno"][1].get('vincente')]
                        if None in vincitori:
                            st.error("⚠️ Seleziona chi passa in finale in tutte le partite prima di archiviare!")
                        else:
                            coppe["cl"]["semis_salvate"] = True
                            save_data(coppe, COPPE_PATH)
                            st.rerun()
                else:
                    st.info("🔒 **Semifinali archiviate.**")
                    if not coppe["cl"]["finale"] and st.button("Genera Finale Champions League", type="primary"):
                        vincitori = [coppe["cl"]["semis_ritorno"][0].get('vincente'), coppe["cl"]["semis_ritorno"][1].get('vincente')]
                        
                        perdenti = []
                        for i in range(2):
                            ma = coppe["cl"]["semis_andata"][i]
                            v = coppe["cl"]["semis_ritorno"][i].get('vincente')
                            p = ma['home'] if v == ma['away'] else ma['away']
                            perdenti.append(p)
                            
                        coppe["cl"]["finale"] = [{"home": vincitori[0], "away": vincitori[1], "gol_home": 0, "gol_away": 0}]
                        coppe["cl"]["perse_semis"] = perdenti
                        save_data(coppe, COPPE_PATH)
                        st.rerun()
                
        if coppe["cl"]["finale"]:
            st.write("🟢 **Finale**")
            finale_salvata = coppe["cl"].get("finale_salvata", False)
            
            with st.container(border=True):
                m = coppe["cl"]["finale"][0]
                c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                c1.markdown(f"<div style='text-align: right; margin-top: 8px; font-weight: bold; font-size: 16px;'>{m['home']}</div>", unsafe_allow_html=True)
                
                if finale_salvata:
                    c2.markdown(f"<div style='{stile_box}'>{m['gol_home']}</div>", unsafe_allow_html=True)
                    c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                    c4.markdown(f"<div style='{stile_box}'>{m['gol_away']}</div>", unsafe_allow_html=True)
                    c5.markdown(f"<div style='text-align: left; margin-top: 8px; font-weight: bold; font-size: 16px;'>{m['away']}</div>", unsafe_allow_html=True)
                    
                    _, c_passa, _ = st.columns([2.5, 2.5, 2.5])
                    c_passa.markdown(f"<div style='text-align: center; margin-top: 8px; font-size: 14px; color: #64748B;'>VINCITORE CL: <b style='color: #0F172A;'>{m.get('vincente', '')}</b></div>", unsafe_allow_html=True)
                else:
                    m['gol_home'] = c2.number_input("H", value=m.get('gol_home',0), key="cl_f_h", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                    c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                    m['gol_away'] = c4.number_input("A", value=m.get('gol_away',0), key="cl_f_a", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                    c5.markdown(f"<div style='text-align: left; margin-top: 8px; font-weight: bold; font-size: 16px;'>{m['away']}</div>", unsafe_allow_html=True)
                    
                    _, c_passa, _ = st.columns([2.5, 2.5, 2.5])
                    opzioni = ["-", m['home'], m['away']]
                    default_idx = opzioni.index(m.get('vincente')) if m.get('vincente') in opzioni else 0
                    scelta = c_passa.selectbox("VINCITORE Champions League:", opzioni, index=default_idx, key="cl_f_v", disabled=not st.session_state.is_admin)
                    m['vincente'] = scelta if scelta != "-" else None

                st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)
                    
            if st.session_state.is_admin:
                if not finale_salvata:
                    if st.button("Salva e Archivia Finale Champions League", type="primary"):
                        if not m.get('vincente'):
                            st.error("⚠️ Seleziona il vincitore prima di archiviare!")
                        else:
                            coppe["cl"]["finale_salvata"] = True
                            save_data(coppe, COPPE_PATH)
                            st.rerun()
                else:
                    st.info("🔒 **Finale archiviata.**")
                    if not coppe["cl"]["premi_dati"] and st.button("🏆 Eroga Premi Champions League", type="primary"):
                        vincente = m.get('vincente')
                        perdente = m['home'] if vincente == m['away'] else m['away']
                        db[vincente]['bilancio']['ricavi']['premi_sportivi'] += 50.0
                        db[vincente]['cassa'] += 50.0
                        db[perdente]['bilancio']['ricavi']['premi_sportivi'] += 35.0
                        db[perdente]['cassa'] += 35.0
                        for sq in coppe["cl"]["perse_semis"]: 
                            db[sq]['bilancio']['ricavi']['premi_sportivi'] += 20.0
                            db[sq]['cassa'] += 20.0
                        coppe["cl"]["premi_dati"] = True
                        save_data(db, DB_PATH); save_data(coppe, COPPE_PATH)
                        st.success("Premi Champions League distribuiti!")

# ==========================================
# 8. CHIUSURA FISCALE
# ==========================================
elif menu == "8. Chiusura Fiscale Bilancio":
    st.header("📜 Chiusura Fiscale")
    
    if not st.session_state.is_admin:
        st.info("🔒 L'esecuzione della chiusura fiscale è riservata all'Amministratore.")
    else:
        st.warning("Attenzione: Da fare SOLO una volta finite tutte le aste, le competizioni e distribuiti i premi!")
        
        # --- LA CHICCA: DEFINIAMO IL POPUP (DIALOG) ---
        @st.dialog("⚠️ CONFERMA CHIUSURA IRREVERSIBILE")
        def popup_conferma_chiusura():
            st.error("Stai per chiudere definitivamente l'anno fiscale di **tutte** le squadre.")
            st.write("I contratti in scadenza verranno annullati, i prestiti riscattati e l'eventuale multa del Fair Play applicata alla Cassa. **L'operazione NON può essere annullata.**")
            
            if st.button("Sì, sono sicuro. Esegui Chiusura", type="primary", use_container_width=True):
                # --- INIZIO DELLA TUA LOGICA ORIGINALE ---
                for sq, dati in db.items():
                    b = dati['bilancio']
                    tot_ammortamenti, tot_ingaggi = 0.0, 0.0
                    for g in dati['rosa']:
                        amm = g['ammortamento_annuo']
                        stip = g['stipendio']
                        if g.get('acquistato_a_gennaio') and g['anni_trascorsi'] == 0:
                            amm /= 2; stip /= 2
                        elif g.get('rinnovato_a_gennaio') and g['anni_trascorsi'] == 0:
                            amm = (g['vecchio_amm_gennaio'] / 2) + (g['ammortamento_annuo'] / 2)
                            stip = (g['vecchio_stip_gennaio'] / 2) + (g['stipendio'] / 2)
                            
                        if not g.get("in_prestito_da"): 
                            tot_ammortamenti += amm
                            if g.get("prestato_a"): tot_ingaggi += stip * ((100 - g['perc_stipendio_pagato']) / 100)
                            else: tot_ingaggi += stip
                        else: tot_ingaggi += stip * (g['perc_stipendio_pagato'] / 100)
                            
                    b['costi']['ammortamenti'] = round(tot_ammortamenti, 2)
                    b['costi']['monte_ingaggi'] = round(tot_ingaggi, 2)
                    
                    dati['cassa'] = round(dati['cassa'] - tot_ingaggi, 2)
                    utile = round(sum(b['ricavi'].values()) - sum(b['costi'].values()), 2)
                    
                    if utile < 0:
                        multa_fpf = round(abs(utile) * 0.15, 2)
                        dati['cassa'] -= multa_fpf  
                        dati['bilancio']['storico_movimenti'].append(f"Multa Fair Play UEFA (15% della perdita di {utile}M): -{multa_fpf}M") 
                    
                    dati['ultimo_bilancio_chiuso'] = {
                        "ricavi": {k: round(v, 2) for k, v in dati['bilancio']['ricavi'].items()},
                        "costi": {k: round(v, 2) for k, v in dati['bilancio']['costi'].items()},
                        "utile": utile,
                        "cassa_partenza_nuovo_anno": dati['cassa']
                    }
                    
                    dati['bilancio'] = init_bilancio()
                    dati['stadio'] = {"livello": None, "costo_annuo": 0, "base": 0, "pari": 0, "vittoria": 0}
                    
                    dati['cassa'] += 70.0
                    dati['bilancio']['ricavi']['nuovo_capitale'] = 70.0
                    dati['bilancio']['storico_movimenti'].append("Iniezione Nuovo Capitale: +70.0M (Cassa e Ricavi)")
                    
                    sponsor_nuovo = dati.get('sponsor_prenotato', 0.0)
                    if sponsor_nuovo > 0:
                        dati['cassa'] += sponsor_nuovo
                        dati['bilancio']['ricavi']['sponsor'] = sponsor_nuovo
                        dati['bilancio']['storico_movimenti'].append(f"Accordo Sponsor Annuale: +{sponsor_nuovo}M")
                        del dati['sponsor_prenotato']
                    
                    nuova_rosa = []
                    for g in dati['rosa']:
                        if g.get("in_prestito_da"):
                            if "riscatto_prenotato" in g:
                                prezzo_r = g['riscatto_prenotato']['cifra']
                                anni_nuovi = g['riscatto_prenotato']['anni']
                                dati['cassa'] -= prezzo_r
                                
                                del g['in_prestito_da']
                                if 'perc_stipendio_pagato' in g: del g['perc_stipendio_pagato']
                                if 'accordo_riscatto' in g: del g['accordo_riscatto']
                                if 'anni_prestito_rimanenti' in g: del g['anni_prestito_rimanenti']
                                del g['riscatto_prenotato']
                                
                                g['costo_acquisto'] = g['valore_residuo'] = prezzo_r
                                g['anni_contratto'] = anni_nuovi
                                g['ammortamento_annuo'] = prezzo_r / anni_nuovi if anni_nuovi > 0 else 0
                                g['stipendio'] = 1.0 if prezzo_r <= 15 else (2.5 if prezzo_r <= 45 else (4.5 if prezzo_r <= 85 else (7.0 if prezzo_r <= 130 else 11.0)))
                                g['anni_trascorsi'] = 0
                                nuova_rosa.append(g)
                            else:
                                if g.get('prestato_a_gennaio'):
                                    g['anni_prestito_rimanenti'] = g.get('anni_prestito_rimanenti', 1) - 0.5
                                    g.pop('prestato_a_gennaio', None) # Dal prossimo anno tornerà un anno pieno normale!
                                else:
                                    g['anni_prestito_rimanenti'] = g.get('anni_prestito_rimanenti', 1) - 1
                                if g['anni_prestito_rimanenti'] > 0:
                                    nuova_rosa.append(g) 
                        elif g.get("prestato_a"):
                            amm_da_togliere = g['ammortamento_annuo']
                            if g.get('acquistato_a_gennaio') and g['anni_trascorsi'] == 0: 
                                amm_da_togliere /= 2
                            elif g.get('rinnovato_a_gennaio') and g['anni_trascorsi'] == 0:
                                amm_da_togliere /= 2 
                                
                            if "riscatto_prenotato" in g:
                                prezzo_r = g['riscatto_prenotato']['cifra']
                                dati['cassa'] += prezzo_r
                                
                                vero_valore_residuo = max(0, g['valore_residuo'] - amm_da_togliere)
                                
                                diff = prezzo_r - vero_valore_residuo
                                if diff > 0: dati['bilancio']['ricavi']['plusvalenze'] += diff
                                else: dati['bilancio']['costi']['minusvalenze'] += abs(diff)
                            else:
                                g['valore_residuo'] = max(0, g['valore_residuo'] - amm_da_togliere)
                                if (g.get('acquistato_a_gennaio', False) or g.get('rinnovato_a_gennaio', False)) and g.get('anni_trascorsi', 0) == 0:
                                    g['anni_trascorsi'] += 0.5
                                else:
                                    g['anni_trascorsi'] += 1
                                if g.get('prestato_a_gennaio'):
                                    g['anni_prestito_rimanenti'] = g.get('anni_prestito_rimanenti', 1) - 0.5
                                    g.pop('prestato_a_gennaio', None) # Dal prossimo anno tornerà un anno pieno normale!
                                else:
                                    g['anni_prestito_rimanenti'] = g.get('anni_prestito_rimanenti', 1) - 1
                                if g['anni_prestito_rimanenti'] > 0:
                                    nuova_rosa.append(g) 
                                else:
                                    del g['prestato_a']
                                    if 'perc_stipendio_pagato' in g: del g['perc_stipendio_pagato']
                                    if 'accordo_riscatto' in g: del g['accordo_riscatto']
                                    if 'anni_prestito_rimanenti' in g: del g['anni_prestito_rimanenti']
                                    nuova_rosa.append(g)
                        else:
                            amm_da_togliere = g['ammortamento_annuo']
                            if g.get('acquistato_a_gennaio') and g['anni_trascorsi'] == 0: 
                                amm_da_togliere /= 2
                            elif g.get('rinnovato_a_gennaio') and g['anni_trascorsi'] == 0:
                                amm_da_togliere /= 2 
                                
                            g['valore_residuo'] = max(0, g['valore_residuo'] - amm_da_togliere)
                            if (g.get('acquistato_a_gennaio', False) or g.get('rinnovato_a_gennaio', False)) and g.get('anni_trascorsi', 0) == 0:
                                g['anni_trascorsi'] += 0.5
                            else:
                                g['anni_trascorsi'] += 1
                            
                            if g['anni_trascorsi'] < g['anni_contratto']:
                                nuova_rosa.append(g)
                    dati['rosa'] = nuova_rosa 
                    
                save_data(db, DB_PATH)
                save_data([], CAL_PATH)
                save_data(init_coppe(), COPPE_PATH)
                # --- FINE LOGICA ORIGINALE ---

                # Inneschiamo la festa e ricarichiamo la pagina per chiudere il popup!
                st.session_state.mostra_festa = True
                st.rerun()

        # Questo è il bottone PRINCIPALE che si vede nella pagina.
        # Invece di eseguire il calcolo, chiama la funzione popup_conferma_chiusura() !
        if st.button("ESEGUI CHIUSURA BILANCIO PER TUTTE LE SQUADRE", type="primary", use_container_width=True):
            popup_conferma_chiusura()

        # Intercetta il comando di festa dal popup e fa esplodere i palloncini
        if st.session_state.get('mostra_festa'):
            st.success("✅ Chiusura Fiscale Completata! Bilanci azzerati, contratti scaduti rimossi, prestiti e riscatti processati per la nuova stagione.")
            st.session_state.mostra_festa = False # Resetta per non far piovere palloncini all'infinito

    st.divider()
    st.subheader("📊 Prospetto Finanziario Stagione Precedente")
    
    if db and any("ultimo_bilancio_chiuso" in t for t in db.values()):
        sq_view = st.selectbox("Seleziona Squadra per visualizzare il bilancio chiuso", list(db.keys()), key="storico_sq")
        sq_dati = db[sq_view]
        
        if "ultimo_bilancio_chiuso" in sq_dati:
            ub = sq_dati["ultimo_bilancio_chiuso"]
            
            tot_ricavi = sum(ub['ricavi'].values())
            tot_costi = sum(ub['costi'].values())
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Totale Ricavi", f"{tot_ricavi:.2f} M")
            c2.metric("Totale Costi", f"{tot_costi:.2f} M")
            c3.metric("Risultato (Utile/Perdita)", f"{ub['utile']:.2f} M", delta_color="normal" if ub['utile'] >= 0 else "inverse")
            c4.metric("Cassa Iniziale Nuovo Anno", f"{ub['cassa_partenza_nuovo_anno']:.2f} M")
            
            col_ric, col_cost = st.columns(2)
            
            with col_ric:
                st.markdown("#### 🟢 Dettaglio Ricavi")
                for k, v in ub['ricavi'].items():
                    if v > 0: 
                        nome_voce = k.replace('_', ' ').title()
                        st.write(f"- **{nome_voce}**: {v:.2f} M")
                        
            with col_cost:
                st.markdown("#### 🔴 Dettaglio Costi")
                for k, v in ub['costi'].items():
                    if v > 0: 
                        nome_voce = k.replace('_', ' ').title()
                        st.write(f"- **{nome_voce}**: {v:.2f} M")
        else:
            st.info("Questa squadra non ha ancora chiuso un bilancio aziendale.")
    else:
        st.info("Nessuno storico disponibile. Esegui la chiusura fiscale a fine stagione per generare i prospetti.")

# ==========================================
# 9. CRONOLOGIA E UFFICIALITÀ LEGA
# ==========================================
elif menu == "9. Cronologia Ufficialità":
    st.header("📰 Notiziario Ufficiale Lega")
    st.caption("Il feed cronologico di tutte le operazioni societarie e di mercato in tempo reale.")
    st.divider()
    
    feed = load_feed()
    
    if not feed:
        st.info("Nessuna operazione registrata finora.")
    else:
        import re  # (Assicurati che sia importato, male non fa rimetterlo qui se serve)
        
        # --- LA MAGIA DEL FILTRO ---
        # 1. Troviamo tutte le squadre uniche che hanno almeno una notizia nel feed
        squadre_con_notizie = sorted(list(set([item['squadra'] for item in feed])))
        
        # 2. Creiamo il selettore
        filtro_sq = st.selectbox("🔍 Filtra notizie per squadra:", ["Tutte le squadre"] + squadre_con_notizie)
        st.write("") # Spazio estetico
        
        # 3. Filtriamo la lista delle notizie in base alla scelta
        if filtro_sq != "Tutte le squadre":
            feed_filtrato = [item for item in feed if item['squadra'] == filtro_sq]
        else:
            feed_filtrato = feed

        # 4. Stampiamo il feed
        if not feed_filtrato:
            st.info(f"Nessuna operazione registrata per {filtro_sq}.")
        else:
            html_feed = "<div style='background-color: white; border-radius: 8px; padding: 20px; border: 1px solid #E2E8F0; box-shadow: 0 2px 4px rgba(0,0,0,0.02);'>"
            
            for item in feed_filtrato:
                # Converte gli ** in grassetto HTML
                testo_formattato = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', item['testo'])
                
                # Niente spazi segreti usando le parentesi!
                html_feed += (
                    "<div style='margin-bottom: 12px;'>"
                    f"<span style='color: #94A3B8; font-size: 11px; text-transform: uppercase;'>🕒 {item['data']}</span><br>"
                    f"<span style='font-size: 16px;'>{item['icona']} <strong style='color: #1E293B;'>{item['squadra']}</strong> {testo_formattato}</span>"
                    "</div>"
                    "<hr style='margin: 12px 0; border: none; border-top: 1px solid #F1F5F9;'>"
                )
            
            html_feed += "</div>"
            st.markdown(html_feed, unsafe_allow_html=True)

# ==========================================
# 10. REGOLAMENTO UFFICIALE
# ==========================================
elif menu == "10. Regolamento Ufficiale":
    st.title("⚽ Osei Football League")
    st.header("Regolamento Ufficiale Manageriale")
    st.caption("A cura della Direzione Osei")
    st.divider()

    # SECTION 1
    st.subheader("1. Disposizioni Generali e Principi Contabili")
    st.markdown("""
    Il presente regolamento disciplina l'organizzazione e la gestione sportivo-finanziaria delle società appartenenti alla Osei Football League. Il sistema manageriale impone il rigoroso rispetto dei vincoli economici, strutturati sulla netta separazione tra due principi contabili fondamentali:

    * **La Liquidità (Cassa):** Rappresenta il capitale circolante a disposizione della società per effettuare transazioni immediate. Le variazioni di liquidità si registrano contestualmente al momento dell'esborso o dell'incasso reale. I fondi in cassa non si azzerano mai a fine anno.
    * **Il Bilancio d'Esercizio:** Rappresenta il documento contabile di fine stagione che riepiloga i Costi e i Ricavi imputabili al singolo anno sportivo, al fine di determinare il risultato d'esercizio (Utile o Perdita) e valutare il rispetto del Fair Play Finanziario. Il Bilancio viene azzerato al termine di ogni stagione sportiva.
    
    ### 1.1 Capitale Sociale Iniziale
    All'atto della costituzione delle società sportive, la Direzione provvede all'assegnazione di un fondo iniziale pari a **500 milioni di fantaeuro** per ciascuna società. Tale somma costituisce la Liquidità (Cassa) di partenza per le operazioni di mercato della prima finestra estiva. 
    """)
    st.info("**Nota:** Al fine di non alterare i parametri del Fair Play Finanziario, tale somma iniziale transita **esclusivamente nella Cassa reale** e non concorre in alcun modo a formare il Valore della Produzione (Ricavi) del primo Bilancio d'Esercizio.")

    st.divider()
    
    # SECTION 2
    st.subheader("2. Infrastrutture e Sponsorizzazioni Commerciali")
    st.markdown("""
    All'apertura di ogni stagione, le società devono strutturare le proprie fondamenta commerciali scegliendo l'impianto sportivo e registrando il Main Sponsor.
    
    ### 2.1 Impianti Sportivi
    Ciascuna società ha l'obbligo di selezionare la capienza del proprio impianto sportivo. Da tale scelta derivano specifici oneri fissi di gestione (da imputare in Cassa e nei Costi di Bilancio) e proventi legati ai risultati delle partite disputate in casa (da imputare in Cassa e nei Ricavi di Bilancio):
    * **Impianto di 1ª Categoria (20.000 posti):**
      * Costo fisso annuo: **7 milioni**
      * Incasso base per partita: **0.2 milioni**
      * Incasso totale in caso di pareggio: **0.3 milioni**
      * Incasso totale in caso di vittoria: **0.6 milioni**
    * **Impianto di 2ª Categoria (50.000 posti):**
      * Costo fisso annuo: **17 milioni**
      * Incasso base per partita: **0.4 milioni**
      * Incasso totale in caso di pareggio: **0.7 milioni**
      * Incasso totale in caso di vittoria: **1.3 milioni**
    * **Impianto di 3ª Categoria (80.000 posti):**
      * Costo fisso annuo: **28 milioni**
      * Incasso base per partita: **0.8 milioni**
      * Incasso totale in caso di pareggio: **1.4 milioni**
      * Incasso totale in caso di vittoria: **2.1 milioni**

    💡 **Nota bene:** Il costo fisso annuo dell'impianto sportivo viene prelevato **immediatamente** dalla Liquidità (Cassa) all'atto della firma del contratto, prima ancora di iniziare il calciomercato.
    
    ### 2.2 Sponsorizzazioni Commerciali
    Ciascuna società ha diritto alla sottoscrizione di un accordo di Main Sponsorship. Per la prima stagione di fondazione della Lega, al fine di garantire l'operatività e la sostenibilità iniziale, tutte le società percepiscono una quota fissa d'ingresso pari a **40 milioni**. 

    A partire dalla seconda stagione, l'importo erogato dallo sponsor all'inizio di ogni anno sportivo è calcolato esclusivamente in base al piazzamento ottenuto nella classifica generale della stagione antecedente:
    * **1ª Classificata:** 70 milioni
    * **2ª Classificata:** 65 milioni
    * **3ª Classificata:** 60 milioni
    * **4ª Classificata:** 55 milioni
    * **5ª Classificata:** 50 milioni
    * **6ª Classificata:** 45 milioni
    * **7ª Classificata:** 42 milioni
    * **8ª Classificata:** 40 milioni

    Tali somme di denaro generano un flusso positivo di Cassa e vanno registrate nei Ricavi di Bilancio.
    """)

    st.divider()

    # SECTION 3
    st.subheader("3. Gestione Sportiva: Composizione della Rosa e Contratti")
    st.markdown("""
    ### 3.1 Limiti e Composizione della Rosa
    Le società hanno la facoltà di tesserare un numero illimitato di calciatori (tra acquisti a titolo definitivo e trasferimenti temporanei), purché nel rigoroso rispetto dei vincoli economici e del Fair Play Finanziario imposti a Bilancio. 

    Tuttavia, per partecipare alle competizioni ufficiali (Campionato e Coppe), ogni allenatore ha l'obbligo di comunicare alla Direzione una lista inderogabile di **25 calciatori convocabili** per l'intera durata della stagione. 
    La ripartizione per ruoli all'interno dei 25 scelti è vincolante ed è fissata a: **3 portieri, 8 difensori, 8 centrocampisti e 6 attaccanti**. I calciatori di proprietà non inseriti in questa speciale lista dei 25 restano a tutti gli effetti a libro paga della società (generando regolarmente oneri di stipendio e ammortamento), ma non potranno prendere parte ad alcuna gara ufficiale.

    ### 3.2 Vincoli Contrattuali e Compensi
    L'acquisizione di un calciatore comporta la contestuale stipula di un contratto di prestazione sportiva di durata compresa tra 1 e 5 anni. Tutti i contratti iniziano l'1 Gennaio oppure l'1 Luglio di ogni anno e terminano tutti il 30 Giugno. Il compenso annuale (Stipendio) costituisce un costo d'esercizio ricorrente, ed è parametrato al costo storico del cartellino:
    * Costo d'acquisto da 1 a 15 milioni: Stipendio annuale di **1.0 milioni**
    * Costo d'acquisto da 16 a 45 milioni: Stipendio annuale di **2.5 milioni**
    * Costo d'acquisto da 46 a 85 milioni: Stipendio annuale di **4.5 milioni**
    * Costo d'acquisto da 86 a 130 milioni: Stipendio annuale di **7.0 milioni**
    * Costo d'acquisto da 131 milioni in su: Stipendio annuale di **11.0 milioni**
    
    Eventuali rinnovi contrattuali comportano un adeguamento salariale obbligatorio pari al +15% dello stipendio in essere. **La durata massima consentita per un rinnovo è di 5 anni.** Una volta scaduto il contratto di un giocatore non è più possibile firmare il rinnovo.
    """)

    st.divider()

    # SECTION 4
    st.subheader("4. Operazioni di Mercato e Conseguenze Contabili")
    
    st.markdown("""
    ### 4.1 Acquisizione a Titolo Definitivo di un Calciatore
    L'acquisizione dei diritti alle prestazioni sportive di un calciatore genera i seguenti effetti:
    1. **Sotto il profilo della Liquidità (Cassa):** Il corrispettivo costo d'acquisto viene detratto integralmente e istantaneamente dal saldo della cassa disponibile.
    2. **Sotto il profilo Economico (Bilancio):** Il costo storico non incide interamente sull'esercizio in corso. Ai costi d'esercizio vengono imputati esclusivamente lo Stipendio annuale e la **Quota di Ammortamento** (pari al costo storico diviso per gli anni di contratto stipulati).
    """)
    
    # ESEMPIO 1 HTML
    st.markdown("""
    <div style="border: 1.5px solid #2B6CB0; border-radius: 4px; background-color: #F4F8FC; margin-bottom: 1rem;">
        <div style="background-color: #2B6CB0; color: white; padding: 6px 12px; font-weight: bold; border-top-left-radius: 2px; border-top-right-radius: 2px;">
            Esempio Pratico: Acquisizione
        </div>
        <div style="padding: 12px; color: #1F2937;">
            La società si aggiudica il <em>Calciatore X</em> per <strong>40 milioni</strong>, siglando un contratto quadriennale (4 anni).
            <ul style="margin-bottom: 0; padding-top: 8px;">
                <li><strong>Impatto sulla Cassa:</strong> Decremento immediato di 40 milioni.</li>
                <li><strong>Impatto a Bilancio (per ogni anno):</strong> Iscrizione nei Costi di <strong>10 milioni</strong> di ammortamento (40 / 4) e di <strong>3.0 milioni</strong> di stipendio.</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    ### 4.2 Acquisti in Sessione Invernale (Gennaio)
    Le operazioni di mercato concluse durante la sessione di Gennaio sono soggette a un trattamento contabile specifico, volto a riflettere l'utilizzo del calciatore per il solo girone di ritorno (6 mesi).
    
    1. **Durata Contrattuale:** Al fine di garantire la naturale scadenza dei contratti al 30 giugno, la durata sottoscritta in fase di acquisto viene decurtata di 0.5 stagioni. (Esempio: un contratto stipulato per 2 anni durante la sessione invernale ha una durata effettiva di 1.5 stagioni).
    2. **Impatto a Bilancio:** Per la stagione in corso (sessione invernale), l'ammortamento del cartellino e lo stipendio lordo vengono calcolati al 50% del valore annuale, riflettendo la maturazione economica dei costi per il solo semestre di competenza.    
    3. **Valore Residuo e Invecchiamento:** Il Valore Residuo a bilancio viene aggiornato sottraendo esclusivamente la quota di ammortamento maturata nel semestre di permanenza. Inoltre, alla prima Chiusura Fiscale estiva successiva all'acquisto, l'età contrattuale del calciatore (anni trascorsi) avanzerà matematicamente di sole 0.5 stagioni, allineandosi perfettamente alla nuova annata sportiva.
    """)
    
    # ESEMPIO 2 HTML
    st.markdown("""
    <div style="border: 1.5px solid #2B6CB0; border-radius: 4px; background-color: #F4F8FC; margin-bottom: 1rem;">
        <div style="background-color: #2B6CB0; color: white; padding: 6px 12px; font-weight: bold; border-top-left-radius: 2px; border-top-right-radius: 2px;">
            Esempio Pratico: Acquisto in sessione invernale
        </div>
        <div style="padding: 12px; color: #1F2937;">
            La società si aggiudica il <em>Calciatore X</em> per <strong>25 milioni</strong>, siglando un contratto triennale (2.5 anni nella realtà).
            <ul style="margin-bottom: 0; padding-top: 8px;">
                <li><strong>Impatto sulla Cassa:</strong> Decremento immediato di 25 milioni.</li>
                <li><strong>Impatto a Bilancio (primo anno):</strong> Iscrizione nei Costi di <strong>5 milioni</strong> di ammortamento (25 / 5) e di <strong>1.25 milioni</strong> di stipendio.</li>
                <li><strong>Impatto a Bilancio (anni successivi):</strong> Iscrizione nei Costi di <strong>10 milioni</strong> di ammortamento e di <strong>2.5 milioni</strong> di stipendio.</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    ### 4.3 Cessione a Titolo Definitivo e Rilevazione di Plusvalenze/Minusvalenze
    Il **Valore Residuo** di un calciatore è il valore patrimoniale netto del cartellino, calcolato sottraendo dal costo storico gli ammortamenti già contabilizzati negli esercizi precedenti. La cessione di un tesserato genera:
    1. **Sotto il profilo della Liquidità (Cassa):** Accredito istantaneo del corrispettivo pattuito per la vendita.
    2. **Sotto il profilo Economico (Bilancio):** L'interruzione degli oneri futuri (ammortamento e stipendio non ancora maturati) e la rilevazione nel Bilancio dell'anno in corso di una **Plusvalenza** (se il prezzo di vendita è superiore al Valore Residuo) o di una **Minusvalenza** (se il prezzo di vendita è inferiore al Valore Residuo), rispettivamente nei Ricavi o nei Costi.
    """)
    
    # ESEMPIO 3 HTML
    st.markdown("""
    <div style="border: 1.5px solid #2B6CB0; border-radius: 4px; background-color: #F4F8FC; margin-bottom: 1rem;">
        <div style="background-color: #2B6CB0; color: white; padding: 6px 12px; font-weight: bold; border-top-left-radius: 2px; border-top-right-radius: 2px;">
            Esempio Pratico: Cessione
        </div>
        <div style="padding: 12px; color: #1F2937;">
            Il <em>Calciatore X</em> (costo storico 40M per 4 anni) è ceduto al termine del secondo anno. L'ammortamento cumulato è pari a 20M. Il suo <strong>Valore Residuo è pari a 20 milioni</strong>. La cessione avviene per <strong>35 milioni</strong>.
            <ul style="margin-bottom: 0; padding-top: 8px;">
                <li><strong>Impatto sulla Cassa:</strong> Incremento immediato di 35 milioni.</li>
                <li><strong>Impatto a Bilancio:</strong> Iscrizione nei Ricavi di una <strong>Plusvalenza pari a 15 milioni</strong> (35 - 20). Annullamento degli oneri per gli esercizi futuri.</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    **Cessioni a Gennaio:** In caso di cessione di un calciatore a Gennaio, la società cedente ha l'obbligo di iscrivere a bilancio la quota di ammortamento e lo stipendio relativi al semestre di permanenza (luglio-dicembre), garantendo così che la società sostenga i costi solo per il periodo in cui ha effettivamente utilizzato il calciatore.
    
    **Vincolo per Cessioni di giocatori in prestito:** Non è assolutamente consentito vendere a titolo definitivo o inserire in scambi di mercato un calciatore che si trova attualmente ceduto in prestito presso un'altra società. È necessario prima accordarsi con la controparte per l'interruzione anticipata del prestito e richiamare il giocatore nella rosa attiva.
    
    ### 4.4 Scambi di Giocatori tra Società
    Nel sistema manageriale, lo scambio puro di giocatori senza transazione economica non è contemplato. Le due società sono obbligate a dichiarare come prezzo di vendita l'**esatto Valore Residuo** del proprio giocatore. In questo modo non verranno generate plusvalenze o minusvalenze, e l'eventuale differenza tra i due valori si tradurrà automaticamente in un conguaglio economico in Cassa a favore di chi cede il giocatore col valore residuo più alto.
    
    ### 4.5 Trasferimenti a Titolo Temporaneo (Prestiti)
    Le società hanno la facoltà di negoziare la cessione a titolo temporaneo dei diritti alle prestazioni sportive di un tesserato per una durata predefinita di **1 o 2 stagioni sportive**. I trasferimenti temporanei possono configurarsi in tre tipologie: **prestito secco**, **prestito con diritto di riscatto** e **prestito con obbligo di riscatto** (subordinato o meno al verificarsi di determinate condizioni sportive).
    
    **Regola UEFA per la Cessione in Prestito (Scadenza Contratto):** Al fine di evitare lo svincolo a parametro zero durante il periodo di lontananza, è severamente vietato cedere in prestito un calciatore la cui durata contrattuale residua sia inferiore o uguale alla durata del prestito stesso. Per ufficializzare l'operazione, il calciatore deve avere almeno un anno di contratto in più rispetto alla durata del prestito (es. per un prestito di 1 anno, il contratto residuo deve essere di minimo 2 anni). In caso contrario, la società madre ha l'obbligo di rinnovargli il contratto prima di cederlo.
    
    **Prestito Oneroso e Impatto Contabile Immediato:** Le società possono pattuire un corrispettivo in denaro per l'affitto temporaneo del tesserato (Prestito Oneroso). L'eventuale onere pattuito genera un impatto istantaneo:
    * **Cassa:** L'importo viene detratto immediatamente dalla Liquidità della società acquirente e versato sul conto della società cedente.
    * **Bilancio:** Al fine di garantire il Fair Play dell'esercizio in corso, l'importo costituisce per la società cedente una **Plusvalenza** da iscrivere nei Ricavi, e per la società acquirente una **Minusvalenza** (costo di locazione) da iscrivere negli Oneri d'esercizio.
    
    *Nota bene:* In caso di interruzione anticipata del prestito oneroso, la quota iniziale versata a titolo di locazione non è soggetta ad alcun rimborso parziale o totale.
    
    **Ammortamenti, Oneri Salariali e Rappresentazione in Rosa:** La stipula di un trasferimento a titolo temporaneo genera i seguenti effetti contabili continuativi per l'intera durata dell'accordo:
    * **Quote di Ammortamento:** L'onere dell'ammortamento annuale rimane **integralmente a carico della società cedente** (proprietaria del cartellino), la quale continuerà a dedurlo regolarmente nel proprio Bilancio.
    * **Oneri Salariali (Stipendio):** La ripartizione del compenso annuale è soggetta a **libera contrattazione** tra le parti. Le società possono concordare qualsivoglia ripartizione percentuale (es. 50% e 50%, 100% a carico della cessionaria, 100% a carico della cedente). Le quote proporzionali così pattuite andranno obbligatoriamente iscritte alla voce "Monte Ingaggi" dei rispettivi Bilanci d'Esercizio.
    * **Rappresentazione per la società acquirente:** Nel gestionale, la squadra che acquisisce il tesserato in prestito lo vedrà iscritto nella propria rosa attiva con un costo d'acquisto figurativo recante la dicitura "Prestito", ammortamento pari a zero, e alla voce stipendio riporterà unicamente l'importo relativo alla quota percentuale pattuita a proprio carico.
    * **Prestito nella Sessione Invernale:** In caso di prestito stipulato nella sessione di Gennaio con condivisione dell'ingaggio, la quota di stipendio a carico della squadra acquirente viene calcolata solo sulla frazione di stagione rimanente (6 mesi). Se la durata del prestito è superiore all'anno, nella stagione sportiva successiva la quota di stipendio a carico dell'acquirente verrà ripristinata e calcolata sull'intero importo del compenso annuale.
    
    **Risoluzione Anticipata del Prestito:** Le due società coinvolte possono accordarsi in qualsiasi momento per l'interruzione anticipata del prestito e il calciatore farà rientro immediato nella rosa attiva della società madre. La risoluzione anticipata annulla in automatico qualsiasi precedente accordo relativo a diritti o obblighi di riscatto.
    
    **Esercizio del Riscatto:** Al fine di preservare l'integrità del Fair Play Finanziario per l'esercizio in corso, l'esercizio dei diritti e obblighi di riscatto agiscono in veste di **pre-accordi vincolanti (Prenotazioni)**. 
    
    La formalizzazione del riscatto non produce alcun effetto immediato sulla Liquidità corrente o sul Bilancio dell'anno in corso. L'esecuzione materiale e contabile, ovvero il transito del denaro in Cassa e il calcolo delle Plusvalenze/Minusvalenze da riscatto, viene posticipata e resa effettiva esclusivamente all'atto della Chiusura Fiscale di fine stagione, ricadendo di fatto quale prima operazione d'apertura del Bilancio della stagione successiva.
    
    Qualora venga esercitato il diritto di riscatto, o al maturare delle condizioni per l'obbligo di riscatto, l'operazione si converte in una **Cessione a Titolo Definitivo** a tutti gli effetti legali e contabili. A far data dall'effettiva esecuzione contabile del riscatto:
    1. La società cedente incassa il corrispettivo pattuito nella Liquidità e calcola l'eventuale Plusvalenza o Minusvalenza, confrontando il prezzo di riscatto con il Valore Residuo del tesserato in quel preciso momento patrimoniale.
    2. La società acquirente detrae l'importo dalla propria Liquidità, subentra nella titolarità del cartellino assumendosi il 100% degli oneri salariali futuri e avvia un nuovo piano di ammortamento basato sul costo del riscatto e sulla durata del nuovo contratto stipulato.
    
    ### 4.6 Risoluzione Anticipata e Scadenza Naturale del Contratto
    L'interruzione anticipata del vincolo contrattuale (svincolo) determina l'azzeramento del valore patrimoniale del calciatore.
    * **Impatto sulla Cassa:** Nessun introito (variazione nulla).
    * **Impatto a Bilancio:** Iscrizione nei Costi d'esercizio di una **Minusvalenza totale**, di importo pari all'intero Valore Residuo del tesserato al momento dello svincolo. Come per le cessioni, lo svincolo in sessione invernale di un giocatore appena acquistato o rinnovato prenderà in esame il Valore Residuo intatto per il calcolo della minusvalenza (anti-doppia decurtazione).
    
    Analogamente alle cessioni, non è consentito svincolare un giocatore qualora questi si trovi in prestito.
    
    **Scadenza Naturale del Vincolo (Parametro Zero):** Al termine della durata contrattuale pattuita, qualora non sia intervenuto alcun accordo di rinnovo, il vincolo sportivo decade in via automatica all'atto della Chiusura Fiscale di fine stagione. Il calciatore viene rimosso dalla rosa a parametro zero. Tale evento **non genera alcuna minusvalenza**, in quanto l'ammortamento del costo storico è giunto a naturale esaurimento (il Valore Residuo è pari a zero). La società beneficerà unicamente dello sgravio a bilancio del relativo onere salariale (stipendio) per gli esercizi futuri.
    
    ### 4.7 Rinnovo Contrattuale e Rimodulazione dell'Ammortamento
    Le società hanno la facoltà di prolungare il contratto di un proprio tesserato. Tuttavia, ci sono dei vincoli che ogni società deve rispettare:
    * Non è consentito rinnovare il contratto di un giocatore nella stessa sessione di mercato in cui è stato acquistato.
    * Non è consentito rinnovare il contratto di un giocatore il cui contratto ha ancora una durata superiore ai 2 anni (il rinnovo è permesso solo in presenza di 1 o 2 anni residui).
    * Non è consentito rinnovare il contratto di un giocatore mentre quest'ultimo si trova in prestito presso un'altra società.
    
    Anche un giocatore acquistato nella sessione estiva con un contratto di 1 anno, non potrà essere rinnovato immediatamente: la società potrà proporre un rinnovo contrattuale solo all'apertura della successiva sessione Invernale.
    
    Il rinnovo non "somma" anni al vecchio contratto, bensì lo sovrascrive, per un prolungamento **massimo di 5 anni**. Come accade per gli acquisti, anche per i rinnovi stipulati nella sessione invernale la durata effettiva del nuovo contratto viene decurtata di 0.5 stagioni.
    
    La sottoscrizione di un rinnovo produce due effetti contabili sul Bilancio d'Esercizio, ma con differenti logiche in base alle sessione (estiva o invernale):
    1. **Rinnovo Estivo:** Lo stipendio annuale subisce un incremento obbligatorio del +15%. Il Valore Residuo attuale viene "spalmato" sui nuovi anni scelti, abbassando istantaneamente la Quota di Ammortamento annuale e fornendo un utile strumento per alleggerire il Bilancio della stagione in corso.
    2. **Rinnovo Invernale:** Il gestionale applicherà un esatto calcolo Pro-Quota (50 e 50) sul bilancio dell'anno in corso. Per la stagione corrente, la società pagherà un ammortamento e uno stipendio calcolati sommando metà del vecchio contratto maturato (da Luglio a Dicembre) e metà del nuovo contratto stipulato (da Gennaio a Giugno). Dall'anno fiscale successivo, i valori del nuovo contratto entreranno a regime al 100%. *Nota bene:* alla prima Chiusura Fiscale successiva al rinnovo invernale, il contratto avanzerà (invecchierà) di sole 0.5 stagioni.
    """)
    
    # ESEMPIO 4 HTML
    st.markdown("""
    <div style="border: 1.5px solid #2B6CB0; border-radius: 4px; background-color: #F4F8FC; margin-bottom: 1rem;">
        <div style="background-color: #2B6CB0; color: white; padding: 6px 12px; font-weight: bold; border-top-left-radius: 2px; border-top-right-radius: 2px;">
            Esempio Pratico: Rinnovo Contrattuale
        </div>
        <div style="padding: 12px; color: #1F2937;">
            Il <em>Calciatore X</em> percepisce uno stipendio di 1.5M e ha un Valore Residuo di <strong>15 milioni</strong>. La società decide di rinnovare il contratto per ulteriori <strong>3 anni</strong>.
            <ul style="margin-bottom: 0; padding-top: 8px;">
                <li><strong>Nuovo Stipendio:</strong> Incremento del 15% su 1.5M &rarr; Nuovo stipendio pari a <strong>1.725 milioni</strong> annui.</li>
                <li><strong>Nuovo Ammortamento:</strong> I 15 milioni di Valore Residuo vengono divisi per i 3 nuovi anni &rarr; Nuova quota di ammortamento pari a <strong>5 milioni</strong> annui.</li>
                <li><strong>Impatto a Bilancio:</strong> A fronte di un lieve aumento del monte ingaggi, la società abbassa notevolmente i costi di ammortamento correnti, alleggerendo il bilancio ed evitando minusvalenze future.</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # SECTION 5
    st.subheader("5. Competizioni Ufficiali e Premi Sportivi")
    st.markdown("""
    Al termine della stagione sportiva, la Direzione provvede all'erogazione dei corrispettivi in denaro maturati in base ai risultati conseguiti nelle tre competizioni ufficiali previste dal calendario. Tali somme vengono erogate istantaneamente nella Cassa e contribuiscono ad accrescere la voce "Premi Sportivi" nel Bilancio d'Esercizio in vista della chiusura fiscale.

    ### 5.1 Campionato di Lega
    Al fine di garantire la competitività, l'equilibrio della Lega nel lungo periodo e agevolare la ricostruzione finanziaria, l'ammontare dei premi di Campionato è distribuito seguendo un criterio che privilegia i posizionamenti inferiori:
    * **1ª Classificata:** 50 milioni
    * **2ª Classificata:** 52 milioni
    * **3ª Classificata:** 55 milioni
    * **4ª Classificata:** 58 milioni
    * **5ª Classificata:** 62 milioni
    * **6ª Classificata:** 65 milioni
    * **7ª Classificata:** 68 milioni
    * **8ª Classificata:** 70 milioni
    
    ### 5.2 Coppa Italia
    La Coppa Italia si articola in tre turni a eliminazione diretta, disputati interamente in **gara secca**.
    
    **Calendario Ufficiale:**
    * **Quarti di Finale:** 15ª Giornata di Campionato
    * **Semifinali:** 25ª Giornata di Campionato
    * **Finale:** 35ª Giornata di Campionato
    
    **Proventi Sportivi:**
    * **1ª Classificata (Vincitrice):** 35 milioni
    * **2ª Classificata (Finalista):** 20 milioni
    * **3ª e 4ª Classificata (Semifinaliste):** 10 milioni

    ### 5.3 Champions League
    La Champions League si struttura in una fase iniziale composta da **due gironi all'italiana da 4 squadre** (con incontri di andata e ritorno), seguita da Semifinali (con incontri di andata e ritorno) e da una Finale in gara secca in campo neutro.
    
    **Calendario Ufficiale:**
    * **Fase a Gironi (Andata e Ritorno):** 4ª, 8ª, 12ª, 16ª, 20ª e 24ª Giornata di Campionato
    * **Semifinali (Andata e Ritorno):** 28ª e 32ª Giornata di Campionato
    * **Finale:** 36ª Giornata di Campionato
    
    **Proventi Sportivi (Meritocratici):**
    * **1ª Classificata (Vincitrice):** 50 milioni
    * **2ª Classificata (Finalista):** 35 milioni
    * **3ª e 4ª Classificata (Semifinaliste):** 20 milioni
    """)

    st.divider()

    # SECTION 6
    st.subheader("6. Redazione e Chiusura del Bilancio d'Esercizio")
    st.markdown("""
    Al termine di ciascuna stagione sportiva, prima dell'avvio della sessione di mercato estiva successiva, le società hanno l'obbligo di redigere il Bilancio d'Esercizio, determinando il differenziale tra il Valore della Produzione e i Costi della Produzione. Questo è l'atto formale che chiude l'anno sportivo.
    
    ### 6.1 Valore della Produzione (Ricavi d'Esercizio)
    Concorrono alla formazione dei ricavi le seguenti voci:
    * **Premi Sportivi:** Introiti accreditati a bilancio a seguito dei piazzamenti finali nelle competizioni ufficiali.
    * **Proventi da Sponsorizzazione:** Quota erogata all'apertura dell'esercizio (pari a 40 milioni fissi per tutti durante la prima stagione sportiva di fondazione; dalla seconda stagione in poi, determinata con criterio meritocratico in base alla classifica finale dell'anno precedente).
    * **Proventi da Stadio:** Somma matematica dei ricavi lordi per singola partita disputata nell'impianto di proprietà.
    * **Plusvalenze Patrimoniali:** Utili generati dalla cessione dei diritti sulle prestazioni sportive.
    * **Nuovo Capitale:** Iniezione di liquidità garantita dalla Lega (pari a 70 milioni) iscritta a Bilancio all'apertura di ogni nuovo esercizio contabile **(esclusivamente a partire dalla seconda stagione)**.

    ### 6.2 Costi della Produzione (Oneri d'Esercizio)
    Concorrono alla formazione dei costi le seguenti voci:
    * **Quote di Ammortamento:** Somma delle quote di competenza per l'esercizio in corso di tutti i tesserati (inclusi i giocatori ceduti in prestito temporaneo).
    * **Monte Ingaggi:** Ammontare complessivo delle retribuzioni fisse spettanti ai tesserati nell'esercizio in corso, al netto delle decurtazioni per i tesserati in prestito.
    * **Oneri di Gestione Infrastrutture:** Costi di mantenimento e operatività dell'impianto sportivo.
    * **Minusvalenze Patrimoniali:** Perdite d'esercizio generate da svincoli o cessioni sotto il Valore Residuo.

    ### 6.3 Determinazione del Risultato d'Esercizio
    Il risultato d'esercizio si determina sottraendo il totale dei Costi della Produzione dal totale del Valore della Produzione (Ricavi - Costi).

    ### 6.4 Flussi di Cassa e Ripianamento Perdite (Fair Play Finanziario)
    Al termine della stagione sportiva, all'atto formale della Chiusura Fiscale, il gestionale applica una procedura automatica e sequenziale in 4 fasi per riconciliare la Cassa reale con il Bilancio d'Esercizio:
    
    1. **Pagamento degli Oneri Correnti:** Viene materialmente prelevato dalla Cassa il fondo necessario al pagamento fisico degli stipendi maturati nell'anno (Monte Ingaggi). *Nota: I costi di gestione dello Stadio non vengono prelevati in questa fase in quanto già saldati anticipatamente all'apertura della stagione.*
    2. **Verifica del Fair Play Finanziario:** Viene calcolato il Risultato d'Esercizio del Bilancio (Ricavi - Costi).
       * 🟢 **Risultato Positivo (Utile d'Esercizio):** La società ha rispettato i parametri economici. Non avviene alcuna sanzione.
       * 🔴 **Risultato Negativo (Perdita d'Esercizio):** La società ha violato i parametri UEFA. Il deficit di bilancio fa scattare in automatico una **multa**. Il sistema preleverà dalla cassa una penale pari al **15% dell'intera perdita registrata**, riducendo di fatto la liquidità disponibile per la stagione successiva.
    3. **Azzeramento Bilancio:** Il documento contabile viene salvato in archivio e azzerato, tornando a un saldo di 0 per preparare la nuova stagione sportiva. Vengono contestualmente resi effettivi i riscatti, i rinnovi prenotati e gli svincoli a parametro zero.
    4. **Apertura del Nuovo Esercizio e Iniezioni di Capitale:** (Fase attiva a partire dalla seconda stagione). Il sistema provvede a immettere **nuova liquidità in Cassa**: accredita istantaneamente i **70 milioni** del nuovo capitale, unitamente ai **Proventi dello Sponsor** maturati grazie alla classifica dell'anno appena concluso. Le stesse identiche voci vengono iscritte nei nuovi Ricavi a Bilancio, fornendo alle società la base operativa su cui fondare il mercato della nuova stagione.
    """)