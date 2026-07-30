import os
import requests
import time
import threading
import json
import urllib.parse
import jdatetime
from flask import Flask
from datetime import datetime, timezone, timedelta

# ---- 1. وب‌سرور برای Render ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ---- 2. تنظیمات ربات ----
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = -1003721340249

btc_ohlc_history = []
gold_ohlc_history = []
time_history = []

current_btc_prices = []
current_gold_prices = []

last_usdt_bid = None
last_usdt_ask = None
last_btc_usdt = None

last_xau_usd = None
last_gold_18k_nobitex = None
last_gold_18k_global = None

def get_iran_datetime():
    iran_offset = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(iran_offset)

def get_iran_time():
    return get_iran_datetime().strftime("%H:%M:%S")

def fetch_nobitex_orderbook(symbol):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
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
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()["bitcoin"]["usd"])
    except Exception as e:
        print(f"[{get_iran_time()}] CoinGecko error: {repr(e)}")
    return None

def fetch_tradingview_gold():
    url = "https://scanner.tradingview.com/global/scan"
    payload = {"symbols": {"tickers": ["TVC:GOLD"]}, "columns": ["close"]}
    headers = {
        "User-Agent": "Mozilla/5.0",
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
        print(f"[{get_iran_time()}] TradingView error: {repr(e)}")
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
        print("خطا: BOT_TOKEN ست نشده است!")
        return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        print(f"[{get_iran_time()}] ارسال متن: {res.status_code}")
    except Exception as e:
        print(f"[{get_iran_time()}] خطا در ارسال متن: {repr(e)}")

def send_photo_url(photo_url, caption):
    if not TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        data = {'chat_id': CHAT_ID, 'photo': photo_url, 'caption': caption, 'parse_mode': 'HTML'}
        res = requests.post(url, data=data, timeout=15)
        print(f"[{get_iran_time()}] ارسال عکس: {res.status_code}")
    except Exception as e:
        print(f"[{get_iran_time()}] خطا در ارسال عکس: {repr(e)}")

def get_candlestick_chart_url(labels, ohlc_data, title):
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
                "color": {"up": "#26a69a", "down": "#ef5350", "unchanged": "#888888"}
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

def publish_charts(timeframe_title, tf_code):
    now_str = get_iran_time()
    caption_btc = f"📊 <b>نمودار بیت‌کوین (BTC/USDT)</b>\n⏱ <b>تایم‌فریم:</b> {timeframe_title}\n⏰ <b>زمان بروزرسانی:</b> {now_str}"
    caption_gold = f"📊 <b>نمودار انس جهانی طلا (XAU/USD)</b>\n⏱ <b>تایم‌فریم:</b> {timeframe_title}\n⏰ <b>زمان بروزرسانی:</b> {now_str}"

    if btc_ohlc_history and gold_ohlc_history:
        btc_chart_url = get_candlestick_chart_url(time_history, btc_ohlc_history, f"Bitcoin (BTC/USDT) - {tf_code}")
        send_photo_url(btc_chart_url, caption_btc)
        time.sleep(2)
        gold_chart_url = get_candlestick_chart_url(time_history, gold_ohlc_history, f"Gold (XAU/USD) - {tf_code}")
        send_photo_url(gold_chart_url, caption_gold)

def hourly_chart_loop():
    time.sleep(10)
    while True:
        try:
            now = get_iran_datetime()
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            wait_seconds = (next_hour - now).total_seconds()
            time.sleep(wait_seconds)

            now = get_iran_datetime()
            hour_label = now.strftime("%H:%M")
            j_now = jdatetime.datetime.fromgregorian(datetime=now)

            if current_btc_prices:
                btc_ohlc_history.append([current_btc_prices[0], max(current_btc_prices), min(current_btc_prices), current_btc_prices[-1]])
                current_btc_prices.clear()
            else:
                p = last_btc_usdt or 65000.0
                btc_ohlc_history.append([p, p, p, p])

            if current_gold_prices:
                gold_ohlc_history.append([current_gold_prices[0], max(current_gold_prices), min(current_gold_prices), current_gold_prices[-1]])
                current_gold_prices.clear()
            else:
                p = last_xau_usd or 2300.0
                gold_ohlc_history.append([p, p, p, p])

            time_history.append(hour_label)
            if len(btc_ohlc_history) > 24: btc_ohlc_history.pop(0)
            if len(gold_ohlc_history) > 24: gold_ohlc_history.pop(0)
            if len(time_history) > 24: time_history.pop(0)

            # --- زمان‌بندی دقیق راس ساعت ۲۱:۰۰ ---
            if now.hour == 21:
                # ۱. ۲۴ ساعته روزانه
                publish_charts("۲۴ ساعته (24h)", "24-Hour Chart")
                time.sleep(3)

                # ۲. هفتگی (روزهای جمعه، اول ماه شمسی، یا اول فصل شمسی)
                is_friday = (now.weekday() == 4)
                is_first_of_jalali_month = (j_now.day == 1)
                is_first_of_jalali_season = (j_now.day == 1 and j_now.month in [1, 4, 7, 10])

                if is_friday or is_first_of_jalali_month or is_first_of_jalali_season:
                    publish_charts("هفتگی (Weekly)", "Weekly Chart")
                    time.sleep(3)

                # ۳. ماهانه (اول هر ماه شمسی یا اول فصل)
                if is_first_of_jalali_month or is_first_of_jalali_season:
                    publish_charts("ماهانه شمسی (Monthly)", "Monthly Chart")
                    time.sleep(3)

                # ۴. سالانه (اول هر فصل شمسی: ۱ فروردین، ۱ تیر، ۱ مهر، ۱ دی)
                if is_first_of_jalali_season:
                    publish_charts("سالانه / فصلی (Yearly)", "Yearly Chart")

        except Exception as e:
            print(f"خطا در ارسال چارت: {repr(e)}")
            time.sleep(60)

def bot_loop():
    global last_usdt_bid, last_usdt_ask, last_btc_usdt
    global last_xau_usd, last_gold_18k_nobitex, last_gold_18k_global
    
    print(f"ربات فعال شد | زمان ایران: {get_iran_time()}")

    while True:
        try:
            now_str = get_iran_time()
            xau_usd = fetch_tradingview_gold()
            xaut_bid, xaut_ask, xaut_last = fetch_nobitex_orderbook("XAUTIRT")
            usdt_bid, usdt_ask, usdt_last = fetch_nobitex_orderbook("USDTIRT")
            _, _, btc_last = fetch_nobitex_orderbook("BTCUSDT")

            if btc_last is None: btc_last = fetch_btc_coingecko()

            usdt_mid = (usdt_bid + usdt_ask) / 2 if (usdt_bid and usdt_ask) else usdt_last
            xaut_mid = (xaut_bid + xaut_ask) / 2 if (xaut_bid and xaut_ask) else xaut_last

            if xau_usd is not None or xaut_mid is not None:
                xau_usd_val = round(xau_usd, 2) if xau_usd else 0.0
                xaut_irt_val = int(xaut_mid / 10) if (xaut_mid and xaut_mid > 1000000) else int(xaut_mid or 0)
                usdt_toman = int(usdt_mid / 10) if (usdt_mid and usdt_mid > 100000) else int(usdt_mid or 60000)

                gold_18k_nobitex = int((xaut_irt_val / 31.1034768) * (18.0 / 24.0)) if xaut_irt_val else 0
                gold_18k_global = int(((xau_usd_val * usdt_toman) / 31.1034768) * (18.0 / 24.0)) if (xau_usd_val and usdt_toman) else 0

                if xau_usd_val > 0: current_gold_prices.append(xau_usd_val)

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

            if usdt_bid is not None or btc_last is not None:
                usdt_bid_val = int(usdt_bid / 10) if (usdt_bid and usdt_bid > 100000) else int(usdt_bid or 0)
                usdt_ask_val = int(usdt_ask / 10) if (usdt_ask and usdt_ask > 100000) else int(usdt_ask or 0)
                btc_usdt_val = round(btc_last, 2) if btc_last else 0.0

                if btc_usdt_val > 0: current_btc_prices.append(btc_usdt_val)

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
            print(f"خطا در حلقه اصلی: {repr(e)}")
            time.sleep(10)

if __name__ == "__main__":
    t_flask = threading.Thread(target=run_flask)
    t_flask.daemon = True
    t_flask.start()

    t_chart = threading.Thread(target=hourly_chart_loop)
    t_chart.daemon = True
    t_chart.start()

    bot_loop()
