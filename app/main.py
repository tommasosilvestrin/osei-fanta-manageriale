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
    
    if not isinstance(feed, list):
        feed = []
        
    orario = (datetime.utcnow() + timedelta(hours=2)).strftime("%d/%m %H:%M")    
    
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
        "ricavi": {"nuovo_capitale": 0.0, 
                   "premi_sportivi": 0.0,
                   "sponsor": 0.0,
                   # "incassi_stadio": 0.0,
                   "plusvalenze": 0.0},
        "costi": {"ammortamenti": 0.0,
                  "monte_ingaggi": 0.0,
                  # "gestione_stadio": 0.0,
                  "minusvalenze": 0.0,
                  "costi_giocatori_ceduti": 0.0},
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

def verifica_obiettivi_dinamici():
    # 1. Calcola vittorie e gol attuali
    standings_temp = {s: {"V": 0, "GF": 0} for s in db.keys()}
    if calendario:
        for md in calendario:
            for m in md:
                if m.get("giocata"):
                    gh, ga = m["gol_home"], m["gol_away"]
                    standings_temp[m["home"]]["GF"] += gh
                    standings_temp[m["away"]]["GF"] += ga
                    if gh > ga: standings_temp[m["home"]]["V"] += 1
                    elif ga > gh: standings_temp[m["away"]]["V"] += 1
                
    # 2. Raccoglie chi è in finale e chi ha vinto le coppe
    finalisti = []
    vincitori_coppe = []
    
    if coppe.get("ci", {}).get("semis_salvate"):
        finalisti.extend([m.get("vincente") for m in coppe["ci"]["semis"] if m.get("vincente")])
    if coppe.get("ci", {}).get("finale_salvata"):
        vincitori_coppe.append(coppe["ci"]["finale"][0].get("vincente"))
        
    if coppe.get("cl", {}).get("semis_salvate"):
        finalisti.extend([m.get("vincente") for m in coppe["cl"]["semis_ritorno"] if m.get("vincente")])
    if coppe.get("cl", {}).get("finale_salvata"):
        vincitori_coppe.append(coppe["cl"]["finale"][0].get("vincente"))

    # 3. Controlla e Paga all'istante
    for sq, dati in db.items():
        obs = dati.get("sponsor", {}).get("obiettivi", {})
        if not obs: continue
        
        pagati = dati["sponsor"].setdefault("obiettivi_pagati", [])
        v = standings_temp[sq]["V"]
        gf = standings_temp[sq]["GF"]
        
        for cat, premio in [("bronzo", 8.0), ("argento", 15.0), ("oro", 30.0)]:
            ob = obs.get(cat, "")
            # Se la casella è vuota o se i soldi sono GIÀ STATI PRESI, skippa!
            if not ob or ob in pagati: continue
            
            sbloccato = False
            # OBIETTIVI A TRAGUARDO (Gol, Vittorie, Coppe)
            if "5 vittorie" in ob and v >= 5: sbloccato = True
            elif "8 vittorie" in ob and v >= 8: sbloccato = True
            elif "12 vittorie" in ob and v >= 12: sbloccato = True
            elif "20 vittorie" in ob and v >= 20: sbloccato = True
            elif "25 gol" in ob and gf >= 25: sbloccato = True
            elif "35 gol" in ob and gf >= 35: sbloccato = True
            elif "Finale" in ob and sq in finalisti: sbloccato = True
            elif "Vinci una Coppa" in ob and sq in vincitori_coppe: sbloccato = True
            
            if sbloccato:
                dati['cassa'] = round(dati['cassa'] + premio, 2)
                dati['bilancio']['ricavi']['sponsor'] += premio
                dati['bilancio']['storico_movimenti'].append(f"Bonus Sponsor Immediato ({ob}): +{premio}M")
                pagati.append(ob) # Lo segna come pagato!
                log_evento(sq, "🎯", f"ha sbloccato in anticipo l'obiettivo stagionale **{ob}** incassando subito **{premio} M**!")
                
    save_data(db, DB_PATH)

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
    "9. Cronologia Ufficialità"
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

# Scarica il CALENDARIO
if menu in ["5. Calendario & Partite", "6. Classifica Campionato", "8. Chiusura Fiscale Bilancio"]:
    calendario = load_data(CAL_PATH)

