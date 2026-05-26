"""
dos.py — Dump Odds Service (Modular Version)
Versi: Gemini v1.00 (Edisi Sniper Middle / Penjepit Harga)
Arsitektur oleh Gemini & Claude AI

Perubahan Ekstrem di Gemini v1.00:
- Pengenalan logika "Middle" (Peluang Kemenangan Ganda dari pergeseran Line).
- Pengenalan rem darurat "BAHAYA_GANDA" untuk mencegah kerugian ganda akibat Line turun.
- dos.py adalah JANTUNG & KOMANDAN pipeline.
- Menghitung BEP/PROFIT dengan murni rumus Indo odds.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

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
    if decimal_odds is None or decimal_odds <= 1.01:
        return None
    if decimal_odds >= 2.0:
        return round(decimal_odds - 1, 2)
    else:
        return round(-1 / (decimal_odds - 1), 2)


# =========================================================
# ANALISA TREN DARI HISTORY SUPABASE
# =========================================================
def analisa_tren(history_odds: list, close_odds_sekarang: float) -> str:
    """
    Membandingkan pergerakan harga kompensasi (close odds) saat ini dengan masa lalu.
    """
    if not history_odds or len(history_odds) < 2:
        return "BARU"

    close_history = []
    for h in history_odds:
        indo = h.get("close_odds")
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
# PROSES SATU TIKET (OTAK UTAMA GEMINI V1.00)
# =========================================================
def proses_tiket(tiket: dict, live_data: dict, history_tiket: list) -> dict:
    ticket_id  = tiket.get("ticket_id", "NO-ID")
    match      = tiket.get("match", "")
    entry_side = tiket.get("entry_side", "").lower()
    entry_odds = tiket.get("entry_odds")
    entry_stake= tiket.get("entry_stake")
    entry_line = tiket.get("entry_line")

    # Validasi Dasar
    if not match or entry_side not in ["over", "under"]:
        return None
    if entry_odds is None or entry_stake is None or entry_stake <= 0:
        return None

    # Cek ketersediaan di Live Data
    if match not in live_data:
        return {
            "ticket_id" : ticket_id,
            "match"     : match,
            "status"    : "NO_LIVE",
            "pesan"     : f"Live odds tutup atau tidak tersedia"
        }

    live        = live_data[match]
    close_side  = "under" if entry_side == "over" else "over"
    close_odds  = live.get(close_side)
    live_line   = live.get("line")
    bookmaker   = live.get("bookmaker", "?")

    if close_odds is None:
        return {
            "ticket_id": ticket_id,
            "match"    : match,
            "status"   : "NO_ODDS",
            "pesan"    : f"Odds {close_side.upper()} ditarik bandar"
        }

    # Hitung Modal Kompensasi (BEP Stake) dan Proyeksi
    close_stake  = hitung_close_stake(entry_stake, close_odds)
    entry_profit = hitung_profit(entry_odds, entry_stake)
    close_profit = hitung_profit(close_odds, close_stake) if close_stake else 0
    total_result = close_profit - entry_stake

    tren = analisa_tren(history_tiket, close_odds)

    # ---------------------------------------------------------
    # LOGIKA MIDDLE (PENJEPIT HARGA) & REM DARURAT
    # ---------------------------------------------------------
    kondisi_line = "AMAN"
    selisih_line = 0.0

    if entry_line and live_line:
        try:
            selisih_line = float(live_line) - float(entry_line)
            if abs(selisih_line) > 0.01: # Ada pergerakan line
                if entry_side == "over":
                    if selisih_line > 0:
                        kondisi_line = "PELUANG_MIDDLE" # Live Line Naik (Menguntungkan)
                    else:
                        kondisi_line = "BAHAYA_GANDA"   # Live Line Turun (Merugikan ganda)
                        
                elif entry_side == "under":
                    if selisih_line < 0:
                        kondisi_line = "PELUANG_MIDDLE" # Live Line Turun (Menguntungkan)
                    else:
                        kondisi_line = "BAHAYA_GANDA"   # Live Line Naik (Merugikan ganda)
        except (ValueError, TypeError):
            pass

    # ---------------------------------------------------------
    # PENENTUAN STATUS (VONIS MESIN)
    # ---------------------------------------------------------
    if kondisi_line == "BAHAYA_GANDA":
        # Rem Darurat ditarik! Mengabaikan hitungan total_result.
        base_status = "DANGER_LINE_SHIFT" 
    else:
        # Jika kondisi AMAN atau PELUANG_MIDDLE, biarkan mesin mengeksekusi hitungan profit
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

    # Bungkus Snapshot
    snapshot = {
        "time"        : datetime.now(WITA).strftime("%Y-%m-%d %H:%M:%S"),
        "ticket_id"   : ticket_id,
        "match"       : match,
        "bookmaker"   : bookmaker,
        "entry_side"  : entry_side,
        "entry_line"  : entry_line,
        "entry_odds"  : entry_odds,
        "entry_stake" : entry_stake,
        "close_side"  : close_side,
        "close_line"  : live_line,
        "close_odds"  : close_odds,
        "close_stake" : close_stake,
        "entry_profit": entry_profit,
        "close_profit": close_profit,
        "total_result": total_result,
        "tren"        : tren,
        "kondisi_line": kondisi_line,
        "status"      : base_status
    }

    return snapshot


def jalankan(live_data: dict, tiket_list: list, history_map: dict) -> list:
    if not live_data or not isinstance(live_data, dict):
        return []
    if not tiket_list:
        return []

    hasil = []
    for tiket in tiket_list:
        ticket_id     = tiket.get("ticket_id", "NO-ID")
        history_tiket = history_map.get(ticket_id, [])
        result = proses_tiket(tiket, live_data, history_tiket)

        if result is not None:
            hasil.append(result)

    return hasil

if __name__ == "__main__":
    print("Mengeksekusi Standalone Tester Myriark DOS Gemini v1.00...")
