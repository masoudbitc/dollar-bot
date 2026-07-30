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

# ذخیره آخرین قیمت‌ها برای تشخیص تغییرات
last_usdt_irt = None
last_btc_usdt = None

last_xau_usd = None
last_xaut_irt = None
last_gold_18k_nobitex = None
last_gold_18k_global = None

last_diff_val = None

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
            if best_bid and best_ask:
                return (best_bid + best_ask) / 2
            return best_bid or best_ask
    except Exception as e:
        print(f"[{get_iran_time()}] Nobitex error for {symbol}: {repr(e)}")
    return None

def fetch_tradingview_gold():
    """دریافت قیمت انس جهانی طلا ($) از TradingView"""
    url = "https://scanner.tradingview.com/global/scan"
    payload = {
        "symbols": {"tickers": ["TVC:GOLD"]},
        "columns": ["close"]
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/"
    }
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("data"):
                price = data["data"][0]["d"][0]
                return float(price)
    except Exception as e:
        print(f"[{get_iran_time()}] TradingView TVC:GOLD error: {repr(e)}")
        
    return None

def get_arrow(new_val, old_val):
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
    except Exception as e:
        print(f"[{get_iran_time()}] استثنا در ارسال به تلگرام: {repr(e)}")

def bot_loop():
    global last_usdt_irt, last_btc_usdt
    global last_xau_usd, last_xaut_irt, last_gold_18k_nobitex, last_gold_18k_global
    global last_diff_val
    
    current_time = get_iran_time()
    print(f"ربات شروع شد | ساعت ایران: {current_time}")
    send_message(f"🤖 <b>ربات فعال شد!</b>\n⏰ {current_time}")

    while True:
        try:
            now_str = get_iran_time()

            # 1. دریافت قیمت تتر و بیت‌کوین از نوبیتکس
            usdt_irt = fetch_nobitex_price("USDTIRT")
            btc_usdt = fetch_nobitex_price("BTCUSDT")

            # 2. دریافت انس جهانی (تریدینگ‌ویو) و انس تومانی (تترگلد نوبیتکس)
            xau_usd = fetch_tradingview_gold()
            xaut_irt = fetch_nobitex_price("XAUTIRT")

            # --- پیام اول: بازار ارز و دیجیتال ---
            if usdt_irt is not None and btc_usdt is not None:
                usdt_irt_val = int(usdt_irt / 10) if usdt_irt > 100000 else int(usdt_irt)
                btc_usdt_val = round(btc_usdt, 2)

                if last_usdt_irt is None or last_btc_usdt is None:
                    last_usdt_irt = usdt_irt_val
                    last_btc_usdt = btc_usdt_val
                elif (usdt_irt_val != last_usdt_irt) or (btc_usdt_val != last_btc_usdt):
                    usdt_arrow = get_arrow(usdt_irt_val, last_usdt_irt)
                    btc_arrow = get_arrow(btc_usdt_val, last_btc_usdt)

                    crypto_msg = (
                        f"⏰ <b>{now_str}</b>\n"
                        f"💵 <b>تتر:</b> {usdt_irt_val:,} تومان {usdt_arrow}\n"
                        f"🪙 <b>بیت‌کوین:</b> ${btc_usdt_val:,.2f} {btc_arrow}"
                    )
                    send_message(crypto_msg)
                    last_usdt_irt = usdt_irt_val
                    last_btc_usdt = btc_usdt_val

            # --- پیام دوم: بازار طلا (۴ قیمت اصلی) ---
            if xau_usd is not None and xaut_irt is not None and usdt_irt is not None:
                xau_usd_val = round(xau_usd, 2)
                xaut_irt_val = int(xaut_irt / 10) if xaut_irt > 1000000 else int(xaut_irt)
                usdt_toman = int(usdt_irt / 10) if usdt_irt > 100000 else int(usdt_irt)

                # محاسبات ۱۸ عیار
                gold_18k_nobitex = int((xaut_irt_val / 31.1034768) * (18.0 / 24.0))
                gold_18k_global = int(((xau_usd_val * usdt_toman) / 31.1034768) * (18.0 / 24.0))

                if last_xau_usd is None or last_xaut_irt is None:
                    last_xau_usd = xau_usd_val
                    last_xaut_irt = xaut_irt_val
                    last_gold_18k_nobitex = gold_18k_nobitex
                    last_gold_18k_global = gold_18k_global
                elif (xau_usd_val != last_xau_usd) or (xaut_irt_val != last_xaut_irt) or \
                     (gold_18k_nobitex != last_gold_18k_nobitex) or (gold_18k_global != last_gold_18k_global):

                    xau_arrow = get_arrow(xau_usd_val, last_xau_usd)
                    xaut_arrow = get_arrow(xaut_irt_val, last_xaut_irt)
                    gold_nobitex_arrow = get_arrow(gold_18k_nobitex, last_gold_18k_nobitex)
                    gold_global_arrow = get_arrow(gold_18k_global, last_gold_18k_global)

                    gold_msg = (
                        f"⏰ <b>{now_str}</b>\n"
                        f"🥇 <b>انس جهانی (تریدینگ‌ویو):</b> ${xau_usd_val:,.2f} {xau_arrow}\n"
                        f"💵 <b>انس تومانی (تترگلد نوبیتکس):</b> {xaut_irt_val:,} تومان {xaut_arrow}\n"
                        f"🔱 <b>طلای ۱۸ عیار (بر اساس تترگلد):</b> {gold_18k_nobitex:,} تومان {gold_nobitex_arrow}\n"
                        f"🌐 <b>طلای ۱۸ عیار (بر اساس انس جهانی + تتر):</b> {gold_18k_global:,} تومان {gold_global_arrow}"
                    )
                    send_message(gold_msg)

                    last_xau_usd = xau_usd_val
                    last_xaut_irt = xaut_irt_val
                    last_gold_18k_nobitex = gold_18k_nobitex
                    last_gold_18k_global = gold_18k_global

                # --- پیام سوم: محاسبه اختلاف/حباب انس در پیام جداگانه ---
                calculated_ounce_irt = int(xau_usd_val * usdt_toman)
                diff_val = xaut_irt_val - calculated_ounce_irt

                if last_diff_val is None:
                    last_diff_val = diff_val
                elif diff_val != last_diff_val:
                    diff_arrow = get_arrow(diff_val, last_diff_val)
                    
                    if diff_val == 0:
                        diff_str = "0"
                    elif diff_val > 0:
                        diff_str = f"+{diff_val:,}"
                    else:
                        diff_str = f"-{abs(diff_val):,}"

                    diff_msg = (
                        f"⏰ <b>{now_str}</b>\n"
                        f"📊 <b>اختلاف انس تومانی نوبیتکس با انس دلاری:</b> {diff_str} تومان {diff_arrow}"
                    )
                    send_message(diff_msg)
                    last_diff_val = diff_val

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
