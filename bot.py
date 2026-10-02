import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# 1. Быстрый запуск веб-сервера для Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Запускаем поток сервера мгновенно при старте
server_thread = threading.Thread(target=run_health_check_server, daemon=True)
server_thread.start()

# 2. Токен бота (проверь его в BotFather!)
TOKEN = '8777407228:AAFw7FMHI4uc_L4GMP_Wt3RZ5-g9tGS_VnI'
bot = telebot.TeleBot(TOKEN)

try:
    bot.remove_webhook()
except Exception:
    pass

START_PHOTO_URL = 'https://i.ibb.co/Gfj8swsV/Untitled21.jpg'

LANG_PHOTOS = {
    'geo': 'AgACAgIAAxkBAAOBararlqGVoGBD7wKJ6huPpS6f6-YAAuQjaxuXHbFJEu-o-AVVgLYBAAMCAAN5AAM9BA',
    'eng': None,
    'rus': None
}

CITY_PHOTOS = {
    'geo': 'AgACAgIAAxkBAAONarasx_pBx0qle13mUv0ZopMBy58AAkkgaxvZVbBJDx5fGnJkpvABAAMCAAN5AAM9BA',
    'eng': None,
    'rus': None
}

TEXTS = {
    'geo': {
        'select_city': 'აირჩიეთ ქალაქი',
        'ambrolauri_btn': 'ამბროლაური',
        'oni_btn': 'ონი',
        'gift_btn': '🎁 საჩუქარი',
        'back_btn': '⬅️ უკან',
        'how_much': 'რამდენი გინდა?',
        'q05_btn': '0.5 გრ - 16 USDT',
        'q1_btn': '1 გრ - 31 USDT',
        'q2_btn': '2 გრ - 58 USDT',
        'q5_btn': '5 გრ - 135 USDT',
        'gift_info': (
            "🎁 **საჩუქარი**\n\n"
            "1. იყიდე 10 - ჯერ და მიიღე მე-11 საჩუქრად;\n"
            "2. მოიწვიე 10 მეგობარი, რომლებიც მინიმუმ ერთხელ იყიდიან და ასევე მიიღე 1 გრ საჩუქრად."
        )
    },
    'eng': {
        'select_city': 'Select a location',
        'ambrolauri_btn': 'Ambrolauri',
        'oni_btn': 'Oni',
        'gift_btn': '🎁 Gift',
        'back_btn': '⬅️ Back',
        'how_much': 'How much do you want?',
        'q05_btn': '0.5 g - 16 USDT',
        'q1_btn': '1 g - 31 USDT',
        'q2_btn': '2 g - 58 USDT',
        'q5_btn': '5 g - 135 USDT',
        'gift_info': (
            "🎁 **Gift Offer**\n\n"
            "1. Buy 10 times and get the 11th for free as a gift;\n"
            "2. Invite 10 friends who make at least 1 purchase and get 1 g as a gift."
        )
    },
    'rus': {
        'select_city': 'Выберите город',
        'ambrolauri_btn': 'Амбролаури',
        'oni_btn': 'Они',
        'gift_btn': '🎁 Подарок',
        'back_btn': '⬅️ Назад',
        'how_much': 'Сколько ты хочешь?',
        'q05_btn': '0.5 г - 16 USDT',
        'q1_btn': '1 g - 31 USDT',
        'q2_btn': '2 g - 58 USDT',
        'q5_btn': '5 g - 135 USDT',
        'gift_info': (
            "🎁 **Подарок**\n\n"
            "1. Купи 10 раз и получи 11-ый в подарок.\n"
            "2. Пригласи 10 друзей, которые хотя бы 1 раз купят и получи подарок."
        )
    }
}

def safe_send(chat_id, message_id, photo_or_url, text, reply_markup):
    if photo_or_url:
        try:
            bot.delete_message(chat_id, message_id)
            bot.send_photo(chat_id, photo=photo_or_url, caption=text, reply_markup=reply_markup, parse_mode='Markdown')
            return
        except Exception:
            pass
            
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass
    bot.send_message(chat_id, text=text, reply_markup=reply_markup, parse_mode='Markdown')

@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🇬🇪 ქართული", callback_data="setlang_geo"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="setlang_eng"),
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_rus")
    )
    bot.send_photo(message.chat.id, photo=START_PHOTO_URL, caption="🌍 Select language / აირჩიეთ ენა / Выберите язык", reply_markup=markup)

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
    photo_file_id = LANG_PHOTOS.get(lang)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t['back_btn'], callback_data=f"setlang_{lang}")
    )
    
    safe_send(call.message.chat.id, call.message.id, photo_file_id, t['gift_info'], markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('go_city_'))
def city_click(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_')
    city = parts[2]
    lang = parts[3]
    
    t = TEXTS[lang]
    photo_file_id = CITY_PHOTOS.get(lang)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t['q05_btn'], callback_data=f"qty_05_{city}_{lang}"),
        types.InlineKeyboardButton(t['q1_btn'], callback_data=f"qty_1_{city}_{lang}"),
        types.InlineKeyboardButton(t['q2_btn'], callback_data=f"qty_2_{city}_{lang}"),
        types.InlineKeyboardButton(t['q5_btn'], callback_data=f"qty_5_{city}_{lang}"),
        types.InlineKeyboardButton(t['back_btn'], callback_data=f"setlang_{lang}")
    )
    
    safe_send(call.message.chat.id, call.message.id, photo_file_id, t['how_much'], markup)

# Обработчик фото: отвечает на любую отправленную картинку
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    file_id = message.photo[-1].file_id
    bot.reply_to(message, f"Вот file_id твоей картинки:\n\n`{file_id}`", parse_mode='Markdown')

bot.infinity_polling(skip_pending=True)
