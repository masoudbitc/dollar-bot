import os
import requests
import time
import threading
from flask import Flask
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime

# ---- 1. وب‌سرور ساده برای راضی نگه داشتن Render ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ---- 2. تنظیمات ربات تلگرام ----
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = -1003721340249

last_price = None

# session با retry برای نوبیتکس
nobitex_session = requests.Session()
retries = Retry(
    total=6,
    backoff_factor=0.8,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False
)
nobitex_session.mount("https://", HTTPAdapter(max_retries=retries))

def get_price():
    try:
        url = "https://apiv2.nobitex.ir/v3/orderbook/USDTIRT"
        r = nobitex_session.get(url, timeout=(5, 20))

        if r.status_code != 200:
            print("Error getting price: HTTP", r.status_code, "body:", r.text[:300])
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
        print("Error getting price:", repr(e))
        return None

def send_message(text):
    if not TOKEN:
        print("خطا: توکن ربات (BOT_TOKEN) در تنظیمات Render ست نشده است!")
        return

    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
        if res.status_code != 200:
            print("Error sending message:", res.status_code, res.text[:300])
    except Exception as e:
        print("Error sending message:", repr(e))

def bot_loop():
    global last_price
    print("ربات شروع شد، ارسال پیام تست به کانال...")
    send_message("🤖 ربات قیمت USDT فعال شد!")

    while True:
        price = get_price()

        if price is None:
            print("قیمت دریافت نشد، ۵ ثانیه دیگر تلاش می‌کنم...")
            time.sleep(5)
            continue

        if last_price is None:
            last_price = price
            time.sleep(3)
            continue

        if price != last_price:
            now = datetime.now().strftime("%H:%M:%S")
            message = f"{now} | {price:,}"
            print(message)
            send_message(message)
            last_price = price

        # ایجاد فاصله ۳ ثانیه‌ای برای جلوگیری از بلاک شدن آی‌پی توسط نوبیتکس
        time.sleep(3)

# ---- 3. اجرای همزمان وب‌سرور و ربات ----
if __name__ == "__main__":
    # اجرای وب‌سرور در یک Thread جداگانه
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    # اجرای حلقه اصلی ربات
    bot_loop()
