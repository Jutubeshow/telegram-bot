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
        print("ОШИБКА: CRYPTO_PAY_TOKEN не настроен!")
        return None
        
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    payload = {
        "asset": asset,
        "amount": str(amount),
        "description": "Top-up balance in bot",
        "paid_btn_name": "openBot"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10).json()
        if res.get("ok"):
            return res["result"]
    except Exception as e:
        print(f"Ошибка CryptoBot API (createInvoice): {e}")
    return None

def crypto_get_invoice(invoice_id):
    if not CRYPTO_PAY_TOKEN:
        return None
        
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    payload = {"invoice_ids": invoice_id}
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10).json()
        if res.get("ok") and len(res["result"]["items"]) > 0:
            return res["result"]["items"][0]
    except Exception as e:
        print(f"Ошибка CryptoBot API (getInvoices): {e}")
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
    'geo': 'AgACAgIAAxkBAAICM2rB2wSKRzXzJNIaHS7jE-LJX9OLAAKiG2sbmdMRStG2q3jM45_rAQADAgADeQADPQQ',
    'eng': 'AgACAgIAAxkBAAICNWrB2wpNDFC0IVPPWnKHAAEQI1uiWQACoxtrG5nTEUr9j5e47yc-ngEAAwIAA3kAAz0E',
    'rus': 'AgACAgIAAxkBAAICN2rB2w6unljidPUE8RJAf1hLJlHqAAKkG2sbmdMRSsZIBeJm0pzVAQADAgADeQADPQQ'
}

CITIES = {
    'amb': {'geo': 'ამბროლაური', 'eng': 'Ambrolauri', 'rus': 'Амбролаури'},
    'oni': {'geo': 'ონი', 'eng': 'Oni', 'rus': 'Они'}
}

QUANTITIES = {
    '05': {'geo': '0.5 გრ', 'eng': '0.5 g', 'rus': '0.5 г', 'price': '16 USDT (40 GEL)', 'usdt': 16.0},
    '1': {'geo': '1 გრ', 'eng': '1 g', 'rus': '1 г', 'price': '31 USDT (80 GEL)', 'usdt': 31.0},
    '2': {'geo': '2 გრ', 'eng': '2 g', 'rus': '2 г', 'price': '58 USDT (150 GEL)', 'usdt': 58.0},
    '5': {'geo': '5 გრ', 'eng': '5 g', 'rus': '5 г', 'price': '135 USDT (350 GEL)', 'usdt': 135.0}
}

