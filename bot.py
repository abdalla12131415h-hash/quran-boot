# -*- coding: utf-8 -*-
"""
بوت تلجرام لاستماع وتحميل تلاوات القرآن الكريم.
الإصدار المحدث مع التفعيل التلقائي للويب هوك.
"""

import requests
import telebot
from flask import Flask, request
from telebot import types

# ---- الإعدادات الأساسية ----
BOT_TOKEN = "9257887300:AAEk8cBzp8L_XxtAvNVeYf-FQbmbXg5EhPY"

API_BASE_URL = "https://mp3quran.net/api/v3"
LANGUAGE = "ar"
RECITERS_PER_PAGE = 10
SURAHS_PER_PAGE = 12

# رابط النشر الحالي على Vercel
WEBHOOK_URL = "https://quran-bot.vercel.app/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; QuranBot/1.0; +https://mp3quran.net)",
    "Accept": "application/json",
}

bot = telebot.TeleBot(BOT_TOKEN)

# تخزين مؤقت لتقليل عدد الطلبات على الواجهة
_reciters_cache = None
_surahs_cache = None


def get_reciters():
    global _reciters_cache
    if _reciters_cache is None:
        try:
            response = requests.get(
                f"{API_BASE_URL}/reciters",
                params={"language": LANGUAGE},
                headers=HEADERS,
                timeout=10,
            )
            response.raise_for_status()
            _reciters_cache = response.json().get("reciters", [])
        except Exception:
            _reciters_cache = []
    return _reciters_cache


def get_surahs():
    global _surahs_cache
    if _surahs_cache is None:
        try:
            response = requests.get(
                f"{API_BASE_URL}/suwar",
                params={"language": LANGUAGE},
                headers=HEADERS,
                timeout=10,
            )
            response.raise_for_status()
            _surahs_cache = {
                surah["id"]: surah["name"]
                for surah in response.json().get("suwar", [])
            }
        except Exception:
            _surahs_cache = {}
    return _surahs_cache


def get_main_moshaf(reciter):
    moshafs = reciter.get("moshaf", [])
    return moshafs[0] if moshafs else None


def build_reciters_keyboard(page):
    reciters = get_reciters()
    if not reciters:
        return None
    total_pages = max(1, (len(reciters) + RECITERS_PER_PAGE - 1) // RECITERS_PER_PAGE)
    start = page * RECITERS_PER_PAGE
    page_items = reciters[start:start + RECITERS_PER_PAGE]

    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton(
            text=reciter["name"],
            callback_data=f"rec|{start + index}|{page}",
        )
        for index, reciter in enumerate(page_items)
    ]
    if buttons:
        keyboard.add(*buttons)

    navigation = []
    if page > 0:
        navigation.append(
            types.InlineKeyboardButton(text="⬅️ السابق", callback_data=f"recpage|{page - 1}")
        )
    navigation.append(
        types.InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
    )
    if page < total_pages - 1:
        navigation.append(
            types.InlineKeyboardButton(text="التالي ➡️", callback_data=f"recpage|{page + 1}")
        )
    keyboard.row(*navigation)
    return keyboard


