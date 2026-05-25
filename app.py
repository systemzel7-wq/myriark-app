"""
Myriark Sniper Dashboard - PWA Version (BULLETPROOF EDITION)
Gabungan MOS, TOS, DOS, dan POS dengan Advanced Error Handling
"""

import streamlit as st
import requests
import uuid
import time
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from supabase import create_client, Client
import pandas as pd

# ==========================================
# KONFIGURASI DASAR & LOGGING
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
WITA = ZoneInfo("Asia/Makassar")

st.set_page_config(page_title="Myriark Sniper", page_icon="🛡️", layout="wide")
st.title("🛡️ Myriark Sniper Dashboard")
st.caption(f"Waktu Sistem: {datetime.now(WITA).strftime('%Y-%m-%d %H:%M:%S')} WITA")

# ==========================================
# 1. KREDENSIAL & SUPABASE STARTUP (PATCHED)
# ==========================================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    ODDS_API_KEY = st.secrets["ODDS_API_KEY"]
    TELEGRAM_BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]
    TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("🔴 Kritis: Gagal memuat kredensial atau koneksi ke Supabase.")
    logging.error(f"Supabase Init Error: {e}")
    st.stop() # Hentikan eksekusi jika DB mati

# ==========================================
# 2. FUNGSI MATEMATIKA DOS (PATCHED)
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
    # PATCH 1: Boundary check mencegah Division by Zero
    if decimal_odds is None or decimal_odds <= 1.01: return None 
    if decimal_odds >= 2.0:
        return round(decimal_odds - 1, 2)
    else:
        return round(-1 / (decimal_odds - 1), 2)

# ==========================================
# 3. FUNGSI NOTIFIKASI POS (PATCHED)
# ==========================================
def kirim_telegram(pesan):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": pesan, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=5)
        res.raise_for_status()
    except Exception as e:
        # PATCH 7: Log ke console, tidak perlu merusak UI dengan st.error
        logging.error(f"Telegram failed: {e}")

# ==========================================
# PATCH 17: FUNGSI DELETE TIKET
# ==========================================
def hapus_tiket(ticket_id):
    """Hapus tiket dari database"""
    try:
        supabase.table("tickets").delete().eq("ticket_id", ticket_id).execute()
        st.success(f"✅ Tiket {ticket_id} berhasil dihapus!")
        logging.info(f"Ticket deleted: {ticket_id}")
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"❌ Gagal menghapus tiket: {str(e)[:100]}")
        logging.error(f"Delete Ticket Error: {e}")

# ==========================================
# 4. TAMPILAN ANTARMUKA (UI)
# ==========================================

# --- BAGIAN A: INPUT TIKET ---
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
            # PATCH 3: ID Unik menghindari duplikasi
            unique_id = f"TKT-{datetime.now().strftime('%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
            data_tiket = {
                "ticket_id": unique_id,
                "match": match_name,
                "status": "RUNNING",
                "entry_side": side,
                "entry_line": line,
                "entry_odds": odds,
                "entry_stake": stake
            }
            try:
                supabase.table("tickets").insert(data_tiket).execute()
                st.success(f"Tiket {match_name} berhasil disimpan!")
                # PATCH 4: Mencegah Race Condition sebelum rerun
                time.sleep(0.5) 
                st.rerun()
            except Exception as e:
                st.error("Gagal menyimpan tiket ke database.")
                logging.error(f"Insert Ticket Error: {e}")

# --- BAGIAN B: DAFTAR TIKET AKTIF ---
st.subheader("📋 Tiket Berjalan (RUNNING)")
try:
    response = supabase.table("tickets").select("*").eq("status", "RUNNING").execute()
    tiket_aktif = response.data
except Exception as e:
    st.error("Gagal mengambil data dari Supabase.")
    logging.error(f"Fetch Tickets Error: {e}")
    tiket_aktif = []

if tiket_aktif:
    # PATCH 9: Data structure validation
    df = pd.DataFrame(tiket_aktif)
    # PATCH 10: Cek DataFrame kosong sebelum akses
    if df.empty:
        st.info("Tidak ada tiket yang sedang berjalan.")
    else:
        kolom_wajib = ["ticket_id", "match", "entry_side", "entry_line", "entry_odds", "entry_stake"]
        kolom_tersedia = [k for k in kolom_wajib if k in df.columns]
        
        # PATCH 17: Tambah kolom aksi (delete button)
        st.write("Klik 🗑️ untuk menghapus tiket:")
        for idx, tiket in enumerate(tiket_aktif):
            col1, col2, col3, col4, col5, col6, col7 = st.columns([1.5, 1.5, 1.2, 1.2, 1.2, 1.5, 0.8])
            with col1:
                st.write(tiket.get("ticket_id", "N/A"))
            with col2:
                st.write(tiket.get("match", "N/A"))
            with col3:
                st.write(tiket.get("entry_side", "N/A").upper())
            with col4:
                st.write(f"{tiket.get('entry_line', 'N/A')}")
            with col5:
                st.write(f"{tiket.get('entry_odds', 'N/A')}")
            with col6:
                st.write(f"Rp {tiket.get('entry_stake', 0):,.0f}")
            with col7:
                if st.button("🗑️", key=f"delete_{tiket.get('ticket_id')}", help="Hapus tiket ini"):
                    # PATCH 17: Konfirmasi sebelum delete
                    if st.session_state.get(f"confirm_delete_{tiket.get('ticket_id')}", False):
                        hapus_tiket(tiket.get("ticket_id"))
                    else:
                        st.session_state[f"confirm_delete_{tiket.get('ticket_id')}"] = True
                        st.warning(f"Yakin ingin hapus tiket {tiket.get('ticket_id')}? Klik 🗑️ lagi untuk confirm.")