TEXTS = {
    'geo': {
        'select_city': 'აირჩიეთ ქალაქი',
        'ambrolauri_btn': 'ამბროლაური',
        'oni_btn': 'ონი',
        'gift_btn': '🎁 საჩუქარი',
        'ref_link_btn': '🔗 ჩემი რეფერალური ბმული',
        'share_btn': '📤 გაუგზავნე მეგობარს',
        'back_btn': '⬅️ უკან',
        'how_much': 'აირჩიე რაოდენობა!',
        'q05_btn': '0.5 გრ - 16 USDT (40 GEL)',
        'q1_btn': '1 გრ - 31 USDT (80 GEL)',
        'q2_btn': '2 გრ - 58 USDT (150 GEL)',
        'q5_btn': '5 გრ - 135 USDT (350 GEL)',
        'gift_info': (
            "🎁 საჩუქრის პირობა:\n\n"
            "1. იყიდე 10 - ჯერ და მიიღე მე-11 საჩუქრად;\n"
            "2. მოიწვიე 10 მეგობარი, რომლებიც მინიმუმ ერთხელ იყიდიან და ასევე მიიღე 1 გრ საჩუქრად."
        ),
        'stats_text': (
            "📊 **შენი სტატისტიკა:**\n\n"
            "• მოწვეული მეგობრები: **{total}**\n"
            "• მათგან იყიდა: **{bought}/10**"
        ),
        'share_msg_text': (
            "👋 გამარჯობა! გამოიყენე ეს ბოტი შეკვეთისთვის:\n"
            "`{link}`\n\n"
            "*(დააჭირე ბმულს დასაკოპირებლად)*"
        ),
        'checkout_text': "არჩეული გაქვს ქალაქი **{city}**, რაოდენობა **{qty}**, ფასია **{price}**. გადაამოწმე! თუ ყველაფერი სწორია, დააჭირე გადახდას! გირჩევ 5 ლარით მეტი ჩარიცხო, რადგანაც კომისიას მიაქვს, ჩვენი ბრალი არაა.",
        'pay_btn': "💳 გადახდა ({price})",
        'how_to_pay_btn': "ℹ როგორ გადაიხდო მარტივად"
    },
    'eng': {
        'select_city': 'Select a location',
        'ambrolauri_btn': 'Ambrolauri',
        'oni_btn': 'Oni',
        'gift_btn': '🎁 Gift',
        'ref_link_btn': '🔗 My Referral Link',
        'share_btn': '📤 Share with a friend',
        'back_btn': '⬅️ Back',
        'how_much': 'Select the quantity!',
        'q05_btn': '0.5 g - 16 USDT (40 GEL)',
        'q1_btn': '1 g - 31 USDT (80 GEL)',
        'q2_btn': '2 g - 58 USDT (150 GEL)',
        'q5_btn': '5 g - 135 USDT (350 GEL)',
        'gift_info': (
            "🎁 Gift Offer\n\n"
            "1. Buy 10 times and get the 11th for free as a gift;\n"
            "2. Invite 10 friends who make at least 1 purchase and get 1 g as a gift."
        ),
        'stats_text': (
            "📊 **Your statistics:**\n\n"
            "• Invited friends: **{total}**\n"
            "• Purchased at least once: **{bought}/10**"
        ),
        'share_msg_text': (
            "👋 Hello! Use this bot for ordering:\n"
            "`{link}`\n\n"
            "*(Tap on the link to copy it)*"
        ),
        'checkout_text': "You selected city **{city}**, quantity **{qty}**, price **{price}**. Double check! If everything is correct, click payment! I recommend topping up by an extra 5 lari, otherwise the commission eats into the amount—that’s not our fault.",
        'pay_btn': "💳 Pay ({price})",
        'how_to_pay_btn': "ℹ How to pay easily"
    },
    'rus': {
        'select_city': 'Выберите город',
        'ambrolauri_btn': 'Амбролаури',
        'oni_btn': 'Они',
        'gift_btn': '🎁 Подарок',
        'ref_link_btn': '🔗 Моя реферальная ссылка',
        'share_btn': '📤 Поделиться с другом',
        'back_btn': '⬅️ Назад',
        'how_much': 'Выбери количество!',
        'q05_btn': '0.5 г - 16 USDT (40 GEL)',
        'q1_btn': '1 г - 31 USDT (80 GEL)',
        'q2_btn': '2 г - 58 USDT (150 GEL)',
        'q5_btn': '5 г - 135 USDT (350 GEL)',
        'gift_info': (
            "🎁 Условия подарка:\n\n"
            "1. Купи 10 раз и получи 11-ый в подарок.\n"
            "2. Пригласи 10 друзей, которые хотя бы 1 раз купят и получи подарок."
        ),
        'stats_text': (
            "📊 **Ваша статистика:**\n\n"
            "• Приглашено друзей: **{total}**\n"
            "• Совершили покупку: **{bought}/10**"
        ),
        'share_msg_text': (
            "👋 Привет! Воспользуйся этим ботом для заказа:\n"
            "`{link}`\n\n"
            "*(Нажми на ссылку выше, чтобы скопировать её)*"
        ),
        'checkout_text': "Ты выбрал город **{city}**, количество **{qty}**, цена **{price}**. Перепроверь! Если все верно, то жми оплату! Советую пополнить на 5 лари больше, а то комиссия забирает, это не наша вина.",
        'pay_btn': "💳 Оплата ({price})",
        'how_to_pay_btn': "ℹ Как легко оплатить"
    }
}

