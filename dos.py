"""
dos.py — Dump Odds Service (Modular Version)
Versi: 2.0 by Kimi AI

Arsitektur oleh Kimi AI (dibangun di atas fondasi Gemini v1.00 & Claude AI)

Perubahan di Kimi v2.0:
- Normalisasi nama match (case-insensitive) untuk eliminasi mismatch.
- Fix analisa_tren: history dengan 1 item tetap bisa dibandingkan.
- Transparansi perhitungan: tambah net_entry_wins & net_close_wins.
- Validasi input lebih ketat, logging lebih jelas.
- dos.py tetap JANTUNG & KOMANDAN pipeline.
- Menghitung BEP/PROFIT dengan murni rumus Indo odds.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

WITA = ZoneInfo("Asia/Makassar")


# =========================================================
# RUMUS INDO ODDS (KEI)
# =========================================================
def hitung_profit(odds, stake):
    """
    Hitung profit jika menang.
    Positif (1.05) : profit = stake * odds
    Negatif (-1.15): profit = stake / abs(odds)
    """
    if odds is None or stake is None or stake <= 0:
        return 0
    if odds < 0:
        return round(stake / abs(odds), 2)
    else:
        return round(stake * odds, 2)


def hitung_close_stake(modal, close_odds):
    """
    Hitung minimum stake close agar BEP.
    Negatif (-1.15): modal * abs(odds) = 115.000
    Positif (1.15) : modal / odds      = 86.956
    """
    if close_odds is None or close_odds == 0:
        return None
    if close_odds < 0:
        return round(modal * abs(close_odds), 2)
    else:
        return round(modal / close_odds, 2)


def decimal_ke_indo(decimal_odds):
    """
    Utility konversi decimal ke Indo odds.
    Decimal >= 2.00 -> Indo positif : decimal - 1
    Decimal <  2.00 -> Indo negatif : -1 / (decimal - 1)
    """
    if decimal_odds is None or decimal_odds <= 1.01:
        return None
    if decimal_odds >= 2.0:
        return round(decimal_odds - 1, 2)
    else:
        return round(-1 / (decimal_odds - 1), 2)


# =========================================================
# UTILITAS
# =========================================================
def normalize_match_name(name):
    """
    Normalisasi nama match untuk matching konsisten.
    lowercase + hapus spasi berlebih.
    """
    if not name or not isinstance(name, str):
        return ""
    return " ".join(name.lower().split())


# =========================================================
# ANALISA TREN DARI HISTORY SUPABASE
# =========================================================
def analisa_tren(history_odds, close_odds_sekarang):
    """
    Membandingkan pergerakan harga kompensasi (close odds) saat ini dengan masa lalu.
    Return: "BARU" | "NAIK" | "TURUN" | "FLAT"
    """
    if not history_odds:
        return "BARU"

    close_history = []
    for h in history_odds:
        indo = h.get("close_odds") if isinstance(h, dict) else None
        if indo is not None:
            close_history.append(indo)

    if not close_history:
        return "BARU"

    semua = close_history + [close_odds_sekarang]
    naik  = 0
    turun = 0

    for i in range(1, len(semua)):
        if semua[i] > semua[i - 1]:
            naik += 1
        elif semua[i] < semua[i - 1]:
            turun += 1

    if naik > turun:
        return "NAIK"
    elif turun > naik:
        return "TURUN"
    else:
        return "FLAT"


# =========================================================
# PROSES SATU TIKET (OTAK UTAMA KIMI V2.0)
# =========================================================
def proses_tiket(tiket, live_data, history_tiket):
    """
    Proses satu tiket terhadap live odds.
    Return snapshot dict atau None jika tiket invalid.
    """
    # --- Ekstraksi & Validasi Dasar ---
    ticket_id  = tiket.get("ticket_id", "NO-ID")
    match_raw  = tiket.get("match", "")
    entry_side = tiket.get("entry_side", "").lower()
    entry_odds = tiket.get("entry_odds")
    entry_stake= tiket.get("entry_stake")
    entry_line = tiket.get("entry_line")

    match_name = normalize_match_name(match_raw)

    if not match_name:
        logging.warning(f"[dos] Skip {ticket_id}: nama match kosong.")
        return None

    if entry_side not in ["over", "under"]:
        logging.warning(f"[dos] Skip {ticket_id}: entry_side invalid ({entry_side}).")
        return None

    if entry_odds is None or entry_stake is None or entry_stake <= 0:
        logging.warning(f"[dos] Skip {ticket_id}: odds atau stake invalid.")
        return None

    # --- Cek ketersediaan di Live Data ---
    if match_name not in live_data:
        logging.info(f"[dos] {ticket_id}: {match_name} tidak ditemukan di live_data.")
        return {
            "ticket_id" : ticket_id,
            "match"     : match_raw,
            "status"    : "NO_LIVE",
            "pesan"     : "Live odds tutup atau tidak tersedia"
        }

    live        = live_data[match_name]
    close_side  = "under" if entry_side == "over" else "over"
    close_odds  = live.get(close_side)
    live_line   = live.get("line")
    bookmaker   = live.get("bookmaker", "?")

    if close_odds is None:
        logging.info(f"[dos] {ticket_id}: odds {close_side.upper()} ditarik bandar.")
        return {
            "ticket_id": ticket_id,
            "match"    : match_raw,
            "status"   : "NO_ODDS",
            "pesan"    : f"Odds {close_side.upper()} ditarik bandar"
        }

    # --- Hitung Modal Kompensasi & Proyeksi ---
    close_stake    = hitung_close_stake(entry_stake, close_odds)
    entry_profit   = hitung_profit(entry_odds, entry_stake)
    close_profit   = hitung_profit(close_odds, close_stake) if close_stake else 0

    # Net profit jika salah satu sisi menang
    net_entry_wins = round(entry_profit - (close_stake or 0), 2)
    net_close_wins = round(close_profit - entry_stake, 2)
    total_result   = net_close_wins  # backward compatible dengan v1.00

    tren = analisa_tren(history_tiket, close_odds)

    # --- Logika Middle (Penjepit Harga) & Rem Darurat ---
    kondisi_line = "AMAN"
    selisih_line = 0.0

    if entry_line is not None and live_line is not None:
        try:
            selisih_line = float(live_line) - float(entry_line)
            if abs(selisih_line) > 0.01:
                if entry_side == "over":
                    if selisih_line > 0:
                        kondisi_line = "PELUANG_MIDDLE"
                    else:
                        kondisi_line = "BAHAYA_GANDA"
                elif entry_side == "under":
                    if selisih_line < 0:
                        kondisi_line = "PELUANG_MIDDLE"
                    else:
                        kondisi_line = "BAHAYA_GANDA"
        except (ValueError, TypeError):
            pass

    # --- Penentuan Status (Vonis Mesin) ---
    if kondisi_line == "BAHAYA_GANDA":
        base_status = "DANGER_LINE_SHIFT"
    else:
        if total_result > 1:
            base_status = "PROFIT_READY"
        elif total_result >= -1:
            base_status = "BEP_READY"
        else:
            if tren == "NAIK":
                base_status = "BETTER"
            elif tren == "TURUN":
                base_status = "WORSE"
            elif tren == "FLAT":
                base_status = "FLAT"
            else:
                base_status = "NOT_READY"

    # --- Bungkus Snapshot ---
    snapshot = {
        "time"          : datetime.now(WITA).strftime("%Y-%m-%d %H:%M:%S"),
        "ticket_id"     : ticket_id,
        "match"         : match_raw,
        "match_norm"    : match_name,
        "bookmaker"     : bookmaker,
        "entry_side"    : entry_side,
        "entry_line"    : entry_line,
        "entry_odds"    : entry_odds,
        "entry_stake"   : entry_stake,
        "entry_profit"  : entry_profit,
        "close_side"    : close_side,
        "close_line"    : live_line,
        "close_odds"    : close_odds,
        "close_stake"   : close_stake,
        "close_profit"  : close_profit,
        "net_entry_wins": net_entry_wins,
        "net_close_wins": net_close_wins,
        "total_result"  : total_result,
        "tren"          : tren,
        "kondisi_line"  : kondisi_line,
        "status"        : base_status
    }

    logging.info(
        f"[dos] {ticket_id} | {match_name} | {base_status} | "
        f"O:{live.get('over')} U:{live.get('under')} Line:{live_line} | "
        f"NetEntry:{net_entry_wins} NetClose:{net_close_wins}"
    )

    return snapshot


# =========================================================
# BATCH PROCESSOR
# =========================================================
def jalankan(live_data, tiket_list, history_map):
    """
    Proses batch tiket terhadap live_data.
    Return list snapshot.
    """
    if not live_data or not isinstance(live_data, dict):
        logging.error("[dos] live_data invalid atau kosong.")
        return []

    if not tiket_list or not isinstance(tiket_list, list):
        logging.error("[dos] tiket_list invalid atau kosong.")
        return []

    # Normalisasi keys di live_data untuk safety
    live_data_norm = {}
    for key, val in live_data.items():
        norm_key = normalize_match_name(key)
        if norm_key:
            live_data_norm[norm_key] = val

    hasil = []
    for tiket in tiket_list:
        if not isinstance(tiket, dict):
            logging.warning("[dos] Skip item non-dict di tiket_list.")
            continue

        ticket_id     = tiket.get("ticket_id", "NO-ID")
        history_tiket = history_map.get(ticket_id, []) if isinstance(history_map, dict) else []
        result        = proses_tiket(tiket, live_data_norm, history_tiket)

        if result is not None:
            hasil.append(result)

    logging.info(f"[dos] Batch selesai: {len(hasil)} tiket diproses.")
    return hasil


# =========================================================
# STANDALONE TESTER
# =========================================================
if __name__ == "__main__":
    print("Mengeksekusi Standalone Tester Myriark DOS v2.0 by Kimi AI...")
    print("=" * 50)

    # Simulasi live_data dari tos.py v3.0 (sudah normalized)
    live_data_test = {
        "manchester united vs liverpool": {
            "over"     : -1.15,
            "under"    : 1.05,
            "line"     : 2.5,
            "bookmaker": "Pinnacle"
        },
        "real madrid vs barcelona": {
            "over"     : 1.10,
            "under"    : -1.20,
            "line"     : 3.0,
            "bookmaker": "Bet365"
        }
    }

    # Simulasi tiket (dengan case berbeda untuk test normalize)
    tiket_list_test = [
        {
            "ticket_id" : "T001",
            "match"     : "Manchester United vs Liverpool",
            "entry_side": "over",
            "entry_odds": -1.15,
            "entry_stake": 100000,
            "entry_line": 2.5
        },
        {
            "ticket_id" : "T002",
            "match"     : "REAL MADRID vs Barcelona",
            "entry_side": "under",
            "entry_odds": 1.05,
            "entry_stake": 100000,
            "entry_line": 2.5
        },
        {
            "ticket_id" : "T003",
            "match"     : "AC Milan vs Juventus",
            "entry_side": "over",
            "entry_odds": 1.10,
            "entry_stake": 50000,
            "entry_line": 2.5
        }
    ]

    history_map_test = {
        "T001": [{"close_odds": 1.00}, {"close_odds": 1.05}],
        "T002": [{"close_odds": -1.25}],
    }

    hasil = jalankan(live_data_test, tiket_list_test, history_map_test)

    print(f"\nHasil: {len(hasil)} snapshot")
    for snap in hasil:
        print(f"\n  Ticket : {snap['ticket_id']}")
        print(f"  Match  : {snap['match']} (norm: {snap['match_norm']})")
        print(f"  Status : {snap['status']}")
        print(f"  Tren   : {snap['tren']}")
        print(f"  Line   : {snap['kondisi_line']} (selisih {snap.get('close_line', 0) - (snap.get('entry_line') or 0)})")
        print(f"  NetEntryWins: {snap['net_entry_wins']}")
        print(f"  NetCloseWins: {snap['net_close_wins']}")
        if "pesan" in snap:
            print(f"  Pesan  : {snap['pesan']}")

    print("\n" + "=" * 50)
