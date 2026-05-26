\
"""
app.py — Myriark Sniper Dashboard (Modular Version)
Versi 2.1 — Edisi Proteksi Kuota API (Brankas Waktu & Placebo Refresh)
Arsitektur oleh Gemini & Claude AI

Alur Orkestrasi:
1. Layar utama murni membaca database Supabase (Gratis & Aman).
2. Sakelar Auto-Refresh murni sebagai hiasan/pemicu layar berkedip ulang untuk data lokal.
3. Tombol SCAN menjadi satu-satunya gerbang eksekusi penarikan odds.
4. Fungsi penarikan API dibungkus @st.cache_data dengan TTL 3 Menit (Anti-Spam Klik).
"""

import streamlit as st
import time
import logging
import uuid
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from supabase import create_client, Client

# Import modul internal Myriark
import tos
import dos
import pos

# =========================================================
# KONFIGURASI & LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
WITA = ZoneInfo("Asia/Makassar")

st.set_page_config(
    page_title="Myriark Sniper",
    page_icon="🛡️",
    layout="wide"
)

# =========================================================
# KONEKSI SUPABASE & SECRETS
# =========================================================
try:
    SUPABASE_URL      = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY      = st.secrets["SUPABASE_KEY"]
    ODDS_API_KEY      = st.secrets["ODDS_API_KEY"]
    BOT_TOKEN         = st.secrets["TELEGRAM_BOT_TOKEN"]
    CHAT_ID           = st.secrets["TELEGRAM_CHAT_ID"]

    supabase: Client  = create_client(SUPABASE_URL, SUPABASE_KEY)
    logging.info("Supabase connected successfully.")

except Exception as e:
    st.error("🔴 Gagal terkoneksi ke Supabase atau berkas Secrets (.streamlit/secrets.toml) tidak lengkap.")
    logging.error(f"Startup Error: {e}")
    st.stop()


# =========================================================
# FUNGSI BRANKAS API (CACHE PROTECTION LAYER)
# =========================================================
@st.cache_data(ttl=180, show_spinner=False)
def tarik_odds_lewat_brankas(api_key):
    """
    Membungkus fungsi tos.jalankan() ke dalam memori jangka pendek Streamlit.
    Jika tombol Scan ditekan berulang kali dalam kurun waktu < 3 menit (180 detik),
    fungsi ini akan langsung memulangkan data hasil tarikan terakhir dari brankas lokal,
    TANPA menembak server The Odds API lagi. Kuota Bos 100% aman dari bocor.
    """
    logging.info("Brankas Kosong/Expired! Menembak The Odds API secara live...")
    return tos.jalankan(api_key)


# =========================================================
# HELPER DATABASE SUPABASE (100% GRATIS REQUEST)
# =========================================================
def ambil_tiket_running():
    try:
        res = supabase.table("tickets").select("*").eq("status", "RUNNING").execute()
        return res.data or []
    except Exception as e:
        logging.error(f"Fetch tickets error: {e}")
        return []


def ambil_history_semua():
    """
    Ambil semua history snapshot dari Supabase.
    Return dict {ticket_id: [list snapshot]}
    """
    try:
        res = supabase.table("snapshots").select("*").execute()
        data = res.data or []

        history_map = {}
        for row in data:
            tid = row.get("ticket_id")
            if tid not in history_map:
                history_map[tid] = []
            history_map[tid].append(row)

        return history_map
    except Exception as e:
        logging.error(f"Fetch history error: {e}")
        return {}


def simpan_snapshot(snapshot: dict):
    try:
        supabase.table("snapshots").insert(snapshot).execute()
    except Exception as e:
        logging.error(f"Save snapshot error: {e}")


def hapus_tiket(ticket_id: str):
    try:
        supabase.table("tickets").delete().eq("ticket_id", ticket_id).execute()
        logging.info(f"Tiket dihapus: {ticket_id}")
        return True
    except Exception as e:
        logging.error(f"Delete ticket error: {e}")
        return False


def settle_tiket(ticket_id: str):
    try:
        supabase.table("tickets").update(
            {"status": "SETTLED"}
        ).eq("ticket_id", ticket_id).execute()
        logging.info(f"Tiket settled: {ticket_id}")
        return True
    except Exception as e:
        logging.error(f"Settle ticket error: {e}")
        return False


# =========================================================
# UI — HEADER UTAMA
# =========================================================
st.title("🛡️ Myriark Sniper Dashboard")
st.caption(
    f"Waktu Sistem Dashboard: {datetime.now(WITA).strftime('%Y-%m-%d %H:%M:%S')} WITA  |  "
    f"v2.1 — Anti-Kuota Bocor Edition"
)