else:
    st.info("Tidak ada tiket yang sedang berjalan.")

# --- BAGIAN C: LIVE ODDS DISPLAY (PATCH 18) ---
st.divider()
st.subheader("📊 Live Odds Tersedia (EPL)")

# PATCH 18: Session state untuk simpan live_market setiap scan
if "live_market_data" not in st.session_state:
    st.session_state.live_market_data = {}

if st.session_state.live_market_data:
    # Tampilkan live odds dalam format table
    live_odds_list = []
    for match_name, odds_data in st.session_state.live_market_data.items():
        live_odds_list.append({
            "Match": match_name,
            "Over Odds": odds_data.get("over", "N/A"),
            "Under Odds": odds_data.get("under", "N/A"),
            "Line": odds_data.get("line", "N/A"),
            "Bookmaker": odds_data.get("bm", "N/A")
        })
    
    if live_odds_list:
        df_odds = pd.DataFrame(live_odds_list)
        st.dataframe(df_odds, use_container_width=True, hide_index=True)
        st.caption(f"✅ Total {len(live_odds_list)} matches EPL dengan odds live")
    else:
        st.info("Belum ada live odds. Jalankan scan untuk fetch data.")
else:
    st.info("📡 Belum ada data live odds. Jalankan scan untuk fetch data dari The Odds API.")

