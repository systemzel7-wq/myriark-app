"""
pos.py — Post Odds Service (Telegram Notifier)
Versi: Gemini v1.00 (Edisi Anti-Spam & Middle Alert)
Arsitektur oleh Gemini & Claude AI

Perubahan di Gemini v1.00:
1. Menangkap status baru DANGER_LINE_SHIFT (Alarm Merah).
2. Menambahkan notifikasi khusus jika ada peluang PELUANG_MIDDLE (Kemenangan Ganda).
3. Memasang Delay (time.sleep) 1 detik setiap kirim pesan untuk menghindari
   pemblokiran Telegram API (Error 429 Too Many Requests).
"""

import requests
import time
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

WITA = ZoneInfo("Asia/Makassar")

# =========================================================
# KONFIGURASI FILTER STATUS
# =========================================================
# Status yang AKAN dikirim ke Telegram
STATUS_KIRIM = [
    "PROFIT_READY", 
    "BEP_READY", 
    "BETTER", 
    "WORSE", 
    "DANGER_LINE_SHIFT"
]

# Status yang DIABAIKAN (Tidak perlu menuh-menuhin chat Bos)
STATUS_SKIP  = [
    "FLAT", 
    "NOT_READY", 
    "NO_LIVE", 
    "NO_ODDS"
]

# =========================================================
# FORMAT PESAN TELEGRAM
# =========================================================
def format_pesan(snapshot: dict) -> str:
    """
    Merakit pesan Telegram sesuai dengan status dan kondisi Line.
    """
    status       = snapshot.get("status", "")
    ticket_id    = snapshot.get("ticket_id", "?")
    match        = snapshot.get("match", "?")
    entry_side   = snapshot.get("entry_side", "?").upper()
    entry_line   = snapshot.get("entry_line", "?")
    entry_stake  = snapshot.get("entry_stake", 0)
    close_side   = snapshot.get("close_side", "?").upper()
    close_odds   = snapshot.get("close_odds", "?")
    close_line   = snapshot.get("close_line", "?")
    close_stake  = snapshot.get("close_stake", 0)
    total_result = snapshot.get("total_result", 0)
    tren         = snapshot.get("tren", "?")
    kondisi_line = snapshot.get("kondisi_line", "AMAN")

    # Deteksi Peluang Middle (Kemenangan Ganda)
    middle_alert = "🎯 **PELUANG MIDDLE (KEMENANGAN GANDA DETECTED)!** 🎯\n" if kondisi_line == "PELUANG_MIDDLE" else ""

    if status == "DANGER_LINE_SHIFT":
        return (
            f"🚨 **BAHAYA: LINE BERGESER (JANGAN HEDGING)!** 🚨\n\n"
            f"🆔 `{ticket_id}`\n"
            f"⚽ {match}\n\n"
            f"Tiket Bos: **{entry_side} {entry_line}**\n"
            f"Line Bandar Saat Ini: **{close_line}**\n\n"
            f"⚠️ *Pergeseran line ini merugikan. Jika dipaksa kompensasi, Bos berisiko Rungkad Ganda (Double Lose). Tahan peluru!*"
        )
    
    elif status == "PROFIT_READY":
        return (
            f"{middle_alert}"
            f"✅ **PROFIT READY** ✅\n"
            f"🆔 `{ticket_id}`\n"
            f"⚽ {match}\n\n"
            f"Target Hedging: **{close_side} {close_line}**\n"
            f"Odds Bandar: {close_odds}\n"
            f"💰 Min Bet Kompensasi: **Rp {close_stake:,.0f}**\n"
            f"📈 Proyeksi Bersih: **Rp {total_result:,.0f}**\n"
            f"📊 Tren Harga: {tren}"
        )
        
    elif status == "BEP_READY":
        return (
            f"{middle_alert}"
            f"🟡 **BEP READY (IMPAS)** 🟡\n"
            f"🆔 `{ticket_id}`\n"
            f"⚽ {match}\n\n"
            f"Target Hedging: **{close_side} {close_line}**\n"
            f"Odds Bandar: {close_odds}\n"
            f"💰 Min Bet Kompensasi: **Rp {close_stake:,.0f}**\n"
            f"🛡️ Proyeksi: Rp {total_result:,.0f} (Balik Modal)\n"
            f"📊 Tren Harga: {tren}"
        )
        
    elif status == "WORSE":
        return (
            f"⚠️ **HARGA MAKIN BURUK** ⚠️\n"
            f"🆔 `{ticket_id}`\n"
            f"⚽ {match}\n\n"
            f"Target Hedging: **{close_side} {close_line}**\n"
            f"Odds Bandar: {close_odds}\n"
            f"💸 Biaya Kompensasi Membengkak: **Rp {close_stake:,.0f}**\n"
            f"📉 Tren Harga: {tren} (Makin Merugikan)"
        )
        
    elif status == "BETTER":
        return (
            f"📈 **HARGA MEMBAIK (BELUM BEP)** 📈\n"
            f"🆔 `{ticket_id}`\n"
            f"⚽ {match}\n\n"
            f"Target Hedging: **{close_side} {close_line}**\n"
            f"Odds Bandar: {close_odds}\n"
            f"🔍 Sedikit lagi menuju BEP. Pantau terus!\n"
            f"📊 Tren Harga: {tren}"
        )

    return ""


# =========================================================
# EKSEKUTOR PENGIRIMAN API TELEGRAM
# =========================================================
def kirim_telegram(pesan: str, bot_token: str, chat_id: str) -> bool:
    if not pesan or not bot_token or not chat_id:
        return False
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": pesan,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Telegram Error: {e}")
        return False


# =========================================================
# FUNGSI UTAMA (DIPANGGIL OLEH APP.PY)
# =========================================================
def jalankan(hasil_dos: list, bot_token: str, chat_id: str) -> list:
    if not hasil_dos:
        return []

    log = []
    for snapshot in hasil_dos:
        status = snapshot.get("status", "")

        # Lewati jika status masuk daftar abaikan
        if status in STATUS_SKIP:
            continue

        pesan = format_pesan(snapshot)
        if pesan:
            terkirim = kirim_telegram(pesan, bot_token, chat_id)
            
            log.append({
                "ticket_id": snapshot.get("ticket_id"),
                "match"    : snapshot.get("match"),
                "status"   : status,
                "terkirim" : terkirim,
                "waktu"    : datetime.now(WITA).strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # [PENGAMAN KUSIAL]: Jeda 1 detik agar Telegram tidak memblokir (Error 429)
            if terkirim:
                time.sleep(1)

    return log
