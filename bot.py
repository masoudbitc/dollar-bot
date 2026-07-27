import os
import requests
import time
import threading
from flask import Flask
from datetime import datetime
import pytz

# ---- 1. وب‌سرور برای Render و UptimeRobot ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ---- 2. تنظیمات ربات و منطقه زمانی ایران ----
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = -1003721340249
TIMEZONE = pytz.timezone('Asia/Tehran')

last_price = None

def get_iran_time():
    """دریافت زمان دقیق به وقت تهران"""
    return datetime.now(TIMEZONE).strftime("%H:%M:%S")

def get_price():
    try:
        url = "https://apiv2.nobitex.ir/v3/orderbook/USDTIRT"
        r = requests.get(url, timeout=10)

        if r.status_code != 200:
            print(f"[{get_iran_time()}] خطا در دریافت قیمت از نوبیتکس: کد {r.status_code}")
            return None

        data = r.json()

        if data.get("lastTradePrice") is not None:
            return int(float(data["lastTradePrice"]))

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        best_bid = float(bids[0][0]) if isinstance(bids, list) and bids else None
        best_ask = float(asks[0][0]) if isinstance(asks, list) and asks else None

        if best_bid is not None and best_ask is not None:
            return int((best_bid + best_ask) / 2)
        if best_bid is not None:
            return int(best_bid)
        if best_ask is not None:
            return int(best_ask)

        return None

    except Exception as e:
        print(f"[{get_iran_time()}] استثنا در دریافت قیمت: {repr(e)}")
        return None

def send_message(text):
    if not TOKEN:
        print("خطا: BOT_TOKEN تنظیم نشده است!")
        return

    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
        if res.status_code != 200:
            print(f"[{get_iran_time()}] خطا در ارسال به تلگرام: {res.status_code} - {res.text[:100]}")
        else:
            print(f"[{get_iran_time()}] پیام با موفقیت به تلگرام ارسال شد.")
    except Exception as e:
        print(f"[{get_iran_time()}] استثنا در ارسال به تلگرام: {repr(e)}")

def bot_loop():
    global last_price
    print("ربات شروع شد، ارسال پیام تست...")
    send_message("🤖 ربات قیمت USDT فعال شد!")

    while True:
        try:
            price = get_price()
            now_str = get_iran_time()

            if price is None:
                print(f"[{now_str}] قیمت دریافت نشد، ۵ ثانیه صبر...")
                time.sleep(5)
                continue

            if last_price is None:
                last_price = price
                print(f"[{now_str}] قیمت اولیه ثبت شد: {price:,} تومان")
                time.sleep(4)
                continue

            if price != last_price:
                message = f"{now_str} | {price:,}"
                print(f"[{now_str}] قیمت تغییر کرد! از {last_price:,} به {price:,}. ارسال به کانال...")
                send_message(message)
                last_price = price
            else:
                print(f"[{now_str}] قیمت بدون تغییر: {price:,} تومان")

        except Exception as e:
            print(f"خطای غیرمنتظره در حلقه اصلی: {repr(e)}")

        time.sleep(4)

# ---- 3. اجرا ----
if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    bot_loop()        # ابتدا چک کردن قیمت آخرین معامله
        if data.get("lastTradePrice") is not None:
            return int(float(data["lastTradePrice"]))

        # در صورت نبودن، محاسبه از روی بهترین پیشنهاد خرید/فروش
        bids = data.get("bids", [])
        asks = data.get("asks", [])

        best_bid = float(bids[0][0]) if isinstance(bids, list) and bids else None
        best_ask = float(asks[0][0]) if isinstance(asks, list) and asks else None

        if best_bid is not None and best_ask is not None:
            return int((best_bid + best_ask) / 2)
        if best_bid is not None:
            return int(best_bid)
        if best_ask is not None:
            return int(best_ask)

        return None

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] استثنا در دریافت قیمت: {repr(e)}")
        return None

def send_message(text):
    if not TOKEN:
        print("خطا: BOT_TOKEN تنظیم نشده است!")
        return

    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
        if res.status_code != 200:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] خطا در ارسال به تلگرام: {res.status_code} - {res.text[:100]}")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] پیام با موفقیت به تلگرام ارسال شد.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] استثنا در ارسال به تلگرام: {repr(e)}")

def bot_loop():
    global last_price
    print("ربات شروع شد، ارسال پیام تست...")
    send_message("🤖 ربات قیمت USDT فعال شد!")

    while True:
        try:
            price = get_price()
            now_str = datetime.now().strftime("%H:%M:%S")

            if price is None:
                print(f"[{now_str}] قیمت دریافت نشد، ۵ ثانیه صبر...")
                time.sleep(5)
                continue

            if last_price is None:
                last_price = price
                print(f"[{now_str}] قیمت اولیه ثبت شد: {price:,} تومان")
                time.sleep(4)
                continue

            if price != last_price:
                message = f"{now_str} | {price:,}"
                print(f"[{now_str}] قیمت تغییر کرد! از {last_price:,} به {price:,}. ارسال به کانال...")
                send_message(message)
                last_price = price
            else:
                # این خط در لوگ چاپ می‌شود تا مطمئن شویم حلقه زنده است
                print(f"[{now_str}] قیمت بدون تغییر: {price:,} تومان")

        except Exception as e:
            print(f"خطای غیرمنتظره در حلقه اصلی: {repr(e)}")

        time.sleep(4)

# ---- 3. اجرا ----
if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    bot_loop()
