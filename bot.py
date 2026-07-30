import os
import requests
import time
import threading
import json
import urllib.parse
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

# ذخیره تاریخچه داده‌های OHLC برای نمودار کندلی (حداکثر ۱۲ کندل ساعتی)
# ساختار هر کندل: [Open, High, Low, Close]
btc_ohlc_history = []
gold_ohlc_history = []
time_history = []

# متغیرهای موقت برای محاسبه کندل فعلی
current_btc_prices = []
current_gold_prices = []

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
    """دریافت قیمت از نوبیتکس"""
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
    """منبع جایگزین برای قیمت بیت‌کوین"""
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

def get_candlestick_chart_url(labels, ohlc_data, title):
    """تولید نمودار کندلی (Candlestick) حرفه‌ای با QuickChart"""
    # ساختار ohlc_data باید فهرستی از لیست‌های [o, h, l, c] باشد
    formatted_data = []
    for d in ohlc_data:
        formatted_data.append({"o": d[0], "h": d[1], "l": d[2], "c": d[3]})

    chart_config = {
        "type": "candlestick",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": title,
                "data": formatted_data,
                "color": {
                    "up": "#26a69a",       # کندل صعودی (سبز)
                    "down": "#ef5350",     # کندل نزولی (قرمز)
                    "unchanged": "#888888"
                }
            }]
        },
        "options": {
            "title": {"display": True, "text": title, "fontColor": "#ffffff", "fontSize": 18},
            "legend": {"display": False},
            "scales": {
                "xAxes": [{"ticks": {"fontColor": "#cccccc"}}],
                "yAxes": [{"ticks": {"fontColor": "#cccccc"}}]
            }
        }
    }
    json_str = json.dumps(chart_config)
    encoded = urllib.parse.quote(json_str)
    return f"https://quickchart.io/chart?bkg=%23131722&w=800&h=420&c={encoded}"

# ---- 3. ارسال ساعتی چارت‌های تصویری کندلی (هر ۶۰ دقیقه) ----
def hourly_chart_loop():
    """انتظار تا انتهای ساعت متداول و سپس ارسال چارت کندلی در انتهای هر ساعت"""
    time.sleep(30)  # انتظار اولیه جهت شروع مطمئن
    
    while True:
        try:
            now = datetime.now()
            # محاسبه زمان باقی‌مانده تا سر ساعت بعدی
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            wait_seconds = (next_hour - now).total_seconds()
            
            print(f"[{get_iran_time()}] چارت ساعتی بعدی در {int(wait_seconds)} ثانیه دیگر ارسال می‌شود.")
            time.sleep(wait_seconds)

            now_str = get_iran_time()
            hour_label = now_str[:5]

            # محاسبه کندل ساعتی بیت‌کوین (Open, High, Low, Close)
            if current_btc_prices:
                o_btc = current_btc_prices[0]
                h_btc = max(current_btc_prices)
                l_btc = min(current_btc_prices)
                c_btc = current_btc_prices[-1]
                btc_ohlc_history.append([o_btc, h_btc, l_btc, c_btc])
                current_btc_prices.clear()
            else:
                p = last_btc_usdt or 65000.0
                btc_ohlc_history.append([p, p, p, p])

            # محاسبه کندل ساعتی طلا
            if current_gold_prices:
                o_gold = current_gold_prices[0]
                h_gold = max(current_gold_prices)
                l_gold = min(current_gold_prices)
                c_gold = current_gold_prices[-1]
                gold_ohlc_history.append([o_gold, h_gold, l_gold, c_gold])
                current_gold_prices.clear()
            else:
                p = last_xau_usd or 2300.0
                gold_ohlc_history.append([p, p, p, p])

            time_history.append(hour_label)

            # مدیریت طول تاریخچه کندل‌ها (حداکثر ۱۲ کندل اخیر)
            if len(btc_ohlc_history) > 12: btc_ohlc_history.pop(0)
            if len(gold_ohlc_history) > 12: gold_ohlc_history.pop(0)
            if len(time_history) > 12: time_history.pop(0)

            # ۱. ارسال چارت کندلی بیت‌کوین
            btc_chart_url = get_candlestick_chart_url(time_history, btc_ohlc_history, "Bitcoin (BTC/USDT) Hourly Candlestick")
            send_photo_url(btc_chart_url, f"📊 <b>نمودار کندلی بیت‌کوین (ساعتی)</b>\n⏰ <b>{now_str}</b>")

            time.sleep(3)

            # ۲. ارسال چارت کندلی انس طلا
            gold_chart_url = get_candlestick_chart_url(time_history, gold_ohlc_history, "Gold (XAU/USD) Hourly Candlestick")
            send_photo_url(gold_chart_url, f"📊 <b>نمودار کندلی انس طلا (ساعتی)</b>\n⏰ <b>{now_str}</b>")

            print(f"[{now_str}] نمودارهای کندلی ساعتی ارسال شدند.")

        except Exception as e:
            print(f"خطا در ارسال نمودارهای ساعتی: {repr(e)}")
            time.sleep(60)

# ---- 4. حلقه اصلی دریافت قیمت‌ها (چک کردن تغییرات هر ۱۰ ثانیه) ----
def bot_loop():
    global last_usdt_bid, last_usdt_ask, last_btc_usdt
    global last_xau_usd, last_gold_18k_nobitex, last_gold_18k_global
    
    current_time = get_iran_time()
    print(f"ربات شروع به کار کرد | ساعت ایران: {current_time}")

    while True:
        try:
            now_str = get_iran_time()
            
            # 1. دریافت داده‌ها
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

                if xau_usd_val > 0:
                    current_gold_prices.append(xau_usd_val)

                if last_xau_usd is None or (xau_usd_val != last_xau_usd) or (gold_18k_nobitex != last_gold_18k_nobitex):
                    xau_arrow = get_arrow(xau_usd_val, last_xau_usd)
                    gold_nobitex_arrow = get_arrow(gold_18k_nobitex, last_gold_18k_nobitex)
                    gold_global_arrow = get_arrow(gold_18k_global, last_gold_18k_global)

                    gold_msg = (
                        f"⏰ <b>{now_str}</b>\n"
                        f"🥇 <b>انس طلا:</b> ${xau_usd_val:,.2f} {xau_arrow}\n"
                        f"🔱 <b>طلا ۱۸عیار (نوبیتکس):</b> {gold_18k_nobitex:,} تومان {gold_nobitex_arrow}\n"
                        f"🌐 <b>طلا ۱۸عیار (انس جهانی):</b> {gold_18k_global:,} تومان {gold_global_arrow}"
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

                if btc_usdt_val > 0:
                    current_btc_prices.append(btc_usdt_val)

                if last_usdt_bid is None or (usdt_bid_val != last_usdt_bid) or (btc_usdt_val != last_btc_usdt):
                    usdt_bid_arrow = get_arrow(usdt_bid_val, last_usdt_bid)
                    usdt_ask_arrow = get_arrow(usdt_ask_val, last_usdt_ask)
                    btc_arrow = get_arrow(btc_usdt_val, last_btc_usdt)

                    crypto_msg = (
                        f"⏰ <b>{now_str}</b>\n"
                        f"💵 <b>تتر (خرید):</b> {usdt_bid_val:,} تومان {usdt_bid_arrow}\n"
                        f"💵 <b>تتر (فروش):</b> {usdt_ask_val:,} تومان {usdt_ask_arrow}\n"
                        f"🪙 <b>بیت‌کوین:</b> ${btc_usdt_val:,.2f} {btc_arrow}"
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