def build_surahs_keyboard(reciter_index, page):
    reciters = get_reciters()
    if reciter_index >= len(reciters):
        return None
    reciter = reciters[reciter_index]
    moshaf = get_main_moshaf(reciter)
    if not moshaf:
        return None
    surah_ids = [int(item) for item in moshaf["surah_list"].split(",") if item]
    surah_names = get_surahs()

    total_pages = max(1, (len(surah_ids) + SURAHS_PER_PAGE - 1) // SURAHS_PER_PAGE)
    start = page * SURAHS_PER_PAGE
    page_items = surah_ids[start:start + SURAHS_PER_PAGE]

    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton(
            text=surah_names.get(surah_id, f"سورة {surah_id}"),
            callback_data=f"surah|{reciter_index}|{surah_id}",
        )
        for surah_id in page_items
    ]
    if buttons:
        keyboard.add(*buttons)

    navigation = []
    if page > 0:
        navigation.append(
            types.InlineKeyboardButton(
                text="⬅️ السابق", callback_data=f"surpage|{reciter_index}|{page - 1}"
            )
        )
    navigation.append(
        types.InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
    )
    if page < total_pages - 1:
        navigation.append(
            types.InlineKeyboardButton(
                text="التالي ➡️", callback_data=f"surpage|{reciter_index}|{page + 1}"
            )
        )
    keyboard.row(*navigation)
    keyboard.row(
        types.InlineKeyboardButton(text="🔙 قائمة القراء", callback_data="recpage|0")
    )
    return keyboard


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    try:
        keyboard = build_reciters_keyboard(0)
        if not keyboard:
            bot.send_message(message.chat.id, "عذراً، توفّر بيانات القراء غير متاح حالياً.")
            return
        bot.send_message(
            message.chat.id,
            "أهلاً بك في بوت القرآن الكريم 🕌\n\nاختر القارئ الذي تريد الاستماع إليه:",
            reply_markup=keyboard,
        )
    except Exception:
        bot.send_message(message.chat.id, "تعذّر الاتصال بخدمة mp3quran.net، حاول لاحقاً.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("recpage|"))
def handle_reciters_page(call):
    try:
        page = int(call.data.split("|")[1])
        keyboard = build_reciters_keyboard(page)
        if keyboard:
            bot.edit_message_text(
                "اختر القارئ الذي تريد الاستماع إليه:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=keyboard,
            )
        bot.answer_callback_query(call.id)
    except Exception:
        bot.answer_callback_query(call.id, "حدث خطأ ما، حاول مرة أخرى.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("rec|"))
def handle_reciter_selected(call):
    try:
        _, reciter_index, _page = call.data.split("|")
        reciter_index = int(reciter_index)
        reciters = get_reciters()
        if reciter_index >= len(reciters):
            bot.answer_callback_query(call.id, "عذراً، انتهت صلاحية الجلسة، اضغط /start من جديد.")
            return

        bot.edit_message_text(
            f"القارئ: {reciters[reciter_index]['name']}\n\nاختر السورة:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=build_surahs_keyboard(reciter_index, 0),
        )
        bot.answer_callback_query(call.id)
    except Exception:
        bot.answer_callback_query(call.id, "حدث خطأ، حاول مجدداً.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("surpage|"))
def handle_surahs_page(call):
    try:
        _, reciter_index, page = call.data.split("|")
        reciter_index = int(reciter_index)
        page = int(page)
        reciters = get_reciters()
        if reciter_index >= len(reciters):
            return

        bot.edit_message_text(
            f"القارئ: {reciters[reciter_index]['name']}\n\nاختر السورة:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=build_surahs_keyboard(reciter_index, page),
        )
        bot.answer_callback_query(call.id)
    except Exception:
        bot.answer_callback_query(call.id, "حدث خطأ، حاول مجدداً.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("surah|"))
def handle_surah_selected(call):
    try:
        _, reciter_index, surah_id = call.data.split("|")
        reciter_index = int(reciter_index)
        surah_id = int(surah_id)

        reciters = get_reciters()
        if reciter_index >= len(reciters):
            bot.answer_callback_query(call.id, "انتهت الجلسة، أرسل /start مجدداً.")
            return
        reciter = reciters[reciter_index]
        moshaf = get_main_moshaf(reciter)
        if not moshaf:
            bot.answer_callback_query(call.id, "عذراً، تلاوة هذا القارئ غير متوفرة حالياً.")
            return

        surah_name = get_surahs().get(surah_id, f"سورة {surah_id}")

        server = moshaf["server"]
        if not server.endswith("/"):
            server += "/"
        audio_url = f"{server}{surah_id:03d}.mp3"
        caption = f"{surah_name} - {reciter['name']}"

        bot.answer_callback_query(call.id, "جارٍ إرسال التلاوة...")
        bot.send_audio(
            call.message.chat.id,
            audio_url,
            caption=caption,
        )
    except Exception:
        bot.answer_callback_query(call.id, "تعذّر إرسال الملف الصوتي، حاول مرة أخرى.")


@bot.callback_query_handler(func=lambda call: call.data == "noop")
def handle_noop(call):
    bot.answer_callback_query(call.id)


# ---- تطبيق الويب (Webhook) الخاص باستضافة Vercel ----
app = Flask(__name__)

# تفعيل الويب هوك تلقائياً عند بدء التشغيل على السيرفر
try:
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
except Exception:
    pass


@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "POST":
        try:
            json_data = request.get_json(force=True)
            if json_data:
                update = telebot.types.Update.de_json(json_data)
                bot.process_new_updates([update])
        except Exception as e:
            print(f"Error processing update: {e}")
        return "OK", 200
    return "Quran bot is running", 200


@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    return f"تم ضبط الـ Webhook على: {WEBHOOK_URL}", 200


@app.route("/webhook_info", methods=["GET"])
def webhook_info():
    info = bot.get_webhook_info()
    return {
        "url": info.url,
        "pending_update_count": info.pending_update_count,
        "last_error_date": info.last_error_date,
        "last_error_message": info.last_error_message,
        "max_connections": info.max_connections,
        "ip_address": info.ip_address,
    }, 200
