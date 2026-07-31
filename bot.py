import os
import requests
import time
import threading
import json
import urllib.parse
import jdatetime
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

# ذخیره تاریخچه قیمت‌ها برای رسم چارت
btc_history = []
gold_history = []
time_history = []

last_usdt_bid = None
last_usdt_ask = None
last_btc_usdt = None

last_xau_usd = None
last_gold_18k_nobitex = None
last_gold_18k_global = None

def get_iran_datetime():
    """دریافت datetime دقیق ایران (UTC + 3:30)"""
    iran_offset = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(iran_offset)

def get_iran_time():
    """دریافت زمان دقیق ایران (UTC + 3:30)"""
    return get_iran_datetime().strftime("%H:%M:%S")

def fetch_nobitex_orderbook(symbol):
    """دریافت قیمت از نوبیتکس با هدرهای استاندارد"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        url = f"https://apiv2.nobitex.ir/v3/orderbook/{symbol}"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            best_bid = float(bids[0][0]) if isinstance(bids, list) and bids else None
            best_ask = float(asks[0][0]) if isinstance(asks, list) and asks else None
            last_trade = float(data.get("lastTradePrice", 0)) if data.get("lastTradePrice") else None
            return best_bid, best_ask, last_trade
    except Exception as e:
        print(f"[{get_iran_time()}] Nobitex error ({symbol}): {repr(e)}")
    return None, None, None

def fetch_btc_coingecko():
    """منبع جایگزین برای قیمت بیت‌کوین در صورت قطع نوبیتکس"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()["bitcoin"]["usd"])
    except Exception as e:
        print(f"[{get_iran_time()}] CoinGecko error: {repr(e)}")
    return None

def fetch_tradingview_gold():
    """دریافت قیمت انس جهانی طلا ($) از TradingView"""
    url = "https://scanner.tradingview.com/global/scan"
    payload = {
        "symbols": {"tickers": ["TVC:GOLD"]},
        "columns": ["close"]
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/"
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("data"):
                return float(data["data"][0]["d"][0])
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
        print(f"[{get_iran_time()}] ارسال پیام متنی - کد وضعیت: {res.status_code}")
    except Exception as e:
        print(f"[{get_iran_time()}] خطا در ارسال پیام به تلگرام: {repr(e)}")

def send_photo_url(photo_url, caption):
    """ارسال مستقیم عکس چارت به تلگرام"""
    if not TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        data = {'chat_id': CHAT_ID, 'photo': photo_url, 'caption': caption, 'parse_mode': 'HTML'}
        res = requests.post(url, data=data, timeout=15)
        print(f"[{get_iran_time()}] ارسال عکس - کد وضعیت: {res.status_code}")
    except Exception as e:
        print(f"[{get_iran_time()}] خطا در ارسال عکس به تلگرام: {repr(e)}")

def get_quickchart_url(labels, data, title, color="rgb(247, 147, 26)"):
    """تولید چارت تصویری سریع و استاندارد"""
    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": title,
                "data": data,
                "borderColor": color,
                "backgroundColor": color.replace("rgb", "rgba").replace(")", ", 0.1)"),
                "fill": True,
                "borderWidth": 3,
                "pointRadius": 4
            }]
        },
        "options": {
            "title": {"display": True, "text": title, "fontColor": "#fff", "fontSize": 16},
            "legend": {"display": False},
            "scales": {
                "xAxes": [{"ticks": {"fontColor": "#ccc"}}],
                "yAxes": [{"ticks": {"fontColor": "#ccc"}}]
            }
        }
    }
    json_str = json.dumps(chart_config)
    encoded = urllib.parse.quote(json_str)
    return f"https://quickchart.io/chart?bkg=%23131722&w=800&h=400&c={encoded}"

