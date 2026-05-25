"""
Myriark Sniper Dashboard - PWA Version
Gabungan MOS, TOS, DOS, dan POS
"""

import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from supabase import create_client, Client
import pandas as pd

# ==========================================
# 1. KONFIGURASI ZONA WAKTU & KREDENSIAL
# ==========================================
WITA = ZoneInfo("Asia/Makassar")

# Rahasia diambil dari Streamlit Secrets (Nanti diatur di web Streamlit)
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
ODDS_API_KEY = st.secrets["ODDS_API_KEY"]
TELEGRAM_BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

# Inisialisasi Database
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. FUNGSI MATEMATIKA DOS (RUMUS MURNI KEI)
# ==========================================
def hitung_profit(odds, stake):
    if odds is None or stake is None or stake <= 0: return 0
    if odds < 0:
        return round(stake / abs(odds))
    else:
        return round(stake * odds)

def hitung_close_stake(modal, close_odds):
    if close_odds is None or close_odds == 0: return None
    if close_odds < 0:
        return round(modal * abs(close_odds))
    else:
        return round(modal / close_odds)

def decimal_ke_indo(decimal_odds):
    if decimal_odds is None or decimal_odds <= 1.0: return None
    if decimal_odds >= 2.0:
        return round(decimal_odds - 1, 2)
    else:
        return round(-1 / (decimal_odds - 1), 2)

# ==========================================
# 3. FUNGSI NOTIFIKASI POS (TELEGRAM)
# ==========================================
def kirim_telegram(pesan):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": pesan, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        st.error(f"Gagal mengirim Telegram: {e}")

# ==========================================
# 4. TAMPILAN ANTARMUKA (UI)
# ==========================================
st.set_page_config(page_title="Myriark Sniper", page_icon="🛡️", layout="wide")
st.title("🛡️ Myriark Sniper Dashboard")
st.caption(f"Waktu Sistem: {datetime.now(WITA).strftime('%Y-%m-%d %H:%M:%S')} WITA")

# --- BAGIAN A: INPUT TIKET (Pengganti mos.py) ---
with st.expander("➕ INPUT TIKET BARU", expanded=False):
    with st.form("form_tiket", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            match_name = st.text_input("Nama Match (Harus persis dengan API, cth: Lazio vs Pisa)")
            side = st.selectbox("Posisi (Side)", ["over", "under"])
            line = st.number_input("Line (cth: 2.5)", value=2.5, step=0.25)
        with col2:
            odds = st.number_input("Odds Indo (Kei pakai minus, cth: -1.15)", value=-1.0)
            stake = st.number_input("Modal / Stake (Rp)", value=100000, step=10000)
        
        submit = st.form_submit_button("💾 Simpan Tiket")
        if submit and match_name:
            data_tiket = {
                "ticket_id": f"TKT-{datetime.now().strftime('%H%M%S')}",
                "match": match_name,
                "status": "RUNNING",
                "entry_side": side,
                "entry_line": line,
                "entry_odds": odds,
                "entry_stake": stake
            }
            supabase.table("tickets").insert(data_tiket).execute()
            st.success(f"Tiket {match_name} berhasil disimpan!")
            st.rerun()

# --- BAGIAN B: DAFTAR TIKET AKTIF ---
st.subheader("📋 Tiket Berjalan (RUNNING)")
try:
    response = supabase.table("tickets").select("*").eq("status", "RUNNING").execute()
    tiket_aktif = response.data
except Exception as e:
    st.error("Gagal mengambil data database. Cek koneksi Supabase.")
    tiket_aktif = []

if tiket_aktif:
    df = pd.DataFrame(tiket_aktif)
    st.dataframe(df[["ticket_id", "match", "entry_side", "entry_line", "entry_odds", "entry_stake"]], use_container_width=True)
else:
    st.info("Tidak ada tiket yang sedang berjalan.")

# --- BAGIAN C: SCANNER (Pengganti tos.py + dos.py) ---
st.divider()
if st.button("🚀 JALANKAN SCAN MYRIARK SEKARANG", type="primary"):
    if not tiket_aktif:
        st.warning("Tidak ada tiket RUNNING untuk discan.")
    else:
        with st.spinner("Menarik data dari The Odds API..."):
            # 1. Tarik Data TOS
            url = "https://api.the-odds-api.com/v4/sports/soccer/odds"
            params = {"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "totals", "oddsFormat": "decimal"}
            res = requests.get(url, params=params)
            
            if res.status_code != 200:
                st.error("Gagal menarik data dari API.")
            else:
                data_api = res.json()
                live_market = {}
                
                # Transformasi Data
                for match in data_api:
                    home = match.get("home_team", "")
                    away = match.get("away_team", "")
                    match_name = f"{home} vs {away}"
                    
                    for bm in match.get("bookmakers", []):
                        if bm.get("key") == "pinnacle": # Prioritas Pinnacle
                            for market in bm.get("markets", []):
                                if market.get("key") == "totals":
                                    o_price, u_price, line_point = None, None, None
                                    for out in market.get("outcomes", []):
                                        if out["name"].lower() == "over": o_price = decimal_ke_indo(out["price"])
                                        if out["name"].lower() == "under": u_price = decimal_ke_indo(out["price"])
                                        line_point = out.get("point")
                                    
                                    if o_price and u_price:
                                        live_market[match_name] = {"over": o_price, "under": u_price, "line": line_point}

                # 2. Proses DOS per tiket aktif
                for tiket in tiket_aktif:
                    t_match = tiket["match"]
                    if t_match not in live_market:
                        st.warning(f"Live odds belum tersedia untuk: {t_match}")
                        continue
                    
                    # Logika Kalkulasi
                    live = live_market[t_match]
                    entry_side = tiket["entry_side"]
                    close_side = "under" if entry_side == "over" else "over"
                    close_odds = live[close_side]
                    
                    modal = tiket["entry_stake"]
                    min_bet = hitung_close_stake(modal, close_odds)
                    
                    if min_bet:
                        close_profit = hitung_profit(close_odds, min_bet)
                        total_result = close_profit - modal
                        
                        if total_result >= -1: # Toleransi pembulatan BEP
                            status_alert = "PROFIT_READY 🟢" if total_result > 1 else "BEP_READY 🟡"
                            st.success(f"**{status_alert} pada {t_match}!** Pasang {close_side.upper()} modal {min_bet} di odds {close_odds}.")
                            
                            # Trigger Telegram (POS)
                            pesan_tg = f"🚨 *MYRIARK SIGNAL: {status_alert}* 🚨\n\n" \
                                       f"⚽ *{t_match}*\n" \
                                       f"▪️ *Tutup Posisi:* {close_side.upper()}\n" \
                                       f"▪️ *Line Target:* {live['line']}\n" \
                                       f"▪️ *Odds (Indo):* {close_odds}\n" \
                                       f"💰 *MIN BET (MODAL):* Rp {min_bet:,.0f}\n\n" \
                                       f"Estimasi Hasil Akhir: Rp {total_result:,.0f}"
                            kirim_telegram(pesan_tg)
                        else:
                            st.info(f"Belum siap untuk {t_match}. Butuh modal {min_bet}, hasil akhir: {total_result}")
