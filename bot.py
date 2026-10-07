import os
import time
import io
import threading
import sqlite3
import requests
import qrcode
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# 1. Веб-сервер для проверки работоспособности (Health Check для Render)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_health_check_server, daemon=True).start()

# 2. Токены бота и Crypto Pay
TOKEN = os.environ.get("BOT_TOKEN")
CRYPTO_PAY_TOKEN = os.environ.get("CRYPTO_PAY_TOKEN")

bot = telebot.TeleBot(TOKEN)

BOT_USERNAME = None
try:
    bot_info = bot.get_me()
    BOT_USERNAME = bot_info.username
except Exception as e:
    print(f"Ошибка получения инфо о боте: {e}")

try:
    bot.remove_webhook()
except Exception:
    pass

# === БАЗА ДАННЫХ (SQLite) ===
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referrer_id INTEGER,
            has_bought INTEGER DEFAULT 0,
            balance REAL DEFAULT 0.0
        )
    ''')
    
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0.0')
    except Exception:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

def register_user(user_id, referrer_id=None):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        if referrer_id and int(referrer_id) == user_id:
            referrer_id = None
        cursor.execute('INSERT INTO users (user_id, referrer_id, balance) VALUES (?, ?, 0.0)', (user_id, referrer_id))
        conn.commit()
    conn.close()

def get_user_balance(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else 0.0

def add_user_balance(user_id, amount):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def deduct_user_balance(user_id, amount):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    if row and row[0] >= amount:
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False

def save_invoice(invoice_id, user_id, amount):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO invoices (invoice_id, user_id, amount, status) VALUES (?, ?, ?, "active")', 
                   (invoice_id, user_id, amount))
    conn.commit()
    conn.close()

def set_invoice_paid(invoice_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE invoices SET status = "paid" WHERE invoice_id = ?', (invoice_id,))
    conn.commit()
    conn.close()

def get_invoice_status(invoice_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM invoices WHERE invoice_id = ?', (invoice_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_referral_stats(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users WHERE referrer_id = ?', (user_id,))
    total_invited = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM users WHERE referrer_id = ? AND has_bought = 1', (user_id,))
    bought_invited = cursor.fetchone()[0]
    conn.close()
    return total_invited, bought_invited

def confirm_purchase(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT referrer_id, has_bought FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    if row:
        referrer_id, has_bought = row
        if has_bought == 0:
            cursor.execute('UPDATE users SET has_bought = 1 WHERE user_id = ?', (user_id,))
            conn.commit()
            
            if referrer_id:
                cursor.execute('SELECT COUNT(*) FROM users WHERE referrer_id = ? AND has_bought = 1', (referrer_id,))
                active_count = cursor.fetchone()[0]
                
                if active_count == 10:
                    gift_caption = (
                        "🎉 **ПОЗДРАВЛЯЕМ! Вы выполнили условия акции!**\n\n"
                        "10 ваших друзей совершили покупку. Ваш подарок — **1 г**!\n\n"
                        "📍 **Инструкция и место:** смотри на скриншоте выше. "
                        "Вся подробная информация указана на изображении!"
                    )
                    try:
                        bot.send_photo(
                            referrer_id, 
                            photo=GIFT_REWARD_PHOTO, 
                            caption=gift_caption, 
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        print(f"Ошибка при отправке подарка: {e}")
                        
    conn.close()

# === ИНТЕГРАЦИЯ CRYPTO BOT API & QR ===

def crypto_create_invoice(amount, asset="USDT"):
    if not CRYPTO_PAY_TOKEN:
        print("ОШИБКА: CRYPTO_PAY_TOKEN не настроен в переменной окружения!")
        return None
        
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN.strip()}
    payload = {
        "asset": asset,
        "amount": "{:.2f}".format(amount),
        "description": "Top-up balance in bot",
        "paid_btn_name": "openBot"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        res = response.json()
        if res.get("ok"):
            return res["result"]
        else:
            print(f"Ошибка от CryptoBot API: {res}")
    except Exception as e:
        print(f"Исключение при запросе к CryptoBot API (createInvoice): {e}")
    return None

def crypto_get_invoice(invoice_id):
    if not CRYPTO_PAY_TOKEN:
        return None
        
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN.strip()}
    payload = {"invoice_ids": str(invoice_id)}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        res = response.json()
        if res.get("ok") and len(res["result"]["items"]) > 0:
            return res["result"]["items"][0]
        else:
            print(f"Ошибка от CryptoBot API (getInvoices): {res}")
    except Exception as e:
        print(f"Исключение при запросе к CryptoBot API (getInvoices): {e}")
    return None

def generate_qr_photo(data_string):
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(data_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    bio = io.BytesIO()
    bio.name = 'qr.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# === БЛОК КАРТИНОК И НАСТРОЕК ===

GIFT_REWARD_PHOTO = 'AgACAgIAAxkBAAICM2rB2wSKRzXzJNIaHS7jE-LJX9OLAAKiG2sbmdMRStG2q3jM45_rAQADAgADeQADPQQ'

START_PHOTO_URL = 'AgACAgIAAxkBAAICOWrB2xd60Xd3uUDKRNTd_SAn0lC2AAKlG2sbmdMRSs4THvk1ETmPAQADAgADeQADPQQ'

LANG_PHOTOS = {
    'geo': 'AgACAgIAAxkBAAICJ2rB2tWMZ1Dh8Ugt8j18Ls0MWMtXAAKcG2sbmdMRSlEUJFW3Gm-WAQADAgADeQADPQQ',
    'eng': 'AgACAgIAAxkBAAICKWrB2t3mVOlCPYFAMShfTwaav1LYAAKdG2sbmdMRSvUvAAF_VjrxagEAAwIAA3kAAz0E',
    'rus': 'AgACAgIAAxkBAAICK2rB2uQvkSF7sRxiNwU4e7NQI9kMAAKeG2sbmdMRSkq5Umfk1PNKAQADAgADeQADPQQ'
}

CITY_PHOTOS = {
    'amb': {
        'geo': 'AgACAgIAAxkBAAICLWrB2vCMzJjCT6sd_VAFsgO8oLWXAAKfG2sbmdMRSkNPd3cIKJWLAQADAgADeQADPQQ',
        'eng': 'AgACAgIAAxkBAAICL2rB2vd1zPCWH0wSTOmxar35DXQdAAKgG2sbmdMRSiTgwCEuz0YBAQADAgADeQADPQQ',
        'rus': 'AgACAgIAAxkBAAICMWrB2v6cssMoGlfnmFvGolRq2ZskAAKhG2sbmdMRSvs7nGmFnT5oAQADAgADeQADPQQ'
    },
    'oni': {
        'geo': 'AgACAgIAAxkBAAICLWrB2vCMzJjCT6sd_VAFsgO8oLWXAAKfG2sbmdMRSkNPd3cIKJWLAQADAgADeQADPQQ',
        'eng': 'AgACAgIAAxkBAAICL2rB2vd1zPCWH0wSTOmxar35DXQdAAKgG2sbmdMRSiTgwCEuz0YBAQADAgADeQADPQQ',
        'rus': 'AgACAgIAAxkBAAICMWrB2v6cssMoGlfnmFvGolRq2ZskAAKhG2sbmdMRSvs7nGmFnT5oAQADAgADeQADPQQ'
    }
}

QTY_PHOTOS = {
    'amb': {
        'geo': {
            '05': 'AgACAgIAAxkBAAICk2rDDB7h8nGvAhFbrmMJBrhX3BuPAAKAGWsbmdMZSqQPZNug7HOcAQADAgADeQADPQQ',
            '1':  'AgACAgIAAxkBAAICkWrDDBv7RxeVvEXsV_5GXNtXVR1iAAJ_GWsbmdMZStqVvVLczlcBAQADAgADeQADPQQ',
            '2':  'AgACAgIAAxkBAAICl2rDDCW6UUMscYLfDwPS2AHP6BJrAAKCGWsbmdMZSgpcyO5OhsgNAQADAgADeQADPQQ',
            '5':  'AgACAgIAAxkBAAICm2rDDC16xQ-H6Ic018gU6HYRqOfjAAKEGWsbmdMZSleKcGqdayb4AQADAgADeQADPQQ'
        },
        'eng': {
            '05': 'AgACAgIAAxkBAAICtWrDESwbuLe-9I67DeS28Cd7A0_aAAKVGWsbmdMZSqJGirY2_hDQAQADAgADeQADPQQ',
            '1':  'AgACAgIAAxkBAAICs2rDELsf941jsxj_f49r8hJzkJ5rAAKUGWsbmdMZSvIz2td59U7SAQADAgADeQADPQQ',
            '2':  'AgACAgIAAxkBAAICuWrDETxqRYaVm_u2bJL3YoQo5CYwAAKXGWsbmdMZSmpcQeXOfNMPAQADAgADeQADPQQ',
            '5':  'AgACAgIAAxkBAAICt2rDETYB-1JYwLbyy2kZwGCPkeRaAAKWGWsbmdMZSldnHtxpE_wBAQADAgADeQADPQQ'
        },
        'rus': {
            '05': 'AgACAgIAAxkBAAIC2mrDK0ohum70jZANz3bn_5m6f9pDAALKGWsbmdMZShyjpfzGBjJ2AQADAgADeQADPQQ',
            '1':  'AgACAgIAAxkBAAIC3GrDK06sFZyFSCvrn-aAiX_FAAF7vwACyxlrG5nTGUqNYvAhcaPtQQEAAwIAA3kAAz0E',
            '2':  'AgACAgIAAxkBAAIC3mrDK1Je_CjiecdhSqt5j39UFByPAALMGWsbmdMZSs-Ef_AOJqYBAQADAgADeQADPQQ',
            '5':  'AgACAgIAAxkBAAIC4GrDK1c-s9XTmnKPFmb_boRFa3geAALNGWsbmdMZSrwaLaowXZFdAQADAgADeQADPQQ'
        }
    },
    'oni': {
        'geo': {
            '05': 'AgACAgIAAxkBAAICrWrDDIPkjTdpho3FG3U1apkQYdsjAAKNGWsbmdMZStKmSgR3CWXYAQADAgADeQADPQQ',
            '1':  'AgACAgIAAxkBAAICn2rDDEC6rFKK2cFuJbjwLpf5ONeUAAKGGWsbmdMZSp4jxX3Jd_LNAQADAgADeQADPQQ',
            '2':  'AgACAgIAAxkBAAIClWrDDCITlFu3oUS7lVR9ddQ4sDt_AAKBGWsbmdMZSijORq1aKa6IAQADAgADeQADPQQ',
            '5':  'AgACAgIAAxkBAAICmWrDDCl4G7W3rKUAAfnUvnM9BPJfrgACgxlrG5nTGUok6Aw79wZuNAEAAwIAA3kAAz0E'
        },
        'eng': {
            '05': 'AgACAgIAAxkBAAICzGrDGkg9zA6YdsBX7LJ3JP_VnLNaAAKlGWsbmdMZSra2wdE2vkiGAQADAgADeQADPQQ',
            '1':  'AgACAgIAAxkBAAICq2rDDGAgulwLyT-O8zZWrMhoPZDPAAKMGWsbmdMZSpfFKZEcUduDAQADAgADeQADPQQ',
            '2':  'AgACAgIAAxkBAAICpWrDDE-MK5LJHTMz5WmJc2G9RdQpAAKJGWsbmdMZSoDXMU7imoodAQADAgADeQADPQQ',
            '5':  'AgACAgIAAxkBAAICr2rDDImnqiwImbEMg1UzKYxSud12AAKOGWsbmdMZSgqX7WilBjbJAQADAgADeQADPQQ'
        },
        'rus': {
            '05': 'AgACAgIAAxkBAAICp2rDDFYknSs_RsnfW6VTasm83t6NAAKKGWsbmdMZSg3J6mxsIZMvAQADAgADeQADPQQ',
            '1':  'AgACAgIAAxkBAAICnWrDDDVKXeZHTcu1WNkE2Kkdl3jsAAKFGWsbmdMZSo3BOeLA75FRAQADAgADeQADPQQ',
            '2':  'AgACAgIAAxkBAAICqWrDDFuQQ_OAy2la_jltXnASEIRPAAKLGWsbmdMZSpwEr7GF4XmtAQADAgADeQADPQQ',
            '5':  'AgACAgIAAxkBAAICoWrDDEUew0TzjK_Fy8eVwT5QXjfoAAKHGWsbmdMZSrP1fL5iHcg2AQADAgADeQADPQQ'
        }
    }
}

GIFT_PHOTOS = {
    'geo': 'AgACAgIAAxkBAAICM2rB2wSKRzXzJNIaHS7jE-LJ