# ---- 3. ارسال چارت‌ها بر اساس زمان‌بندی دقیق ----
def publish_specific_chart(timeframe_label):
    """تابع کمکی برای ارسال جفت چارت (بیت‌کوین و طلا) با عنوان دلخواه"""
    now_str = get_iran_time()
    times = time_history if len(time_history) > 1 else [now_str[:5], now_str[:5]]
    
    # ۱. چارت بیت‌کوین
    btc_prices = btc_history if len(btc_history) > 1 else ([last_btc_usdt, last_btc_usdt] if last_btc_usdt else [65000, 65000])
    btc_chart_url = get_quickchart_url(times, btc_prices, f"Bitcoin (BTC/USDT) - {timeframe_label}", "rgb(247, 147, 26)")
    send_photo_url(btc_chart_url, f"📊 <b>چارت {timeframe_label} بیت‌کوین (BTC/USDT)</b>\n⏰ <b>{now_str}</b>")
    
    time.sleep(3)

    # ۲. چارت طلا
    gold_prices = gold_history if len(gold_history) > 1 else ([last_xau_usd, last_xau_usd] if last_xau_usd else [2300, 2300])
    gold_chart_url = get_quickchart_url(times, gold_prices, f"Gold (XAU/USD) - {timeframe_label}", "rgb(255, 215, 0)")
    send_photo_url(gold_chart_url, f"📊 <b>چارت {timeframe_label} انس جهانی طلا (XAU/USD)</b>\n⏰ <b>{now_str}</b>")

def hourly_chart_loop():
    """حلقه مدیریت زمان‌بندی چارت‌ها (راس ساعت ۲۱:۰۰ هر روز)"""
    time.sleep(15)
    
    while True:
        try:
            now = get_iran_datetime()
            # محاسبه زمان باقی‌مانده تا ساعت ۲۱:۰۰ بعدی یا سر ساعت بعدی برای بررسی
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            wait_seconds = (next_hour - now).total_seconds()
            time.sleep(wait_seconds)

            now = get_iran_datetime()
            j_now = jdatetime.datetime.fromgregorian(datetime=now)

            # بررسی اینکه آیا ساعت الان ۲۱:۰۰ است؟
            if now.hour == 21:
                # ۱. همیشه در ساعت ۲۱ چارت روزانه (۲۴ ساعته) ارسال می‌شود
                publish_specific_chart("۲۴ ساعته (روزانه)")
                time.sleep(3)

                # ۲. اگر روز جمعه باشد (Weekday 4)، چارت هفتگی هم ارسال شود
                if now.weekday() == 4:
                    publish_specific_chart("هفتگی")
                    time.sleep(3)

                # ۳. اگر روز اول ماه شمسی باشد، چارت ماهانه ارسال شود
                if j_now.day == 1:
                    publish_specific_chart("ماهانه شمسی")
                    time.sleep(3)

                # ۴. اگر اول فصل شمسی باشد (فروردین، تیر، مهر، دی)، چارت فصلی/سالانه ارسال شود
                if j_now.day == 1 and j_now.month in [1, 4, 7, 10]:
                    publish_specific_chart("فصلی / سالانه")

                print(f"[{get_iran_time()}] چارت‌های ساعت ۲۱:۰۰ با موفقیت پردازش و ارسال شدند.")

        except Exception as e:
            print(f"[{get_iran_time()}] خطا در حلقه زمان‌بندی چارت‌ها: {repr(e)}")
            time.sleep(60)