# =========================================================
# UI — INPUT TIKET BARU
# =========================================================
with st.expander("➕ INPUT TIKET BARU", expanded=False):
    with st.form("form_tiket", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            match_name = st.text_input(
                "Nama Match (Pertandingan)",
                placeholder="Contoh: Lazio vs Pisa (Nama wajib 100% persis rilis API)"
            )
            side = st.selectbox("Posisi Taruhan (Side)", ["over", "under"])
            line = st.number_input("Garis Batas (Line)", value=2.5, step=0.25, min_value=0.25)

        with col2:
            odds = st.number_input(
                "Odds Indo / Kei (Pakai tanda minus jika negatif)",
                value=-1.10,
                step=0.01,
                format="%.2f"
            )
            stake = st.number_input(
                "Modal / Nilai Taruhan (Rp)",
                value=100000,
                step=10000,
                min_value=1000
            )

        submit = st.form_submit_button("💾 Simpan Tiket Baru", type="primary")

        if submit:
            if not match_name.strip():
                st.error("❌ Nama pertandingan tidak boleh kosong.")
            elif odds == 0:
                st.error("❌ Nilai Odds/Kei tidak valid (tidak boleh 0).")
            else:
                ticket_id = f"TKT-{datetime.now(WITA).strftime('%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
                data_tiket = {
                    "ticket_id"  : ticket_id,
                    "match"      : match_name.strip(),
                    "status"     : "RUNNING",
                    "entry_side" : side,
                    "entry_line" : line,
                    "entry_odds" : odds,
                    "entry_stake": stake
                }
                try:
                    supabase.table("tickets").insert(data_tiket).execute()
                    st.success(f"✅ Tiket {ticket_id} berhasil masuk ke antrean radar!")
                    logging.info(f"Tiket disimpan ke DB: {ticket_id} | {match_name}")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error("❌ Gagal menyimpan tiket ke database Supabase.")
                    logging.error(f"Insert database error: {e}")


# =========================================================
# UI — DAFTAR TIKET YANG SEDANG RUNNING
# =========================================================
st.subheader("📋 Tiket Berjalan (RUNNING)")
tiket_aktif = ambil_tiket_running()

if not tiket_aktif:
    st.info("Tidak ada tiket yang sedang berjalan di dalam radar saat ini.")
else:
    for tiket in tiket_aktif:
        with st.container():
            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(
                [1.5, 2.0, 1.0, 1.0, 1.0, 1.5, 0.7, 0.7]
            )
            tid = tiket.get("ticket_id", "?")
            with col1: st.write(f"`{tid}`")
            with col2: st.write(tiket.get("match", "?"))
            with col3: st.write(tiket.get("entry_side", "?").upper())
            with col4: st.write(tiket.get("entry_line", "?"))
            with col5: st.write(tiket.get("entry_odds", "?"))
            with col6: st.write(f"Rp {tiket.get('entry_stake', 0):,.0f}")

            with col7:
                if st.button("✅", key=f"settle_{tid}", help="Tandai tiket Settle/Selesai"):
                    if settle_tiket(tid):
                        st.success(f"Settled!")
                        time.sleep(0.5)
                        st.rerun()

            with col8:
                if st.button("🗑️", key=f"del_{tid}", help="Hapus tiket dari radar"):
                    if st.session_state.get(f"confirm_{tid}", False):
                        if hapus_tiket(tid):
                            st.success("Dihapus!")
                            time.sleep(0.5)
                            st.rerun()
                    else:
                        st.session_state[f"confirm_{tid}"] = True
                        st.warning("Konfirmasi hapus? Klik ikon sampah sekali lagi.")


# =========================================================
# UI — CONTROL PANEL SCANNER (ANTI-BOCOOR ENGINE)
# =========================================================
st.divider()
col_scan, col_auto = st.columns([2, 1])

with col_scan:
    scan_button = st.button(
        "🚀 JALANKAN SCAN MYRIARK SEKARANG",
        type="primary",
        use_container_width=True
    )

with col_auto:
    # SAKELAR REFRESH HIASAN UI (Placebo / Dummy Filter)
    # Berfungsi me-refresh UI dan Supabase lokal saja, sama sekali tidak memanggil API luar.
    auto_refresh_placebo = st.checkbox("🔄 Auto-Refresh Layar (30 detik)")

if auto_refresh_placebo:
    time.sleep(30)
    st.rerun()

# =========================================================
# PIPELINE EKSEKUSI UTAMA (HANYA AKTIF JIKA TOMBOL DIKLIK)
# =========================================================
if scan_button:
    if not tiket_aktif:
        st.warning("⚠️ Scanner dibatalkan: Tidak ada tiket bertanda RUNNING di database.")
    else:
        with st.spinner("Membidik target pasar... (Mengambil dari Brankas jika klik < 3 menit)"):

            # STEP 1 — Ambil Data Melalui Lapisan Brankas (Proteksi Kuota Mutlak)
            hasil_tos = tarik_odds_lewat_brankas(ODDS_API_KEY)

            if hasil_tos["status"] != "OK":
                st.error(f"❌ Kegagalan Mesin Penarik (TOS): {hasil_tos.get('pesan', 'Unknown')}")
                logging.error(f"TOS Critical Error: {hasil_tos}")
            else:
                live_data = hasil_tos["live_data"]

                # Menampilkan Laporan Sisa Amunisi/Kuota API ke Tampilan
                quota = hasil_tos.get("quota", {})
                st.caption(
                    f"📊 Status Amunisi Kuota — Sisa Jatah (Remaining): {quota.get('remaining','?')} | "
                    f"Terpakai (Used): {quota.get('used','?')} | "
                    f"Biaya Tarikan Terakhir (Cost): {quota.get('cost','?')} | "
                    f"Pertandingan Aktif Terfilter: {hasil_tos['total_aktif']}"
                )

                # STEP 2 — Tarik Riwayat Lama dari Database Supabase (100% Gratis)
                history_map = ambil_history_semua()

                # STEP 3 — Hitung Kalkulasi Hedging & Analisis Tren (DOS Engine)
                hasil_dos = dos.jalankan(live_data, tiket_aktif, history_map)

                # Simpan Snapshot Perubahan ke Database (Kecuali Pertandingan Hilang/No Live)
                for snapshot in hasil_dos:
                    if snapshot.get("status") not in ["NO_LIVE", "NO_ODDS"]:
                        simpan_snapshot(snapshot)

                # STEP 4 — Kirim Notifikasi via Telegram (POS Engine)
                log_pos = pos.jalankan(hasil_dos, BOT_TOKEN, CHAT_ID)

                # =========================================================
                # UI — TAMPILKAN HASIL BIDIKAN SCANNER
                # =========================================================
                st.subheader("📊 Laporan Bidikan Harga Pasar")

                ikon_status = {
                    "PROFIT_READY": "🟢",
                    "BEP_READY"   : "🟡",
                    "BETTER"      : "📈",
                    "WORSE"       : "⚠️",
                    "FLAT"        : "➡️",
                    "NOT_READY"   : "🔴",
                    "NO_LIVE"     : "❓",
                    "NO_ODDS"     : "❓",
                }

                for hasil in hasil_dos:
                    status      = hasil.get("status", "?")
                    ikon        = ikon_status.get(status, "❓")
                    match       = hasil.get("match", "?")
                    tid         = hasil.get("ticket_id", "?")
                    tren        = hasil.get("tren", "?")
                    close_stake = hasil.get("close_stake")
                    total       = hasil.get("total_result", 0)

                    if status in ["NO_LIVE", "NO_ODDS"]:
                        st.warning(f"{ikon} `{tid}` — {hasil.get('pesan', status)}")
                        continue

                    if status == "PROFIT_READY":
                        st.success(
                            f"{ikon} **{status}** | `{tid}` | {match}

"
                            f"Lawan Arah: {hasil.get('close_side','?').upper()} "
                            f"Odds Bandar: {hasil.get('close_odds','?')} | "
                            f"Rekomendasi Min Bet: Rp {close_stake:,.0f} | "
                            f"Proyeksi Bersih: Rp {total:,.0f} | "
                            f"Arah Pergerakan Tren: {tren}"
                        )
                    elif status == "BEP_READY":
                        st.warning(
                            f"{ikon} **{status}** | `{tid}` | {match}

"
                            f"Lawan Arah: {hasil.get('close_side','?').upper()} "
                            f"Odds Bandar: {hasil.get('close_odds','?')} | "
                            f"Rekomendasi Min Bet: Rp {close_stake:,.0f} | "
                            f"Proyeksi Hasil: Rp {total:,.0f} (Balik Modal) | "
                            f"Arah Pergerakan Tren: {tren}"
                        )
                    elif status == "WORSE":
                        st.error(
                            f"{ikon} **{status}** | `{tid}` | {match}

"
                            f"Odds Lawan: {hasil.get('close_odds','?')} | "
                            f"Biaya Min Bet Membengkak: Rp {close_stake:,.0f} | "
                            f"Arah Pergerakan Tren: {tren}"
                        )
                    else:
                        st.info(
                            f"{ikon} **{status}** | `{tid}` | {match} | "
                            f"Tren Pergerakan: {tren}"
                        )

                # Laporan Pengiriman Pesan Telegram
                if log_pos:
                    terkirim = sum(1 for l in log_pos if l["terkirim"])
                    st.caption(f"📨 Jalur Log Komunikasi: {terkirim}/{len(log_pos)} pesan terkirim ke Telegram.")

                # Menyimpan data pasar terakhir ke session state untuk tampilan bawah Expand
                if live_data:
                    st.session_state.live_market_data = live_data

        time.sleep(0.3)

# =========================================================
# UI — MONITORING DATA PASAR LENGKAP (EXPANDER)
# =========================================================
if st.session_state.get("live_market_data"):
    st.divider()
    with st.expander(
        f"📡 Intisari Data Pasar Terakhir ({len(st.session_state.live_market_data)} Pertandingan)",
        expanded=False
    ):
        odds_list = []
        for match_name, odds_data in st.session_state.live_market_data.items():
            odds_list.append({
                "Pertandingan": match_name,
                "Harga Over"   : odds_data.get("over", "N/A"),
                "Harga Under"  : odds_data.get("under", "N/A"),
                "Garis Pasaran": odds_data.get("line", "N/A"),
                "Nama Bandar"  : odds_data.get("bookmaker", "N/A")
            })

        df = pd.DataFrame(odds_list)
        st.dataframe(df, use_container_width=True, hide_index=True)