INSTRUCTIONS = {
    'geo': (
        "ℹ️ **როგორ გადავიხადოთ Crypto Bot-ით:**\n\n"
        "1. დააჭირეთ ღილაკს **«💳 გადახდა (Crypto Bot)»** ქვემოთ.\n"
        "2. გახსნილ ჩატში დააჭირეთ **Оплатить**.\n"
        "3. თუ ანგარიშზე არ გაქვთ USDT, აირჩიეთ **Пополнить** და გადაიხადეთ ნებისმიერი ბარათით ან крипто-საფულით (Trust Wallet / Binance / TON).\n"
        "4. გადახდის შემდეგ დაბრუნდით ბოტში და დააჭირეთ **«🔄 შეამოწმე გადახდა»**."
    ),
    'eng': (
        "ℹ️ **How to pay via Crypto Bot:**\n\n"
        "1. Click the **«💳 Pay (Crypto Bot)»** button below.\n"
        "2. In the opened chat, click **Pay**.\n"
        "3. If you don't have USDT in your balance, select **Top Up** and pay using any card or wallet (Trust Wallet / Binance / TON).\n"
        "4. After payment, return to this bot and click **«🔄 Check Payment»**."
    ),
    'rus': (
        "ℹ️ **Как легко оплатить через Crypto Bot:**\n\n"
        "1. Нажмите кнопку **«💳 Оплатить (Crypto Bot)»** ниже.\n"
        "2. В открывшемся чате нажмите **Оплатить**.\n"
        "3. Если у вас нет USDT на балансе, выберите **Пополнить** и оплатите с любой карты или внешнего кошелька (Trust Wallet / Binance / TON / QR-код).\n"
        "4. После оплаты вернитесь в этого бота и нажмите кнопку **«🔄 Проверить оплату»**."
    )
}

def safe_send(chat_id, message_id, photo_or_url, text, reply_markup, parse_mode=None):
    if message_id:
        try:
            bot.delete_message(chat_id, message_id)
        except Exception:
            pass

    if photo_or_url:
        try:
            bot.send_photo(chat_id, photo=photo_or_url, caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
            return
        except Exception:
            pass

    bot.send_message(chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        
    register_user(user_id, referrer_id)

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🇬🇪 ქართული", callback_data="setlang_geo"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="setlang_eng"),
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_rus")
    )
    
    try:
        bot.send_photo(
            user_id, 
            photo=START_PHOTO_URL, 
            caption="🌍 Select language / აირჩიეთ ენა / Выберите язык", 
            reply_markup=markup
        )
    except Exception:
        bot.send_message(
            user_id, 
            text="🌍 Select language / აირჩიეთ ენა / Выберите язык", 
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data == 'nav_main_start')
def nav_main_start(call):
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🇬🇪 ქართული", callback_data="setlang_geo"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="setlang_eng"),
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_rus")
    )
    safe_send(call.message.chat.id, call.message.id, START_PHOTO_URL, "🌍 Select language / აირჩიეთ ენა / Выберите язык", markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('setlang_'))
def set_language(call):
    bot.answer_callback_query(call.id)
    lang = call.data.split('_')[1]
    t = TEXTS[lang]
    photo_file_id = LANG_PHOTOS.get(lang)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t['ambrolauri_btn'], callback_data=f"go_city_amb_{lang}"),
        types.InlineKeyboardButton(t['oni_btn'], callback_data=f"go_city_oni_{lang}"),
        types.InlineKeyboardButton(t['gift_btn'], callback_data=f"show_gift_{lang}"),
        types.InlineKeyboardButton(t['back_btn'], callback_data="nav_main_start")
    )
    
    safe_send(call.message.chat.id, call.message.id, photo_file_id, t['select_city'], markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('show_gift_'))
