import telebot
import requests
from datetime import datetime, timedelta
import os
import threading
import time as time_module
from dotenv import load_dotenv
from telebot import types

load_dotenv()

# Твой токен
TELEGRAM_TOKEN = "8669371488:AAGtGAvjm1NJKgmdSg8FviBDn6yCf4CcEJA"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

user_data = {}           # сохранённая локация
user_notify_times = {}   # времена уведомлений

def deg_to_dir(deg):
    dirs = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]
    emojis = ["⬆️", "↗️", "➡️", "↘️", "⬇️", "↙️", "⬅️", "↖️"]
    idx = round(deg / 45) % 8
    return dirs[idx], emojis[idx]

def get_emoji_desc(code):
    wmo = {
        0: ("☀️", "Ясно"), 1: ("🌤️", "Преимущественно ясно"), 3: ("☁️", "Пасмурно"),
        61: ("🌧️", "Слабый дождь"), 63: ("🌧️", "Дождь"), 65: ("🌧️", "Сильный дождь"),
        71: ("❄️", "Слабый снег"), 73: ("❄️", "Снег"), 75: ("❄️", "Сильный снег"),
        80: ("🌦️", "Ливень"), 95: ("⛈️", "Гроза")
    }
    return wmo.get(code, ("🌥️", "Облачно"))

# ==================== Погода сейчас ====================
def send_weather(chat_id, lat=None, lon=None, city_name=None, country=None):
    try:
        if lat is None or lon is None:
            if chat_id not in user_data:
                bot.send_message(chat_id, "📍 Сначала укажи город или локацию!")
                return
            data = user_data[chat_id]
            lat, lon = data["lat"], data["lon"]
            city_name = data["city"]
            country = data["country"]

        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,"
               f"wind_direction_10m,pressure_msl,weather_code&daily=sunrise,sunset&timezone=auto")
        
        data = requests.get(url, timeout=10).json()
        c = data["current"]
        d = data["daily"]

        temp = round(c["temperature_2m"])
        feels = round(c["apparent_temperature"])
        hum = c["relative_humidity_2m"]
        wind_sp = round(c["wind_speed_10m"], 1)
        wind_deg = c["wind_direction_10m"]
        press = round(c["pressure_msl"] * 0.75006)
        emoji, desc = get_emoji_desc(c["weather_code"])
        direction, dir_emoji = deg_to_dir(wind_deg)
        sunrise = datetime.fromisoformat(d["sunrise"][0]).strftime("%H:%M")
        sunset = datetime.fromisoformat(d["sunset"][0]).strftime("%H:%M")

        location = f"{city_name}, {country}" if country else city_name

        text = f"**Погода в {location}**\n\n"
        text += f"{emoji} **{desc}**\n"
        text += f"🌡️ {temp}°C (ощущается как {feels}°C)\n"
        text += f"💧 Влажность: {hum}%\n"
        text += f"🌬 Ветер: {wind_sp} м/с {dir_emoji} {direction}\n"
        text += f"📈 Давление: {press} мм рт. ст.\n"
        text += f"🌅 Восход: {sunrise} | 🌇 Заход: {sunset}\n"
        text += f"🕒 {datetime.now().strftime('%d.%m.%Y %H:%M')}"

        bot.send_message(chat_id, text, parse_mode='Markdown')
        user_data[chat_id] = {"city": city_name, "lat": lat, "lon": lon, "country": country or ""}

    except:
        bot.send_message(chat_id, "Не удалось получить данные 😔")

# ==================== Почасовой прогноз (5 часов) ====================
def send_hourly_forecast(chat_id):
    if chat_id not in user_data:
        bot.send_message(chat_id, "📍 Сначала сохрани локацию кнопкой «Локация»")
        return
    data = user_data[chat_id]
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={data['lat']}&longitude={data['lon']}"
               f"&hourly=temperature_2m,weather_code,wind_speed_10m,wind_direction_10m"
               f"&timezone=auto")
        resp = requests.get(url, timeout=10).json()
        hourly = resp["hourly"]

        text = f"⏰ **Почасовой прогноз на сегодня в {data['city']}, {data['country']}**\n\n"
        now = datetime.now()
        count = 0

        for i in range(len(hourly["time"])):
            hour_time = datetime.fromisoformat(hourly["time"][i])
            if hour_time < now - timedelta(hours=1):
                continue

            emoji, desc = get_emoji_desc(hourly["weather_code"][i])
            temp = round(hourly["temperature_2m"][i])
            wind_sp = round(hourly["wind_speed_10m"][i], 1)
            wind_deg = hourly["wind_direction_10m"][i]
            direction, dir_emoji = deg_to_dir(wind_deg)

            text += f"{hour_time.strftime('%H:%M')} — {emoji} {desc}  🌡️ {temp}°C  🌬 {wind_sp} м/с {dir_emoji} {direction}\n"
            
            count += 1
            if count >= 5:
                break

        bot.send_message(chat_id, text, parse_mode='Markdown')
    except Exception as e:
        bot.send_message(chat_id, f"Не удалось получить почасовой прогноз 😔")

