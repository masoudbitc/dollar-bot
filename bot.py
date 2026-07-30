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
last_usdt_bid = None
last_usdt_ask = None
last_btc_usdt = None

last_xau_usd = None
last_gold_18k_nobitex = None
last_gold_18k_global = None

def get_iran_time():
    """دریافت زمان دقیق ایران (UTC + 3:30)"""
    iran_offset = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(iran_offset).strftime("%H:%M:%S")

def fetch_nobitex_orderbook(symbol):
    """دریافت بهترین قیمت خرید (Bid) و بهترین قیمت فروش (Ask) از نوبیتکس"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        url = f"https://apiv2.nobitex.ir/v3/orderbook/{symbol}"
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            
            best_bid = float(bids[0][0]) if isinstance(bids, list) and bids else None
            best_ask = float(asks[0][0]) if isinstance(asks, list) and asks else None
            last_trade = float(data.get("lastTradePrice", 0)) if data.get("lastTradePrice") else None
            
            return best_bid, best_ask, last_trade
    except Exception as e:
        print(f"[{get_iran_time()}] Nobitex error for {symbol}: {repr(e)}")
    return None, None, None

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
        return "➖"
    elif new_val > old_val:
        return "🔺"
    else:
        return "🔻"

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

def send_photo(photo_url, caption):
    """ارسال تصویر همراه با توضیحات به تلگرام"""
    if not TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        payload = {
            "chat_id": CHAT_ID,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
        res = requests.post(url, data=payload, timeout=15)
        if res.status_code != 200:
            print(f"[{get_iran_time()}] خطا در ارسال عکس به تلگرام: {res.status_code} - {res.text[:100]}")
    except Exception as e:
        print(f"[{get_iran_time()}] استثنا در ارسال عکس: {repr(e)}")

# ---- 3. پردازش ارسال چارت‌های ۱ ساعته ----
def hourly_chart_loop():
    """ارسال چارت بیت‌کوین، انس و تتر؛ بلافاصله در استارت و سپس هر ۱ ساعت"""
    time.sleep(10) # ۱۰ ثانیه صبر پس از روشن شدن ربات برای اولین تست
    
    while True:
        try:
            now_str = get_iran_time()
            
            # لینک‌های تصویر چارت ۱ ساعته (Interval: 60)
            btc_chart_url = "https://charts2.tradingview.com/chart-image/?symbol=BINANCE:BTCUSDT&interval=60&theme=light"
            gold_chart_url = "https://charts2.tradingview.com/chart-image/?symbol=TVC:GOLD&interval=60&theme=light"
            usdt_chart_url = "https://charts2.tradingview.com/chart-image/?symbol=CRYPTO:USDTIRR&interval=60&theme=light"
            
            # ۱. ارسال چارت بیت‌کوین
            btc_caption = f"📊 <b>چارت ۱ ساعته بیت‌کوین (BTC/USDT)</b>\n⏰ <b>{now_str}</b>\n🌐 <i>TradingView</i>"
            send_photo(btc_chart_url, btc_caption)
            time.sleep(3)
            
            # ۲. ارسال چارت انس جهانی طلا
            gold_caption = f"📊 <b>چارت ۱ ساعته انس جهانی طلا (XAU/USD)</b>\n⏰ <b>{now_str}</b>\n🌐 <i>TradingView</i>"
            send_photo(gold_chart_url, gold_caption)
            time.sleep(3)

            # ۳. ارسال چارت تتر به ریال/تومان
            usdt_caption = f"📊 <b>چارت ۱ ساعته تتر (USDT/IRR)</b>\n⏰ <b>{now_str}</b>\n🌐 <i>TradingView</i>"
            send_photo(usdt_chart_url, usdt_caption)
            
            print(f"[{now_str}] چارت‌های تصویری با موفقیت در کانال منتشر شدند.")
            
        except Exception as e:
            print(f"خطا در ارسال چارت تصویری: {repr(e)}")
            
        # ۳۶۰۰ ثانیه استراحت (معادل ۱ ساعت) تا نوبت بعدی
        time.sleep(3600)

# ---- 4. حلقه اصلی قیمت‌های لحظه‌ای ----
def bot_loop():
    global last_usdt_bid, last_usdt_ask, last_btc_usdt
    global last_xau_usd, last_gold_18k_nobitex, last_gold_18k_global
    
    current_time = get_iran_time()
    print(f"ربات شروع شد | ساعت ایران: {current_time}")
    send_message(f"🤖 <b>ربات فعال شد!</b>\n⏰ {current_time}")

    while True:
        try:
            # -------------------------------------------------------------
            # گام ۱: (ثانیه ۰) بررسی و ارسال پیام انس و طلا
            # -------------------------------------------------------------
            xau_usd = fetch_tradingview_gold()
            xaut_bid, xaut_ask, xaut_last = fetch_nobitex_orderbook("XAUTIRT")
            usdt_bid, usdt_ask, usdt_last = fetch_nobitex_orderbook("USDTIRT")

            # میانگین تتر و تترگلد برای محاسبات طلا
            usdt_mid = (usdt_bid + usdt_ask) / 2 if (usdt_bid and usdt_ask) else usdt_last
            xaut_mid = (xaut_bid + xaut_ask) / 2 if (xaut_bid and xaut_ask) else xaut_last

            if xau_usd is not None and xaut_mid is not None and usdt_mid is not None:
                now_str_gold = get_iran_time()
                xau_usd_val = round(xau_usd, 2)
                xaut_irt_val = int(xaut_mid / 10) if xaut_mid > 1000000 else int(xaut_mid)
                usdt_toman = int(usdt_mid / 10) if usdt_mid > 100000 else int(usdt_mid)

                # محاسبات ۱۸ عیار
                gold_18k_nobitex = int((xaut_irt_val / 31.1034768) * (18.0 / 24.0))
                gold_18k_global = int(((xau_usd_val * usdt_toman) / 31.1034768) * (18.0 / 24.0))

                if last_xau_usd is None or last_gold_18k_nobitex is None or last_gold_18k_global is None:
                    last_xau_usd = xau_usd_val
                    last_gold_18k_nobitex = gold_18k_nobitex
                    last_gold_18k_global = gold_18k_global
                elif (xau_usd_val != last_xau_usd) or \
                     (gold_18k_nobitex != last_gold_18k_nobitex) or \
                     (gold_18k_global != last_gold_18k_global):

                    xau_arrow = get_arrow(xau_usd_val, last_xau_usd)
                    gold_nobitex_arrow = get_arrow(gold_18k_nobitex, last_gold_18k_nobitex)
                    gold_global_arrow = get_arrow(gold_18k_global, last_gold_18k_global)

                    gold_msg = (
                        f"⏰ <b>{now_str_gold}</b>\n"
                        f"🥇 <b>انس:</b> ${xau_usd_val:,.2f} {xau_arrow}\n"
                        f"🔱 <b>طلا/تومان ۱۸عیار:</b> {gold_18k_nobitex:,} تومان {gold_nobitex_arrow}\n"
                        f"🌐 <b>طلا/تتر ۱۸عیار:</b> {gold_18k_global:,} تومان {gold_global_arrow}"
                    )
                    send_message(gold_msg)

                    last_xau_usd = xau_usd_val
                    last_gold_18k_nobitex = gold_18k_nobitex
                    last_gold_18k_global = gold_18k_global

            # -------------------------------------------------------------
            # توقف به مدت ۵ ثانیه
            # -------------------------------------------------------------
            time.sleep(5)

            # -------------------------------------------------------------
            # گام ۲: (ثانیه ۵) بررسی و ارسال پیام تتر (خرید و فروش) و بیت‌کوین
            # -------------------------------------------------------------
            _, _, btc_last = fetch_nobitex_orderbook("BTCUSDT")

            if usdt_bid is not None and usdt_ask is not None and btc_last is not None:
                now_str_crypto = get_iran_time()
                
                # تبدیل به تومان
                usdt_bid_val = int(usdt_bid / 10) if usdt_bid > 100000 else int(usdt_bid)
                usdt_ask_val = int(usdt_ask / 10) if usdt_ask > 100000 else int(usdt_ask)
                btc_usdt_val = round(btc_last, 2)

                if last_usdt_bid is None or last_usdt_ask is None or last_btc_usdt is None:
                    last_usdt_bid = usdt_bid_val
                    last_usdt_ask = usdt_ask_val
                    last_btc_usdt = btc_usdt_val
                elif (usdt_bid_val != last_usdt_bid) or (usdt_ask_val != last_usdt_ask) or (btc_usdt_val != last_btc_usdt):
                    usdt_bid_arrow = get_arrow(usdt_bid_val, last_usdt_bid)
                    usdt_ask_arrow = get_arrow(usdt_ask_val, last_usdt_ask)
                    btc_arrow = get_arrow(btc_usdt_val, last_btc_usdt)

                    crypto_msg = (
                        f"⏰ <b>{now_str_crypto}</b>\n"
                        f"💵 <b>تتر (خرید):</b> {usdt_bid_val:,} تومان {usdt_bid_arrow}\n"
                        f"💵 <b>تتر (فروش):</b> {usdt_ask_val:,} تومان {usdt_ask_arrow}\n"
                        f"🪙 <b>بیت‌کوین:</b> ${btc_usdt_val:,.2f} {btc_arrow}"
                    )
                    send_message(crypto_msg)
                    last_usdt_bid = usdt_bid_val
                    last_usdt_ask = usdt_ask_val
                    last_btc_usdt = btc_usdt_val

            print(f"[{get_iran_time()}] چرخه ۱۰ ثانیه‌ای کامل شد.")

            # -------------------------------------------------------------
            # ۵ ثانیه استراحت دوم جهت تکمیل کل زمان ۱۰ ثانیه‌ای چرخه
            # -------------------------------------------------------------
            time.sleep(5)

        except Exception as e:
            print(f"خطای غیرمنتظره در حلقه اصلی: {repr(e)}")
            time.sleep(5)

# ---- 5. اجرا ----
if __name__ == "__main__":
    # ۱. اجرای وب‌سرور Flask
    t_flask = threading.Thread(target=run_flask)
    t_flask.daemon = True
    t_flask.start()

    # ۲. اجرای پردازش ساعتی ارسال چارت‌ها در پس‌زمینه
    t_chart = threading.Thread(target=hourly_chart_loop)
    t_chart.daemon = True
    t_chart.start()

    # ۳. اجرای حلقه اصلی ارسال قیمت‌ها
    bot_loop()
