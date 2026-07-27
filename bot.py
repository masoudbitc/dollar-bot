import os
import requests
import time
import threading
from flask import Flask
from datetime import datetime, timezone, timedelta

# ---- 1. وب‌سرور برای Render و UptimeRobot ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ---- 2. تنظیمات ربات و زمان ایران ----
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = -1003721340249

# ذخیره آخرین قیمت‌های ثبت شده
last_usdt_irt = None
last_btc_usdt = None

def get_iran_time():
    """دریافت زمان دقیق ایران (UTC + 3:30)"""
    iran_offset = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(iran_offset).strftime("%H:%M:%S")

def fetch_nobitex_price(symbol):
    """تابع عمومی برای دریافت قیمت از نوبیتکس"""
    try:
        url = f"https://apiv2.nobitex.ir/v3/orderbook/{symbol}"
        r = requests.get(url, timeout=10)

        if r.status_code != 200:
            print(f"[{get_iran_time()}] خطا در دریافت {symbol}: کد {r.status_code}")
            return None

        data = r.json()

        if data.get("lastTradePrice") is not None:
            return float(data["lastTradePrice"])

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        best_bid = float(bids[0][0]) if isinstance(bids, list) and bids else None
        best_ask = float(asks[0][0]) if isinstance(asks, list) and asks else None

        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2
        if best_bid is not None:
            return best_bid
        if best_ask is not None:
            return best_ask

        return None

    except Exception as e:
        print(f"[{get_iran_time()}] استثنا در دریافت {symbol}: {repr(e)}")
        return None

def get_arrow(new_val, old_val):
    """تعیین فلش بر اساس تغییرات قیمت"""
    if old_val is None or new_val == old_val:
        return "⚪️ ➖"
    elif new_val > old_val:
        return "🟢 🔺"
    else:
        return "🔴 🔻"

def send_message(text):
    if not TOKEN:
        print("خطا: BOT_TOKEN تنظیم نشده است!")
        return

    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        if res.status_code != 200:
            print(f"[{get_iran_time()}] خطا در ارسال به تلگرام: {res.status_code} - {res.text[:100]}")
        else:
            print(f"[{get_iran_time()}] پیام با موفقیت به تلگرام ارسال شد.")
    except Exception as e:
        print(f"[{get_iran_time()}] استثنا در ارسال به تلگرام: {repr(e)}")

def bot_loop():
    global last_usdt_irt, last_btc_usdt
    
    current_time = get_iran_time()
    print(f"ربات شروع شد | ساعت ایران: {current_time}")
    send_message(f"🤖 <b>ربات قیمت تتر و بیت‌کوین فعال شد!</b>\n⏰ ساعت ثبت: {current_time}")

    while True:
        try:
            # دریافت قیمت‌ها از نوبیتکس
            usdt_irt = fetch_nobitex_price("USDTIRT")
            btc_usdt = fetch_nobitex_price("BTCUSDT")

            now_str = get_iran_time()

            # اگر هر کدام از قیمت‌ها دریافت نشد، ۵ ثانیه صبر کن
            if usdt_irt is None or btc_usdt is None:
                print(f"[{now_str}] دریافت کامل قیمت‌ها انجام نشد، ۵ ثانیه صبر...")
                time.sleep(5)
                continue

            usdt_irt = int(usdt_irt)
            btc_usdt = round(btc_usdt, 2)

            # مقداردهی اولیه قیمت‌ها در اولین اجرا
            if last_usdt_irt is None or last_btc_usdt is None:
                last_usdt_irt = usdt_irt
                last_btc_usdt = btc_usdt
                print(f"[{now_str}] قیمت‌های اولیه ثبت شدند.")
                time.sleep(4)
                continue

            # چک کردن تغییر در هر یک از قیمت‌ها
            if (usdt_irt != last_usdt_irt) or (btc_usdt != last_btc_usdt):
                # محاسبه فلش‌ها برای تتر و بیت‌کوین
                usdt_arrow = get_arrow(usdt_irt, last_usdt_irt)
                btc_arrow = get_arrow(btc_usdt, last_btc_usdt)

                # ساخت قالب پیام جدید
                message = (
                    f"⏰ <b>{now_str}</b>\n\n"
                    f"💵 <b>تتر:</b> {usdt_irt:,} تومان {usdt_arrow}\n"
                    f"🪙 <b>بیت‌کوین:</b> ${btc_usdt:,.2f} {btc_arrow}"
                )
                
                print(f"[{now_str}] قیمت تغییر کرد! ارسال به کانال...")
                send_message(message)

                # به‌روزرسانی مقادیر قبلی
                last_usdt_irt = usdt_irt
                last_btc_usdt = btc_usdt
            else:
                print(f"[{now_str}] قیمت‌ها بدون تغییر | USDT: {usdt_irt:,} | BTC: ${btc_usdt:,.2f}")

        except Exception as e:
            print(f"خطای غیرمنتظره در حلقه اصلی: {repr(e)}")

        time.sleep(4)

# ---- 3. اجرا ----
if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    bot_loop()