# Scarica le COPPE
if menu in ["5. Calendario & Partite", "7. Coppe (Italia & CL)", "8. Chiusura Fiscale Bilancio"]:
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
        st.error("🔒 Accesso riservato. Solo l'Amministratore della Lega può effettuare operazioni di sistema.")
    else:
        with st.form("crea_squadra"):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome Squadra")
            mister = c2.text_input("Presidente")
            if st.form_submit_button("Iscrivi Squadra (Fondo 500M)"):
                if nome and mister and nome not in db:
                    db[nome] = {
                        "allenatore": mister, "cassa": 500.0,
                        # "stadio": {"livello": None, "costo_annuo": 0, "base": 0, "pari": 0, "vittoria": 0},
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
            
            # col1, col2 = st.columns(2)
            
            # with col1:
            #     st.subheader("Stadio")
            #     # CONTROLLO: Se lo stadio è già stato scelto, nasconde il menu e mostra l'info
            #     if sq_dati["stadio"].get("livello"):
            #         st.info(f"✅ **Stadio Confermato:** Impianto da {sq_dati['stadio']['livello']} posti.")
            #     else:
            #         stadi = {
            #             "Categoria 1 (20.000 posti) - 7M Costo": {"livello": "20k", "costo": 7.0, "base": 0.2, "pari": 0.3, "vittoria": 0.6},
            #             "Categoria 2 (50.000 posti) - 17M Costo": {"livello": "50k", "costo": 17.0, "base": 0.4, "pari": 0.7, "vittoria": 1.3},
            #             "Categoria 3 (80.000 posti) - 28M Costo": {"livello": "80k", "costo": 28.0, "base": 0.8, "pari": 1.4, "vittoria": 2.1}
            #         }
            #         scelta = st.selectbox("Livello Stadio", list(stadi.keys()))
            #         if st.button("Firma Contratto Stadio"):
            #             costo_nuovo = stadi[scelta]["costo"]
            #             costo_vecchio = sq_dati["bilancio"]["costi"]["gestione_stadio"]
                        
            #             # Rimborsa l'eventuale stadio vecchio (se sta cambiando idea) e addebita il nuovo
            #             sq_dati["cassa"] = round(sq_dati["cassa"] + costo_vecchio - costo_nuovo, 2)
                        
            #             sq_dati["stadio"] = stadi[scelta]
            #             sq_dati["bilancio"]["costi"]["gestione_stadio"] = costo_nuovo
                        
            #             if costo_vecchio == 0:
            #                 sq_dati['bilancio']['storico_movimenti'].append(f"Affitto Stadio ({stadi[scelta]['livello']}): -{costo_nuovo}M")
                        
            #             save_data(db, DB_PATH)
            #             log_evento(sq_sel, "🏟️", f"ha ufficializzato il nuovo stadio ({stadi[scelta]['livello']}).")
            #             st.toast(f"Stadio firmato! Pagato l'affitto annuale di {costo_nuovo}M.", icon="🏟️")
            #             st.rerun() # Ricarica istantaneamente la pagina per mostrare il blocco ✅

            # with col2:
            st.subheader("💼 Gestione Sponsor e Obiettivi")

            # Liste degli obiettivi esatti
            ob_bronzo = [
                "1. Non arrivare all'8° posto in campionato", 
                "2. Almeno 8 vittorie in Campionato", 
                "3. Segna almeno 35 gol in Campionato"
            ]
            ob_argento = [
                "1. Arriva tra le prime 4 in campionato", 
                "2. Almeno 12 vittorie in campionato", 
                "3. Raggiungi una Finale (Coppa Italia o Champions League)"
            ]
            ob_oro = [
                "1. Vinci il Campionato", 
                "2. Almeno 20 vittorie in Campionato", 
                "3. Vinci una Coppa (Coppa Italia o Champions League)"
            ]

            # Mappa segreta per far capire al programma la "Famiglia" dell'obiettivo
            tipo_obiettivo = {
                "1. Non arrivare all'8° posto in campionato": "Piazzamento",
                "2. Almeno 8 vittorie in Campionato": "Vittorie",
                "3. Segna almeno 35 gol in Campionato": "Speciali",
                
                "1. Arriva tra le prime 4 in campionato": "Piazzamento",
                "2. Almeno 12 vittorie in campionato": "Vittorie",
                "3. Raggiungi una Finale (Coppa Italia o Champions League)": "Speciali",
                
                "1. Vinci il Campionato": "Piazzamento",
                "2. Almeno 20 vittorie in Campionato": "Vittorie",
                "3. Vinci una Coppa (Coppa Italia o Champions League)": "Speciali"
            }

            # CONTROLLO: Se lo sponsor ha già un nome, nasconde gli input e mostra l'info
            if sq_dati["sponsor"].get("nome"):
                st.info(f"✅ **Sponsor Confermato:** Accordo base di 30M siglato con **{sq_dati['sponsor']['nome']}**.")
                st.write("🎯 **Obiettivi scelti per questa stagione:**")
                st.markdown(f"- 🥉 {sq_dati['sponsor']['obiettivi']['bronzo']} (8M)")
                st.markdown(f"- 🥈 {sq_dati['sponsor']['obiettivi']['argento']} (15M)")
                st.markdown(f"- 🥇 {sq_dati['sponsor']['obiettivi']['oro']} (30M)")
            else:
                with st.container(border=True):
                    st.write("La firma garantisce un introito base di **30 Milioni** istantanei. I premi degli obiettivi verranno erogati a fine anno.")
                    ns = st.text_input("Nome del Main Sponsor")
                    
                    st.write("Scegli un obiettivo per categoria. **Non puoi ripetere la stessa tipologia (Piazzamento, Vittorie, Coppe/Gol)**.")
                    scelta_br = st.selectbox("🥉 Bronzo (8 Milioni)", ob_bronzo)
                    scelta_ar = st.selectbox("🥈 Argento (15 Milioni)", ob_argento)
                    scelta_or = st.selectbox("🥇 Oro (30 Milioni)", ob_oro)
                    
                    # --- CONTROLLO LOGICO SULLE SCELTE ---
                    # Creiamo una lista con le tre "famiglie" scelte dall'utente
                    tipi_selezionati = [tipo_obiettivo[scelta_br], tipo_obiettivo[scelta_ar], tipo_obiettivo[scelta_or]]
                    
                    # Il comando 'set' rimuove i doppioni. Se la lunghezza è < 3, vuol dire che ha ripetuto qualcosa!
                    ha_duplicati = len(set(tipi_selezionati)) < 3
                    
                    if ha_duplicati:
                        st.error("⚠️ **ERRORE:** Hai selezionato più obiettivi della stessa tipologia. Modifica le scelte per poter firmare il contratto.")
                    else:
                        st.success("✅ Obiettivi diversificati correttamente! Il contratto è pronto.")
                    
                    st.divider()
                    
                    # Il bottone viene disattivato (disabled=True) se ci sono duplicati o manca il nome
                    if st.button("Firma Contratto Sponsor", type="primary", disabled=ha_duplicati):
                        if ns.strip():
                            # Salviamo il nome e i 3 obiettivi scelti nel database della squadra
                            sq_dati["sponsor"] = {
                                "nome": ns, 
                                "valore_base": 30.0,
                                "obiettivi": {
                                    "bronzo": scelta_br,
                                    "argento": scelta_ar,
                                    "oro": scelta_or
                                },
                                "obiettivi_pagati": []
                            }
                            
                            # Accredita i 30M fissi se la voce sponsor a bilancio è a zero
                            if sq_dati["bilancio"]["ricavi"]["sponsor"] == 0.0:
                                sq_dati["bilancio"]["ricavi"]["sponsor"] = 30.0
                                sq_dati["cassa"] = round(sq_dati["cassa"] + 30.0, 2)
                                sq_dati['bilancio']['storico_movimenti'].append(f"Base Fissa Sponsor: +30.0M")
                            
                            save_data(db, DB_PATH)
                            log_evento(sq_sel, "💼", f"ha firmato con **{ns}**. Punta all'obiettivo Oro: *{scelta_or.split(' (')[0]}*.")
                            st.toast(f"Sponsor {ns} firmato! 30 Milioni di base accreditati.", icon="💼")
                            st.rerun()
                        else:
                            st.warning("⚠️ Inserisci il nome dello sponsor prima di firmare!")

# ==========================================
# 2. DASHBOARD & ROSA
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
                html_table += "<tr><th>Nome</th><th>Ruolo</th><th>Anni Residui</th><th>Costo Acquisto</th><th>Valore Residuo</th><th>Ammortamento</th><th>Stipendio</th><th>Costo Bilancio</th></tr>"
                
                # Definizione dei colori per i badge
                badge_color = {
                    "Portiere": "background-color: #F59E0B; color: white;",         # Giallo
                    "Difensore": "background-color: #3B82F6; color: white;",        # Blu
                    "Centrocampista": "background-color: #10B981; color: white;",   # Verde
                    "Attaccante": "background-color: #EF4444; color: white;"        # Rosso
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
                    html_table += f"<tr><td><strong>{g['nome']}</strong></td><td>{badge_html}</td><td>{anni_format}</td><td>{g['acquisto']}</td><td><strong>{g['val_res']}</strong></td><td>{g['amm']}</td><td>{g['stip']}</td><td style='color: #EF4444; font-weight: 600;'>{g['costo_totale']}</td></tr>"

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
                html_fuori += "<tr><th>Nome</th><th>Ruolo</th><th>Prestato a</th><th>Anni Residui</th><th>Valore Residuo</th><th>Ammortamento</th><th>Stipendio</th><th>% Stipendio</th></tr>"
                
                for g in giocatori_fuori:
                    perc_pagata_da_loro = g.get('perc_stipendio_pagato', 100)
                    anni_res_fuori = g['anni_contratto'] - g.get('anni_trascorsi', 0)
                    
                    html_fuori += f"<tr><td><strong>{g['nome']}</strong></td><td>{g['ruolo'][:3].upper()}</td><td>{g['prestato_a']}</td><td>{anni_res_fuori}</td><td><strong>{g['valore_residuo']:.2f} M</strong></td><td><span style='color: #EF4444;'>{g['ammortamento_annuo']:.2f} M</span></td><td>{g['stipendio']:.2f} M</td><td><span style='color: #10B981; font-weight: 600;'>{perc_pagata_da_loro}%</span></td></tr>"
                    
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
        if not db: 
            st.warning("Crea una squadra.")
        else:
            # Ordine ruoli fisso per tutti
            ordine_ruoli = {"Portiere": 1, "Difensore": 2, "Centrocampista": 3, "Attaccante": 4}

            t_acq, t_trasf, t_svin, t_rin = st.tabs(["Asta", "Trasferimenti", "Svincola", "Rinnovo"])
            
            # --- TAB 1: ACQUISTA (Dall'asta o svincolati) ---
            with t_acq:
                sq_acq_name = st.selectbox("Seleziona Squadra Acquirente", list(db.keys()), key="tab1_sq")
                sq_acq = db[sq_acq_name]
                st.write(f"💰 **Cassa:** {sq_acq['cassa']:.2f} MLN | 👥 **Rosa:** {len(sq_acq['rosa'])}/25")
                
                with st.container(border=True):
                    sessione_acq = st.radio("Sessione di Mercato", ["☀️ Estiva", "❄️ Invernale"], horizontal=True, key="sess_acq")
                    st.divider()
                    
                    col1, col2, col3 = st.columns(3)
                    n = col1.text_input("Calciatore")
                    r = col2.selectbox("Ruolo", ["Portiere", "Difensore", "Centrocampista", "Attaccante"])
                    c = col3.number_input("Prezzo Acquisto (MLN)", min_value=1.0, step=1.0)
                    anni = st.slider("Anni Contratto", 1, 5, 3)
                    
                    # Calcolo Stipendi
                    s_base = 1.0 if c <= 15 else (2.5 if c <= 45 else (4.5 if c <= 85 else (7.0 if c <= 130 else 11.0)))
                    
                    is_gennaio = True if "Invernale" in sessione_acq else False
                    anni_effettivi = anni - 0.5 if is_gennaio else anni
                    amm = c / anni_effettivi if anni_effettivi > 0 else c
                    
                    if is_gennaio:
                        st.info(f"💡 Durata Effettiva: {anni_effettivi} anni. | Stipendio Annuo Base: {s_base}M | Ammortamento Annuo Base: {amm:.2f}M.\n(Per i 6 mesi correnti pagherai la METÀ: {amm/2:.2f}M di ammortamento e {s_base/2:.2f}M di stipendio).")
                    else:
                        st.info(f"💡 Dati Contratto: Stipendio {s_base}M | Ammortamento {amm:.2f}M annui.")
                    
                    if st.button("Conferma Acquisto da Asta", type="primary"):
                        if c > sq_acq['cassa']: 
                            st.error("Cassa insufficiente!")
                        elif not n:
                            st.warning("Inserisci il nome del calciatore prima di acquistare.")
                        else:
                            giocatore = {"nome": n, "ruolo": r, "costo_acquisto": c, "anni_contratto": anni_effettivi, "stipendio": s_base, "ammortamento_annuo": amm, "anni_trascorsi": 0, "valore_residuo": c, "acquistato_a_gennaio": is_gennaio}
                            sq_acq['rosa'].append(giocatore)
                            sq_acq['cassa'] = round(sq_acq['cassa'] - c, 2)
                            sq_acq['bilancio']['storico_movimenti'].append(f"Acquisto {n}: -{c}M")
                            save_data(db, DB_PATH)
                            log_evento(sq_acq_name, "✍️", f"ha acquistato **{n}** per **{c} M** ({anni_effettivi} anni di contratto).")
                            st.toast(f"Contratto firmato! {n} è un tuo giocatore.", icon="✍️")
                            st.rerun()

            # --- TAB 2: TRASFERIMENTI (Tra società) ---
            with t_trasf:
                if len(db.keys()) < 2:
                    st.warning("⚠️ Servono almeno due squadre per poter effettuare trasferimenti di mercato.")
                else:
                    col_ced, col_comp = st.columns(2)
                    sq_ced_name = col_ced.selectbox("📤 Società Cedente", list(db.keys()), key="tab2_sq_ced")
                    
                    squadre_acquirenti = [s for s in db.keys() if s != sq_ced_name]
                    sq_comp_name = col_comp.selectbox("📥 Società Acquirente", squadre_acquirenti, key="tab2_sq_comp")
                    
                    sq_ced = db[sq_ced_name]
                    sq_comp = db[sq_comp_name]
                    
                    st.write(f"**Cassa {sq_ced_name}:** {sq_ced['cassa']:.2f} MLN &nbsp;&nbsp;|&nbsp;&nbsp; **Cassa {sq_comp_name}:** {sq_comp['cassa']:.2f} MLN")
                    
                    rosa_ordinata_ced = sorted(sq_ced['rosa'], key=lambda x: ordine_ruoli.get(x['ruolo'], 5))
                    
                    if rosa_ordinata_ced:
                        with st.container(border=True):
                            sessione_ven = st.radio("Sessione di Mercato", ["☀️ Estiva", "❄️ Invernale"], horizontal=True, key="sess_ven")
                            st.divider()
                            
                            indice_a = st.selectbox(
                                "Calciatore da Trasferire", 
                                options=range(len(rosa_ordinata_ced)), 
                                format_func=lambda i: f"{rosa_ordinata_ced[i]['nome']} ({rosa_ordinata_ced[i]['ruolo'][:3].upper()})", 
                                key="vendita_idx"
                            )
                            
                            g_obj = rosa_ordinata_ced[indice_a]
                            
                            if g_obj:
                                if g_obj.get("prestato_a"):
                                    st.error(f"❌ Impossibile trasferire. {g_obj['nome']} è attualmente in prestito a {g_obj['prestato_a']}.")
                                elif g_obj.get("in_prestito_da"):
                                    st.error(f"❌ Operazione Illegale. Non puoi vendere {g_obj['nome']} perché è in prestito da: {g_obj['in_prestito_da']}.")
                                else:
                                    if "Invernale" in sessione_ven:
                                        if (g_obj.get('rinnovato_a_gennaio') or g_obj.get('acquistato_a_gennaio')) and g_obj.get('anni_trascorsi', 0) == 0:
                                            val_res_effettivo = g_obj['valore_residuo']
                                        else:
                                            val_res_effettivo = g_obj['valore_residuo'] - (g_obj['ammortamento_annuo'] / 2)
                                    else:
                                        val_res_effettivo = g_obj['valore_residuo']
                                    
                                    st.divider()
                                    
                                    c3, c4 = st.columns(2)
                                    prezzo_v = c3.number_input("Prezzo di Vendita (MLN)", min_value=0.0, step=1.0)
                                    nuovi_anni = c4.slider("Nuovi anni di contratto (per l'Acquirente)", 1, 5, 3, key="anni_nuovi_trasf")
                                    
                                    is_gennaio = True if "Invernale" in sessione_ven else False
                                    anni_effettivi_nuovi = nuovi_anni - 0.5 if is_gennaio else nuovi_anni
                                    s_base_nuovo = 1.0 if prezzo_v <= 15 else (2.5 if prezzo_v <= 45 else (4.5 if prezzo_v <= 85 else (7.0 if prezzo_v <= 130 else 11.0)))
                                    amm_nuovo = prezzo_v / anni_effettivi_nuovi if anni_effettivi_nuovi > 0 else prezzo_v

                                    diff_plus_minus = prezzo_v - val_res_effettivo
                                    
                                    st.markdown("##### 📊 Impatto Finanziario")
                                    col_out, col_in = st.columns(2)
                                    
                                    with col_out:
                                        with st.container(border=True):
                                            st.markdown(f"**📤 {sq_ced_name}**")
                                            st.write(f"- Valore Residuo Attuale: **{val_res_effettivo:.2f} M**")
                                            st.write(f"- Cassa: **+{prezzo_v:.2f} M**")
                                            if diff_plus_minus > 0:
                                                st.markdown(f"- Impatto a Bilancio: <span style='color: #10B981; font-weight: bold;'>Plusvalenza di +{diff_plus_minus:.2f} M</span>", unsafe_allow_html=True)
                                            elif diff_plus_minus < 0:
                                                st.markdown(f"- Impatto a Bilancio: <span style='color: #EF4444; font-weight: bold;'>Minusvalenza di {diff_plus_minus:.2f} M</span>", unsafe_allow_html=True)
                                            else:
                                                st.markdown("- Impatto a Bilancio: **Pari (Nessuna plus/minusvalenza)**")
                                            
                                    with col_in:
                                        with st.container(border=True):
                                            st.markdown(f"**📥 {sq_comp_name}**")
                                            st.write(f"- Costo d'Acquisto: **-{prezzo_v:.2f} M**")
                                            st.write(f"- Nuovo Ammortamento: **{amm_nuovo:.2f} M** annui")
                                            st.write(f"- Nuovo Stipendio: **{s_base_nuovo:.2f} M** annui")
                                            if is_gennaio:
                                                st.caption(f"*(Per i 6 mesi correnti l'impatto a bilancio sarà dimezzato)*")

                                    st.write("")
                                    
                                    if st.button("Conferma Trasferimento", type="primary", key="btn_conferma_trasf"):
                                        if prezzo_v > sq_comp['cassa']:
                                            st.error(f"❌ Operazione annullata: {sq_comp_name} non ha fondi sufficienti ({sq_comp['cassa']:.2f} M in cassa).")
                                        else:
                                            # AZIONI PER CHI VENDE
                                            if is_gennaio:
                                                sq_ced['bilancio']['costi']['costi_giocatori_ceduti'] += (g_obj['ammortamento_annuo'] / 2) + (g_obj['stipendio'] / 2)
                                            
                                            sq_ced['cassa'] = round(sq_ced['cassa'] + prezzo_v, 2)
                                            if diff_plus_minus > 0: 
                                                sq_ced['bilancio']['ricavi']['plusvalenze'] += diff_plus_minus
                                            else: 
                                                sq_ced['bilancio']['costi']['minusvalenze'] += abs(diff_plus_minus)
                                                
                                            sq_ced['rosa'].remove(g_obj)
                                            
                                            # AZIONI PER CHI COMPRA
                                            nuovo_giocatore = {
                                                "nome": g_obj['nome'], 
                                                "ruolo": g_obj['ruolo'], 
                                                "costo_acquisto": prezzo_v, 
                                                "anni_contratto": anni_effettivi_nuovi, 
                                                "stipendio": s_base_nuovo, 
                                                "ammortamento_annuo": amm_nuovo, 
                                                "anni_trascorsi": 0, 
                                                "valore_residuo": prezzo_v, 
                                                "acquistato_a_gennaio": is_gennaio
                                            }
                                            sq_comp['rosa'].append(nuovo_giocatore)
                                            sq_comp['cassa'] = round(sq_comp['cassa'] - prezzo_v, 2)
                                            
                                            # STORICO MOVIMENTI E LOG
                                            sq_ced['bilancio']['storico_movimenti'].append(f"Cessione {g_obj['nome']} a {sq_comp_name}: +{prezzo_v}M")
                                            sq_comp['bilancio']['storico_movimenti'].append(f"Acquisto {g_obj['nome']} da {sq_ced_name}: -{prezzo_v}M")
                                            
                                            save_data(db, DB_PATH)
                                            log_evento(sq_ced_name, "🤝", f"ha ceduto a titolo definitivo **{g_obj['nome']}** al **{sq_comp_name}** per **{prezzo_v} M**.")
                                            st.toast(f"Trasferimento completato con successo!", icon="🤝")
                                            st.rerun()
                    else:
                        st.info("Nessun giocatore in rosa da trasferire.")

            # --- TAB 3: SVINCOLA ---
            with t_svin:
                sq_svin_name = st.selectbox("Seleziona Squadra", list(db.keys()), key="tab3_sq")
                sq_svin = db[sq_svin_name]
                st.write(f"💰 **Cassa:** {sq_svin['cassa']:.2f} MLN | 👥 **Rosa:** {len(sq_svin['rosa'])}/25")
                
                rosa_ordinata_svin = sorted(sq_svin['rosa'], key=lambda x: ordine_ruoli.get(x['ruolo'], 5))
                
                if rosa_ordinata_svin:
                    with st.container(border=True):
                        sessione_svin = st.radio("Sessione di Mercato", ["☀️ Estiva", "❄️ Invernale"], horizontal=True, key="sess_svin")
                        st.divider()
                        
                        indice_s = st.selectbox(
                            "Seleziona da Svincolare", 
                            options=range(len(rosa_ordinata_svin)), 
                            format_func=lambda i: f"{rosa_ordinata_svin[i]['nome']} ({rosa_ordinata_svin[i]['ruolo'][:3].upper()})", 
                            key="svincolo_idx"
                        )

                        g_obj_s = rosa_ordinata_svin[indice_s]
                        
                        if g_obj_s:
                            if g_obj_s.get("prestato_a"):
                                st.error(f"❌ Impossibile svincolare. {g_obj_s['nome']} è attualmente in prestito a {g_obj_s['prestato_a']}.")
                            elif g_obj_s.get("in_prestito_da"):
                                st.error(f"❌ Non puoi svincolare un giocatore in prestito. Proprietà: {g_obj_s['in_prestito_da']}.")
                            else:
                                if "Invernale" in sessione_svin:
                                    if (g_obj_s.get('rinnovato_a_gennaio') or g_obj_s.get('acquistato_a_gennaio')) and g_obj_s.get('anni_trascorsi', 0) == 0:
                                        val_res_effettivo_s = g_obj_s['valore_residuo']
                                    else:
                                        val_res_effettivo_s = g_obj_s['valore_residuo'] - (g_obj_s['ammortamento_annuo'] / 2)
                                else:
                                    val_res_effettivo_s = g_obj_s['valore_residuo']
                                st.error(f"⚠️ Svincolare azzera il valore residuo generando una minusvalenza di {val_res_effettivo_s:.2f}M.")
                                
                                if st.button("Conferma Svincolo", type="primary", key="btn_conferma_svincolo"):
                                    if "Invernale" in sessione_svin:
                                        sq_svin['bilancio']['costi']['costi_giocatori_ceduti'] += (g_obj_s['ammortamento_annuo'] / 2) + (g_obj_s['stipendio'] / 2)
                                    
                                    sq_svin['bilancio']['costi']['minusvalenze'] += val_res_effettivo_s
                                    sq_svin['rosa'].remove(g_obj_s)
                                    save_data(db, DB_PATH)
                                    log_evento(sq_svin_name, "📄", f"ha rescisso il contratto di **{g_obj_s['nome']}**.")
                                    st.toast(f"{g_obj_s['nome']} è stato svincolato.", icon="📄")
                                    st.rerun()
                else:
                    st.info("Nessun giocatore in rosa da svincolare.")
                        
            # --- TAB 4: RINNOVA ---
            with t_rin:
                sq_rin_name = st.selectbox("Seleziona Squadra", list(db.keys()), key="tab4_sq")
                sq_rin = db[sq_rin_name]
                st.write(f"💰 **Cassa:** {sq_rin['cassa']:.2f} MLN | 👥 **Rosa:** {len(sq_rin['rosa'])}/25")
                
                rosa_ordinata_rin = sorted(sq_rin['rosa'], key=lambda x: ordine_ruoli.get(x['ruolo'], 5))
                
                if rosa_ordinata_rin:
                    with st.container(border=True):
                        sessione_rin = st.radio("Sessione di Mercato", ["☀️ Estiva", "❄️ Invernale"], horizontal=True, key="sess_rin")
                        is_gen_rin = "Invernale" in sessione_rin
                        st.divider()
                        
                        indice_r = st.selectbox(
                            "Seleziona da Rinnovare", 
                            options=range(len(rosa_ordinata_rin)), 
                            format_func=lambda i: f"{rosa_ordinata_rin[i]['nome']} ({rosa_ordinata_rin[i]['ruolo'][:3].upper()})", 
                            key="rinnovo_idx"
                        )
                        
                        g_obj_r = rosa_ordinata_rin[indice_r]
                        
                        if g_obj_r:
                            if g_obj_r.get("prestato_a"):
                                st.error(f"❌ Impossibile rinnovare. {g_obj_r['nome']} è in prestito.")
                            elif g_obj_r.get("in_prestito_da"):
                                st.error(f"❌ Impossibile rinnovare. {g_obj_r['nome']} non è un tuo giocatore (Proprietà: {g_obj_r['in_prestito_da']}).")
                            else:
                                blocco_rinnovo = False
                                msg_blocco = ""
                                
                                if g_obj_r.get('anni_trascorsi', 0) == 0:
                                    if not g_obj_r.get('acquistato_a_gennaio') and not is_gen_rin:
                                        blocco_rinnovo = True
                                        msg_blocco = "Hai appena firmato questo giocatore in questa Sessione Estiva. Le regole non permettono un rinnovo istantaneo."
                                    elif g_obj_r.get('acquistato_a_gennaio') and is_gen_rin:
                                        blocco_rinnovo = True
                                        msg_blocco = "Hai appena firmato questo giocatore in questa Sessione Invernale. Le regole non permettono un rinnovo istantaneo."
                                
                                if not blocco_rinnovo: 
                                    anni_rimanenti = g_obj_r.get('anni_contratto', 1) - g_obj_r.get('anni_trascorsi', 0)
                                    if anni_rimanenti >= 3:
                                        blocco_rinnovo = True
                                        msg_blocco = f"Il giocatore ha ancora {anni_rimanenti} anni di contratto. Puoi rinnovarlo solo quando gli restano 1 o 2 anni."
                                
                                if blocco_rinnovo:
                                    st.warning(f"✋ **Operazione Bloccata.** {msg_blocco}")
                                else:
                                    st.write(f"📊 **Stipendio Attuale:** {g_obj_r['stipendio']:.3f} M | **Valore Residuo Attuale:** {g_obj_r['valore_residuo']:.2f} M")
                                    
                                    nuovi_anni = st.slider("Nuovi Anni di Contratto (Max 5)", 1, 5, 1, key="anni_rinnovo")
                                    
                                    anni_effettivi = nuovi_anni - 0.5 if is_gen_rin else nuovi_anni
                                    # Applicato il nuovo incremento del 30% come da regolamento
                                    nuovo_stipendio = g_obj_r['stipendio'] * 1.30 
                                    
                                    if is_gen_rin:
                                        st.info(f"❄️ **Rinnovo Invernale:** Impatto pro-quota. Durata effettiva {anni_effettivi} anni.")
                                        vr_a_gennaio = g_obj_r['valore_residuo'] - (g_obj_r['ammortamento_annuo'] / 2)
                                        nuovo_amm = vr_a_gennaio / anni_effettivi if anni_effettivi > 0 else 0
                                    else:
                                        st.info("☀️ **Rinnovo Estivo:** Nuovo contratto applicato all'intera stagione.")
                                        nuovo_amm = g_obj_r['valore_residuo'] / anni_effettivi if anni_effettivi > 0 else 0
                                        
                                    st.write(f"🔄 **Nuova Proiezione:** Stipendio **{nuovo_stipendio:.3f} M** | Ammortamento Annuo **{nuovo_amm:.2f} M**")
                                    
                                    if st.button("Conferma Rinnovo", type="primary", key="btn_conferma_rinnovo"):
                                        if is_gen_rin:
                                            g_obj_r['rinnovato_a_gennaio'] = True
                                            g_obj_r['vecchio_amm_gennaio'] = g_obj_r['ammortamento_annuo']
                                            g_obj_r['vecchio_stip_gennaio'] = g_obj_r['stipendio']
                                            g_obj_r['valore_residuo'] = vr_a_gennaio
                                            
                                        g_obj_r['stipendio'] = nuovo_stipendio
                                        g_obj_r['costo_acquisto'] = g_obj_r['valore_residuo']
                                        g_obj_r['anni_contratto'] = anni_effettivi 
                                        g_obj_r['ammortamento_annuo'] = nuovo_amm
                                        g_obj_r['anni_trascorsi'] = 0
                                        
                                        save_data(db, DB_PATH)
                                        log_evento(sq_rin_name, "🤝", f"ha prolungato il contratto di **{g_obj_r['nome']}** per altri {anni_effettivi} anno/i.")
                                        st.toast(f"Contratto di {g_obj_r['nome']} rinnovato!", icon="🤝")
                                        st.rerun()
                else:
                    st.info("Nessun giocatore in rosa da rinnovare.")

            # with t_bosman:
            #     st.info("❄️ Disponibile esclusivamente per giocatori in scadenza a fine anno (1 anno residuo). Il cartellino passerà alla nuova società **a parametro zero** all'inizio del nuovo anno fiscale.")
                
            #     col_ced_b, col_acq_b = st.columns(2)
            #     sq_ced_name_b = col_ced_b.selectbox("📤 Società Attuale", list(db.keys()), key="tab5_sq_ced")
            #     sq_ced_b = db[sq_ced_name_b]
                
            #     sq_acq_name_b = col_acq_b.selectbox("📥 Nuova Società", [s for s in db.keys() if s != sq_ced_name_b], key="tab5_sq_acq")
            #     sq_acq_b = db[sq_acq_name_b]
                
            #     # Filtra SOLO chi ha 1 anno residuo e non in prestito
            #     giocatori_scadenza = []
            #     for g in sq_ced_b['rosa']:
            #         anni_res = g['anni_contratto'] - g.get('anni_trascorsi', 0)
            #         if anni_res == 1 and not g.get('in_prestito_da') and "pre_contratto" not in g:
            #             giocatori_scadenza.append(g)
                
            #     giocatori_scadenza = sorted(giocatori_scadenza, key=lambda x: ordine_ruoli.get(x['ruolo'], 5))
                
            #     if giocatori_scadenza:
            #         with st.container(border=True):
            #             indice_b = st.selectbox("Calciatore in Scadenza", options=range(len(giocatori_scadenza)), format_func=lambda i: f"{giocatori_scadenza[i]['nome']} ({giocatori_scadenza[i]['ruolo'][:3].upper()})")
            #             g_obj_b = giocatori_scadenza[indice_b]
                        
            #             st.divider()
            #             c1_b, c2_b = st.columns(2)
            #             premio_firma = c1_b.number_input("💰 Premio alla Firma (Offerta alla Busta in MLN)", min_value=0.0, step=1.0)
            #             nuovi_anni_b = c2_b.slider("Anni di Contratto Futuro", 1, 5, 3, key="anni_bosman")
                        
            #             s_base_bosman = 1.0 if premio_firma <= 15 else (2.5 if premio_firma <= 45 else (4.5 if premio_firma <= 85 else (7.0 if premio_firma <= 130 else 11.0)))
            #             amm_bosman = premio_firma / nuovi_anni_b if nuovi_anni_b > 0 else premio_firma
                        
            #             st.warning(f"⏳ **Importante:** I soldi del premio non verranno scalati ora. A fine stagione, il **{sq_acq_name_b}** pagherà {premio_firma:.2f} M e il giocatore costerà a bilancio {amm_bosman:.2f} M di ammortamento e {s_base_bosman:.2f} M di stipendio annuo.")
                        
            #             if st.button("Firma Pre-Contratto", type="primary", key="btn_bosman"):
            #                 g_obj_b['pre_contratto'] = {
            #                     "squadra_futura": sq_acq_name_b,
            #                     "premio_firma": premio_firma,
            #                     "anni": nuovi_anni_b,
            #                     "stipendio": s_base_bosman,
            #                     "ammortamento_annuo": amm_bosman
            #                 }
            #                 save_data(db, DB_PATH)
            #                 log_evento(sq_acq_name_b, "📝", f"ha depositato in Lega un pre-contratto per **{g_obj_b['nome']}** (attualmente tesserato al {sq_ced_name_b}). Il giocatore si trasferirà a parametro zero al termine della stagione!")
            #                 st.toast(f"Accordo futuro blindato per {g_obj_b['nome']}!", icon="📝")
            #                 st.rerun()
            #     else:
            #         st.info("Nessun giocatore in scadenza (1 anno residuo) in questa squadra, oppure hanno già tutti firmato un pre-contratto.")

# ==========================================
# 4. MERCATO (PRESTITI)
# ==========================================
elif menu == "4. Mercato (Prestiti)":
    st.header("🤝 Gestione Prestiti e Riscatti")

    if not st.session_state.is_admin:
        st.error("🔒 Accesso riservato. Solo l'Amministratore della Lega può effettuare operazioni di mercato.")
    else:
        if len(db) < 2:
            st.warning("Servono almeno 2 squadre per i prestiti.")
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
                    "Seleziona Giocatore", 
                    options=range(len(rosa_ordinata)), 
                    format_func=lambda i: f"{rosa_ordinata[i]['nome']} ({rosa_ordinata[i]['ruolo'][:3].upper()})", 
                    key="prestito_out_idx"
                )
                
                # Recuperiamo il giocatore dalla lista temporanea ordinata
                g_selezionato = rosa_ordinata[indice_p]
                
                # MODIFICA 2: Troviamo il giocatore REALE dentro il database per modificarlo direttamente alla fonte
                g_obj = next(g for g in db[sq_cedente]['rosa'] if g['nome'] == g_selezionato['nome'])
                
                st.divider()
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
                
                stip_totale = g_obj['stipendio']
                amm_totale = g_obj['ammortamento_annuo']
                
                if is_gen_prestito:
                    # A gennaio, metà stipendio è già in pancia al cedente. L'altra metà si divide in base allo slider.
                    stip_acq = (stip_totale / 2) * (perc_stipendio / 100)
                    stip_ced = (stip_totale / 2) + ((stip_totale / 2) * ((100 - perc_stipendio) / 100))
                else:
                    stip_acq = stip_totale * (perc_stipendio / 100)
                    stip_ced = stip_totale * ((100 - perc_stipendio) / 100)
                    
                html_prospetto = f"""
                <div style='background-color: white; border-radius: 8px; padding: 15px; border: 1px solid #E2E8F0; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);'>
                    <div style='color: #64748B; font-size: 13px; font-weight: bold; margin-bottom: 10px; text-transform: uppercase;'>📊 Impatto Finanziario Stagione Corrente</div>
                    <div style='display: flex; justify-content: space-between;'>
                        <div style='text-align: left;'>
                            <div style='color: #94A3B8; font-size: 12px;'>Ammortamento ({sq_cedente})</div>
                            <div style='color: #EF4444; font-weight: bold; font-size: 16px;'>{amm_totale:.2f} M</div>
                        </div>
                        <div style='text-align: center;'>
                            <div style='color: #94A3B8; font-size: 12px;'>Stipendio a carico ({sq_cedente})</div>
                            <div style='color: #10B981; font-weight: bold; font-size: 16px;'>{stip_ced:.2f} M</div>
                        </div>
                        <div style='text-align: right;'>
                            <div style='color: #94A3B8; font-size: 12px;'>Stipendio a carico ({sq_acquirente})</div>
                            <div style='color: #F59E0B; font-weight: bold; font-size: 16px;'>{stip_acq:.2f} M</div>
                        </div>
                    </div>
                </div>
                """
                st.markdown(html_prospetto, unsafe_allow_html=True)

                col_on, col_tipo, col_cifra = st.columns(3)
                costo_prestito = col_on.number_input("Costo Prestito (Oneroso in MLN)", min_value=0.0, step=0.5, value=0.0)
                tipo_accordo = col_tipo.selectbox("Tipo di Accordo", ["Prestito Secco", "Diritto di Riscatto", "Obbligo di Riscatto"])
                
                cifra_riscatto = 0.0
                if tipo_accordo != "Prestito Secco":
                    cifra_riscatto = col_cifra.number_input("Cifra Riscatto Pattuita (MLN)", min_value=1.0, step=1.0, value=10.0)
                
                st.markdown("<br>", unsafe_allow_html=True)
                anni_rimanenti = g_obj['anni_contratto'] - g_obj.get('anni_trascorsi', 0)

                if anni_rimanenti < (durata_prestito + 1):
                    st.error(f"⚠️ **Operazione Bloccata.** Il giocatore ha solo {anni_rimanenti} anno/i di contratto residuo. Per un prestito di {durata_prestito} anno/i, servono almeno {durata_prestito + 1} anni di contratto. **Rinnovalo prima di cederlo!**")
                else:
                    # Mostra il bottone SOLO se la regola è rispettata
                    if st.button("Ufficializza Prestito", type="primary"):
                        if costo_prestito > db[sq_acquirente]['cassa']:
                            st.error("Cassa acquirente insufficiente per il prestito oneroso!")
                        else:
                            g_acq = g_obj.copy()
                            g_acq['in_prestito_da'], g_acq['perc_stipendio_pagato'] = sq_cedente, perc_stipendio
                            g_acq['accordo_riscatto'] = {"tipo": tipo_accordo, "cifra": cifra_riscatto}
                            g_acq['anni_prestito_rimanenti'] = anni_effettivi_prestito
                            g_acq['prestato_a_gennaio'] = is_gen_prestito
                            db[sq_acquirente]['rosa'].append(g_acq)
                            
                            g_obj['prestato_a'], g_obj['perc_stipendio_pagato'] = sq_acquirente, perc_stipendio
                            g_obj['accordo_riscatto'] = {"tipo": tipo_accordo, "cifra": cifra_riscatto}
                            g_obj['anni_prestito_rimanenti'] = anni_effettivi_prestito
                            g_obj['prestato_a_gennaio'] = is_gen_prestito
                            
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
                    
                    if st.button("Prenota Riscatto (Effettivo al 1° Luglio)", type="primary"):
                        g_r_obj['riscatto_prenotato'] = {'cifra': prezzo_r, 'anni': anni_nuovi}
                        g_ced_obj = next(g for g in db[sq_cedente]['rosa'] if g['nome'] == g_riscatto)
                        g_ced_obj['riscatto_prenotato'] = {'cifra': prezzo_r, 'anni': anni_nuovi}
                        save_data(db, DB_PATH)
                        log_evento(sq_cedente, "💰", f"ha ufficializzato il riscatto di **{g_riscatto}** al **{sq_acquirente}** per **{prezzo_r} M**.")
                        st.toast(f"Riscatto di {g_riscatto} prenotato per fine anno!", icon="⏳")
                        st.rerun()

            st.divider()
            st.subheader("❌ Risoluzione Anticipata Prestito")
            if in_prestito:
                g_risoluzione = st.selectbox("Calciatore selezionato", [g['nome'] for g in in_prestito], key="risoluzione")
                st.info("Interrompendo il prestito, il giocatore tornerà immediatamente attivo nella rosa della società proprietaria e l'eventuale accordo di riscatto verrà annullato.")
                
                if st.button("Interrompi Prestito Subito", type="primary"):
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

                #####################################################################################
                # BLOCCO PER TEST
                #####################################################################################
                if st.session_state.is_admin:
                    if st.button("🎲 Simula tutto il Campionato in un colpo solo", type="primary"):
                        import random
                        for giornata_idx, giornata_dati in enumerate(calendario):
                            for match in giornata_dati:
                                if not match.get("giocata", False):
                                    # Genera gol realistici (con un leggero vantaggio per chi gioca in casa)
                                    gh = random.choices([0, 1, 2, 3, 4, 5], weights=[20, 30, 25, 15, 8, 2])[0]
                                    ga = random.choices([0, 1, 2, 3, 4, 5], weights=[30, 35, 20, 10, 4, 1])[0]
                                    
                                    match["gol_home"] = gh
                                    match["gol_away"] = ga
                                    match["giocata"] = True
                                    
                                    # # ASSEGNAZIONE INCASSI AUTOMATICA
                                    # if not match.get("incassi_assegnati", False):
                                    #     h_team = db[match["home"]]
                                    #     if h_team['stadio']['livello']:
                                    #         incasso = h_team['stadio']['vittoria'] if gh > ga else (h_team['stadio']['pari'] if gh == ga else h_team['stadio']['base'])
                                    #         h_team['bilancio']['ricavi']['incassi_stadio'] += incasso
                                    #         h_team['cassa'] = round(h_team['cassa'] + incasso, 2)
                                    #         h_team['bilancio']['storico_movimenti'].append(f"Stadio G{giornata_idx + 1}: +{incasso}M")
                                    #     match["incassi_assegnati"] = True
                        
                        save_data(db, DB_PATH)
                        save_data(calendario, CAL_PATH)
                        verifica_obiettivi_dinamici()
                        log_evento("Lega", "🎲", "L'Amministratore ha simulato l'intero Campionato!")
                        st.success("Simulazione completata! Tutti i risultati sono stati generati e gli incassi versati.")
                        st.rerun()
                        
                #####################################################################################
                # FINE BLOCCO PER TEST
                #####################################################################################
                
                st.info("👇 Scorri per vedere tutte le giornate.")
                
                for giornata_idx, giornata_dati in enumerate(calendario):
                    
                    st.subheader(f"Partite Giornata {giornata_idx + 1}")
                    
                    # Controlliamo se la giornata è già stata giocata e salvata
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
                            st.info(f"🔒 **Giornata {giornata_idx + 1} archiviata.** I risultati sono ufficiali.")
                    
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
                                if st.form_submit_button(f"Salva Risultati (G. {giornata_idx + 1})", type="primary"):
                                    gol_map = {}
                                    for idx, match in enumerate(giornata_dati):
                                        gh = st.session_state[f"g{giornata_idx}_h_{idx}"]
                                        ga = st.session_state[f"g{giornata_idx}_a_{idx}"]
                                        
                                        match["gol_home"] = gh
                                        match["gol_away"] = ga
                                        match["giocata"] = True

                                        gol_map[match["home"]] = gh
                                        gol_map[match["away"]] = ga
                                        
                                        # if not match["incassi_assegnati"]:
                                        #     h_team = db[match["home"]]
                                        #     if h_team['stadio']['livello']:
                                        #         incasso = h_team['stadio']['vittoria'] if gh > ga else (h_team['stadio']['pari'] if gh == ga else h_team['stadio']['base'])
                                        #         h_team['bilancio']['ricavi']['incassi_stadio'] += incasso
                                        #         h_team['cassa'] += incasso 
                                        #         h_team['bilancio']['storico_movimenti'].append(f"Stadio G{giornata_idx + 1}: +{incasso}M")
                                        #     match["incassi_assegnati"] = True
                                    
                                    save_data(db, DB_PATH)
                                    save_data(calendario, CAL_PATH)

                                    verifica_obiettivi_dinamici()
                                    
                                    log_evento("Lega", "📅", f"Risultati della **Giornata {giornata_idx + 1}** ufficializzati.")
                                    st.rerun() 
                    
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

        squadre_ordinate = df_c.index.tolist()
        premi_gia_dati = db[squadre_ordinate[0]].get("premi_campionato_dati", False)
        if not st.session_state.is_admin:
            st.error("🔒 Accesso riservato. Solo l'Amministratore della Lega può distribuire i premi e i ricavi da sponsor.")
        else:
            if premi_gia_dati:
                st.info("✅ **Premi di fine campionato e Sponsor già erogati per questa stagione.**")
            else: 
                if st.button("🏆 Distribuisci Premi Campionato", type="primary"):
                    st.subheader("💰 Resoconto Assegnazione Premi") # <-- TITOLO AGGIUNTO
                    
                    squadre_ordinate = df_c.index.tolist()
                    premi_campionato = [50.0, 52.0, 55.0, 58.0, 62.0, 65.0, 68.0, 70.0]
                    
                    # --- CONTEGGIO PARTITE IN CASA ---
                    # partite_in_casa = {s: 0 for s in db.keys()}
                    # for md in calendario:
                    #     for m in md:
                    #         partite_in_casa[m["home"]] += 1
                    # max_casa = max(partite_in_casa.values())
                    
                    for pos, nome_sq in enumerate(squadre_ordinate):
                        team = db[nome_sq]
                        p_camp = premi_campionato[pos]
                        team["premi_campionato_dati"] = True
                        
                        # 1. PREMIO CAMPIONATO: Entra ORA in Cassa e Bilancio corrente
                        team['cassa'] = round(team['cassa'] + p_camp, 2)
                        team['bilancio']['ricavi']['premi_sportivi'] += p_camp
                        team['bilancio']['storico_movimenti'].append(f"Premio Campionato ({pos+1}°): +{p_camp}M")
                        
                        # ---> AGGIUNTA 1: Mostra a schermo e logga il Premio <---
                        st.success(f"🏅 **{pos+1}° Posto - {nome_sq}**: incassa **{p_camp} M** di premio.")
                        log_evento(nome_sq, "🏆", f"ha incassato **{p_camp} M** per essersi classificata al {pos+1}° posto in Campionato.")
                        
                        # 2. CONGUAGLIO STADIO: Rimborsa chi ha giocato meno partite in casa
                        # diff_casa = max_casa - partite_in_casa[nome_sq]
                        # if diff_casa > 0 and team['stadio']['livello']:
                        #     conguaglio = diff_casa * team['stadio']['base']
                        #     team['cassa'] = round(team['cassa'] + conguaglio, 2)
                        #     team['bilancio']['ricavi']['incassi_stadio'] += conguaglio
                        #     team['bilancio']['storico_movimenti'].append(f"Conguaglio Equità ({diff_casa} partite in meno in casa): +{conguaglio}M")
                            
                        #     # ---> AGGIUNTA 2: Mostra a schermo e logga il Conguaglio <---
                        #     st.info(f"⚖️ **{nome_sq}** riceve **{conguaglio} M** di conguaglio stadio ({diff_casa} partita/e in meno in casa).")
                        #     log_evento(nome_sq, "⚖️", f"ha ricevuto un conguaglio di **{conguaglio} M** per compensare le minori partite giocate in casa.")
                        
                        # 2. CONTROLLO OBIETTIVI DI PIAZZAMENTO A FINE ANNO
                        obiettivi = team.get("sponsor", {}).get("obiettivi", {})
                        pagati = team.get("sponsor", {}).setdefault("obiettivi_pagati", [])

                        if obiettivi:
                            ob_br = obiettivi.get("bronzo", "")
                            if "8° posto" in ob_br and pos < 7 and ob_br not in pagati:
                                team['cassa'] = round(team['cassa'] + 8.0, 2)
                                team['bilancio']['ricavi']['sponsor'] += 8.0
                                team['bilancio']['storico_movimenti'].append(f"Bonus Sponsor Piazzamento ({ob_br}): +8.0M")
                                pagati.append(ob_br)
                                log_evento(nome_sq, "🎯", f"ha sbloccato l'obiettivo stagionale **{ob_br}** incassando **8.0 M**!")

                            ob_ar = obiettivi.get("argento", "")
                            if "prime 4" in ob_ar and pos < 4 and ob_ar not in pagati:
                                team['cassa'] = round(team['cassa'] + 15.0, 2)
                                team['bilancio']['ricavi']['sponsor'] += 15.0
                                team['bilancio']['storico_movimenti'].append(f"Bonus Sponsor Piazzamento ({ob_ar}): +15.0M")
                                pagati.append(ob_ar)
                                log_evento(nome_sq, "🎯", f"ha sbloccato l'obiettivo stagionale **{ob_ar}** incassando **15.0 M**!")

                            ob_or = obiettivi.get("oro", "")
                            if "Vinci il Campionato" in ob_or and pos == 0 and ob_or not in pagati:
                                team['cassa'] = round(team['cassa'] + 30.0, 2)
                                team['bilancio']['ricavi']['sponsor'] += 30.0
                                team['bilancio']['storico_movimenti'].append(f"Bonus Sponsor Piazzamento ({ob_or}): +30.0M")
                                pagati.append(ob_or)
                                log_evento(nome_sq, "🎯", f"ha sbloccato l'obiettivo stagionale **{ob_or}** incassando **30.0 M**!")

                    save_data(db, DB_PATH)

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
            st.write("🔴 **Quarti di Finale (G. 10)**")
            
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
                            verifica_obiettivi_dinamici()
                            st.rerun()
                else:
                    st.info("🔒 **Quarti di Finale archiviati.**")
                    if not coppe["ci"]["semis"] and st.button("Genera Semifinali Coppa Italia", type="primary"):
                        vincitori = [m.get('vincente') for m in coppe["ci"]["quarti"]]
                        coppe["ci"]["semis"] = [{"home": vincitori[0], "away": vincitori[1], "gol_home": 0, "gol_away": 0}, {"home": vincitori[2], "away": vincitori[3], "gol_home": 0, "gol_away": 0}]
                        save_data(coppe, COPPE_PATH)
                        st.rerun()

        if coppe["ci"]["semis"]:
            st.write("🟡 **Semifinali (G. 20)**")
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
                            verifica_obiettivi_dinamici()
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
            st.write("🟢 **Finale (G. 28)**")
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
                            verifica_obiettivi_dinamici()
                            st.rerun()
                else:
                    st.info("🔒 **Finale archiviata.**")
                    if not coppe["ci"]["premi_dati"] and st.button("🏆 Eroga Premi Coppa Italia", type="primary"):
                        st.subheader("💰 Resoconto Premi Coppa Italia")
                        
                        vincente = m.get('vincente')
                        perdente = m['home'] if vincente == m['away'] else m['away']
                        
                        # --- 1. VINCITORE (35 M) ---
                        premio_v = 35.0
                        db[vincente]['bilancio']['ricavi']['premi_sportivi'] += premio_v
                        db[vincente]['cassa'] = round(db[vincente]['cassa'] + premio_v, 2)
                        db[vincente]['bilancio']['storico_movimenti'].append(f"Vittoria Coppa Italia: +{premio_v}M")
                        
                        st.success(f"🥇 **Vincitore - {vincente}**: incassa **{premio_v} M**!")
                        log_evento(vincente, "🇮🇹", f"ha vinto la Coppa Italia e incassa **{premio_v} M**!")

                        # --- 2. FINALISTA (20 M) ---
                        premio_f = 20.0
                        db[perdente]['bilancio']['ricavi']['premi_sportivi'] += premio_f
                        db[perdente]['cassa'] = round(db[perdente]['cassa'] + premio_f, 2)
                        db[perdente]['bilancio']['storico_movimenti'].append(f"Finalista Coppa Italia: +{premio_f}M")
                        
                        st.info(f"🥈 **Finalista - {perdente}**: incassa **{premio_f} M**.")
                        log_evento(perdente, "🥈", f" incassa **{premio_f} M** come finalista di Coppa Italia.")

                        # --- 3. SEMIFINALISTI (10 M) ---
                        premio_s = 10.0
                        for sq in coppe["ci"].get("perse_semis", []): 
                            db[sq]['bilancio']['ricavi']['premi_sportivi'] += premio_s
                            db[sq]['cassa'] = round(db[sq]['cassa'] + premio_s, 2)
                            db[sq]['bilancio']['storico_movimenti'].append(f"Semifinale Coppa Italia: +{premio_s}M")
                            
                            st.warning(f"🥉 **Semifinalista - {sq}**: incassa **{premio_s} M**.")
                            log_evento(sq, "🥉", f" incassa **{premio_s} M** per aver raggiunto la Semifinale di Coppa Italia.")
                            
                        # Chiusura e salvataggio
                        coppe["ci"]["premi_dati"] = True
                        save_data(db, DB_PATH)
                        save_data(coppe, COPPE_PATH)
    
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

            # --- TABELLA CLASSIFICA GIRONI CUSTOM ---
            st.markdown("""
            <style>
            .tabella-gironi {
                border-collapse: collapse;
                width: 100%;
                background-color: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
                font-family: sans-serif;
                margin-bottom: 20px;
                border: 1px solid #E2E8F0;
            }
            .tabella-gironi th {
                background-color: #F8FAFC;
                color: #64748B;
                padding: 12px 15px;
                font-size: 13px;
                text-align: center;
                border-bottom: 2px solid #E2E8F0;
            }
            .tabella-gironi td {
                padding: 12px 15px;
                font-size: 14px;
                color: #334155;
                text-align: center;
                border-bottom: 1px solid #F1F5F9;
            }
            .tabella-gironi th:first-child, .tabella-gironi td:first-child {
                text-align: left;
            }
            .tabella-gironi tr:last-child td {
                border-bottom: none;
            }
            .tabella-gironi tr:hover {
                background-color: #F1F5F9;
            }
            </style>
            """, unsafe_allow_html=True)

            colA, colB = st.columns(2)
            
            with colA:
                st.markdown("#### 🔵 Girone A")
                html_A = '<table class="tabella-gironi"><tr><th>Squadra</th><th>Punti</th><th>DR</th></tr>'
                for _, row in df_A.iterrows():
                    html_A += f"<tr><td><strong>{row['Squadra']}</strong></td><td style='font-weight: bold; color: #2563EB;'>{row['Punti']}</td><td>{row['DR']}</td></tr>"
                html_A += "</table>"
                st.markdown(html_A, unsafe_allow_html=True)
                
                with st.expander("Calendario Girone A" if gironi_salvati else "Calendario Girone A"):
                    for g_idx, md in enumerate(coppe["cl"].get("cal_A", [])):
                        gior = 2
                        st.markdown(f"**Giornata {g_idx + 1} (G. {gior + 3*g_idx})**")
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
                html_B = '<table class="tabella-gironi"><tr><th>Squadra</th><th>Punti</th><th>DR</th></tr>'
                for _, row in df_B.iterrows():
                    html_B += f"<tr><td><strong>{row['Squadra']}</strong></td><td style='font-weight: bold; color: #2563EB;'>{row['Punti']}</td><td>{row['DR']}</td></tr>"
                html_B += "</table>"
                st.markdown(html_B, unsafe_allow_html=True)
                
                with st.expander("Calendario Girone B" if gironi_salvati else "Calendario Girone B"):
                    for g_idx, md in enumerate(coppe["cl"].get("cal_B", [])):
                        gior = 2
                        st.markdown(f"**Giornata {g_idx + 1} (G. {gior + 3*g_idx})**")
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
                        verifica_obiettivi_dinamici()
                        st.success("Risultati parziali salvati!.")
                        st.rerun()
                        
                    # Bottone 2: Blocca tutto alla fine
                    if btn_archivia.button("🔒 Archivia Gironi Champions League", type="primary", use_container_width=True, key="btn_archivia_cl"):
                        coppe["cl"]["gironi_salvati"] = True
                        save_data(coppe, COPPE_PATH)
                        verifica_obiettivi_dinamici()
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
                        c1.markdown(f"<div style='text-align: right; margin-top: 8px;'>✈️ Andata (G. 22): <b style='font-size: 16px;'>{ma['home']}</b></div>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='{stile_box}'>{ma['gol_home']}</div>", unsafe_allow_html=True)
                        c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                        c4.markdown(f"<div style='{stile_box}'>{ma['gol_away']}</div>", unsafe_allow_html=True)
                        c5.markdown(f"<div style='text-align: left; margin-top: 8px;'><b style='font-size: 16px;'>{ma['away']}</b></div>", unsafe_allow_html=True)
                        
                        # RITORNO BLOCCATO
                        c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                        c1.markdown(f"<div style='text-align: right; margin-top: 8px;'>🏠 Ritorno (G. 25): <b style='font-size: 16px;'>{mr['home']}</b></div>", unsafe_allow_html=True)
                        c2.markdown(f"<div style='{stile_box}'>{mr['gol_home']}</div>", unsafe_allow_html=True)
                        c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                        c4.markdown(f"<div style='{stile_box}'>{mr['gol_away']}</div>", unsafe_allow_html=True)
                        c5.markdown(f"<div style='text-align: left; margin-top: 8px;'><b style='font-size: 16px;'>{mr['away']}</b></div>", unsafe_allow_html=True)
                        
                        _, c_passa, _ = st.columns([2.5, 2.5, 2.5])
                        c_passa.markdown(f"<div style='text-align: center; margin-top: 8px; font-size: 14px; color: #64748B;'>Passa in Finale: <b style='color: #0F172A;'>{mr.get('vincente', '')}</b></div>", unsafe_allow_html=True)
                    else:
                        # ANDATA EDITABILE
                        c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                        c1.markdown(f"<div style='text-align: right; margin-top: 8px;'>✈️ Andata (G. 22): <b style='font-size: 16px;'>{ma['home']}</b></div>", unsafe_allow_html=True)
                        ma['gol_home'] = c2.number_input("H", value=ma.get('gol_home',0), key=f"cl_s_ah_{i}", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                        c3.markdown("<div style='text-align: center; margin-top: 8px; font-weight: bold;'>-</div>", unsafe_allow_html=True)
                        ma['gol_away'] = c4.number_input("A", value=ma.get('gol_away',0), key=f"cl_s_aa_{i}", disabled=not st.session_state.is_admin, label_visibility="collapsed")
                        c5.markdown(f"<div style='text-align: left; margin-top: 8px;'><b style='font-size: 16px;'>{ma['away']}</b></div>", unsafe_allow_html=True)

                        # RITORNO EDITABILE
                        c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                        c1.markdown(f"<div style='text-align: right; margin-top: 8px;'>🏠 Ritorno (G. 25): <b style='font-size: 16px;'>{mr['home']}</b></div>", unsafe_allow_html=True)
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
                            verifica_obiettivi_dinamici()
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
            st.write("🟢 **Finale (G. 32)**")
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
                            verifica_obiettivi_dinamici()
                            st.rerun()
                else:
                    st.info("🔒 **Finale archiviata.**")
                    if not coppe["cl"]["premi_dati"] and st.button("🏆 Eroga Premi Champions League", type="primary"):
                        st.subheader("💰 Resoconto Premi Champions League")
                        
                        vincente = m.get('vincente')
                        perdente = m['home'] if vincente == m['away'] else m['away']
                        
                        # --- 1. VINCITORE (50 M) ---
                        premio_v = 50.0
                        db[vincente]['bilancio']['ricavi']['premi_sportivi'] += premio_v
                        db[vincente]['cassa'] = round(db[vincente]['cassa'] + premio_v, 2)
                        db[vincente]['bilancio']['storico_movimenti'].append(f"Vittoria Champions League: +{premio_v}M")
                        
                        st.success(f"🏆 **Campione d'Europa - {vincente}**: incassa **{premio_v} M**!")
                        log_evento(vincente, "🇪🇺", f"ha vinto la Champions League e incassa **{premio_v} M**!")

                        # --- 2. FINALISTA (35 M) ---
                        premio_f = 35.0
                        db[perdente]['bilancio']['ricavi']['premi_sportivi'] += premio_f
                        db[perdente]['cassa'] = round(db[perdente]['cassa'] + premio_f, 2)
                        db[perdente]['bilancio']['storico_movimenti'].append(f"Finalista Champions League: +{premio_f}M")
                        
                        st.info(f"🥈 **Finalista - {perdente}**: incassa **{premio_f} M**.")
                        log_evento(perdente, "🥈", f" incassa **{premio_f} M** come finalista di Champions League.")

                        # --- 3. SEMIFINALISTI (20 M) ---
                        premio_s = 20.0
                        for sq in coppe["cl"].get("perse_semis", []): 
                            db[sq]['bilancio']['ricavi']['premi_sportivi'] += premio_s
                            db[sq]['cassa'] = round(db[sq]['cassa'] + premio_s, 2)
                            db[sq]['bilancio']['storico_movimenti'].append(f"Semifinale Champions League: +{premio_s}M")
                            
                            st.warning(f"🥉 **Semifinalista - {sq}**: incassa **{premio_s} M**.")
                            log_evento(sq, "🥉", f" incassa **{premio_s} M** per aver raggiunto la Semifinale di Champions League.")
                            
                        # Chiusura e salvataggio
                        coppe["cl"]["premi_dati"] = True
                        save_data(db, DB_PATH)
                        save_data(coppe, COPPE_PATH)

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
                
                giocatori_in_arrivo_bosman = []
                # --- 1. CICLO DI CHIUSURA SQUADRE ---
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
                    
                    # CATTURIAMO LA CASSA PRIMA E DOPO
                    cassa_pre_stipendi = dati['cassa']
                    dati['cassa'] = round(dati['cassa'] - tot_ingaggi, 2)
                    cassa_post_stipendi = dati['cassa']
                    
                    utile = round(sum(b['ricavi'].values()) - sum(b['costi'].values()), 2)
                    
                    multa_fpf = 0.0
                    if utile < 0:
                        multa_fpf = round(abs(utile) * 0.15, 2)
                        dati['cassa'] -= multa_fpf  
                        dati['bilancio']['storico_movimenti'].append(f"Multa Fair Play UEFA (15% della perdita di {utile}M): -{multa_fpf}M") 
                    
                    dati['ultimo_bilancio_chiuso'] = {
                        "cassa_prima_stipendi": cassa_pre_stipendi,
                        "cassa_dopo_stipendi": cassa_post_stipendi,
                        "ricavi": {k: round(v, 2) for k, v in dati['bilancio']['ricavi'].items()},
                        "costi": {k: round(v, 2) for k, v in dati['bilancio']['costi'].items()},
                        "utile": utile,
                        "multa": multa_fpf,
                        "cassa_partenza_nuovo_anno": round(dati['cassa'] + 70.0, 2) # Includiamo già i 70M in arrivo
                    }
                    
                    dati['bilancio'] = init_bilancio()
                    # dati['stadio'] = {"livello": None, "costo_annuo": 0, "base": 0, "pari": 0, "vittoria": 0}
                    
                    dati['cassa'] += 70.0
                    dati['bilancio']['ricavi']['nuovo_capitale'] = 70.0
                    dati['bilancio']['storico_movimenti'].append("Iniezione Nuovo Capitale: +70.0M (Cassa e Ricavi)")
                    
                    # Azzeriamo lo sponsor per la nuova stagione (svuotando anche i pagati)
                    dati['sponsor'] = {"nome": None, "valore_base": 0, "obiettivi": {}, "obiettivi_pagati": []}
                    
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
                            else:
                                # IL CONTRATTO SCADE. SE HA UN PRE-CONTRATTO, LO SALVIAMO IN VALIGIA!
                                if "pre_contratto" in g:
                                    giocatori_in_arrivo_bosman.append(g)
                    dati['rosa'] = nuova_rosa
                    dati["premi_campionato_dati"] = False
                
                # ========================================================
                # 4. ESECUZIONE DEI PRE-CONTRATTI BOSMAN
                # ========================================================
                for gb in giocatori_in_arrivo_bosman:
                    pc = gb['pre_contratto']
                    sq_futura = pc['squadra_futura']
                    
                    # Togliamo il premio alla firma dalla cassa della nuova squadra
                    db[sq_futura]['cassa'] = round(db[sq_futura]['cassa'] - pc['premio_firma'], 2)
                    db[sq_futura]['bilancio']['storico_movimenti'].append(f"Premio firma parametro zero ({gb['nome']}): -{pc['premio_firma']}M")
                    
                    # Creiamo il profilo nuovo fiammante e lo infiliamo in rosa
                    nuovo_giocatore = {
                        "nome": gb['nome'],
                        "ruolo": gb['ruolo'],
                        "costo_acquisto": pc['premio_firma'],
                        "anni_contratto": pc['anni'],
                        "stipendio": pc['stipendio'],
                        "ammortamento_annuo": pc['ammortamento_annuo'],
                        "anni_trascorsi": 0,
                        "valore_residuo": pc['premio_firma'],
                        "acquistato_a_gennaio": False
                    }
                    db[sq_futura]['rosa'].append(nuovo_giocatore)
                    log_evento(sq_futura, "🤝", f"ha accolto ufficialmente in rosa **{gb['nome']}** a parametro zero. Spesa per il premio alla firma: {pc['premio_firma']} M.")

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
            
            # Recuperiamo i dati (usando .get per retrocompatibilità in caso di vecchi salvataggi)
            c_pre = ub.get('cassa_prima_stipendi', 0.0)
            c_post = ub.get('cassa_dopo_stipendi', 0.0)
            multa = ub.get('multa', 0.0)
            utile = ub.get('utile', 0.0)
            c_new = ub.get('cassa_partenza_nuovo_anno', 0.0)
            
            # --- SEZIONE 1: FLUSSO DI CASSA ---
            st.markdown("##### 1. Flusso di Cassa")
            col1, col2, col3 = st.columns(3)
            col1.metric("Cassa Pre-Stipendi", f"{c_pre:.2f} M")
            col2.metric("Pagamento Monte Ingaggi", f"-{ub['costi'].get('monte_ingaggi', 0.0):.2f} M")
            col3.metric("Cassa Post-Stipendi", f"{c_post:.2f} M")
            
            st.write("")
            
            # --- SEZIONE 2: BILANCIO D'ESERCIZIO ---
            st.markdown("##### ⚖️ 2. Conto Economico (Bilancio)")
            col_ric, col_cost = st.columns(2)
            
            with col_ric:
                html_ric = f"<div style='background-color: #F0FDF4; padding: 15px; border-radius: 8px; border: 1px solid #BBF7D0;'>"
                html_ric += f"<h4 style='color: #166534; margin-top: 0;'>🟢 Totale Ricavi: {tot_ricavi:.2f} M</h4><hr style='border-color: #BBF7D0;'>"
                for k, v in ub['ricavi'].items():
                    if v > 0: 
                        html_ric += f"<div style='display: flex; justify-content: space-between; margin-bottom: 5px;'><span style='color: #166534;'>{k.replace('_', ' ').title()}</span> <strong>{v:.2f} M</strong></div>"
                html_ric += "</div>"
                st.markdown(html_ric, unsafe_allow_html=True)
                        
            with col_cost:
                html_cost = f"<div style='background-color: #FEF2F2; padding: 15px; border-radius: 8px; border: 1px solid #FECACA;'>"
                html_cost += f"<h4 style='color: #991B1B; margin-top: 0;'>🔴 Totale Costi: {tot_costi:.2f} M</h4><hr style='border-color: #FECACA;'>"
                for k, v in ub['costi'].items():
                    if v > 0: 
                        html_cost += f"<div style='display: flex; justify-content: space-between; margin-bottom: 5px;'><span style='color: #991B1B;'>{k.replace('_', ' ').title()}</span> <strong>{v:.2f} M</strong></div>"
                html_cost += "</div>"
                st.markdown(html_cost, unsafe_allow_html=True)

            st.write("")

            # --- SEZIONE 3: RISULTATO E NUOVO ANNO ---
            st.markdown("##### 🏛️ 3. Fair Play Finanziario e Nuovo Anno")
            col_u, col_m, col_f = st.columns(3)
            
            col_u.metric("Risultato d'Esercizio", f"{utile:.2f} M", delta="In Utile" if utile >= 0 else "In Perdita", delta_color="normal" if utile >= 0 else "inverse")
            
            if utile < 0:
                col_m.metric("🚨 Multa FPF Pagata (15%)", f"-{multa:.2f} M")
            else:
                col_m.metric("✅ Multa FPF", "Nessuna sanzione")
                
            col_f.metric("Cassa Iniziale Nuova Stagione", f"{c_new:.2f} M", delta="+70.0M Nuovi Capitali Lega", delta_color="normal")
            
        else:
            st.info("Questa squadra non ha ancora chiuso un bilancio aziendale.")
    else:
        st.info("Nessuno storico disponibile. Esegui la chiusura fiscale a fine stagione per generare i prospetti.")

# ==========================================
# 9. CRONOLOGIA E UFFICIALITÀ LEGA
# ==========================================
elif menu == "9. Cronologia Ufficialità":
    st.header("📰 Notiziario Ufficiale Lega")
    st.caption("L'elenco cronologico di tutte le operazioni societarie e di mercato in tempo reale.")
    st.divider()
    
    feed = load_feed()
    
    if not feed:
        st.info("Nessuna operazione registrata finora.")
    else:
        import re
        
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