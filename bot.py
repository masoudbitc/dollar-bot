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

last_xau_usd = None
last_gold_18k = None

def get_iran_time():
    """دریافت زمان دقیق ایران (UTC + 3:30)"""
    iran_offset = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(iran_offset).strftime("%H:%M:%S")

def fetch_nobitex_price(symbol):
    """دریافت قیمت از نوبیتکس"""
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

    return None

def fetch_tradingview_xauusd():
    """دریافت قیمت انس جهانی طلا (XAUUSD) از TradingView"""
    url = "https://scanner.tradingview.com/forex/scan"
    payload = {
        "symbols": {"tickers": ["FOREXCOM:XAUUSD"]},
        "columns": ["close"]
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            price = data["data"][0]["d"][0]
            return float(price)
    except Exception as e:
        print(f"[{get_iran_time()}] TradingView XAUUSD error: {repr(e)}")
        
    # روش جایگزین (Fallback) برای انس جهانی
    try:
        r2 = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/GC=F", headers=headers, timeout=10)
        if r2.status_code == 200:
            price = r2.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]
            return float(price)
    except Exception as e:
        print(f"[{get_iran_time()}] Yahoo Finance Fallback error: {repr(e)}")
        
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
    global last_xau_usd, last_gold_18k
    
    current_time = get_iran_time()
    print(f"ربات شروع شد | ساعت ایران: {current_time}")
    send_message(f"🤖 <b>ربات فعال شد!</b>\n⏰ {current_time}")

    while True:
        try:
            now_str = get_iran_time()

            # 1. دریافت قیمت‌های ارز و دیجیتال
            usdt_irt = fetch_nobitex_price("USDTIRT")
            btc_usdt = fetch_nobitex_price("BTCUSDT")

            # 2. دریافت انس طلا از تریدینگ‌ویو
            xau_usd = fetch_tradingview_xauusd()

            # پردازش تتر و بیت‌کوین
            if usdt_irt is not None and btc_usdt is not None:
                usdt_irt = int(usdt_irt / 10) if usdt_irt > 100000 else int(usdt_irt)
                btc_usdt = round(btc_usdt, 2)

                if last_usdt_irt is None or last_btc_usdt is None:
                    last_usdt_irt = usdt_irt
                    last_btc_usdt = btc_usdt
                elif (usdt_irt != last_usdt_irt) or (btc_usdt != last_btc_usdt):
                    usdt_arrow = get_arrow(usdt_irt, last_usdt_irt)
                    btc_arrow = get_arrow(btc_usdt, last_btc_usdt)

                    crypto_msg = (
                        f"⏰ <b>{now_str}</b>\n"
                        f"💵 <b>تتر:</b> {usdt_irt:,} تومان {usdt_arrow}\n"
                        f"🪙 <b>بیت‌کوین:</b> ${btc_usdt:,.2f} {btc_arrow}"
                    )
                    print(f"[{now_str}] قیمت ارز/بیت‌کوین تغییر کرد! ارسال به کانال...")
                    send_message(crypto_msg)

                    last_usdt_irt = usdt_irt
                    last_btc_usdt = btc_usdt

            # پردازش انس جهانی و محاسبه ۱۸ عیار
            if xau_usd is not None and usdt_irt is not None:
                xau_usd = round(xau_usd, 2)
                
                # فرمول: (قیمت انس جهانی * قیمت دلار/تتر) / 31.1034768 * (18 / 24)
                gold_18k_calculated = int(((xau_usd * usdt_irt) / 31.1034768) * (18.0 / 24.0))

                if last_xau_usd is None or last_gold_18k is None:
                    last_xau_usd = xau_usd
                    last_gold_18k = gold_18k_calculated
                elif (xau_usd != last_xau_usd) or (gold_18k_calculated != last_gold_18k):
                    xau_arrow = get_arrow(xau_usd, last_xau_usd)
                    gold_18k_arrow = get_arrow(gold_18k_calculated, last_gold_18k)

                    gold_msg = (
                        f"⏰ <b>{now_str}</b>\n"
                        f"🥇 <b>انس جهانی:</b> ${xau_usd:,.2f} {xau_arrow}\n"
                        f"🔱 <b>طلای ۱۸ عیار:</b> {gold_18k_calculated:,} تومان {gold_18k_arrow}"
                    )
                    print(f"[{now_str}] قیمت انس طلا/۱۸عیار تغییر کرد! ارسال به کانال...")
                    send_message(gold_msg)

                    last_xau_usd = xau_usd
                    last_gold_18k = gold_18k_calculated

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
