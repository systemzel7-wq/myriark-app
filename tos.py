"""
tos.py — Tarik Odds Service (Modular Version)
Versi 2.1 — Edisi Sniper Targeting
Arsitektur oleh Gemini & Claude AI

Perbaikan:
- Menghapus hardcode SPORT_KEY = "soccer" (Mencegah Error 400 & Kuota Bocor).
- Menambahkan parameter `daftar_liga` agar app.py bisa membidik target spesifik.
- Jika daftar_liga tidak dikirim, otomatis memakai "upcoming" (Jalan pintas 1 kuota).
- Loop multi-liga untuk menarik beberapa liga sekaligus jika diperlukan.
- Konversi Decimal ke Indo Odds tetap dipertahankan.
"""

import requests
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

WITA = ZoneInfo("Asia/Makassar")
REGIONS = "eu"
MARKETS = "totals"
ODDS_FORMAT = "decimal"

# Prioritas bandar, mesin akan mengunci Pinnacle pertama kali. 
# Jika Pinnacle tidak buka harga, mundur ke bet365, dst.
BOOKMAKER_PRIORITY = [
    "pinnacle",
    "bet365",
    "williamhill",
    "betfair",
    "unibet",
    "bwin",
    "betway",
]

def decimal_ke_indo(decimal_odds):
    if decimal_odds is None or decimal_odds <= 1.01:
        return None
    if decimal_odds >= 2.0:
        return round(decimal_odds - 1, 2)
    else:
        return round(-1 / (decimal_odds - 1), 2)

def jalankan(api_key, daftar_liga=None):
    """
    Fungsi utama untuk menarik data dari The Odds API.
    daftar_liga: list string berisi sport_key spesifik (misal: ['soccer_epl', 'soccer_italy_serie_a']).
    Jika kosong, default ke ['upcoming'].
    """
    
    # [PENGAMAN] Jika dari app.py belum mengirim daftar liga spesifik,
    # kita arahkan ke 'upcoming' agar tetap aman dan hanya makan 1 kuota.
    if not daftar_liga:
        daftar_liga = ["upcoming"]

    hasil_akhir = {
        "status": "OK",
        "pesan": "Sukses",
        "live_data": {},
        "total_raw": 0,
        "total_aktif": 0,
        "quota": {"used": 0, "remaining": "Unknown", "cost": 0}
    }

    # Mesin Sniper mulai membidik satu per satu liga yang diminta
    for liga in daftar_liga:
        logging.info(f"TOS membidik liga: {liga}...")
        url = f"https://api.the-odds-api.com/v4/sports/{liga}/odds"
        params = {
            "apiKey": api_key,
            "regions": REGIONS,
            "markets": MARKETS,
            "oddsFormat": ODDS_FORMAT
        }

        try:
            # Tembak API
            response = requests.get(url, params=params, timeout=15)
            
            # Rekap pemakaian Kuota dari Server The Odds
            quota_used = response.headers.get("x-requests-used", "0")
            quota_rem = response.headers.get("x-requests-remaining", "Unknown")
            hasil_akhir["quota"]["used"] = quota_used
            hasil_akhir["quota"]["remaining"] = quota_rem
            hasil_akhir["quota"]["cost"] += 1  # Tambah 1 kuota terpakai di mesin lokal

            if response.status_code == 200:
                data = response.json()
                hasil_akhir["total_raw"] += len(data)
                
                # Proses Pemilahan Data (Parsing)
                for match in data:
                    match_name = f"{match['home_team']} vs {match['away_team']}"
                    best_odds = None
                    
                    # Cari Bookmaker dengan urutan prioritas (Pinnacle tertinggi)
                    for bookie_key in BOOKMAKER_PRIORITY:
                        bookie_data = next((b for b in match.get("bookmakers", []) if b["key"] == bookie_key), None)
                        if bookie_data:
                            markets = bookie_data.get("markets", [])
                            totals_market = next((m for m in markets if m["key"] == "totals"), None)
                            
                            if totals_market:
                                outcomes = totals_market.get("outcomes", [])
                                over_data = next((o for o in outcomes if o["name"].lower() == "over"), None)
                                under_data = next((o for o in outcomes if o["name"].lower() == "under"), None)
                                
                                if over_data and under_data:
                                    best_odds = {
                                        "over": decimal_ke_indo(over_data.get("price")),
                                        "under": decimal_ke_indo(under_data.get("price")),
                                        "line": over_data.get("point"),
                                        "bookmaker": bookie_data.get("title", bookie_key)
                                    }
                                    break # Langsung keluar dari loop karena prioritas tertinggi sudah dapat

                    # Jika dapat harga O/U, simpan ke hasil live_data
                    if best_odds:
                        hasil_akhir["live_data"][match_name] = best_odds
                        hasil_akhir["total_aktif"] += 1

            elif response.status_code == 401:
                return {"status": "ERROR", "pesan": "API Key tidak valid.", "live_data": {}}
            elif response.status_code == 429:
                return {"status": "ERROR", "pesan": "Quota API The Odds Habis!", "live_data": {}}
            else:
                logging.error(f"TOS Error API {response.status_code} pada liga {liga}")

        except requests.exceptions.Timeout:
            logging.error(f"TOS Timeout pada liga {liga}")
        except Exception as e:
            logging.error(f"TOS Critical Error pada {liga}: {e}")

    return hasil_akhir

# =========================================================
# STANDALONE — UNTUK DEBUG TESTER
# =========================================================
if __name__ == "__main__":
    # Cara test manual di terminal:
    # API_KEY = "TULIS_API_KEY_BOS_DISINI"
    # hasil = jalankan(API_KEY, ["soccer_epl"])
    # print(hasil)
    pass
