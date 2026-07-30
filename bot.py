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
last_milli_price = None
last_melligold_price = None

def get_iran_time():
    """دریافت زمان دقیق ایران (UTC + 3:30)"""
    iran_offset = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(iran_offset).strftime("%H:%M:%S")

def fetch_nobitex_price(symbol):
    """دریافت قیمت از نوبیتکس با هدر مرورگر واقعی"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
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
    except Exception as e:
        print(f"[{get_iran_time()}] Nobitex error for {symbol}: {repr(e)}")

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
        print(f"[{get_iran_time()}] Nobitex fallback error for {symbol}: {repr(e)}")

    return None

def fetch_milli_price():
    """دریافت قیمت یک گرم طلای ۱۸ عیار از میلی (Milli)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*"
    }
    try:
        # فراخوانی ای‌پای عمومی میلی
        url = "https://milli.gold/api/v1/price/latest"
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            # استخراج قیمت هر گرم یا هر میلی‌گرم
            price = data.get("price") or data.get("buyPrice") or data.get("data", {}).get("price")
            if price:
                price = float(price)
                # در صورت ریال بودن به تومان تبدیل می‌شود
                return int(price / 10) if price > 10000000 else int(price)
    except Exception as e:
        print(f"[{get_iran_time()}] Milli gold fetch error: {repr(e)}")
    return None

def fetch_melligold_price():
    """دریافت قیمت یک گرم طلای ۱۸ عیار از ملی‌گلد (Melli Gold)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*"
    }
    try:
        url = "https://melligold.com/api/v1/gold-price"
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            price = data.get("price") or data.get("buy_price") or data.get("data", {}).get("price")
            if price:
                price = float(price)
                return int(price / 10) if price > 10000000 else int(price)
    except Exception as e:
        print(f"[{get_iran_time()}] Melli Gold fetch error: {repr(e)}")
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
    global last_xaut_irt, last_gold_18k, last_milli_price, last_melligold_price
    
    current_time = get_iran_time()
    print(f"ربات شروع شد | ساعت ایران: {current_time}")
    send_message(f"🤖 <b>ربات قیمت ارز و طلا فعال شد!</b>\n⏰ ساعت ثبت: {current_time}")

    while True:
        try:
            now_str = get_iran_time()

            # 1. دریافت قیمت‌های ارز و کریپتو
            usdt_irt = fetch_nobitex_price("USDTIRT")
            btc_usdt = fetch_nobitex_price("BTCUSDT")

            # 2. دریافت قیمت‌های طلا
            xaut_irt = fetch_nobitex_price("XAUTIRT")
            milli_price = fetch_milli_price()
            melligold_price = fetch_melligold_price()

            # پردازش تتر و بیت کوین
            if usdt_irt is not None and btc_usdt is not None:
                usdt_irt = int(usdt_irt / 10) if usdt_irt > 100000 else int(usdt_irt)
                btc_usdt = round(btc_usdt, 2)

                # اولین مقداردهی یا تغییر در دلار/بیت‌کوین
                if last_usdt_irt is None or last_btc_usdt is None:
                    last_usdt_irt = usdt_irt
                    last_btc_usdt = btc_usdt
                elif (usdt_irt != last_usdt_irt) or (btc_usdt != last_btc_usdt):
                    usdt_arrow = get_arrow(usdt_irt, last_usdt_irt)
                    btc_arrow = get_arrow(btc_usdt, last_btc_usdt)

                    crypto_msg = (
                        f"⏰ <b>{now_str}</b> | 💱 <b>بازار ارز و دیجیتال</b>\n\n"
                        f"💵 <b>تتر:</b> {usdt_irt:,} تومان {usdt_arrow}\n"
                        f"🪙 <b>بیت‌کوین:</b> ${btc_usdt:,.2f} {btc_arrow}"
                    )
                    print(f"[{now_str}] قیمت ارز/بیت‌کوین تغییر کرد! ارسال به کانال...")
                    send_message(crypto_msg)

                    last_usdt_irt = usdt_irt
                    last_btc_usdt = btc_usdt

            # پردازش طلا
            if xaut_irt is not None:
                xaut_irt = int(xaut_irt / 10) if xaut_irt > 1000000 else int(xaut_irt)
                # فرمول تبدیل هر انس تترگلد به یک گرم طلای ۱۸ عیار
                gold_18k = int((xaut_irt / 31.1034768) * (18 / 24))

                # اولین مقداردهی طلا
                if last_xaut_irt is None or last_gold_18k is None:
                    last_xaut_irt = xaut_irt
                    last_gold_18k = gold_18k
                    last_milli_price = milli_price
                    last_melligold_price = melligold_price
                elif (xaut_irt != last_xaut_irt) or (gold_18k != last_gold_18k) or \
                     (milli_price != last_milli_price and milli_price is not None) or \
                     (melligold_price != last_melligold_price and melligold_price is not None):

                    xaut_arrow = get_arrow(xaut_irt, last_xaut_irt)
                    gold_18k_arrow = get_arrow(gold_18k, last_gold_18k)
                    milli_arrow = get_arrow(milli_price, last_milli_price) if milli_price else "⚪️ ➖"
                    melligold_arrow = get_arrow(melligold_price, last_melligold_price) if melligold_price else "⚪️ ➖"

                    milli_str = f"{milli_price:,} تومان" if milli_price else "در حال دریافت..."
                    melligold_str = f"{melligold_price:,} تومان" if melligold_price else "در حال دریافت..."

                    gold_msg = (
                        f"⏰ <b>{now_str}</b> | 🏆 <b>بازار طلا</b>\n\n"
                        f"🥇 <b>تتر گلد (انس):</b> {xaut_irt:,} تومان {xaut_arrow}\n"
                        f"🔱 <b>هر گرم تترگلد (۱۸ عیار):</b> {gold_18k:,} تومان {gold_18k_arrow}\n"
                        f"🟡 <b>طلای ۱۸ عیار (میلی):</b> {milli_str} {milli_arrow}\n"
                        f"✨ <b>طلای ۱۸ عیار (ملی‌گلد):</b> {melligold_str} {melligold_arrow}"
                    )
                    print(f"[{now_str}] قیمت طلا تغییر کرد! ارسال به کانال...")
                    send_message(gold_msg)

                    last_xaut_irt = xaut_irt
                    last_gold_18k = gold_18k
                    if milli_price: last_milli_price = milli_price
                    if melligold_price: last_melligold_price = melligold_price

            print(f"[{now_str}] بررسی انجام شد.")

        except Exception as e:
            print(f"خطای غیرمنتظره در حلقه اصلی: {repr(e)}")

        time.sleep(5)

# ---- 3. اجرا ----
if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    bot_loop()