def show_gift_info(call):
    bot.answer_callback_query(call.id)
    lang = call.data.split('_')[2]
    t = TEXTS[lang]
    gift_photo_id = GIFT_PHOTOS.get(lang)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t['ref_link_btn'], callback_data=f"get_ref_{lang}"),
        types.InlineKeyboardButton(t['back_btn'], callback_data=f"setlang_{lang}")
    )
    
    safe_send(call.message.chat.id, call.message.id, gift_photo_id, t['gift_info'], markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('get_ref_'))
def get_ref_link(call):
    bot.answer_callback_query(call.id)
    lang = call.data.split('_')[2]
    t = TEXTS[lang]
    user_id = call.message.chat.id
    gift_photo_id = GIFT_PHOTOS.get(lang)
    
    link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    total_invited, bought_invited = get_referral_stats(user_id)
    
    stats_msg = t['stats_text'].format(
        total=total_invited,
        bought=bought_invited
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t['back_btn'], callback_data=f"show_gift_{lang}")
    )
    
    safe_send(user_id, call.message.id, gift_photo_id, stats_msg, markup, parse_mode='Markdown')
    
    share_text = t['share_msg_text'].format(link=link)
    share_markup = types.InlineKeyboardMarkup(row_width=1)
    share_markup.add(
        types.InlineKeyboardButton(t['share_btn'], switch_inline_query=f"\nПользуйся ботом: {link}")
    )
    
    bot.send_message(user_id, text=share_text, reply_markup=share_markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('go_city_'))
def city_click(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_')
    city = parts[2]
    lang = parts[3]
    
    t = TEXTS[lang]
    photo_file_id = CITY_PHOTOS.get(city, {}).get(lang)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t['q05_btn'], callback_data=f"qty_05_{city}_{lang}"),
        types.InlineKeyboardButton(t['q1_btn'], callback_data=f"qty_1_{city}_{lang}"),
        types.InlineKeyboardButton(t['q2_btn'], callback_data=f"qty_2_{city}_{lang}"),
        types.InlineKeyboardButton(t['q5_btn'], callback_data=f"qty_5_{city}_{lang}"),
        types.InlineKeyboardButton(t['back_btn'], callback_data=f"setlang_{lang}")
    )
    
    safe_send(call.message.chat.id, call.message.id, photo_file_id, t['how_much'], markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('qty_'))
def qty_click(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_')
    qty_key = parts[1]
    city_key = parts[2]
    lang = parts[3]
    
    t = TEXTS[lang]
    city_name = CITIES[city_key][lang]
    qty_info = QUANTITIES[qty_key]
    qty_name = qty_info[lang]
    price = qty_info['price']
    
    text = t['checkout_text'].format(
        city=city_name,
        qty=qty_name,
        price=price
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t['pay_btn'].format(price=price), callback_data=f"pay_{qty_key}_{city_key}_{lang}"),
        types.InlineKeyboardButton(t['how_to_pay_btn'], callback_data=f"howpay_{lang}"),
        types.InlineKeyboardButton(t['back_btn'], callback_data=f"go_city_{city_key}_{lang}")
    )
    
    photo_file_id = QTY_PHOTOS.get(city_key, {}).get(lang, {}).get(qty_key)
    if not photo_file_id:
        photo_file_id = CITY_PHOTOS.get(city_key, {}).get(lang)

    safe_send(call.message.chat.id, call.message.id, photo_file_id, text, markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('howpay_'))