# --- BAGIAN D: SCANNER ---
st.divider()
if st.button("🚀 JALANKAN SCAN MYRIARK SEKARANG", type="primary"):
    if not tiket_aktif:
        st.warning("Tidak ada tiket RUNNING untuk discan.")
    else:
        with st.spinner("Menarik data dari The Odds API (EPL)..."):
            # PATCH 16: Ganti ke soccer_epl endpoint (Option B)
            url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"
            params = {
                "apiKey": ODDS_API_KEY,
                "regions": "eu",
                "markets": "totals",
                "oddsFormat": "decimal"
            }
            
            try:
                # PATCH 15: Validasi API Key sebelum request
                if not ODDS_API_KEY or ODDS_API_KEY.strip() == "":
                    st.error("❌ API Key tidak ditemukan di Streamlit secrets. Hubungi admin untuk setup ODDS_API_KEY.")
                    logging.error("ODDS_API_KEY is empty or not configured")
                    raise Exception("Missing API Key")
                
                logging.info(f"Requesting API from: {url}")
                res = requests.get(url, params=params, timeout=15)
                
                # PATCH 15: Log HTTP status code
                logging.info(f"API Response Status: {res.status_code}")
                
                # PATCH 15: Check for HTTP errors dengan detail
                if res.status_code == 401:
                    st.error("❌ API Key Invalid atau Expired. Hubungi admin untuk renew.")
                    logging.error(f"API Auth Error 401: {res.text}")
                    data_api = None
                elif res.status_code == 429:
                    st.error("❌ Rate limit exceeded. Tunggu beberapa menit sebelum scan ulang.")
                    logging.error(f"API Rate Limit 429")
                    data_api = None
                elif res.status_code == 404:
                    st.error("❌ Endpoint tidak ditemukan (404). Liga EPL mungkin tidak tersedia saat ini.")
                    logging.error(f"API Not Found 404: {res.text}")
                    data_api = None
                elif res.status_code >= 400:
                    st.error(f"❌ API Error {res.status_code}: {res.reason}")
                    logging.error(f"API HTTP Error {res.status_code}: {res.text[:200]}")
                    data_api = None
                else:
                    res.raise_for_status()
                    # PATCH 5: Validasi JSON
                    data_api = res.json()
                    logging.info(f"Successfully fetched {len(data_api) if isinstance(data_api, list) else 'unknown'} matches from EPL API")
                    
            except requests.exceptions.Timeout:
                st.error("⏱️ Timeout - Server API lambat, coba lagi dalam beberapa detik.")
                logging.error(f"API Timeout Error after 15s")
                data_api = None
            except requests.exceptions.ConnectionError:
                st.error("🌐 Gagal terhubung ke The Odds API. Cek koneksi internet atau API server down.")
                logging.error(f"API Connection Error: Network unreachable")
                data_api = None
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Gagal terhubung ke server API Bandar: {str(e)[:100]}")
                logging.error(f"API Fetch Error: {e}")
                data_api = None
            except ValueError as e:
                st.error("❌ Format data dari API tidak valid (Bukan JSON).")
                logging.error(f"JSON Parse Error: {e}")
                data_api = None
            except Exception as e:
                st.error(f"❌ Error tidak terduga: {str(e)[:100]}")
                logging.error(f"Unexpected Error: {e}")
                data_api = None

            if data_api:
                live_market = {}
                
                # Transformasi Data
                for match in data_api:
                    home = match.get("home_team", "")
                    away = match.get("away_team", "")
                    match_name = f"{home} vs {away}"
                    
                    # PATCH 12: Hapus unused variable target_market
                    # PATCH 8: Fallback bookmaker jika pinnacle tidak ada
                    bms = {bm["key"]: bm for bm in match.get("bookmakers", [])}
                    if "pinnacle" in bms:
                        target_bm = bms["pinnacle"]
                    elif "onexbet" in bms:
                        target_bm = bms["onexbet"]
                    elif "williamhill" in bms:
                        target_bm = bms["williamhill"]
                    else:
                        target_bm = bms[list(bms.keys())[0]] if bms else None

                    if target_bm:
                        for market in target_bm.get("markets", []):
                            if market.get("key") == "totals":
                                o_price, u_price, line_point = None, None, None
                                for out in market.get("outcomes", []):
                                    if out["name"].lower() == "over": o_price = decimal_ke_indo(out["price"])
                                    if out["name"].lower() == "under": u_price = decimal_ke_indo(out["price"])
                                    # PATCH 13: Tambah default value untuk line_point
                                    line_point = out.get("point", "N/A")
                                
                                if o_price and u_price:
                                    live_market[match_name] = {"over": o_price, "under": u_price, "line": line_point, "bm": target_bm["key"]}

                # PATCH 18: Simpan live_market ke session state
                st.session_state.live_market_data = live_market

                if live_market:
                    st.success(f"✅ Berhasil fetch {len(live_market)} matches EPL dari API")
                else:
                    st.warning("⚠️ API return data tapi tidak ada totals market tersedia. Cek API response structure.")
                    logging.warning("No live_market entries found after API response")

                # Proses DOS per tiket aktif
                for tiket in tiket_aktif:
                    t_match = tiket["match"]
                    if t_match not in live_market:
                        st.warning(f"Live odds belum tersedia untuk: {t_match}")
                        continue
                    
                    live = live_market[t_match]
                    entry_side = tiket["entry_side"]
                    close_side = "under" if entry_side == "over" else "over"
                    
                    # PATCH 14: Validasi close_odds sebelum digunakan
                    close_odds = live.get(close_side)
                    if close_odds is None:
                        st.error(f"❌ Odds untuk {close_side} tidak tersedia di {t_match}")
                        logging.error(f"Missing odds for {close_side} in {t_match}")
                        continue
                    
                    # PATCH 6: Cek Inkonsistensi Line dengan tolerance float
                    try:
                        entry_line_float = float(tiket["entry_line"])
                        live_line_float = float(live["line"]) if live["line"] != "N/A" else None
                        
                        if live_line_float and abs(entry_line_float - live_line_float) > 0.01:
                            st.warning(f"⚠️ Hati-hati! Line {t_match} bergeser dari {tiket['entry_line']} menjadi {live['line']}")
                    except (ValueError, TypeError) as e:
                        logging.warning(f"Line comparison error for {t_match}: {e}")

                    modal = tiket["entry_stake"]
                    min_bet = hitung_close_stake(modal, close_odds)
                    
                    if min_bet:
                        close_profit = hitung_profit(close_odds, min_bet)
                        total_result = close_profit - modal
                        
                        if total_result >= -1: 
                            status_alert = "PROFIT_READY 🟢" if total_result > 1 else "BEP_READY 🟡"
                            st.success(f"**{status_alert} pada {t_match}!** Pasang {close_side.upper()} modal {min_bet} di odds {close_odds} (Sumber: {live['bm']}).")
                            
                            pesan_tg = f"🚨 *MYRIARK SIGNAL: {status_alert}* 🚨\n\n" \
                                       f"⚽ *{t_match}*\n" \
                                       f"▪️ *Tutup Posisi:* {close_side.upper()}\n" \
                                       f"▪️ *Line Target:* {live['line']} \n" \
                                       f"▪️ *Odds (Indo):* {close_odds} ({live['bm']})\n" \
                                       f"💰 *MIN BET:* Rp {min_bet:,.0f}\n\n" \
                                       f"Estimasi Hasil: Rp {total_result:,.0f}"
                            kirim_telegram(pesan_tg)
                        else:
                            st.info(f"Belum siap untuk {t_match}. Butuh modal {min_bet}, hasil akhir masih minus: {total_result}")
                
                # PATCH 18: Rerun untuk update live odds display
                time.sleep(0.5)
                st.rerun()
