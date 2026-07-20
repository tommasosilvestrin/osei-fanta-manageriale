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
        "ricavi": {"capitale_iniziale": 350.0, "nuovo_capitale": 0.0, "premi_sportivi": 0.0, "sponsor": 0.0, "incassi_stadio": 0.0, "plusvalenze": 0.0},
        "costi": {"ammortamenti": 0.0, "monte_ingaggi": 0.0, "gestione_stadio": 0.0, "minusvalenze": 0.0, "costi_giocatori_ceduti": 0.0},
        "storico_movimenti": []
    }

def init_coppe():
    return {
        "ci": {"quarti": [], "semis": [], "finale": [], "perse_semis": [], "premi_dati": False},
        "cl": {
            "gir_A": [], "gir_B": [], 
            "cal_A": [], "cal_B": [], 
            "semis_andata": [], "semis_ritorno": [], 
            "finale": [], "perse_semis": [], "premi_dati": False
        }
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

def genera_gironi_4(sq):
    return [
        [{"home": sq[0], "away": sq[3], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi": False}, {"home": sq[1], "away": sq[2], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi": False}],
        [{"home": sq[3], "away": sq[1], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi": False}, {"home": sq[2], "away": sq[0], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi": False}],
        [{"home": sq[0], "away": sq[1], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi": False}, {"home": sq[2], "away": sq[3], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi": False}],
        [{"home": sq[3], "away": sq[0], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi": False}, {"home": sq[2], "away": sq[1], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi": False}],
        [{"home": sq[1], "away": sq[3], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi": False}, {"home": sq[0], "away": sq[2], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi": False}],
        [{"home": sq[1], "away": sq[0], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi": False}, {"home": sq[3], "away": sq[2], "gol_home": 0, "gol_away": 0, "giocata": False, "incassi": False}]
    ]

def sync_cups_with_league(giornata_idx, gol_map, coppe):
    # Mapping delle Giornate di Campionato ai Turni di Coppa
    mappa = {
        # Coppa Italia
        15: [("ci", "quarti")], 
        25: [("ci", "semis")], 
        35: [("ci", "finale")],
        
        # Champions League
        4: [("cl", "gironi", 0)], 
        8: [("cl", "gironi", 1)], 
        12: [("cl", "gironi", 2)],
        16: [("cl", "gironi", 3)], 
        20: [("cl", "gironi", 4)], 
        24: [("cl", "gironi", 5)],
        28: [("cl", "semis_andata")], 
        32: [("cl", "semis_ritorno")], 
        36: [("cl", "finale")]
    }
    if giornata_idx in mappa:
        for info in mappa[giornata_idx]:
            comp, fase = info[0], info[1]
            if comp == "ci":
                for m in coppe[comp][fase]:
                    if m["home"] in gol_map: m["gol_home"] = gol_map[m["home"]]
                    if m["away"] in gol_map: m["gol_away"] = gol_map[m["away"]]
            elif comp == "cl":
                if fase == "gironi":
                    idx_turno = info[2]
                    for g_key in ["cal_A", "cal_B"]:
                        if len(coppe["cl"][g_key]) > idx_turno:
                            for m in coppe["cl"][g_key][idx_turno]:
                                if m["home"] in gol_map: m["gol_home"] = gol_map[m["home"]]
                                if m["away"] in gol_map: m["gol_away"] = gol_map[m["away"]]
                                m["giocata"] = True
                else:
                    for m in coppe[comp][fase]:
                        if m["home"] in gol_map: m["gol_home"] = gol_map[m["home"]]
                        if m["away"] in gol_map: m["gol_away"] = gol_map[m["away"]]

LIMITI_ROSA = {"Portiere": 3, "Difensore": 8, "Centrocampista": 8, "Attaccante": 6}

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
    if pwd == "osei2026": # Sostituisci con la password che preferisci!
        st.session_state.is_admin = True
        st.rerun()
    elif pwd:
        st.sidebar.error("Password errata")
else:
    st.sidebar.success("👑 Modalità Admin Attiva")
    if st.sidebar.button("Logout (Torna Spettatore)"):
        st.session_state.is_admin = False
        st.rerun()
        
    # --- NUOVO: ZONA DOWNLOAD BACKUP ---
    st.sidebar.divider()
    st.sidebar.caption("💾 SALVATAGGIO DATI (Fallo a fine sessione!)")
    
    # Bottone Squadre
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r", encoding="utf-8") as f:
            st.sidebar.download_button("📥 Scarica squadre.json", f.read(), "squadre.json", "application/json")
            
    # Bottone Calendario
    if os.path.exists(CAL_PATH):
        with open(CAL_PATH, "r", encoding="utf-8") as f:
            st.sidebar.download_button("📥 Scarica calendario.json", f.read(), "calendario.json", "application/json")
            
    # Bottone Coppe
    if os.path.exists(COPPE_PATH):
        with open(COPPE_PATH, "r", encoding="utf-8") as f:
            st.sidebar.download_button("📥 Scarica coppe.json", f.read(), "coppe.json", "application/json")

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
    "8. Chiusura Fiscale Bilancio"
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
                # Tolto l'input del valore, impostato a 30M fisso
                ns = st.text_input("Nome Sponsor", value=sq_dati["sponsor"]["nome"] or "")
                
                if st.button("Firma Accordo Sponsor"):
                    vs = 30.0 # Valore fissato automaticamente a 30M
                    sq_dati["sponsor"] = {"nome": ns, "valore": vs}
                    sq_dati["bilancio"]["ricavi"]["sponsor"] = vs
                    save_data(db, DB_PATH)
                    st.success(f"Sponsor {ns} firmato a 30M!")

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
                st.markdown("#### 🔴 Costi Proiettati")
                for k, v in b['costi'].items():
                    if v > 0: 
                        st.write(f"- **{k.replace('_', ' ').title()}**: {v:.2f} M")
        
        st.divider()
        st.subheader(f"👥 Rosa Ufficiale ({len(squadra['rosa'])}/25)")
        
        conteggio = {"Portiere": 0, "Difensore": 0, "Centrocampista": 0, "Attaccante": 0}
        for g in squadra['rosa']: conteggio[g['ruolo']] += 1
        st.write(f"**POR:** {conteggio['Portiere']}/3 | **DIF:** {conteggio['Difensore']}/8 | **CEN:** {conteggio['Centrocampista']}/8 | **ATT:** {conteggio['Attaccante']}/6")

        if squadra['rosa']:
            df = pd.DataFrame(squadra['rosa'])
            df_display = df[['nome', 'ruolo', 'anni_contratto', 'costo_acquisto', 'valore_residuo', 'ammortamento_annuo', 'stipendio']].copy()
            st.dataframe(df_display, use_container_width=True)

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
            
            st.write(f"💰 **Cassa:** {squadra['cassa']} MLN | 👥 **Rosa:** {len(squadra['rosa'])}/25")
            
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
                        ruoli_attuali = sum(1 for g in squadra['rosa'] if g['ruolo'] == r)
                        if len(squadra['rosa']) >= 25: st.error("Rosa piena (25/25).")
                        elif ruoli_attuali >= LIMITI_ROSA[r]: st.error(f"Limite per ruolo {r} raggiunto ({LIMITI_ROSA[r]}).")
                        elif c > squadra['cassa']: st.error("Cassa insufficiente!")
                        else:
                            giocatore = {"nome": n, "ruolo": r, "costo_acquisto": c, "anni_contratto": anni_effettivi, "stipendio": s_base, "ammortamento_annuo": amm, "anni_trascorsi": 0, "valore_residuo": c, "acquistato_a_gennaio": is_gennaio}
                            squadra['rosa'].append(giocatore)
                            squadra['cassa'] -= c
                            squadra['bilancio']['storico_movimenti'].append(f"Acquisto {n}: -{c}M")
                            save_data(db, DB_PATH)
                            st.success(f"{n} acquistato!")
                            
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
                        squadra['cassa'] += prezzo_v
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
                            db[sq_acquirente]['cassa'] -= costo_prestito
                            db[sq_cedente]['cassa'] += costo_prestito
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
                        
                        # MAGIA COPPE: Sincronizza i gol appena inseriti con le Coppe!
                        sync_cups_with_league(giornata_idx + 1, gol_map, coppe)
                        
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
                
                # Aggiunge i soldi REALI alla Cassa
                team['cassa'] += (p_spons + p_camp)
                
                team['bilancio']['ricavi']['sponsor'] += p_spons
                team['bilancio']['ricavi']['premi_sportivi'] += p_camp
                team['bilancio']['storico_movimenti'].append(f"Premio Campionato ({pos+1}°): +{p_camp}M (Cassa e Bilancio)")
                team['bilancio']['storico_movimenti'].append(f"Sponsor Finale ({pos+1}°): +{p_spons}M (Cassa e Bilancio)")
            save_data(db, DB_PATH)
            st.success("Premi Campionato e Sponsor distribuiti!")

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
            if st.button("Sorteggia Tabellone Quarti"):
                teams = list(db.keys())
                random.shuffle(teams)
                coppe["ci"]["quarti"] = [{"home": teams[i], "away": teams[i+1], "gol_home": 0, "gol_away": 0, "vincente": teams[i]} for i in range(0, 8, 2)]
                save_data(coppe, COPPE_PATH)
                st.rerun()
        
        if coppe["ci"]["quarti"]:
            st.write("🔴 **Quarti di Finale** (Sincronizzati con Giornata 15)")
            for i, m in enumerate(coppe["ci"]["quarti"]):
                c1, c2, c3 = st.columns([2,1,2])
                c1.write(f"{m['home']} vs {m['away']}")
                c2.write(f"**{m['gol_home']} - {m['gol_away']}**")
                m['vincente'] = c3.selectbox("Passa il turno:", [m['home'], m['away']], index=0 if m['vincente']==m['home'] else 1, key=f"ci_q_{i}", disabled=not st.session_state.is_admin)
            
            if st.session_state.is_admin:
                if not coppe["ci"]["semis"] and st.button("Salva Quarti & Genera Semifinali"):
                    vincitori = [m['vincente'] for m in coppe["ci"]["quarti"]]
                    coppe["ci"]["semis"] = [{"home": vincitori[0], "away": vincitori[1], "gol_home": 0, "gol_away": 0, "vincente": vincitori[0]}, {"home": vincitori[2], "away": vincitori[3], "gol_home": 0, "gol_away": 0, "vincente": vincitori[2]}]
                    save_data(coppe, COPPE_PATH)
                    st.rerun()

        if coppe["ci"]["semis"]:
            st.divider()
            st.write("🟡 **Semifinali** (Sincronizzate con Giornata 25)")
            for i, m in enumerate(coppe["ci"]["semis"]):
                c1, c2, c3 = st.columns([2,1,2])
                c1.write(f"{m['home']} vs {m['away']}")
                c2.write(f"**{m['gol_home']} - {m['gol_away']}**")
                m['vincente'] = c3.selectbox("Passa in Finale:", [m['home'], m['away']], index=0 if m['vincente']==m['home'] else 1, key=f"ci_s_{i}", disabled=not st.session_state.is_admin)
            
            if st.session_state.is_admin:
                if not coppe["ci"]["finale"] and st.button("Salva Semifinali & Genera Finale"):
                    vincitori = [m['vincente'] for m in coppe["ci"]["semis"]]
                    perdenti = [m['home'] if m['vincente']==m['away'] else m['away'] for m in coppe["ci"]["semis"]]
                    coppe["ci"]["finale"] = [{"home": vincitori[0], "away": vincitori[1], "gol_home": 0, "gol_away": 0, "vincente": vincitori[0]}]
                    coppe["ci"]["perse_semis"] = perdenti
                    save_data(coppe, COPPE_PATH)
                    st.rerun()
                
        if coppe["ci"]["finale"]:
            st.divider()
            st.write("🟢 **Finale** (Sincronizzata con Giornata 35)")
            m = coppe["ci"]["finale"][0]
            c1, c2, c3 = st.columns([2,1,2])
            c1.write(f"{m['home']} vs {m['away']}")
            c2.write(f"**{m['gol_home']} - {m['gol_away']}**")
            m['vincente'] = c3.selectbox("VINCITORE:", [m['home'], m['away']], index=0 if m['vincente']==m['home'] else 1, key="ci_f", disabled=not st.session_state.is_admin)
            save_data(coppe, COPPE_PATH)
            
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
            if st.button("Sorteggia Gironi CL"):
                teams = list(db.keys())
                random.shuffle(teams)
                coppe["cl"]["gir_A"] = teams[:4]; coppe["cl"]["gir_B"] = teams[4:]
                coppe["cl"]["cal_A"] = genera_gironi_4(coppe["cl"]["gir_A"])
                coppe["cl"]["cal_B"] = genera_gironi_4(coppe["cl"]["gir_B"])
                save_data(coppe, COPPE_PATH)
                st.rerun()
                
        if coppe["cl"]["gir_A"]:
            st.write("Fase a Gironi (Sincronizzata Giornate 4, 8, 12, 16, 20, 24)")
            colA, colB = st.columns(2)
            
            # Calcolo Punti Rapido per Girone A
            p_A = {s: 0 for s in coppe["cl"]["gir_A"]}
            for turno in coppe["cl"]["cal_A"]:
                for m in turno:
                    if m["giocata"]:
                        if m["gol_home"] > m["gol_away"]: p_A[m["home"]] += 3
                        elif m["gol_home"] == m["gol_away"]: p_A[m["home"]] += 1; p_A[m["away"]] += 1
                        else: p_A[m["away"]] += 3
            df_A = pd.DataFrame(list(p_A.items()), columns=["Squadra", "Punti"]).sort_values(by="Punti", ascending=False)
            colA.write("**Girone A**")
            colA.dataframe(df_A, hide_index=True)
            
            # Calcolo Punti Rapido per Girone B
            p_B = {s: 0 for s in coppe["cl"]["gir_B"]}
            for turno in coppe["cl"]["cal_B"]:
                for m in turno:
                    if m["giocata"]:
                        if m["gol_home"] > m["gol_away"]: p_B[m["home"]] += 3
                        elif m["gol_home"] == m["gol_away"]: p_B[m["home"]] += 1; p_B[m["away"]] += 1
                        else: p_B[m["away"]] += 3
            df_B = pd.DataFrame(list(p_B.items()), columns=["Squadra", "Punti"]).sort_values(by="Punti", ascending=False)
            colB.write("**Girone B**")
            colB.dataframe(df_B, hide_index=True)

            if not coppe["cl"]["semis_andata"] and st.button("Genera Semifinali CL"):
                # Primi vs Secondi
                a1, a2 = df_A.iloc[0]["Squadra"], df_A.iloc[1]["Squadra"]
                b1, b2 = df_B.iloc[0]["Squadra"], df_B.iloc[1]["Squadra"]
                coppe["cl"]["semis_andata"] = [{"home": a1, "away": b2, "gol_home": 0, "gol_away": 0}, {"home": b1, "away": a2, "gol_home": 0, "gol_away": 0}]
                coppe["cl"]["semis_ritorno"] = [{"home": b2, "away": a1, "gol_home": 0, "gol_away": 0, "vincente": a1}, {"home": a2, "away": b1, "gol_home": 0, "gol_away": 0, "vincente": b1}]
                save_data(coppe, COPPE_PATH)
                st.rerun()

        if coppe["cl"]["semis_andata"]:
            st.divider()
            st.write("🟡 **Semifinali Andata (G28) e Ritorno (G32)**")
            for i in range(2):
                ma = coppe["cl"]["semis_andata"][i]
                mr = coppe["cl"]["semis_ritorno"][i]
                st.write(f"**{ma['home']} vs {ma['away']}** | Andata: {ma['gol_home']}-{ma['gol_away']} | Ritorno: {mr['gol_home']}-{mr['gol_away']}")
                mr['vincente'] = st.selectbox("Passa in Finale:", [ma['home'], ma['away']], index=0 if mr['vincente']==ma['home'] else 1, key=f"cl_s_{i}", disabled=not st.session_state.is_admin)
            
            if st.session_state.is_admin:
                if not coppe["cl"]["finale"] and st.button("Genera Finale CL"):
                    vincitori = [m['vincente'] for m in coppe["cl"]["semis_ritorno"]]
                    perdenti = [m['home'] if m['vincente']==m['away'] else m['away'] for m in coppe["cl"]["semis_ritorno"]]
                    coppe["cl"]["finale"] = [{"home": vincitori[0], "away": vincitori[1], "gol_home": 0, "gol_away": 0, "vincente": vincitori[0]}]
                    coppe["cl"]["perse_semis"] = perdenti
                    save_data(coppe, COPPE_PATH)
                    st.rerun()
                
        if coppe["cl"]["finale"]:
            st.divider()
            st.write("🟢 **Finale** (Sincronizzata con Giornata 36)")
            m = coppe["cl"]["finale"][0]
            c1, c2, c3 = st.columns([2,1,2])
            c1.write(f"{m['home']} vs {m['away']}")
            c2.write(f"**{m['gol_home']} - {m['gol_away']}**")
            m['vincente'] = c3.selectbox("VINCITORE CL:", [m['home'], m['away']], index=0 if m['vincente']==m['home'] else 1, key="cl_f", disabled=not st.session_state.is_admin)
            save_data(coppe, COPPE_PATH)
            
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
# 9. CHIUSURA FISCALE
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
                        
                b['costi']['ammortamenti'] = tot_ammortamenti
                b['costi']['monte_ingaggi'] = tot_ingaggi
                
                costo_stadio = b['costi']['gestione_stadio']
                dati['cassa'] -= (tot_ingaggi + costo_stadio)
                
                utile = sum(b['ricavi'].values()) - sum(b['costi'].values())
                
                if utile < 0:
                    dati['cassa'] += utile  
                
                dati['ultimo_bilancio_chiuso'] = {
                    "ricavi": dict(dati['bilancio']['ricavi']),
                    "costi": dict(dati['bilancio']['costi']),
                    "utile": utile,
                    "cassa_partenza_nuovo_anno": dati['cassa']
                }
                
                dati['bilancio'] = init_bilancio()
                dati['bilancio']['ricavi']['capitale_iniziale'] = 0.0 
                
                dati['cassa'] += 50.0
                dati['bilancio']['ricavi']['nuovo_capitale'] = 50.0
                dati['bilancio']['storico_movimenti'].append("Iniezione Diritti TV: +50.0M")
                
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