def how_pay_click(call):
    bot.answer_callback_query(call.id)
    lang = call.data.split('_')[1]
    text = INSTRUCTIONS.get(lang, INSTRUCTIONS['rus'])
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_'))
def pay_click(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_')
    qty_key = parts[1]
    city_key = parts[2]
    lang = parts[3]
    user_id = call.message.chat.id
    
    required_usdt = QUANTITIES[qty_key]['usdt']
    current_balance = get_user_balance(user_id)
    
    # 1. Если на балансе хватает денег — сразу покупаем!
    if current_balance >= required_usdt:
        deduct_user_balance(user_id, required_usdt)
        confirm_purchase(user_id)
        rem_balance = get_user_balance(user_id)
        
        msg = f"✅ **Оплата прошла успешно с вашего баланса!**\n\nСписано: `{required_usdt} USDT`\nОстаток на балансе: `{rem_balance} USDT`"
        bot.send_message(user_id, msg, parse_mode='Markdown')
        return

    # 2. Если баланса не хватает — выставляем счет на недостающую сумму
    need_to_pay = round(required_usdt - current_balance, 2)
    
    invoice = crypto_create_invoice(need_to_pay)
    if not invoice:
        bot.send_message(user_id, "❌ Ошибка создания чека. Попробуйте позже.")
        return

    invoice_id = invoice['invoice_id']
    pay_url = invoice['bot_invoice_url']
    save_invoice(invoice_id, user_id, need_to_pay)

    # Генерация QR-кода на лету в памяти
    qr_bio = generate_qr_photo(pay_url)

    caption = (
        f"💳 **ОПЛАТА ЗАКАЗА (USDT)**\n\n"
        f"📌 Ваш текущий баланс: `{current_balance} USDT`\n"
        f"📌 К оплате: `{need_to_pay} USDT`\n\n"
        f"📲 **Инструкция:**\n"
        f"1. Отсканируйте QR-код выше ИЛИ нажмите кнопку ниже для оплаты через Crypto Bot.\n"
        f"2. После перевода нажмите кнопку **«🔄 Проверить оплату»**.\n\n"
        f"💡 *Все «лишние» зачисленные средства сохранятся на вашем балансе для следующих покупок!*"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💳 Оплатить (Crypto Bot)", url=pay_url),
        types.InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_{invoice_id}_{qty_key}_{lang}"),
        types.InlineKeyboardButton(TEXTS[lang]['back_btn'], callback_data=f"qty_{qty_key}_{city_key}_{lang}")
    )

    bot.send_photo(user_id, photo=qr_bio, caption=caption, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_'))
def check_payment_click(call):
    parts = call.data.split('_')
    invoice_id = int(parts[1])
    qty_key = parts[2]
    lang = parts[3]
    user_id = call.message.chat.id

    db_status = get_invoice_status(invoice_id)
    if db_status == 'paid':
        bot.answer_callback_query(call.id, "Счет уже был оплачен и зачислен!", show_alert=True)
        return

    invoice_info = crypto_get_invoice(invoice_id)
    if invoice_info and invoice_info.get('status') == 'paid':
        amount_paid = float(invoice_info['amount'])
        set_invoice_paid(invoice_id)
        add_user_balance(user_id, amount_paid)
        
        bot.answer_callback_query(call.id, "✅ Оплата получена! Средства зачислены на ваш баланс.", show_alert=True)
        
        # Сразу пытаемся совершить покупку
        required_usdt = QUANTITIES[qty_key]['usdt']
        if deduct_user_balance(user_id, required_usdt):
            confirm_purchase(user_id)
            rem_balance = get_user_balance(user_id)
            msg = f"🎉 **Заказ успешно оплачен!**\n\nЗачислено: `{amount_paid} USDT`\nСписано за товар: `{required_usdt} USDT`\nОстаток баланса: `{rem_balance} USDT`"
            bot.send_message(user_id, msg, parse_mode='Markdown')
        else:
            cur_bal = get_user_balance(user_id)
            bot.send_message(user_id, f"Ваш баланс пополнен на `{amount_paid} USDT`. Текущий баланс: `{cur_bal} USDT`.", parse_mode='Markdown')
    else:
        bot.answer_callback_query(call.id, "⏳ Оплата еще не поступила. Попробуйте через 10-15 секунд.", show_alert=True)

# Обработчик сжатых фото
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    file_id = message.photo[-1].file_id
    bot.send_message(message.chat.id, f"ID картинки:\n\n{file_id}")

# Обработчик документов
@bot.message_handler(content_types=['document'])
def handle_document(message):
    file_id = message.document.file_id
    bot.send_message(message.chat.id, f"ID файла:\n\n{file_id}")

while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        time.sleep(5)