# ==================== Прогноз на 7 дней ====================
def send_7day_forecast(chat_id):
    if chat_id not in user_data:
        bot.send_message(chat_id, "📍 Сначала сохрани локацию кнопкой «Локация»")
        return
    data = user_data[chat_id]
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={data['lat']}&longitude={data['lon']}"
               f"&daily=weather_code,temperature_2m_max,temperature_2m_min,wind_speed_10m_max,"
               f"wind_direction_10m_dominant,pressure_msl_mean,sunrise,sunset&timezone=auto")
        resp = requests.get(url, timeout=10).json()
        daily = resp["daily"]

        text = f"📅 **Прогноз на 7 дней в {data['city']}, {data['country']}**\n\n"
        for i in range(7):
            date = datetime.fromisoformat(daily["time"][i])
            emoji, desc = get_emoji_desc(daily["weather_code"][i])
            tmax = round(daily["temperature_2m_max"][i])
            tmin = round(daily["temperature_2m_min"][i])
            wind = round(daily["wind_speed_10m_max"][i], 1)
            wind_deg = daily["wind_direction_10m_dominant"][i]
            direction, dir_emoji = deg_to_dir(wind_deg)
            press = round(daily["pressure_msl_mean"][i] * 0.75006)
            sunrise = datetime.fromisoformat(daily["sunrise"][i]).strftime("%H:%M")
            sunset = datetime.fromisoformat(daily["sunset"][i]).strftime("%H:%M")

            text += f"{date.strftime('%d.%m')} — {emoji} {desc}\n"
            text += f"   🌡️ {tmin}° … {tmax}°C\n"
            text += f"   🌬 Ветер: {wind} м/с {dir_emoji} {direction}\n"
            text += f"   📈 Давление: {press} мм рт. ст.\n"
            text += f"   🌅 {sunrise} | 🌇 {sunset}\n\n"

        bot.send_message(chat_id, text, parse_mode='Markdown')
    except:
        bot.send_message(chat_id, "Не удалось получить прогноз 😔")

# ==================== Уведомления ====================
last_notification = {}

def notification_scheduler():
    while True:
        now = datetime.now().strftime("%H:%M")
        for chat_id, times in list(user_notify_times.items()):
            if now in times and chat_id in user_data:
                key = f"{chat_id}_{now}"
                if key not in last_notification or (time_module.time() - last_notification[key]) > 70:
                    data = user_data[chat_id]
                    send_weather(chat_id, data["lat"], data["lon"], data["city"], data["country"])
                    bot.send_message(chat_id, f"🕒 Погода на {now}")
                    last_notification[key] = time_module.time()
        time_module.sleep(30)

# ==================== Меню ====================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🌤 Погода сейчас", "⏰ Почасовой прогноз")
    markup.add("📅 7 дней", "📍 Локация")
    markup.add("🕒 Уведомления", "🔄 Обновить")
    
    bot.send_message(message.chat.id,
                     "👋 Привет! Я бот погоды.\n\n"
                     "Напиши город или отправь свою локацию 👇",
                     reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📍 Локация")
def show_location(message):
    if message.chat.id in user_data:
        data = user_data[message.chat.id]
        text = f"📍 **Текущая локация:**\n{data['city']}, {data['country']}\n\nНапиши новый город, чтобы изменить."
        bot.send_message(message.chat.id, text, parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "📍 Локация не сохранена.\nНапиши город или отправь координаты.")

@bot.message_handler(func=lambda m: m.text == "🌤 Погода сейчас")
def current_weather(message):
    send_weather(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "⏰ Почасовой прогноз")
def hourly_forecast(message):
    send_hourly_forecast(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "📅 7 дней")
def forecast_7days(message):
    send_7day_forecast(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "🔄 Обновить")
def refresh(message):
    send_weather(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "🕒 Уведомления")
def set_notifications(message):
    bot.send_message(message.chat.id, "🕒 Во сколько присылать погоду?\nМожно два времени через запятую\nПример: 07:30, 18:00")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    text = message.text.strip()
    chat_id = message.chat.id

    if text in ["🌤 Погода сейчас", "⏰ Почасовой прогноз", "📅 7 дней", "📍 Локация", "🕒 Уведомления", "🔄 Обновить"]:
        return

    if ":" in text:
        times = [t.strip() for t in text.replace(" ", "").split(",")]
        valid = [t for t in times if len(t) == 5 and t[2] == ":"]
        if valid:
            user_notify_times[chat_id] = valid[:2]
            bot.send_message(chat_id, f"✅ Уведомления будут приходить в {', '.join(valid)}")
            return

    if "," in text or " " in text:
        try:
            parts = text.replace(" ", ",").split(",")
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            send_weather(chat_id, lat, lon, "Твоя локация")
            return
        except:
            pass

    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={text}&count=1&language=ru&format=json"
    try:
        geo = requests.get(geo_url, timeout=10).json()
        if not geo.get("results"):
            bot.send_message(chat_id, "😔 Город не найден. Проверь название.")
            return
        r = geo["results"][0]
        lat, lon = r["latitude"], r["longitude"]
        city = r.get("name", text)
        country = r.get("country", "")
        send_weather(chat_id, lat, lon, city, country)
    except:
        bot.send_message(chat_id, "😔 Город не найден. Проверь название.")

threading.Thread(target=notification_scheduler, daemon=True).start()

print("✅ Бот запущен! Почасовой прогноз исправлен.")
bot.infinity_polling()