# ---- 4. حلقه اصلی قیمت‌های لحظه‌ای ----
def bot_loop():
    global last_usdt_bid, last_usdt_ask, last_btc_usdt
    global last_xau_usd, last_gold_18k_nobitex, last_gold_18k_global
    
    current_time = get_iran_time()
    print(f"ربات شروع شد | ساعت ایران: {current_time}")
    send_message(f"🤖 <b>ربات فعال شد!</b>\n⏰ {current_time}")

    while True:
        try:
            now_str = get_iran_time()
            
            xau_usd = fetch_tradingview_gold()
            xaut_bid, xaut_ask, xaut_last = fetch_nobitex_orderbook("XAUTIRT")
            usdt_bid, usdt_ask, usdt_last = fetch_nobitex_orderbook("USDTIRT")
            _, _, btc_last = fetch_nobitex_orderbook("BTCUSDT")

            if btc_last is None:
                btc_last = fetch_btc_coingecko()

            usdt_mid = (usdt_bid + usdt_ask) / 2 if (usdt_bid and usdt_ask) else usdt_last
            xaut_mid = (xaut_bid + xaut_ask) / 2 if (xaut_bid and xaut_ask) else xaut_last

            # --- بخش طلا ---
            if xau_usd is not None or xaut_mid is not None:
                xau_usd_val = round(xau_usd, 2) if xau_usd else 0.0
                xaut_irt_val = int(xaut_mid / 10) if (xaut_mid and xaut_mid > 1000000) else int(xaut_mid or 0)
                usdt_toman = int(usdt_mid / 10) if (usdt_mid and usdt_mid > 100000) else int(usdt_mid or 60000)

                gold_18k_nobitex = int((xaut_irt_val / 31.1034768) * (18.0 / 24.0)) if xaut_irt_val else 0
                gold_18k_global = int(((xau_usd_val * usdt_toman) / 31.1034768) * (18.0 / 24.0)) if (xau_usd_val and usdt_toman) else 0

                if xau_usd_val > 0 and (len(gold_history) == 0 or gold_history[-1] != xau_usd_val):
                    gold_history.append(xau_usd_val)
                    if len(gold_history) > 30: gold_history.pop(0)

                if last_xau_usd is None or (xau_usd_val != last_xau_usd) or (gold_18k_nobitex != last_gold_18k_nobitex):
                    gold_msg = (
                        f"⏰ <b>{now_str}</b>\n"
                        f"🥇 <b>انس طلا:</b> ${xau_usd_val:,.2f} {get_arrow(xau_usd_val, last_xau_usd)}\n"
                        f"🔱 <b>طلا ۱۸عیار (نوبیتکس):</b> {gold_18k_nobitex:,} تومان {get_arrow(gold_18k_nobitex, last_gold_18k_nobitex)}\n"
                        f"🌐 <b>طلا ۱۸عیار (انس جهانی):</b> {gold_18k_global:,} تومان {get_arrow(gold_18k_global, last_gold_18k_global)}"
                    )
                    send_message(gold_msg)

                    last_xau_usd = xau_usd_val
                    last_gold_18k_nobitex = gold_18k_nobitex
                    last_gold_18k_global = gold_18k_global

            time.sleep(2)

            # --- بخش تتر و کریپتو ---
            if usdt_bid is not None or btc_last is not None:
                usdt_bid_val = int(usdt_bid / 10) if (usdt_bid and usdt_bid > 100000) else int(usdt_bid or 0)
                usdt_ask_val = int(usdt_ask / 10) if (usdt_ask and usdt_ask > 100000) else int(usdt_ask or 0)
                btc_usdt_val = round(btc_last, 2) if btc_last else 0.0

                if btc_usdt_val > 0 and (len(btc_history) == 0 or btc_history[-1] != btc_usdt_val):
                    btc_history.append(btc_usdt_val)
                    time_history.append(now_str[:5])
                    if len(btc_history) > 30: 
                        btc_history.pop(0)
                        time_history.pop(0)

                if last_usdt_bid is None or (usdt_bid_val != last_usdt_bid) or (btc_usdt_val != last_btc_usdt):
                    crypto_msg = (
                        f"⏰ <b>{now_str}</b>\n"
                        f"💵 <b>تتر (خرید):</b> {usdt_bid_val:,} تومان {get_arrow(usdt_bid_val, last_usdt_bid)}\n"
                        f"💵 <b>تتر (فروش):</b> {usdt_ask_val:,} تومان {get_arrow(usdt_ask_val, last_usdt_ask)}\n"
                        f"🪙 <b>بیت‌کوین:</b> ${btc_usdt_val:,.2f} {get_arrow(btc_usdt_val, last_btc_usdt)}"
                    )
                    send_message(crypto_msg)

                    last_usdt_bid = usdt_bid_val
                    last_usdt_ask = usdt_ask_val
                    last_btc_usdt = btc_usdt_val

            time.sleep(10)

        except Exception as e:
            print(f"[{get_iran_time()}] خطا در حلقه اصلی: {repr(e)}")
            time.sleep(10)

# ---- 5. اجرا ----
if __name__ == "__main__":
    t_flask = threading.Thread(target=run_flask)
    t_flask.daemon = True
    t_flask.start()

    t_chart = threading.Thread(target=hourly_chart_loop)
    t_chart.daemon = True
    t_chart.start()

    bot_loop()
