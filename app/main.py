import streamlit as st
import json
import os
import pandas as pd
import random

# Costruisce il percorso assoluto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "squadre.json")
CAL_PATH = os.path.join(BASE_DIR, "database", "calendario.json")
COPPE_PATH = os.path.join(BASE_DIR, "database", "coppe.json")

st.set_page_config(page_title="Osei Football League", layout="wide", initial_sidebar_state="expanded")

# --- FUNZIONI DATI E LOGICA ---
def load_data(path):
    if not os.path.exists(path):
        return {} if "squadre" in path or "coppe" in path else []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def init_bilancio():
    return {
        "ricavi": {"nuovo_capitale": 0.0, "premi_sportivi": 0.0, "sponsor": 0.0, "incassi_stadio": 0.0, "plusvalenze": 0.0},
        "costi": {"ammortamenti": 0.0, "monte_ingaggi": 0.0, "gestione_stadio": 0.0, "minusvalenze": 0.0, "costi_giocatori_ceduti": 0.0},
        "storico_movimenti": []
    }

def genera_calendario_berger(squadre_lista):
    n = len(squadre_lista)
    squadre = list(squadre_lista)
    matchdays = []
    
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
        
    full_calendar = []
    for round_num in range(6): 
        for md in matchdays:
            if len(full_calendar) < 38:
                new_md = []
                for match in md:
                    if round_num % 2 == 1: 
                        new_md.append({"home": match["away"], "away": match["home"], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi_assegnati": False})
                    else: 
                        new_md.append({"home": match["home"], "away": match["away"], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi_assegnati": False})
                full_calendar.append(new_md)
    return full_calendar


def init_coppe():
    return {
        "ci": {"quarti": [], "semis": [], "finale": [], "perse_semis": [], "premi_dati": False},
        "cl": {
            "gir_A": [], "gir_B": [], 
            "punti_A": {}, "punti_B": {}, # Nuovo: Database manuale per i punti
            "semis_andata": [], "semis_ritorno": [], 
            "finale": [], "perse_semis": [], "premi_dati": False
        }
    }

# Caricamento Dati
db = load_data(DB_PATH)
calendario = load_data(CAL_PATH)
coppe = load_data(COPPE_PATH)
if not coppe: coppe = init_coppe()

for sq in db.values():
    if "costi_giocatori_ceduti" not in sq["bilancio"]["costi"]:
        sq["bilancio"]["costi"]["costi_giocatori_ceduti"] = 0.0

# --- GESTIONE ACCESSO ADMIN ---
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

st.sidebar.title("🔐 Accesso")
if not st.session_state.is_admin:
    pwd = st.sidebar.text_input("Password Amministratore", type="password")
    if pwd == "osei":
        st.session_state.is_admin = True
        st.rerun()
    elif pwd:
        st.sidebar.error("Password errata")
else:
    st.sidebar.success("👑 Modalità Admin Attiva")
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
    "9. Regolamento Ufficiale"
])

# ==========================================
# 1. SETUP SOCIETÀ
# ==========================================
if menu == "1. Setup Società":
    st.header("🏢 Gestione Società e Stadi")

    if not st.session_state.is_admin:
        st.error("🔒 Accesso riservato. Solo l'Amministratore della Lega può effettuare operazioni di mercato.")
    else:
        with st.form("crea_squadra"):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome Squadra")
            mister = c2.text_input("Allenatore")
            if st.form_submit_button("Iscrivi Squadra (Fondo 350M)"):
                if nome and mister and nome not in db:
                    db[nome] = {
                        "allenatore": mister, "cassa": 350.0,
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
            sq_sel = st.selectbox("Seleziona Squadra per Stadio", list(db.keys()))
            sq_dati = db[sq_sel]
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Impianto Sportivo")
                stadi = {
                    "Categoria 1 (20.000 posti) - 5M Costo": {"livello": "20k", "costo": 5.0, "base": 0.1, "pari": 0.2, "vittoria": 0.4},
                    "Categoria 2 (50.000 posti) - 12M Costo": {"livello": "50k", "costo": 12.0, "base": 0.3, "pari": 0.5, "vittoria": 0.9},
                    "Categoria 3 (80.000 posti) - 20M Costo": {"livello": "80k", "costo": 20.0, "base": 0.6, "pari": 1.0, "vittoria": 1.5}
                }
                scelta = st.selectbox("Livello", list(stadi.keys()))
                if st.button("Firma Contratto Stadio"):
                    sq_dati["stadio"] = stadi[scelta]
                    sq_dati["bilancio"]["costi"]["gestione_stadio"] = stadi[scelta]["costo"]
                    save_data(db, DB_PATH)
                    st.success("Stadio aggiornato! Costi inseriti a bilancio.")

            with col2:
                st.subheader("Main Sponsor")
                ns = st.text_input("Nome Sponsor", value=sq_dati["sponsor"]["nome"] or "")
                
                if st.button("Firma Accordo Sponsor"):
                    sq_dati["sponsor"] = {"nome": ns, "valore": 30.0}
                    # Accredita i 30M solo se la voce sponsor a bilancio è ancora a zero
                    if sq_dati["bilancio"]["ricavi"]["sponsor"] == 0.0:
                        sq_dati["bilancio"]["ricavi"]["sponsor"] = 30.0
                        sq_dati["cassa"] = round(sq_dati["cassa"] + 30.0, 2)
                        sq_dati['bilancio']['storico_movimenti'].append(f"Sponsor di Fondazione: +30.0M")
                    
                    save_data(db, DB_PATH)
                    st.success(f"Sponsor {ns} firmato! 30 Milioni accreditati in Cassa e a Bilancio per la stagione 1.")

# ==========================================
# 2. DASHBOARD & ROSA
# ==========================================
elif menu == "2. Dashboard & Rosa":
    st.header("📊 Prospetto Finanziario")
    if not db: st.warning("Nessuna squadra presente.")
    else:
        sq_sel = st.selectbox("Analizza Società", list(db.keys()))
        squadra = db[sq_sel]
        b = squadra['bilancio']
        
        tot_ammortamenti, tot_ingaggi = 0.0, 0.0
        for g in squadra['rosa']:
            amm = g['ammortamento_annuo']
            stip = g['stipendio']
            if g.get('acquistato_a_gennaio') and g['anni_trascorsi'] == 0:
                amm /= 2
                stip /= 2
                
            if g.get("in_prestito_da"): tot_ingaggi += stip * (g['perc_stipendio_pagato'] / 100)
            elif g.get("prestato_a"):
                tot_ammortamenti += amm
                tot_ingaggi += stip * ((100 - g['perc_stipendio_pagato']) / 100)
            else:
                tot_ammortamenti += amm
                tot_ingaggi += stip
                
        b['costi']['ammortamenti'] = tot_ammortamenti
        b['costi']['monte_ingaggi'] = tot_ingaggi
        
        tot_ricavi = sum(b['ricavi'].values())
        tot_costi = sum(b['costi'].values())
        utile = tot_ricavi - tot_costi

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 LIQUIDITÀ (CASSA)", f"{squadra['cassa']:.2f} M")
        c2.metric("📈 Totale Ricavi", f"{tot_ricavi:.2f} M")
        c3.metric("📉 Totale Costi", f"{tot_costi:.2f} M")
        c4.metric("⚖️ Risultato (Utile/Perdita)", f"{utile:.2f} M")

        # Mettilo esattamente sotto le 4 metriche (c1, c2, c3, c4) nel Menu 2
        
        with st.expander("🔍 Dettaglio Voci di Bilancio (Live)"):
            col_ric, col_cost = st.columns(2)
            with col_ric:
                st.markdown("#### 🟢 Ricavi Attuali")
                for k, v in b['ricavi'].items():
                    if v > 0: 
                        st.write(f"- **{k.replace('_', ' ').title()}**: {v:.2f} M")
            with col_cost:
                st.markdown("#### 🔴 Costi Attuali")
                for k, v in b['costi'].items():
                    if v > 0: 
                        st.write(f"- **{k.replace('_', ' ').title()}**: {v:.2f} M")
        
        st.divider()
        
        # Filtriamo chi è in prestito altrove e chi è attivo
        rosa_attiva = [g for g in squadra['rosa'] if not g.get("prestato_a")]
        rosa_fuori = [g for g in squadra['rosa'] if g.get("prestato_a")]
        
        st.subheader(f"👥 Rosa Attiva ({len(rosa_attiva)} giocatori)")
        conteggio = {"Portiere": 0, "Difensore": 0, "Centrocampista": 0, "Attaccante": 0}
        for g in rosa_attiva: conteggio[g['ruolo']] += 1
        st.write(f"**POR:** {conteggio['Portiere']} | **DIF:** {conteggio['Difensore']} | **CEN:** {conteggio['Centrocampista']} | **ATT:** {conteggio['Attaccante']}")

        if rosa_attiva:
            df_attiva = pd.DataFrame(rosa_attiva)
            colonne_visibili = ['nome', 'ruolo', 'anni_contratto', 'costo_acquisto', 'valore_residuo', 'ammortamento_annuo', 'stipendio']
            df_display = df_attiva[colonne_visibili].copy()
            if 'in_prestito_da' in df_attiva.columns:
                df_display['In Prestito Da'] = df_attiva['in_prestito_da']
            st.dataframe(df_display, use_container_width=True)
            
        if rosa_fuori:
            st.subheader(f"✈️ Giocatori Ceduti in Prestito ({len(rosa_fuori)})")
            df_fuori = pd.DataFrame(rosa_fuori)
            df_fuori_disp = df_fuori[['nome', 'ruolo', 'prestato_a', 'valore_residuo', 'ammortamento_annuo']].copy()
            df_fuori_disp.rename(columns={'prestato_a': 'In Prestito A'}, inplace=True)
            st.dataframe(df_fuori_disp, use_container_width=True)

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
            sq_sel = st.selectbox("Squadra Operante", list(db.keys()))
            squadra = db[sq_sel]
            
            # --- 1. CREIAMO IL SEGNAPOSTO ---
            info_header = st.empty()
            # Lo riempiamo subito con i dati attuali
            info_header.write(f"💰 **Cassa:** {squadra['cassa']:.2f} MLN | 👥 **Rosa:** {len(squadra['rosa'])}/25")
            
            t1, t2, t3, t4 = st.tabs(["Acquista", "Vendi", "Svincola", "Rinnovo"])
            
            with t1:
                with st.form("buy"):
                    sessione_acq = st.radio("Sessione di Mercato", ["☀️ Estiva (Stagione Intera)", "❄️ Invernale / Gennaio (Mezza Stagione)"], horizontal=True)
                    st.divider()
                    
                    col1, col2, col3 = st.columns(3)
                    n = col1.text_input("Calciatore")
                    r = col2.selectbox("Ruolo", ["Portiere", "Difensore", "Centrocampista", "Attaccante"])
                    c = col3.number_input("Prezzo Acquisto (MLN)", min_value=1.0, step=1.0)
                    anni = st.slider("Anni Contratto", 1, 5, 3)
                    
                    s_base = 0.5 if c <= 10 else (1.5 if c <= 30 else (3.0 if c <= 60 else (5.0 if c <= 90 else 8.0)))
                    
                    is_gennaio = True if "Invernale" in sessione_acq else False
                    anni_effettivi = anni - 0.5 if is_gennaio else anni
                    amm = c / anni_effettivi if anni_effettivi > 0 else c
                    
                    if is_gennaio:
                        st.info(f"Durata Effettiva: {anni_effettivi} anni. | Stipendio Annuo Base: {s_base}M | Ammortamento Annuo Base: {amm:.2f}M.\n(Per i 6 mesi correnti pagherai la METÀ: {amm/2:.2f}M di ammortamento e {s_base/2:.2f}M di stipendio).")
                    else:
                        st.info(f"Dati Contratto: Stipendio {s_base}M | Ammortamento {amm:.2f}M annui.")
                    
                    if st.form_submit_button("Acquista"):
                        if c > squadra['cassa']: st.error("Cassa insufficiente!")
                        else:
                            giocatore = {"nome": n, "ruolo": r, "costo_acquisto": c, "anni_contratto": anni_effettivi, "stipendio": s_base, "ammortamento_annuo": amm, "anni_trascorsi": 0, "valore_residuo": c, "acquistato_a_gennaio": is_gennaio}
                            squadra['rosa'].append(giocatore)
                            squadra['cassa'] = round(squadra['cassa'] - c, 2)
                            squadra['bilancio']['storico_movimenti'].append(f"Acquisto {n}: -{c}M")
                            save_data(db, DB_PATH)
                            st.success(f"{n} acquistato!")
                            
                            # --- 2. AGGIORNIAMO IL SEGNAPOSTO ---
                            # Scriviamo i nuovi dati sopra quelli vecchi in tempo reale!
                            info_header.write(f"💰 **Cassa:** {squadra['cassa']:.2f} MLN | 👥 **Rosa:** {len(squadra['rosa'])}/25")
                            
            with t2:
                if squadra['rosa']:
                    g_vendita = st.selectbox("Seleziona da Vendere", [g['nome'] for g in squadra['rosa']], key="vendita")
                    g_obj = next(g for g in squadra['rosa'] if g['nome'] == g_vendita)
                    
                    sessione_ven = st.radio("Sessione Cessione", ["☀️ Estiva (Inizio Stagione)", "❄️ Invernale / Gennaio (Mezza Stagione)"], horizontal=True, key="sess_ven")
                    val_res_effettivo = g_obj['valore_residuo'] - (g_obj['ammortamento_annuo'] / 2) if "Invernale" in sessione_ven else g_obj['valore_residuo']
                    st.write(f"Valore Residuo Attuale: **{val_res_effettivo:.2f} M**")
                    
                    prezzo_v = st.number_input("Prezzo di Vendita", min_value=0.0, step=1.0)
                    if st.button("Vendi Definitivamente"):
                        if "Invernale" in sessione_ven:
                            squadra['bilancio']['costi']['costi_giocatori_ceduti'] += (g_obj['ammortamento_annuo'] / 2) + (g_obj['stipendio'] / 2)
                        
                        diff = prezzo_v - val_res_effettivo
                        squadra['cassa'] = round(squadra['cassa'] + prezzo_v, 2)
                        if diff > 0: squadra['bilancio']['ricavi']['plusvalenze'] += diff
                        else: squadra['bilancio']['costi']['minusvalenze'] += abs(diff)
                        
                        squadra['rosa'].remove(g_obj)
                        save_data(db, DB_PATH)
                        st.rerun()
                        
            with t3:
                if squadra['rosa']:
                    g_svincolo = st.selectbox("Seleziona da Svincolare", [g['nome'] for g in squadra['rosa']], key="svincolo")
                    g_obj_s = next(g for g in squadra['rosa'] if g['nome'] == g_svincolo)
                    
                    sessione_svin = st.radio("Sessione Svincolo", ["☀️ Estiva", "❄️ Invernale / Gennaio"], horizontal=True, key="sess_svin")
                    val_res_effettivo_s = g_obj_s['valore_residuo'] - (g_obj_s['ammortamento_annuo'] / 2) if "Invernale" in sessione_svin else g_obj_s['valore_residuo']
                    st.error(f"Svincolare azzera il valore residuo generando una minusvalenza di {val_res_effettivo_s:.2f}M.")
                    
                    if st.button("Svincola Subito"):
                        if "Invernale" in sessione_svin:
                            squadra['bilancio']['costi']['costi_giocatori_ceduti'] += (g_obj_s['ammortamento_annuo'] / 2) + (g_obj_s['stipendio'] / 2)
                        
                        squadra['bilancio']['costi']['minusvalenze'] += val_res_effettivo_s
                        squadra['rosa'].remove(g_obj_s)
                        save_data(db, DB_PATH)
                        st.success("Svincolato.")
                        st.rerun()
                        
            with t4:
                if squadra['rosa']:
                    g_rinnovo = st.selectbox("Seleziona da Rinnovare", [g['nome'] for g in squadra['rosa']], key="rinnovo")
                    g_obj_r = next(g for g in squadra['rosa'] if g['nome'] == g_rinnovo)
                    
                    if "rinnovo_prenotato" in g_obj_r:
                        st.warning(f"⏳ Attenzione: {g_obj_r['nome']} ha già firmato un pre-accordo di rinnovo di {g_obj_r['rinnovo_prenotato']['nuovi_anni']} anni per la prossima stagione.")
                    
                    st.write(f"📊 **Stipendio Attuale:** {g_obj_r['stipendio']:.3f} M | **Valore Residuo Attuale:** {g_obj_r['valore_residuo']:.2f} M")
                    st.info("📝 Il rinnovo prenota un prolungamento che scatterà DALLA PROSSIMA STAGIONE. Quest'anno il suo impatto a bilancio non cambia. Dal prossimo anno lo stipendio salirà del 15%.")
                    
                    nuovi_anni = st.slider("Nuovi Anni di Contratto dalla prossima stagione (Max 3)", 1, 3, 2, key="anni_rinnovo")
                    stipendio_futuro = g_obj_r['stipendio'] * 1.15
                    st.write(f"🔄 **Proiezione Prossimo Anno:** Stipendio {stipendio_futuro:.3f} M")
                    
                    if st.button("Firma Pre-Contratto per l'anno prossimo"):
                        g_obj_r['rinnovo_prenotato'] = {"nuovi_anni": nuovi_anni}
                        save_data(db, DB_PATH)
                        st.success(f"Contratto di {g_obj_r['nome']} prenotato! L'accordo entrerà in vigore alla chiusura del bilancio.")
                        st.rerun()

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
            sq_cedente = c1.selectbox("Società Cedente (Proprietaria)", list(db.keys()))
            sq_acquirente = c2.selectbox("Società Acquirente (Chi riceve)", [s for s in db.keys() if s != sq_cedente])
            
            rosa_cedente = [g for g in db[sq_cedente]['rosa'] if not g.get("prestato_a")]
            if not rosa_cedente: st.info("Nessun giocatore disponibile.")
            else:
                g_prestito = st.selectbox("Calciatore da prestare", [g['nome'] for g in rosa_cedente])
                g_obj = next(g for g in rosa_cedente if g['nome'] == g_prestito)
                
                st.markdown("### 📝 Dettagli Contratto di Prestito")
                col_dur, col_stip = st.columns(2)
                durata_prestito = col_dur.slider("Durata Prestito (Anni)", 1, 2, 1)
                perc_stipendio = col_stip.slider("% Stipendio a carico dell'Acquirente", 0, 100, 50, step=10)
                
                col_on, col_tipo, col_cifra = st.columns(3)
                costo_prestito = col_on.number_input("Costo Prestito (Oneroso in MLN)", min_value=0.0, step=0.5, value=0.0)
                tipo_accordo = col_tipo.selectbox("Tipo di Accordo", ["Prestito Secco", "Diritto di Riscatto", "Obbligo di Riscatto"])
                
                cifra_riscatto = 0.0
                if tipo_accordo != "Prestito Secco":
                    cifra_riscatto = col_cifra.number_input("Cifra Riscatto Pattuita (MLN)", min_value=1.0, step=1.0, value=10.0)
                
                if st.button("Ufficializza Prestito"):
                    if costo_prestito > db[sq_acquirente]['cassa']:
                        st.error("Cassa acquirente insufficiente per il prestito oneroso!")
                    else:
                        if len(db[sq_acquirente]['rosa']) >= 25: st.error("Rosa acquirente piena!")
                        elif costo_prestito > db[sq_acquirente]['cassa']: st.error("Cassa acquirente insufficiente per il prestito oneroso!")
                        else:
                            g_acq = g_obj.copy()
                            g_acq['in_prestito_da'], g_acq['perc_stipendio_pagato'] = sq_cedente, perc_stipendio
                            g_acq['accordo_riscatto'] = {"tipo": tipo_accordo, "cifra": cifra_riscatto}
                            g_acq['anni_prestito_rimanenti'] = durata_prestito
                            db[sq_acquirente]['rosa'].append(g_acq)
                            
                            g_obj['prestato_a'], g_obj['perc_stipendio_pagato'] = sq_acquirente, perc_stipendio
                            g_obj['accordo_riscatto'] = {"tipo": tipo_accordo, "cifra": cifra_riscatto}
                            g_obj['anni_prestito_rimanenti'] = durata_prestito
                            
                            if costo_prestito > 0:
                                db[sq_acquirente]['cassa'] = round(db[sq_acquirente]['cassa'] - costo_prestito, 2)
                                db[sq_cedente]['cassa'] = round(db[sq_cedente]['cassa'] + costo_prestito, 2)
                                db[sq_cedente]['bilancio']['ricavi']['plusvalenze'] += costo_prestito
                                db[sq_acquirente]['bilancio']['costi']['minusvalenze'] += costo_prestito
                                
                            save_data(db, DB_PATH)
                            st.success(f"Prestito di {durata_prestito} anno/i registrato con successo!")
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
                        st.success("Riscatto prenotato! L'operazione sarà contabilizzata nel bilancio della prossima stagione.")
                        st.rerun()

# ==========================================
# 5. CALENDARIO E PARTITE
# ==========================================
elif menu == "5. Calendario & Partite":
    st.header("🗓️ Calendario")
    
    if len(db) != 8:
        st.error(f"Per generare il calendario servono 8 squadre. Attualmente ce ne sono {len(db)}.")
    else:
        if not calendario:
            if st.button("🚀 Genera Calendario Ufficiale", type="primary"):
                calendario = genera_calendario_berger(list(db.keys()))
                save_data(calendario, CAL_PATH)
                st.success("Calendario generato con successo!")
                st.rerun()
        
        if calendario:
            giornata_idx = st.selectbox("Seleziona Giornata", range(1, 39)) - 1
            giornata_dati = calendario[giornata_idx]
            
            st.subheader(f"Partite Giornata {giornata_idx + 1}")
            
            with st.form(f"giornata_{giornata_idx}"):
                for idx, match in enumerate(giornata_dati):
                    c1, c2, c3, c4, c5 = st.columns([3, 1, 0.5, 1, 3])
                    c1.markdown(f"<h5 style='text-align: right'>{match['home']}</h5>", unsafe_allow_html=True)
                    gol_h = c2.number_input("", min_value=0, value=match["gol_home"], key=f"h_{idx}", disabled=not st.session_state.is_admin)
                    c3.markdown("<h4 style='text-align: center'>-</h4>", unsafe_allow_html=True)
                    gol_a = c4.number_input("", min_value=0, value=match["gol_away"], key=f"a_{idx}", disabled=not st.session_state.is_admin)
                    c5.markdown(f"<h5>{match['away']}</h5>", unsafe_allow_html=True)

                if st.session_state.is_admin:
                    if st.form_submit_button("Salva Risultati & Assegna Incassi"):
                        gol_map = {}
                        for idx, match in enumerate(giornata_dati):
                            gh = st.session_state[f"h_{idx}"]
                            ga = st.session_state[f"a_{idx}"]
                            match["gol_home"], match["gol_away"], match["giocata"] = gh, ga, True
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
                        save_data(coppe, COPPE_PATH)
                        st.success("Risultati salvati! (Incassi stadio e dati Coppe aggiornati in automatico)")

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
        st.dataframe(df_c.style.highlight_max(subset=['Punti'], color='lightgreen'), use_container_width=True)
        
        st.divider()
        if st.button("Distribuisci Premi Campionato & Sponsor (Solo a fine anno)"):
            squadre_ordinate = df_c.index.tolist()
            premi_sponsor = [50.0, 46.0, 42.0, 38.0, 35.0, 32.0, 30.0, 30.0]
            premi_campionato = [35.0, 36.0, 38.0, 40.0, 43.0, 45.0, 48.0, 50.0]
            for pos, nome_sq in enumerate(squadre_ordinate):
                team = db[nome_sq]
                p_spons = premi_sponsor[pos]
                p_camp = premi_campionato[pos]
                
                # 1. PREMIO CAMPIONATO: Entra ORA in Cassa e Bilancio corrente
                team['cassa'] = round(team['cassa'] + p_camp, 2)
                team['bilancio']['ricavi']['premi_sportivi'] += p_camp
                team['bilancio']['storico_movimenti'].append(f"Premio Campionato ({pos+1}°): +{p_camp}M")
                
                # 2. PREMIO SPONSOR: Viene solo "prenotato" per la prossima stagione
                team['sponsor_prenotato'] = p_spons
                
            save_data(db, DB_PATH)
            st.success("Premi Campionato erogati! I contratti Sponsor per l'anno prossimo sono stati prenotati.")

# ==========================================
# 7. COPPE UFFICIALI
# ==========================================
elif menu == "7. Coppe (Italia & CL)":
    st.header("🏆 Gestione Coppe")
    
    t_ci, t_cl = st.tabs(["🇮🇹 Coppa Italia", "🇪🇺 Champions League"])
    
    # ---------------- COPPA ITALIA ----------------
    with t_ci:
        st.subheader("Tabellone Coppa Italia")
        if not coppe["ci"]["quarti"]:
            if st.session_state.is_admin and st.button("Sorteggia Tabellone Quarti"):
                teams = list(db.keys())
                random.shuffle(teams)
                coppe["ci"]["quarti"] = [{"home": teams[i], "away": teams[i+1], "gol_home": 0, "gol_away": 0, "vincente": teams[i]} for i in range(0, 8, 2)]
                save_data(coppe, COPPE_PATH)
                st.rerun()
        
        if coppe["ci"]["quarti"]:
            st.write("🔴 **Quarti di Finale**")
            for i, m in enumerate(coppe["ci"]["quarti"]):
                c1, c2, c3, c4 = st.columns([2,1,1,2])
                c1.write(m['home'])
                m['gol_home'] = c2.number_input("Gol H", value=m.get('gol_home',0), key=f"ci_q_h_{i}", disabled=not st.session_state.is_admin)
                m['gol_away'] = c3.number_input("Gol A", value=m.get('gol_away',0), key=f"ci_q_a_{i}", disabled=not st.session_state.is_admin)
                m['vincente'] = c4.selectbox("Passa il turno:", [m['home'], m['away']], index=0 if m.get('vincente')==m['home'] else 1, key=f"ci_q_v_{i}", disabled=not st.session_state.is_admin)
            
            if st.session_state.is_admin:
                if st.button("Salva Risultati Quarti CI"): save_data(coppe, COPPE_PATH); st.success("Salvati!")
                if not coppe["ci"]["semis"] and st.button("Genera Semifinali"):
                    vincitori = [m['vincente'] for m in coppe["ci"]["quarti"]]
                    coppe["ci"]["semis"] = [{"home": vincitori[0], "away": vincitori[1], "gol_home": 0, "gol_away": 0, "vincente": vincitori[0]}, {"home": vincitori[2], "away": vincitori[3], "gol_home": 0, "gol_away": 0, "vincente": vincitori[2]}]
                    save_data(coppe, COPPE_PATH)
                    st.rerun()

        if coppe["ci"]["semis"]:
            st.divider()
            st.write("🟡 **Semifinali**")
            for i, m in enumerate(coppe["ci"]["semis"]):
                c1, c2, c3, c4 = st.columns([2,1,1,2])
                c1.write(m['home'])
                m['gol_home'] = c2.number_input("Gol H", value=m.get('gol_home',0), key=f"ci_s_h_{i}", disabled=not st.session_state.is_admin)
                m['gol_away'] = c3.number_input("Gol A", value=m.get('gol_away',0), key=f"ci_s_a_{i}", disabled=not st.session_state.is_admin)
                m['vincente'] = c4.selectbox("Passa in Finale:", [m['home'], m['away']], index=0 if m.get('vincente')==m['home'] else 1, key=f"ci_s_v_{i}", disabled=not st.session_state.is_admin)
            
            if st.session_state.is_admin:
                if st.button("Salva Risultati Semifinali CI"): save_data(coppe, COPPE_PATH); st.success("Salvati!")
                if not coppe["ci"]["finale"] and st.button("Genera Finale"):
                    vincitori = [m['vincente'] for m in coppe["ci"]["semis"]]
                    perdenti = [m['home'] if m['vincente']==m['away'] else m['away'] for m in coppe["ci"]["semis"]]
                    coppe["ci"]["finale"] = [{"home": vincitori[0], "away": vincitori[1], "gol_home": 0, "gol_away": 0, "vincente": vincitori[0]}]
                    coppe["ci"]["perse_semis"] = perdenti
                    save_data(coppe, COPPE_PATH)
                    st.rerun()
                
        if coppe["ci"]["finale"]:
            st.divider()
            st.write("🟢 **Finale**")
            m = coppe["ci"]["finale"][0]
            c1, c2, c3, c4 = st.columns([2,1,1,2])
            c1.write(m['home'])
            m['gol_home'] = c2.number_input("Gol H", value=m.get('gol_home',0), key="ci_f_h", disabled=not st.session_state.is_admin)
            m['gol_away'] = c3.number_input("Gol A", value=m.get('gol_away',0), key="ci_f_a", disabled=not st.session_state.is_admin)
            m['vincente'] = c4.selectbox("VINCITORE:", [m['home'], m['away']], index=0 if m.get('vincente')==m['home'] else 1, key="ci_f_v", disabled=not st.session_state.is_admin)
            
            if st.session_state.is_admin:
                if st.button("Salva Risultato Finale CI"): save_data(coppe, COPPE_PATH); st.success("Salvato!")
                st.divider()
                if not coppe["ci"]["premi_dati"] and st.button("🏆 Eroga Premi Coppa Italia (Bilancio e Cassa)", type="primary"):
                    vincente = m['vincente']
                    perdente = m['home'] if vincente == m['away'] else m['away']
                    db[vincente]['bilancio']['ricavi']['premi_sportivi'] += 25.0
                    db[vincente]['cassa'] += 25.0
                    db[perdente]['bilancio']['ricavi']['premi_sportivi'] += 15.0
                    db[perdente]['cassa'] += 15.0
                    for sq in coppe["ci"]["perse_semis"]: 
                        db[sq]['bilancio']['ricavi']['premi_sportivi'] += 5.0
                        db[sq]['cassa'] += 5.0
                    coppe["ci"]["premi_dati"] = True
                    save_data(db, DB_PATH); save_data(coppe, COPPE_PATH)
                    st.success("Premi Coppa Italia distribuiti!")

    # ---------------- CHAMPIONS LEAGUE ----------------
    with t_cl:
        st.subheader("Champions League")
        if not coppe["cl"]["gir_A"]:
            if st.session_state.is_admin and st.button("Sorteggia Gironi CL"):
                teams = list(db.keys())
                random.shuffle(teams)
                coppe["cl"]["gir_A"] = teams[:4]
                coppe["cl"]["gir_B"] = teams[4:]
                coppe["cl"]["punti_A"] = {t: 0 for t in teams[:4]}
                coppe["cl"]["punti_B"] = {t: 0 for t in teams[4:]}
                save_data(coppe, COPPE_PATH)
                st.rerun()
                
        if coppe["cl"]["gir_A"]:
            st.write("Fase a Gironi (Classifica Manuale)")
            if "punti_A" not in coppe["cl"]: coppe["cl"]["punti_A"] = {t: 0 for t in coppe["cl"]["gir_A"]}
            if "punti_B" not in coppe["cl"]: coppe["cl"]["punti_B"] = {t: 0 for t in coppe["cl"]["gir_B"]}

            colA, colB = st.columns(2)
            
            with colA:
                st.write("**Girone A**")
                for t in coppe["cl"]["gir_A"]:
                    coppe["cl"]["punti_A"][t] = st.number_input(f"Punti {t}", value=coppe["cl"]["punti_A"].get(t,0), key=f"pa_{t}", disabled=not st.session_state.is_admin)
                df_A = pd.DataFrame(list(coppe["cl"]["punti_A"].items()), columns=["Squadra", "Punti"]).sort_values(by="Punti", ascending=False)
                st.dataframe(df_A, hide_index=True)
            
            with colB:
                st.write("**Girone B**")
                for t in coppe["cl"]["gir_B"]:
                    coppe["cl"]["punti_B"][t] = st.number_input(f"Punti {t}", value=coppe["cl"]["punti_B"].get(t,0), key=f"pb_{t}", disabled=not st.session_state.is_admin)
                df_B = pd.DataFrame(list(coppe["cl"]["punti_B"].items()), columns=["Squadra", "Punti"]).sort_values(by="Punti", ascending=False)
                st.dataframe(df_B, hide_index=True)

            if st.session_state.is_admin:
                if st.button("Salva Punti Gironi CL"): save_data(coppe, COPPE_PATH); st.success("Punti Salvati!")
                if not coppe["cl"]["semis_andata"] and st.button("Genera Semifinali CL"):
                    a1, a2 = df_A.iloc[0]["Squadra"], df_A.iloc[1]["Squadra"]
                    b1, b2 = df_B.iloc[0]["Squadra"], df_B.iloc[1]["Squadra"]
                    coppe["cl"]["semis_andata"] = [{"home": a1, "away": b2, "gol_home": 0, "gol_away": 0}, {"home": b1, "away": a2, "gol_home": 0, "gol_away": 0}]
                    coppe["cl"]["semis_ritorno"] = [{"home": b2, "away": a1, "gol_home": 0, "gol_away": 0, "vincente": a1}, {"home": a2, "away": b1, "gol_home": 0, "gol_away": 0, "vincente": b1}]
                    save_data(coppe, COPPE_PATH)
                    st.rerun()

        if coppe["cl"]["semis_andata"]:
            st.divider()
            st.write("🟡 **Semifinali (Andata e Ritorno)**")
            for i in range(2):
                ma = coppe["cl"]["semis_andata"][i]
                mr = coppe["cl"]["semis_ritorno"][i]
                st.write(f"**{ma['home']} vs {ma['away']}**")
                c1, c2, c3, c4, c5 = st.columns(5)
                ma['gol_home'] = c1.number_input(f"And. {ma['home']}", value=ma.get('gol_home',0), key=f"cl_s_ah_{i}", disabled=not st.session_state.is_admin)
                ma['gol_away'] = c2.number_input(f"And. {ma['away']}", value=ma.get('gol_away',0), key=f"cl_s_aa_{i}", disabled=not st.session_state.is_admin)
                mr['gol_home'] = c3.number_input(f"Rit. {mr['home']}", value=mr.get('gol_home',0), key=f"cl_s_rh_{i}", disabled=not st.session_state.is_admin)
                mr['gol_away'] = c4.number_input(f"Rit. {mr['away']}", value=mr.get('gol_away',0), key=f"cl_s_ra_{i}", disabled=not st.session_state.is_admin)
                mr['vincente'] = c5.selectbox("Passa in Finale:", [ma['home'], ma['away']], index=0 if mr.get('vincente')==ma['home'] else 1, key=f"cl_s_v_{i}", disabled=not st.session_state.is_admin)
            
            if st.session_state.is_admin:
                if st.button("Salva Risultati Semifinali CL"): save_data(coppe, COPPE_PATH); st.success("Salvati!")
                if not coppe["cl"]["finale"] and st.button("Genera Finale CL"):
                    vincitori = [m['vincente'] for m in coppe["cl"]["semis_ritorno"]]
                    perdenti = [m['home'] if m['vincente']==m['away'] else m['away'] for m in coppe["cl"]["semis_ritorno"]]
                    coppe["cl"]["finale"] = [{"home": vincitori[0], "away": vincitori[1], "gol_home": 0, "gol_away": 0, "vincente": vincitori[0]}]
                    coppe["cl"]["perse_semis"] = perdenti
                    save_data(coppe, COPPE_PATH)
                    st.rerun()
                
        if coppe["cl"]["finale"]:
            st.divider()
            st.write("🟢 **Finale**")
            m = coppe["cl"]["finale"][0]
            c1, c2, c3, c4 = st.columns([2,1,1,2])
            c1.write(m['home'])
            m['gol_home'] = c2.number_input("Gol H", value=m.get('gol_home',0), key="cl_f_h", disabled=not st.session_state.is_admin)
            m['gol_away'] = c3.number_input("Gol A", value=m.get('gol_away',0), key="cl_f_a", disabled=not st.session_state.is_admin)
            m['vincente'] = c4.selectbox("VINCITORE CL:", [m['home'], m['away']], index=0 if m.get('vincente')==m['home'] else 1, key="cl_f_v", disabled=not st.session_state.is_admin)
            
            if st.session_state.is_admin:
                if st.button("Salva Risultato Finale CL"): save_data(coppe, COPPE_PATH); st.success("Salvato!")
                st.divider()
                if not coppe["cl"]["premi_dati"] and st.button("🏆 Eroga Premi Champions (Bilancio e Cassa)", type="primary"):
                    vincente = m['vincente']
                    perdente = m['home'] if vincente == m['away'] else m['away']
                    db[vincente]['bilancio']['ricavi']['premi_sportivi'] += 35.0
                    db[vincente]['cassa'] += 35.0
                    db[perdente]['bilancio']['ricavi']['premi_sportivi'] += 25.0
                    db[perdente]['cassa'] += 25.0
                    for sq in coppe["cl"]["perse_semis"]: 
                        db[sq]['bilancio']['ricavi']['premi_sportivi'] += 15.0
                        db[sq]['cassa'] += 15.0
                    coppe["cl"]["premi_dati"] = True
                    save_data(db, DB_PATH); save_data(coppe, COPPE_PATH)
                    st.success("Premi Champions League distribuiti!")

# ==========================================
# 8. CHIUSURA FISCALE
# ==========================================
elif menu == "8. Chiusura Fiscale Bilancio":
    st.header("📜 Chiusura Fiscale")
    
    # --- ZONA PROTETTA (SOLO ADMIN PUÒ CHIUDERE L'ANNO) ---
    if not st.session_state.is_admin:
        st.info("🔒 L'esecuzione della chiusura fiscale è riservata all'Amministratore.")
    else:
        st.warning("Attenzione: Da fare SOLO una volta finite tutte le aste, le competizioni e distribuiti i premi!")
        
        if st.button("ESEGUI CHIUSURA BILANCIO PER TUTTE LE SQUADRE", type="primary"):
            for sq, dati in db.items():
                b = dati['bilancio']
                tot_ammortamenti, tot_ingaggi = 0.0, 0.0
                for g in dati['rosa']:
                    amm = g['ammortamento_annuo']
                    stip = g['stipendio']
                    if g.get('acquistato_a_gennaio') and g['anni_trascorsi'] == 0:
                        amm /= 2; stip /= 2
                        
                    if not g.get("in_prestito_da"): 
                        tot_ammortamenti += amm
                        if g.get("prestato_a"): tot_ingaggi += stip * ((100 - g['perc_stipendio_pagato']) / 100)
                        else: tot_ingaggi += stip
                    else: tot_ingaggi += stip * (g['perc_stipendio_pagato'] / 100)
                        
                b['costi']['ammortamenti'] = round(tot_ammortamenti, 2)
                b['costi']['monte_ingaggi'] = round(tot_ingaggi, 2)
                
                costo_stadio = b['costi']['gestione_stadio']
                dati['cassa'] = round(dati['cassa'] - (tot_ingaggi + costo_stadio), 2)
                
                utile = round(sum(b['ricavi'].values()) - sum(b['costi'].values()), 2)
                
                if utile < 0:
                    dati['cassa'] += utile  
                
                dati['ultimo_bilancio_chiuso'] = {
                    "ricavi": {k: round(v, 2) for k, v in dati['bilancio']['ricavi'].items()},
                    "costi": {k: round(v, 2) for k, v in dati['bilancio']['costi'].items()},
                    "utile": utile,
                    "cassa_partenza_nuovo_anno": dati['cassa']
                }
                
                # 1. AZZERAMENTO BILANCIO: Chiudiamo l'anno vecchio, apriamo l'anno nuovo
                dati['bilancio'] = init_bilancio()
                
                # --- 1.5 INIEZIONE DI CAPITALE NUOVO ANNO (Diritti TV + Sponsor Prenotato) ---
                # Inietta 50 Milioni freschi in CASSA per fare mercato
                dati['cassa'] += 50.0
                # E li registra regolarmente nei RICAVI della nuova stagione
                dati['bilancio']['ricavi']['nuovo_capitale'] = 50.0
                dati['bilancio']['storico_movimenti'].append("Iniezione Nuovo Capitale: +50.0M (Cassa e Ricavi)")
                
                # Eroga lo Sponsor calcolato alla fine della stagione precedente!
                # (Se non c'è una prenotazione - ovvero il 1° anno - eroga 0.0)
                sponsor_nuovo = dati.get('sponsor_prenotato', 0.0)
                if sponsor_nuovo > 0:
                    dati['cassa'] += sponsor_nuovo
                    dati['bilancio']['ricavi']['sponsor'] = sponsor_nuovo
                    dati['bilancio']['storico_movimenti'].append(f"Accordo Sponsor Annuale: +{sponsor_nuovo}M")
                    del dati['sponsor_prenotato'] # Rimuove la prenotazione dopo l'erogazione
                
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
                            g['stipendio'] = 0.5 if prezzo_r <= 10 else (1.5 if prezzo_r <= 30 else (3.0 if prezzo_r <= 60 else (5.0 if prezzo_r <= 90 else 8.0)))
                            g['anni_trascorsi'] = 0
                            nuova_rosa.append(g)
                        else:
                            g['anni_prestito_rimanenti'] -= 1
                            if g['anni_prestito_rimanenti'] > 0:
                                nuova_rosa.append(g) 
                    elif g.get("prestato_a"):
                        if "riscatto_prenotato" in g:
                            prezzo_r = g['riscatto_prenotato']['cifra']
                            dati['cassa'] += prezzo_r
                            diff = prezzo_r - g['valore_residuo']
                            if diff > 0: dati['bilancio']['ricavi']['plusvalenze'] += diff
                            else: dati['bilancio']['costi']['minusvalenze'] += abs(diff)
                        else:
                            amm = g['ammortamento_annuo']
                            g['valore_residuo'] = max(0, g['valore_residuo'] - amm)
                            g['anni_trascorsi'] += 1
                            g['anni_prestito_rimanenti'] -= 1
                            if g['anni_prestito_rimanenti'] > 0:
                                nuova_rosa.append(g) 
                            else:
                                del g['prestato_a']
                                if 'perc_stipendio_pagato' in g: del g['perc_stipendio_pagato']
                                if 'accordo_riscatto' in g: del g['accordo_riscatto']
                                if 'anni_prestito_rimanenti' in g: del g['anni_prestito_rimanenti']
                                nuova_rosa.append(g)
                    else:
                        amm = g['ammortamento_annuo']
                        if g.get('acquistato_a_gennaio') and g['anni_trascorsi'] == 0: amm /= 2
                        g['valore_residuo'] = max(0, g['valore_residuo'] - amm)
                        g['anni_trascorsi'] += 1
                        
                        if "rinnovo_prenotato" in g:
                            g['stipendio'] *= 1.15
                            g['anni_contratto'] = g['rinnovo_prenotato']['nuovi_anni']
                            g['costo_acquisto'] = g['valore_residuo']
                            g['ammortamento_annuo'] = g['valore_residuo'] / g['anni_contratto'] if g['anni_contratto'] > 0 else 0
                            g['anni_trascorsi'] = 0
                            del g['rinnovo_prenotato']
                            nuova_rosa.append(g)
                        elif g['anni_trascorsi'] < g['anni_contratto']:
                            nuova_rosa.append(g)
                dati['rosa'] = nuova_rosa 
                
            save_data(db, DB_PATH)
            st.success("✅ Chiusura Fiscale Completata! Bilanci azzerati, contratti scaduti rimossi, prestiti e riscatti processati per la nuova stagione.")
            st.balloons()


    # --- ZONA LIBERA (PROSPETTO VISIBILE A TUTTI GLI UTENTI) ---
    st.divider()
    st.subheader("📊 Prospetto Finanziario Stagione Precedente")
    
    # Controlla se c'è almeno una squadra che ha uno storico salvato
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
# 9. REGOLAMENTO UFFICIALE
# ==========================================
elif menu == "9. Regolamento Ufficiale":
    st.title("⚽ Osei Football League")
    st.header("Regolamento Ufficiale Manageriale")
    st.caption("A cura della Direzione Osei")
    st.divider()

    # SECTION 1
    st.subheader("1. Disposizioni Generali e Principi Contabili")
    st.markdown("""
    Il presente regolamento disciplina l'organizzazione e la gestione sportivo-finanziaria delle società appartenenti alla Osei Football League. Il sistema manageriale impone il rigoroso rispetto dei vincoli economici, strutturati sulla netta separazione tra due principi contabili fondamentali:

    * **La Liquidità (Cassa):** Rappresenta il capitale circolante a disposizione della società per effettuare transazioni immediate (es. rilanci d'asta, offerte di mercato). Le variazioni di liquidità si registrano contestualmente al momento dell'esborso o dell'incasso reale. I fondi in cassa non si azzerano mai a fine anno.
    * **Il Bilancio d'Esercizio:** Rappresenta il documento contabile di fine stagione che riepiloga i Costi e i Ricavi imputabili al singolo anno sportivo, al fine di determinare il risultato d'esercizio (Utile o Perdita) e valutare il rispetto del Fair Play Finanziario. Il Bilancio viene azzerato al termine di ogni stagione sportiva.
    
    ### 1.1 Capitale Sociale Iniziale (Anno 1)
    All'atto della costituzione, la Direzione provvede all'assegnazione di un fondo di dotazione iniziale pari a **350 milioni di fantaeuro** per ciascuna società. Tale somma costituisce la Liquidità (Cassa) di partenza per le operazioni di mercato della prima finestra estiva. 

    **Nota Contabile:** Al fine di non alterare i parametri del Fair Play Finanziario, tale somma iniziale transita **esclusivamente nella Cassa reale** e non concorre in alcun modo a formare il Valore della Produzione (Ricavi) del primo Bilancio d'Esercizio.
    """)

    st.divider()
    
    # SECTION 2
    st.subheader("2. Infrastrutture e Sponsorizzazioni Commerciali")
    st.markdown("""
    All'apertura di ogni stagione, le società devono strutturare le proprie fondamenta commerciali scegliendo l'impianto sportivo e registrando il Main Sponsor.
    
    ### 2.1 Impianti Sportivi
    Ciascuna società ha l'obbligo di selezionare la capienza del proprio impianto sportivo. Da tale scelta derivano specifici oneri fissi di gestione (da imputare nei Costi di Bilancio) e proventi legati ai risultati delle partite disputate in casa (da imputare immediatamente in Cassa e nei Ricavi di Bilancio):
    * **Impianto di 1ª Categoria (20.000 posti):**
      * Costo fisso annuo: **5 milioni**
      * Incasso base per partita: **0.1 milioni**
      * Incasso totale in caso di pareggio: **0.2 milioni**
      * Incasso totale in caso di vittoria: **0.4 milioni**
    * **Impianto di 2ª Categoria (50.000 posti):**
      * Costo fisso annuo: **12 milioni**
      * Incasso base per partita: **0.3 milioni**
      * Incasso totale in caso di pareggio: **0.5 milioni**
      * Incasso totale in caso di vittoria: **0.9 milioni**
    * **Impianto di 3ª Categoria (80.000 posti):**
      * Costo fisso annuo: **20 milioni**
      * Incasso base per partita: **0.6 milioni**
      * Incasso totale in caso di pareggio: **1.0 milioni**
      * Incasso totale in caso di vittoria: **1.5 milioni**
    
    ### 2.2 Sponsorizzazioni Commerciali
    Ciascuna società ha diritto alla sottoscrizione di un accordo di Main Sponsorship (scelta del nome commerciale). Per la primissima stagione di fondazione della Lega, al fine di garantire l'operatività e la sostenibilità iniziale, tutte le società percepiscono una quota fissa d'ingresso pari a **30 milioni**. 

    A partire dalla seconda stagione, l'importo erogato all'inizio di ogni anno sportivo è calcolato esclusivamente in base al piazzamento ottenuto nella classifica generale della stagione antecedente:
    * **1ª Classificata:** 50 milioni
    * **2ª Classificata:** 46 milioni
    * **3ª Classificata:** 42 milioni
    * **4ª Classificata:** 38 milioni
    * **5ª Classificata:** 35 milioni
    * **6ª Classificata:** 32 milioni
    * **7ª Classificata:** 30 milioni
    * **8ª Classificata:** 30 milioni
    """)

    st.divider()

    # SECTION 3
    st.subheader("3. Gestione Sportiva: Composizione della Rosa e Contratti")
    st.markdown("""
    ### 3.1 Limiti e Composizione della Rosa
    L'organico ufficiale di ciascuna società deve essere composto da un numero inderogabile di **25 calciatori**. Non sono ammessi posti vacanti né tesseramenti in esubero. La ripartizione per ruoli è vincolante ed è fissata a: **3 portieri, 8 difensori, 8 centrocampisti e 6 attaccanti**.

    ### 3.2 Vincoli Contrattuali e Compensi
    L'acquisizione di un calciatore comporta la contestuale stipula di un contratto di prestazione sportiva di durata compresa tra 1 e 5 anni. Tutti i contratti iniziano l'1 Gennaio oppure l'1 Luglio di ogni anno e terminano tutti il 30 Giugno. Il compenso annuale (Stipendio) costituisce un costo d'esercizio ricorrente, ed è parametrato al costo storico del cartellino:
    * Costo d'acquisto da 1 a 10 milioni: Stipendio annuale di **0.5 milioni**
    * Costo d'acquisto da 11 a 30 milioni: Stipendio annuale di **1.5 milioni**
    * Costo d'acquisto da 31 a 60 milioni: Stipendio annuale di **3.0 milioni**
    * Costo d'acquisto da 61 a 90 milioni: Stipendio annuale di **5.0 milioni**
    * Costo d'acquisto da 91 milioni in su: Stipendio annuale di **8.0 milioni**
    
    Eventuali rinnovi contrattuali, da formalizzarsi prima della naturale scadenza (ovvero prima del 30 Giugno dell'ultimo anno di contratto), comportano un adeguamento salariale obbligatorio pari al +15% dello stipendio in essere.
    """)

    st.divider()

    # SECTION 4
    st.subheader("4. Operazioni di Mercato e Imputazioni Contabili")
    st.markdown("""
    ### 4.1 Acquisizione a Titolo Definitivo di un Calciatore
    L'acquisizione dei diritti alle prestazioni sportive di un calciatore genera i seguenti effetti:
    1. **Sotto il profilo della Liquidità (Cassa):** Il corrispettivo d'acquisto viene detratto integralmente e istantaneamente dal saldo disponibile.
    2. **Sotto il profilo Economico (Bilancio):** Il costo storico non incide interamente sull'esercizio in corso. Ai costi d'esercizio vengono imputati esclusivamente lo Stipendio annuale e la **Quota di Ammortamento** (pari al costo storico diviso per gli anni di contratto stipulati).
    """)
    st.info("""**Esempio Pratico: Acquisizione**  
    La società si aggiudica il *Calciatore X* per **40 milioni**, siglando un contratto quadriennale (4 anni).
    * **Impatto sulla Cassa:** Decremento immediato di 40 milioni.
    * **Impatto a Bilancio (per ogni anno):** Iscrizione nei Costi di **10 milioni** di ammortamento (40 / 4) e di **3.0 milioni** di stipendio.""")
    
    st.markdown("""
    ### 4.2 Acquisti in Sessione Invernale (Gennaio)
    Le operazioni di mercato concluse durante la sessione di Gennaio sono soggette a un trattamento contabile specifico, volto a riflettere l'utilizzo del calciatore per il solo girone di ritorno (6 mesi).
    1. **Durata Contrattuale:** Al fine di garantire la naturale scadenza dei contratti al 30 giugno, la durata sottoscritta in fase di acquisto viene decurtata di 0.5 stagioni. (Esempio: un contratto stipulato per 2 anni durante la sessione invernale ha una durata effettiva di 1.5 stagioni).
    2. **Impatto a Bilancio (Pro-quota):** Per la stagione in corso (sessione invernale), l'ammortamento del cartellino e lo stipendio lordo vengono calcolati al 50% del valore annuale, riflettendo la maturazione economica dei costi per il solo semestre di competenza.
    3. **Valore Residuo:** Il Valore Residuo a bilancio viene aggiornato sottraendo esclusivamente la quota di ammortamento maturata nel semestre di permanenza.
    4. **Cessioni a Gennaio:** In caso di cessione di un calciatore a Gennaio, la società cedente ha l'obbligo di iscrivere a bilancio la quota di ammortamento e lo stipendio relativi al semestre di permanenza (luglio-dicembre), garantendo così che la società sostenga i costi solo per il periodo in cui ha effettivamente utilizzato il calciatore.
    
    ### 4.3 Cessione a Titolo Definitivo e Rilevazione di Plusvalenze/Minusvalenze
    Il **Valore Residuo** di un calciatore è il valore patrimoniale netto del cartellino, calcolato sottraendo dal costo storico gli ammortamenti già contabilizzati negli esercizi precedenti. La cessione di un tesserato genera:
    1. **Sotto il profilo della Liquidità (Cassa):** Accredito istantaneo del corrispettivo pattuito per la vendita.
    2. **Sotto il profilo Economico (Bilancio):** L'interruzione degli oneri futuri (ammortamento e stipendio non ancora maturati) e la rilevazione nel Bilancio dell'anno in corso di una **Plusvalenza** (se il prezzo di vendita è superiore al Valore Residuo) o di una **Minusvalenza** (se il prezzo di vendita è inferiore al Valore Residuo).
    """)
    st.info("""**Esempio Pratico: Cessione**  
    Il *Calciatore X* (costo storico 40M per 4 anni) è ceduto al termine del secondo anno. L'ammortamento cumulato è pari a 20M. Il suo **Valore Residuo è pari a 20 milioni**. La cessione avviene per **35 milioni**.
    * **Impatto sulla Cassa:** Incremento immediato di 35 milioni.
    * **Impatto a Bilancio:** Iscrizione nei Ricavi di una **Plusvalenza pari a 15 milioni** (35 - 20). Annullamento degli oneri per gli esercizi futuri.""")

    st.markdown("""
    ### 4.4 Risoluzione Anticipata e Scadenza Naturale del Contratto
    L'interruzione anticipata del vincolo contrattuale senza contropartita economica (svincolo) determina l'azzeramento del valore patrimoniale del calciatore.
    * **Impatto sulla Cassa:** Nessun introito (variazione nulla).
    * **Impatto a Bilancio:** Iscrizione nei Costi d'esercizio di una **Minusvalenza totale**, di importo pari all'intero Valore Residuo del tesserato al momento dello svincolo.

    **Scadenza Naturale del Vincolo (Parametro Zero):**  
    Al termine della durata contrattuale pattuita, qualora non sia intervenuto alcun accordo di rinnovo, il vincolo sportivo decade in via automatica all'atto della Chiusura Fiscale di fine stagione. Il calciatore viene rimosso dalla rosa a parametro zero. Tale evento **non genera alcuna minusvalenza**, in quanto l'ammortamento del costo storico è giunto a naturale esaurimento (il Valore Residuo è pari a zero). La società beneficerà unicamente dello sgravio a bilancio del relativo onere salariale (stipendio) per gli esercizi futuri.

    ### 4.5 Trasferimenti a Titolo Temporaneo (Prestiti)
    Le società hanno facoltà di negoziare la cessione a titolo temporaneo dei diritti alle prestazioni sportive di un tesserato per una durata predefinita di **1 o 2 stagioni sportive**. I trasferimenti temporanei possono configurarsi in tre tipologie: **prestito secco**, **prestito con diritto di riscatto** e **prestito con obbligo di riscatto** (subordinato o meno al verificarsi di determinate condizioni sportive).

    **Prestito Oneroso e Impatto Contabile Immediato:**  
    Le società possono pattuire un corrispettivo in denaro per l'affitto temporaneo del tesserato (Prestito Oneroso). L'eventuale onere pattuito genera un impatto istantaneo:
    * **Cassa:** L'importo viene detratto immediatamente dalla Liquidità della società acquirente e versato sul conto della società cedente.
    * **Bilancio:** Al fine di garantire il Fair Play dell'esercizio in corso, l'importo costituisce per la società cedente una **Plusvalenza** da iscrivere nei Ricavi, e per la società acquirente una **Minusvalenza** (costo di locazione) da iscrivere negli Oneri d'esercizio.

    **Ammortamenti e Oneri Salariali:**  
    La stipula di un trasferimento a titolo temporaneo genera i seguenti effetti contabili continuativi per l'intera durata dell'accordo:
    * **Quote di Ammortamento:** L'onere dell'ammortamento annuale rimane **integralmente a carico della società cedente** (proprietaria del cartellino), la quale continuerà a dedurlo regolarmente nel proprio Bilancio d'Esercizio alla voce Costi della Produzione.
    * **Oneri Salariali (Stipendio):** La ripartizione del compenso annuale è soggetta a **libera contrattazione** tra le parti. Le società possono concordare qualsivoglia ripartizione percentuale (es. 50% e 50%, 100% a carico della cessionaria, 100% a carico della cedente). Le quote proporzionali così pattuite andranno obbligatoriamente iscritte alla voce "Monte Ingaggi" dei rispettivi Bilanci d'Esercizio.

    **Esercizio del Riscatto:**  
    Qualora venga esercitato il diritto di riscatto, o al maturare delle condizioni per l'obbligo di riscatto, l'operazione si converte in una **Cessione a Titolo Definitivo** a tutti gli effetti legali e contabili. A far data dall'effettiva esecuzione contabile del riscatto:
    1. La società cedente incassa il corrispettivo pattuito nella Liquidità e calcola l'eventuale Plusvalenza o Minusvalenza, confrontando il prezzo di riscatto con il Valore Residuo del tesserato in quel preciso momento patrimoniale.
    2. La società acquirente detrae l'importo dalla propria Liquidità, subentra nella titolarità del cartellino assumendosi il 100% degli oneri salariali futuri e avvia un nuovo piano di ammortamento basato sul costo del riscatto e sulla durata del nuovo contratto stipulato.

    ### 4.6 Rinnovo Contrattuale e Rimodulazione dell'Ammortamento
    Le società hanno facoltà di prolungare il vincolo contrattuale di un proprio tesserato prima della naturale scadenza. La sottoscrizione di un rinnovo produce due effetti contabili immediati sul Bilancio d'Esercizio:
    1. **Adeguamento Salariale:** Lo stipendio annuale del tesserato subisce un incremento obbligatorio pari al +15% rispetto al compenso attualmente in essere.
    2. **Rimodulazione dell'Ammortamento:** Il Valore Residuo del calciatore, calcolato al momento del rinnovo, costituisce la nuova base patrimoniale e viene ripartito ("spalmato") sulla nuova durata contrattuale pattuita (massimo 3 anni aggiuntivi). La nuova **Quota di Ammortamento annuale** sarà pertanto ricalcolata al ribasso, dividendo il Valore Residuo per i nuovi anni di contratto. Contestualmente, il conteggio degli "anni trascorsi" si azzera.
    """)
    st.info("""**Esempio Pratico: Rinnovo Contrattuale**  
    Il *Calciatore X* percepisce uno stipendio di 1.5M e, a seguito degli ammortamenti pregressi, ha un Valore Residuo di **15 milioni**. La società decide di rinnovare il contratto per ulteriori **3 anni**.
    * **Nuovo Stipendio:** Incremento del 15% su 1.5M $\\rightarrow$ Nuovo stipendio pari a **1.725 milioni** annui.
    * **Nuovo Ammortamento:** I 15 milioni di Valore Residuo vengono divisi per i 3 nuovi anni $\\rightarrow$ Nuova quota di ammortamento pari a **5 milioni** annui.
    * **Impatto a Bilancio:** A fronte di un lieve aumento del monte ingaggi, la società abbassa notevolmente i costi di ammortamento correnti, alleggerendo il bilancio ed evitando minusvalenze future.""")

    st.markdown("""
    ### 4.7 Efficacia Temporale degli Accordi (Sistema di Prenotazione)
    Al fine di preservare l'integrità del Fair Play Finanziario per l'esercizio in corso, l'esercizio dei diritti/obblighi di riscatto e i rinnovi contrattuali operati a stagione in corso agiscono in veste di **pre-accordi vincolanti (Prenotazioni)**. 

    La formalizzazione di tali operazioni tramite il gestionale **non produce alcun effetto immediato** sulla Liquidità corrente o sul Bilancio dell'anno in corso. L'esecuzione materiale e contabile (transito del denaro in Cassa, calcolo delle Plusvalenze/Minusvalenze da riscatto, incremento salariale del +15% da rinnovo e ricalcolo dei nuovi ammortamenti) viene posticipata e resa effettiva **esclusivamente all'atto della Chiusura Fiscale di fine stagione**, ricadendo di fatto quale prima operazione d'apertura del Bilancio della stagione successiva.
    """)

    st.divider()

    # SECTION 5
    st.subheader("5. Competizioni Ufficiali e Premi Sportivi")
    st.markdown("""
    Al termine della stagione sportiva, la Direzione provvede all'erogazione dei corrispettivi in denaro maturati in base ai risultati conseguiti nelle tre competizioni ufficiali previste dal calendario. Tali somme vengono erogate istantaneamente nella Cassa e contribuiscono ad accrescere la voce "Premi Sportivi" nel Bilancio d'Esercizio in vista della chiusura fiscale.

    ### 5.1 Campionato di Lega
    Al fine di garantire la competitività, l'equilibrio della Lega nel lungo periodo e agevolare la ricostruzione finanziaria, l'ammontare dei premi di Campionato (totale 287 milioni) è distribuito seguendo un criterio che privilegia i posizionamenti inferiori:
    * **1ª Classificata:** 35 milioni
    * **2ª Classificata:** 36 milioni
    * **3ª Classificata:** 38 milioni
    * **4ª Classificata:** 40 milioni
    * **5ª Classificata:** 43 milioni
    * **6ª Classificata:** 45 milioni
    * **7ª Classificata:** 48 milioni
    * **8ª Classificata:** 50 milioni
    
    ### 5.2 Coppa Italia
    La competizione nazionale parallela al campionato si articola in tre turni a eliminazione diretta, disputati interamente in **gara secca**.
    
    **Calendario Ufficiale:**
    * **Quarti di Finale:** 15ª Giornata di Campionato
    * **Semifinali:** 25ª Giornata di Campionato
    * **Finale:** 35ª Giornata di Campionato
    
    **Proventi Sportivi:**
    * **1ª Classificata (Vincitrice):** 25 milioni
    * **2ª Classificata (Finalista):** 15 milioni
    * **3ª e 4ª Classificata (Semifinaliste):** 5 milioni

    ### 5.3 Champions League
    La massima competizione si struttura in una fase iniziale composta da **due gironi all'italiana da 4 squadre** (con incontri di andata e ritorno), seguita da Semifinali (con incontri di andata e ritorno) e da una Finale in gara secca in campo neutro.
    
    **Calendario Ufficiale:**
    * **Fase a Gironi (Andata e Ritorno):** 4ª, 8ª, 12ª, 16ª, 20ª e 24ª Giornata di Campionato
    * **Semifinali (Andata e Ritorno):** 28ª e 32ª Giornata di Campionato
    * **Finale:** 36ª Giornata di Campionato
    
    **Proventi Sportivi (Meritocratici):**
    * **1ª Classificata (Vincitrice):** 35 milioni
    * **2ª Classificata (Finalista):** 25 milioni
    * **3ª e 4ª Classificata (Semifinaliste):** 15 milioni
    """)

    st.divider()

    # SECTION 6
    st.subheader("6. Redazione e Chiusura del Bilancio d'Esercizio")
    st.markdown("""
    Al termine di ciascuna stagione sportiva, prima dell'avvio della sessione di mercato successiva, le società hanno l'obbligo di redigere il Bilancio d'Esercizio, determinando il differenziale tra il Valore della Produzione e i Costi della Produzione. Questo è l'atto formale che chiude l'anno sportivo.
    
    ### 6.1 Valore della Produzione (Ricavi d'Esercizio)
    Concorrono alla formazione dei ricavi le seguenti voci:
    * **Premi Sportivi:** Introiti accreditati a bilancio a seguito dei piazzamenti finali nelle competizioni ufficiali.
    * **Proventi da Sponsorizzazione:** Quota erogata all'apertura dell'esercizio (pari a 30 milioni fissi per tutti durante la prima stagione sportiva di fondazione; dalla seconda stagione in poi, determinata con criterio meritocratico in base alla classifica finale dell'anno precedente).
    * **Proventi da Stadio (Ticketing):** Somma matematica dei ricavi lordi per singola partita disputata nell'impianto di proprietà.
    * **Plusvalenze Patrimoniali:** Utili generati dalla cessione dei diritti sulle prestazioni sportive.
    * **Nuovo Capitale:** Iniezione di liquidità garantita dalla Lega (pari a 50 milioni) iscritta a Bilancio all'apertura di ogni nuovo esercizio contabile **(esclusivamente a partire dalla seconda stagione)**.

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
    
    1. **Pagamento degli Oneri Correnti:** Vengono materialmente prelevati dalla Cassa i fondi necessari al pagamento fisico degli stipendi maturati nell'anno (Monte Ingaggi) e dei costi di gestione dello Stadio.
    2. **Verifica del Fair Play Finanziario:** Viene calcolato il Risultato d'Esercizio del Bilancio (Ricavi - Costi).
       * 🟢 **Risultato Positivo (Utile d'Esercizio):** La società ha rispettato i parametri economici. Non avviene alcun prelievo aggiuntivo. (L'utile non si somma alla Cassa in quanto gli introiti dei ricavi sono già stati percepiti nel corso dell'anno).
       * 🔴 **Risultato Negativo (Perdita d'Esercizio):** La società ha violato i parametri UEFA vivendo al di sopra delle proprie possibilità. Scatta l'obbligo di ricapitalizzazione immediata: **un importo pari all'intera Perdita certificata viene prelevato coattivamente e sottratto dalla Cassa societaria** per ripianare il debito.
    3. **Azzeramento Bilancio:** Il documento contabile viene salvato in archivio e azzerato, tornando a un saldo di 0 per preparare la nuova stagione sportiva. Vengono contestualmente resi effettivi i riscatti, i rinnovi prenotati e gli svincoli a parametro zero.
    4. **Apertura del Nuovo Esercizio e Iniezioni di Capitale:** (Fase attiva a partire dalla seconda stagione). Il sistema provvede a immettere **nuova liquidità in Cassa**: accredita istantaneamente i **50 milioni** del nuovo capitale, unitamente ai **Proventi dello Sponsor** maturati grazie alla classifica dell'anno appena concluso. Le stesse identiche voci vengono iscritte nei nuovi Ricavi a Bilancio, fornendo alle società la base operativa su cui fondare il mercato della nuova stagione.
    """)