"""
tos.py — Tarik Odds Service (Modular Version)
Versi 3.0 by Kimi AI

Tugas:
1. Tarik data dari The Odds API (sport=upcoming, 1 quota)
2. Filter soccer_ di RAM — sampah tidak menyentuh storage
3. Update teams_db.json dari data bola saja
4. Filter waktu (LIVE + 24 jam ke depan)
5. Transformasi format untuk dos.py
6. Return hasil ke app.py

Tidak ada penyimpanan raw — data langsung dilempar ke dos.py.
dos.py yang bertanggung jawab menyimpan ke Supabase.
"""

import requests
import json
import os
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

logging.basicConfig(
    level=logging.DEBUG,  # UBAH dari INFO ke DEBUG
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# =========================================================
# KONFIGURASI
# =========================================================
WITA        = ZoneInfo("Asia/Makassar")
UTC         = timezone.utc
REGIONS     = "us,au"
MARKETS     = "totals"
ODDS_FORMAT = "decimal"
TEAMS_DB    = "teams_db.json"

# Prioritas bookmaker — Pinnacle paling akurat untuk Asian market
BOOKMAKER_PRIORITY = [
    "pinnacle",
    "bet365",
    "williamhill",
    "betfair",
    "unibet",
    "bwin",
    "betway",
]


# =========================================================
# KONVERSI DECIMAL KE INDO ODDS
# =========================================================
def decimal_ke_indo(decimal_odds):
    """
    Decimal >= 2.00 -> Indo positif : decimal - 1
    Decimal <  2.00 -> Indo negatif : -1 / (decimal - 1)
    Return None jika odds tidak valid.
    """
    if decimal_odds is None or decimal_odds <= 1.01:
        return None
    if decimal_odds >= 2.0:
        return round(decimal_odds - 1, 2)
    else:
        return round(-1 / (decimal_odds - 1), 2)


# =========================================================
# NORMALISASI NAMA MATCH
# =========================================================
def normalize_match_name(name):
    """
    Normalisasi nama match untuk matching konsisten.
    lowercase + hapus spasi berlebih.
    """
    return " ".join(name.lower().split())


# =========================================================
# FILTER SAMPAH DI RAM — HANYA SOCCER
# =========================================================
def filter_soccer(data_mentah):
    """
    Filter di RAM sebelum menyentuh storage apapun.
    Buang semua yang bukan sepakbola.
    Sampah tidak pernah masuk storage.
    Return list data bola saja.
    """
    data_bola    = [
        match for match in data_mentah
        if match.get("sport_key", "").startswith("soccer_")
    ]
    total_masuk  = len(data_mentah)
    total_bola   = len(data_bola)
    total_sampah = total_masuk - total_bola

    logging.info(
        f"[tos] Filter RAM: {total_masuk} total -> "
        f"{total_bola} bola | {total_sampah} sampah dibuang"
    )
    return data_bola


# =========================================================
# UPDATE TEAMS DATABASE — DARI DATA BOLA SAJA
# =========================================================
def update_teams_db(data_bola):
    """
    Catat nama tim + liga dari data bola ke teams_db.json.
    Logika duplikasi:
    - Nama sama + liga sama -> SKIP
    - Nama sama + liga beda -> SIMPAN (beda kelas/kompetisi)
    Hanya terima data_bola yang sudah difilter.
    Return (jumlah_tambah, total_db).
    """
    if os.path.exists(TEAMS_DB):
        with open(TEAMS_DB, "r", encoding="utf-8") as f:
            try:
                db = json.load(f)
            except Exception:
                db = []
    else:
        db = []

    existing = {
        (t.get("nama", "").strip(), t.get("liga", "").strip())
        for t in db
        if t.get("nama") and t.get("liga")
    }
    tambah = 0

    for match in data_bola:
        home      = match.get("home_team", "").strip()
        away      = match.get("away_team", "").strip()
        liga      = match.get("sport_title", "").strip()
        sport_key = match.get("sport_key", "").strip()

        if not home or not away or not liga:
            continue

        for nama in [home, away]:
            key = (nama, liga)
            if key not in existing:
                db.append({
                    "nama"     : nama,
                    "liga"     : liga,
                    "sport_key": sport_key
                })
                existing.add(key)
                tambah += 1

    with open(TEAMS_DB, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    logging.info(f"[tos] Teams DB: +{tambah} tim baru. Total: {len(db)} tim.")
    return tambah, len(db)


# =========================================================
# FILTER WAKTU — LIVE + 24 JAM KE DEPAN
# =========================================================
def filter_waktu(data_bola):
    now_wita = datetime.now(WITA)
    hasil = []
    
    # TAMBAH DEBUGGING DETAIL
    for match in data_bola:
        waktu_str = match.get("commence_time")
        if not waktu_str:
            logging.warning(f"[DEBUG] Match tanpa commence_time: {match.get('home_team')} vs {match.get('away_team')}")
            continue
        try:
            kickoff_utc = datetime.fromisoformat(waktu_str.replace("Z", "+00:00"))
            kickoff_wita = kickoff_utc.astimezone(WITA)
        except (ValueError, TypeError) as e:
            logging.warning(f"[DEBUG] Parse waktu gagal: {waktu_str} - Error: {e}")
            continue
        
        selisih_menit = (kickoff_wita - now_wita).total_seconds() / 60
        
        # TAMPILKAN SETIAP MATCH & SELISIH WAKTUNYA
        logging.debug(f"[DEBUG] {match.get('home_team')} vs {match.get('away_team')} | Selisih: {selisih_menit:.0f} menit | Range OK: {-180 <= selisih_menit <= 1440}")
        
        if -180 <= selisih_menit <= 1440:
            hasil.append(match)
    
    logging.info(f"[tos] Filter waktu: {len(data_bola)} -> {len(hasil)} aktif.")
    return hasil


# =========================================================
# EKSTRAK ODDS DENGAN PRIORITAS BOOKMAKER
# =========================================================
def ekstrak_ou_odds(match_data):
    """
    Ekstrak over/under odds dari bookmakers.
    Urutan prioritas: Pinnacle -> Bet365 -> bookmaker lain.
    Return dict {over, under, line, bookmaker} atau None.
    """
    bookmakers = match_data.get("bookmakers", [])
    if not bookmakers:
        return None

    # Index bookmaker berdasarkan key untuk lookup cepat
    bm_dict = {bm.get("key", "").lower(): bm for bm in bookmakers}

    # Susun urutan sesuai prioritas
    urutan = []
    for p in BOOKMAKER_PRIORITY:
        if p in bm_dict:
            urutan.append(bm_dict[p])

    # Tambahkan bookmaker lain yang tidak ada di priority list
    for bm in bookmakers:
        if bm.get("key", "").lower() not in BOOKMAKER_PRIORITY:
            urutan.append(bm)

    # Cari odds dari bookmaker sesuai urutan prioritas
    for bm in urutan:
        nama_bm = bm.get("title", bm.get("key", "Unknown"))
        markets = bm.get("markets", [])

        for market in markets:
            if market.get("key") != "totals":
                continue

            outcomes    = market.get("outcomes", [])
            over_price  = None
            under_price = None
            line        = None

            for out in outcomes:
                name  = out.get("name", "").lower()
                price = out.get("price")
                point = out.get("point")

                if name == "over":
                    over_price = price
                    if point is not None:
                        line = point
                elif name == "under":
                    under_price = price
                    if point is not None and line is None:
                        line = point

            # Hanya return kalau data lengkap
            if over_price is not None and under_price is not None and line is not None:
                return {
                    "over"     : decimal_ke_indo(over_price),
                    "under"    : decimal_ke_indo(under_price),
                    "line"     : line,
                    "bookmaker": nama_bm
                }

    return None


# =========================================================
# TRANSFORMASI UNTUK dos.py
# =========================================================
def transformasi_ke_dos_format(data_aktif):
    hasil = {}
    
    for match in data_aktif:
        home = match.get("home_team", "").strip()
        away = match.get("away_team", "").strip()
        
        if not home or not away:
            continue
        
        match_name = normalize_match_name(f"{home} vs {away}")
        ou_data = ekstrak_ou_odds(match)
        
        if ou_data is None:
            # TAMPILKAN DETAIL MENGAPA SKIP
            bookmakers = match.get("bookmakers", [])
            bm_list = [bm.get("key", "?") for bm in bookmakers]
            logging.warning(f"[DEBUG] Skip {match_name}: Bookmakers: {bm_list} | Markets ada: {[m.get('key') for bm in bookmakers for m in bm.get('markets', [])]}")
            continue
        
        hasil[match_name] = {
            "over": ou_data["over"],
            "under": ou_data["under"],
            "line": ou_data["line"],
            "bookmaker": ou_data["bookmaker"]
        }
    
    logging.info(f"[tos] Transformasi: {len(hasil)} match siap untuk dos.py.")
    return hasil


# =========================================================
# FUNGSI UTAMA — DIPANGGIL app.py
# =========================================================
def jalankan(api_key):
    """
    Fungsi utama tos.py v3.0 by Kimi AI.

    Alur kerja:
    1. Request API sport=upcoming -> 1 quota
    2. Filter soccer_ di RAM -> sampah dibuang
    3. Update teams_db dari data bola saja
    4. Filter waktu LIVE + 24 jam
    5. Transformasi format untuk dos.py
    6. Return hasil ke app.py

    Parameter:
        api_key : str — API key The Odds API

    Return:
        dict berisi status, live_data, dan info quota
    """
    url    = "https://api.the-odds-api.com/v4/sports/upcoming/odds"
    params = {
        "apiKey"    : api_key,
        "regions"   : REGIONS,
        "markets"   : MARKETS,
        "oddsFormat": ODDS_FORMAT,
    }

    logging.info("[tos] Request ke The Odds API (sport=upcoming)...")

    try:
        response = requests.get(url, params=params, timeout=10)

        # Baca info quota dari response header
        remaining  = response.headers.get("x-requests-remaining", "?")
        used       = response.headers.get("x-requests-used", "?")
        cost       = response.headers.get("x-requests-last", "?")
        quota_info = {
            "remaining": remaining,
            "used"     : used,
            "cost"     : cost
        }

        logging.info(
            f"[tos] Quota — Cost: {cost} | Used: {used} | Remaining: {remaining}"
        )

        if response.status_code == 200:

            # Step 1 — Data mentah masuk RAM saja
            data_mentah = response.json()
            logging.info(
                f"[tos] Data mentah: {len(data_mentah)} pertandingan (semua sport)."
            )

            # Step 2 — Filter soccer di RAM, sampah dibuang dari RAM
            data_bola = filter_soccer(data_mentah)
            jumlah_bola = len(data_bola)
            del data_mentah  # Bebaskan RAM dari data mentah

            # Kalau tidak ada pertandingan bola sama sekali
            if not data_bola:
                return {
                    "status"     : "OK",
                    "live_data"  : {},
                    "total_bola" : 0,
                    "total_aktif": 0,
                    "total_match": 0,
                    "teams_baru" : 0,
                    "quota"      : quota_info,
                    "pesan"      : "Tidak ada pertandingan sepakbola saat ini."
                }

            # Step 3 — Update teams_db dari data bola saja
            tambah, total_db = update_teams_db(data_bola)

            # Step 4 — Filter waktu
            data_aktif = filter_waktu(data_bola)
            jumlah_aktif = len(data_aktif)
            del data_bola  # Bebaskan RAM dari data bola

            # Step 5 — Transformasi untuk dos.py
            live_data = transformasi_ke_dos_format(data_aktif)
            del data_aktif  # Bebaskan RAM dari data aktif

            # Log sample 3 match pertama untuk verifikasi
            for i, (match, odds) in enumerate(list(live_data.items())[:3]):
                logging.info(
                    f"[tos] Sample {i+1}: {match} | "
                    f"O:{odds['over']} U:{odds['under']} "
                    f"Line:{odds['line']} via {odds['bookmaker']}"
                )

            return {
                "status"     : "OK",
                "live_data"  : live_data,
                "total_bola" : jumlah_bola,
                "total_aktif": jumlah_aktif,
                "total_match": len(live_data),
                "teams_baru" : tambah,
                "quota"      : quota_info
            }

        elif response.status_code == 401:
            logging.error("[tos] API Key tidak valid.")
            return {
                "status"   : "ERROR",
                "pesan"    : "API Key tidak valid.",
                "live_data": {}
            }

        elif response.status_code == 429:
            logging.error("[tos] Quota API habis.")
            return {
                "status"   : "ERROR",
                "pesan"    : "Quota API habis.",
                "live_data": {}
            }

        else:
            logging.error(f"[tos] Error {response.status_code}: {response.text}")
            return {
                "status"   : "ERROR",
                "pesan"    : f"Error {response.status_code}.",
                "live_data": {}
            }

    except requests.exceptions.Timeout:
        logging.error("[tos] Timeout 10 detik.")
        return {
            "status"   : "ERROR",
            "pesan"    : "Timeout. Coba lagi.",
            "live_data": {}
        }

    except requests.exceptions.RequestException as e:
        logging.error(f"[tos] Koneksi error: {e}")
        return {
            "status"   : "ERROR",
            "pesan"    : str(e),
            "live_data": {}
        }


# =========================================================
# STANDALONE — UNTUK DEBUG LANGSUNG DI TERMINAL
# =========================================================
if __name__ == "__main__":
    API_KEY = "ISI_API_KEY_DISINI"
    hasil   = jalankan(API_KEY)

    print(f"\n{'='*50}")
    print(f"  TOS v3.0 by Kimi AI — HASIL SCAN")
    print(f"{'='*50}")
    print(f"Status    : {hasil['status']}")

    if hasil["status"] == "OK":
        print(f"Total bola: {hasil['total_bola']}")
        print(f"Match aktif: {hasil['total_aktif']}")
        print(f"Match O/U : {hasil['total_match']}")
        print(f"Teams baru: {hasil['teams_baru']}")
        print(f"Quota cost: {hasil['quota']['cost']}")
        print(f"Remaining : {hasil['quota']['remaining']}")

        if hasil["live_data"]:
            print(f"\nSample 5 match:")
            for i, (match, odds) in enumerate(list(hasil["live_data"].items())[:5]):
                print(
                    f"  {i+1}. {match}\n"
                    f"     O:{odds['over']} U:{odds['under']} "
                    f"Line:{odds['line']} via {odds['bookmaker']}"
                )
        else:
            print("\nTidak ada match yang tersedia saat ini.")
    else:
        print(f"Pesan     : {hasil.get('pesan', '?')}")

    print(f"{'='*50}\n")
