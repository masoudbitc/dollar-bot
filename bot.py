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
last_xaut_irt = None
last_gold_18k = None

def get_iran_time():
    """دریافت زمان دقیق ایران (UTC + 3:30)"""
    iran_offset = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(iran_offset).strftime("%H:%M:%S")

def fetch_nobitex_price(symbol):
    """دریافت قیمت از نوبیتکس با هدر مرورگر واقعی"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # روش اول: استفاده از endpoint اصلی orderbook
    try:
        url = f"https://apiv2.nobitex.ir/v3/orderbook/{symbol}"
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code == 200:
            data = r.json()
            if data.get("lastTradePrice") is not None and float(data["lastTradePrice"]) > 0:
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
        else:
            print(f"[{get_iran_time()}] Orderbook {symbol} status code: {r.status_code}")
    except Exception as e:
        print(f"[{get_iran_time()}] Orderbook error for {symbol}: {repr(e)}")

    # روش دوم (جایگزین): دریافت از endpoint آمار بازار
    try:
        url = "https://api.nobitex.ir/v2/market/stats"
        src_dst = symbol.lower().replace("irt", "-irt").replace("usdt", "-usdt")
        r = requests.post(url, json={"src": src_dst.split("-")[0], "dst": src_dst.split("-")[1]}, headers=headers, timeout=10)
        if r.status_code == 200:
            stats = r.json().get("stats", {})
            key = f"{src_dst.split('-')[0]}-{src_dst.split('-')[1]}"
            price = stats.get(key, {}).get("latest")
            if price:
                return float(price)
    except Exception as e:
        print(f"[{get_iran_time()}] Stats fallback error for {symbol}: {repr(e)}")

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
    global last_usdt_irt, last_btc_usdt, last_xaut_irt, last_gold_18k
    
    current_time = get_iran_time()
    print(f"ربات شروع شد | ساعت ایران: {current_time}")
    send_message(f"🤖 <b>ربات قیمت تتر، طلا و بیت‌کوین فعال شد!</b>\n⏰ ساعت ثبت: {current_time}")

    while True:
        try:
            # دریافت قیمت‌ها از نوبیتکس
            usdt_irt = fetch_nobitex_price("USDTIRT")
            btc_usdt = fetch_nobitex_price("BTCUSDT")
            xaut_irt = fetch_nobitex_price("XAUTIRT")

            now_str = get_iran_time()

            # اگر هر کدام از قیمت‌ها دریافت نشد، ۵ ثانیه صبر کن
            if usdt_irt is None or btc_usdt is None or xaut_irt is None:
                print(f"[{now_str}] دریافت کامل انجام نشد (USDT: {usdt_irt} | BTC: {btc_usdt} | XAUT: {xaut_irt})، ۵ ثانیه صبر...")
                time.sleep(5)
                continue

            # تبدیل قیمت تتر و طلا از ریال به تومان (در صورت نیاز)
            usdt_irt = int(usdt_irt / 10) if usdt_irt > 100000 else int(usdt_irt)
            xaut_irt = int(xaut_irt / 10) if xaut_irt > 1000000 else int(xaut_irt)
            btc_usdt = round(btc_usdt, 2)

            # فرمول تبدیل هر انس تترگلد به یک گرم طلای ۱۸ عیار
            # ۱ انس = ۳۱.۱۰۳۴۷۶۸ گرم | عیار ۱۸ = ۱۸/۲۴ (یا ۰.۷۵)
            gold_18k = int((xaut_irt / 31.1034768) * (18 / 24))

            # مقداردهی اولیه قیمت‌ها در اولین اجرا
            if last_usdt_irt is None or last_btc_usdt is None or last_xaut_irt is None or last_gold_18k is None:
                last_usdt_irt = usdt_irt
                last_btc_usdt = btc_usdt
                last_xaut_irt = xaut_irt
                last_gold_18k = gold_18k
                print(f"[{now_str}] قیمت‌های اولیه ثبت شدند | USDT: {usdt_irt:,} | XAUT: {xaut_irt:,} | 18K: {gold_18k:,} | BTC: ${btc_usdt:,.2f}")
                time.sleep(4)
                continue

            # چک کردن تغییر در هر یک از قیمت‌ها (حتی ۱ تومان تغییر در گرم طلا باعث آپدیت می‌شود)
            if (usdt_irt != last_usdt_irt) or (btc_usdt != last_btc_usdt) or (xaut_irt != last_xaut_irt) or (gold_18k != last_gold_18k):
                usdt_arrow = get_arrow(usdt_irt, last_usdt_irt)
                btc_arrow = get_arrow(btc_usdt, last_btc_usdt)
                xaut_arrow = get_arrow(xaut_irt, last_xaut_irt)
                gold_18k_arrow = get_arrow(gold_18k, last_gold_18k)

                message = (
                    f"⏰ <b>{now_str}</b>\n\n"
                    f"💵 <b>تتر:</b> {usdt_irt:,} تومان {usdt_arrow}\n"
                    f"🥇 <b>تتر گلد (انس):</b> {xaut_irt:,} تومان {xaut_arrow}\n"
                    f"🔱 <b>تترگلد (۱۸ عیار):</b> {gold_18k:,} تومان {gold_18k_arrow}\n"
                    f"🪙 <b>بیت‌کوین:</b> ${btc_usdt:,.2f} {btc_arrow}"
                )
                
                print(f"[{now_str}] قیمت تغییر کرد! ارسال به کانال...")
                send_message(message)

                # به‌روزرسانی مقادیر قبلی
                last_usdt_irt = usdt_irt
                last_btc_usdt = btc_usdt
                last_xaut_irt = xaut_irt
                last_gold_18k = gold_18k
            else:
                print(f"[{now_str}] بدون تغییر | USDT: {usdt_irt:,} | 18K: {gold_18k:,} | BTC: ${btc_usdt:,.2f}")

        except Exception as e:
            print(f"خطای غیرمنتظره در حلقه اصلی: {repr(e)}")

        time.sleep(4)

# ---- 3. اجرا ----
if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    bot_loop()
