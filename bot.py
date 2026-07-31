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

# ذخیره تاریخچه قیمت‌ها برای تایم‌فریم‌های مختلف
btc_history_10m = []
gold_history_10m = []
time_history_10m = []

btc_history_1h = []
gold_history_1h = []
time_history_1h = []

btc_history_daily = []
gold_history_daily = []
time_history_daily = []

last_usdt_bid = None
last_btc_usdt = None
last_xau_usd = None
last_gold_18k_nobitex = None
last_gold_18k_global = None

def get_iran_datetime():
    """دریافت datetime دقیق ایران (UTC + 3:30)"""
    iran_offset = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(iran_offset)

def get_iran_time():
    """دریافت زمان دقیق ایران"""
    return get_iran_datetime().strftime("%H:%M:%S")

def fetch_nobitex_orderbook(symbol):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
        return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"خطا در ارسال پیام: {repr(e)}")

def send_photo_url(photo_url, caption):
    if not TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        requests.post(url, data={'chat_id': CHAT_ID, 'photo': photo_url, 'caption': caption, 'parse_mode': 'HTML'}, timeout=15)
    except Exception as e:
        print(f"خطا در ارسال عکس: {repr(e)}")

def get_quickchart_url(labels, data, title, color="rgb(247, 147, 26)"):
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
                "borderWidth": 2,
                "pointRadius": 3
            }]
        },
        "options": {
            "title": {"display": True, "text": title, "fontColor": "#fff", "fontSize": 15},
            "legend": {"display": False},
            "scales": {
                "xAxes": [{"ticks": {"fontColor": "#ccc", "maxRotation": 45}}],
                "yAxes": [{"ticks": {"fontColor": "#ccc"}}]
            }
        }
    }
    json_str = json.dumps(chart_config)
    encoded = urllib.parse.quote(json_str)
    return f"https://quickchart.io/chart?bkg=%23131722&w=800&h=400&c={encoded}"

def publish_chart(asset_name, timeframe_str, data_list, times_list, color):
    if not data_list:
        return
    now_str = get_iran_time()
    title = f"چارت {asset_name} - تایم فریم {timeframe_str}"
    chart_url = get_quickchart_url(times_list, data_list, title, color)
    caption = f"📊 <b>{title}</b>\n⏰ {now_str}"
    send_photo_url(chart_url, caption)

# ---- ۳. حلقه‌های زمان‌بندی چارت‌ها ----
def chart_10m_loop():
    """چارت هر ۱۰ دقیقه یک‌بار"""
    time.sleep(30)
    while True:
        try:
            now_str = get_iran_time()
            if last_btc_usdt and last_xau_usd:
                btc_history_10m.append(last_btc_usdt)
                gold_history_10m.append(last_xau_usd)
                time_history_10m.append(now_str[:5])
                
                if len(btc_history_10m) > 30:
                    btc_history_10m.pop(0)
                    gold_history_10m.pop(0)
                    time_history_10m.pop(0)

                publish_chart("بیتکوین", "10 دقیقه ای", btc_history_10m, time_history_10m, "rgb(247, 147, 26)")
                time.sleep(3)
                publish_chart("انس جهانی طلا", "10 دقیقه ای", gold_history_10m, time_history_10m, "rgb(255, 215, 0)")
        except Exception as e:
            print(f"خطا در چارت ۱۰ دقیقه‌ای: {repr(e)}")
        time.sleep(600) # هر 10 دقیقه

def chart_1h_loop():
    """چارت هر ۱ ساعت رند"""
    time.sleep(40)
    while True:
        try:
            now = get_iran_datetime()
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            time.sleep((next_hour - now).total_seconds())

            now_str = get_iran_time()
            if last_btc_usdt and last_xau_usd:
                btc_history_1h.append(last_btc_usdt)
                gold_history_1h.append(last_xau_usd)
                time_history_1h.append(now_str[:5])

                if len(btc_history_1h) > 24:
                    btc_history_1h.pop(0)
                    gold_history_1h.pop(0)
                    time_history_1h.pop(0)

                publish_chart("بیتکوین", "1 ساعته", btc_history_1h, time_history_1h, "rgb(247, 147, 26)")
                time.sleep(3)
                publish_chart("انس جهانی طلا", "1 ساعته", gold_history_1h, time_history_1h, "rgb(255, 215, 0)")
        except Exception as e:
            print(f"خطا در چارت ۱ ساعته: {repr(e)}")
            time.sleep(60)

def daily_and_periodic_charts_loop():
    """بقیه چارت‌ها رأس ساعت ۲۱:۰۰ هر روز"""
    time.sleep(50)
    while True:
        try:
            now = get_iran_datetime()
            target = now.replace(hour=21, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            time.sleep((target - now).total_seconds())

            now = get_iran_datetime()
            j_now = jdatetime.datetime.fromgregorian(datetime=now)

            # ۱. چارت روزانه (۲۴ ساعته) - هر روز ساعت ۲۱
            if last_btc_usdt and last_xau_usd:
                btc_history_daily.append(last_btc_usdt)
                gold_history_daily.append(last_xau_usd)
                if len(btc_history_daily) > 30:
                    btc_history_daily.pop(0)
                    gold_history_daily.pop(0)
                
                dates_list = [(jdatetime.datetime.fromgregorian(datetime=now).strftime("%m/%d"))] * len(btc_history_daily)

                publish_chart("بیتکوین", "روزانه", btc_history_daily, dates_list, "rgb(247, 147, 26)")
                time.sleep(3)
                publish_chart("انس جهانی طلا", "روزانه", gold_history_daily, dates_list, "rgb(255, 215, 0)")
                time.sleep(3)

            # ۲. چارت هفتگی (روزهای جمعه)
            if now.weekday() == 4:
                publish_chart("بیتکوین", "هفتگی", btc_history_daily, dates_list, "rgb(247, 147, 26)")
                time.sleep(3)
                publish_chart("انس جهانی طلا", "هفتگی", gold_history_daily, dates_list, "rgb(255, 215, 0)")
                time.sleep(3)

            # ۳. چارت ماهانه (اول هر ماه شمسی)
            if j_now.day == 1:
                publish_chart("بیتکوین", "ماهانه", btc_history_daily, dates_list, "rgb(247, 147, 26)")
                time.sleep(3)
                publish_chart("انس جهانی طلا", "ماهانه", gold_history_daily, dates_list, "rgb(255, 215, 0)")
                time.sleep(3)

            # ۴. چارت فصلی و سالانه (اول فصل‌های شمسی: ۱ فروردین، تیر، مهر، دی)
            if j_now.day == 1 and j_now.month in [1, 4, 7, 10]:
                publish_chart("بیتکوین", "فصلی", btc_history_daily, dates_list, "rgb(247, 147, 26)")
                time.sleep(3)
                publish_chart("انس جهانی طلا", "فصلی", gold_history_daily, dates_list, "rgb(255, 215, 0)")
                time.sleep(3)
                publish_chart("بیتکوین", "سالیانه", btc_history_daily, dates_list, "rgb(247, 147, 26)")
                time.sleep(3)
                publish_chart("انس جهانی طلا", "سالیانه", gold_history_daily, dates_list, "rgb(255, 215, 0)")

        except Exception as e:
            print(f"خطا در چارت‌های دوره‌ای: {repr(e)}")
            time.sleep(60)

# ---- ۴. حلقه قیمت‌های لحظه‌ای ----
def bot_loop():
    global last_usdt_bid, last_btc_usdt, last_xau_usd
    global last_gold_18k_nobitex, last_gold_18k_global
    
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

            usdt_mid = usdt_bid if usdt_bid else usdt_last
            xaut_mid = xaut_bid if xaut_bid else xaut_last

            # --- بخش طلا ---
            if xau_usd is not None or xaut_mid is not None:
                xau_usd_val = round(xau_usd, 2) if xau_usd else 0.0
                xaut_irt_val = int(xaut_mid / 10) if (xaut_mid and xaut_mid > 1000000) else int(xaut_mid or 0)
                usdt_toman = int(usdt_mid / 10) if (usdt_mid and usdt_mid > 100000) else int(usdt_mid or 60000)

                gold_18k_nobitex = int((xaut_irt_val / 31.1034768) * (18.0 / 24.0)) if xaut_irt_val else 0
                gold_18k_global = int(((xau_usd_val * usdt_toman) / 31.1034768) * (18.0 / 24.0)) if (xau_usd_val and usdt_toman) else 0

                if last_xau_usd is None or (xau_usd_val != last_xau_usd) or (gold_18k_nobitex != last_gold_18k_nobitex):
                    gold_msg = (
                        f"🥇 <b>انس طلا:</b> ${xau_usd_val:,.2f} {get_arrow(xau_usd_val, last_xau_usd)}\n"
                        f"🔱 <b>طلا/تومان ۱۸ عیار:</b> {gold_18k_nobitex:,} تومان {get_arrow(gold_18k_nobitex, last_gold_18k_nobitex)}\n"
                        f"🌐 <b>طلا/تتر ۱۸ عیار:</b> {gold_18k_global:,} تومان {get_arrow(gold_18k_global, last_gold_18k_global)}\n"
                        f"⏰ {now_str}"
                    )
                    send_message(gold_msg)

                    last_xau_usd = xau_usd_val
                    last_gold_18k_nobitex = gold_18k_nobitex
                    last_gold_18k_global = gold_18k_global

            time.sleep(3)

            # --- بخش تتر و کریپتو (فقط تتر خرید) ---
            if usdt_bid is not None or btc_last is not None:
                usdt_bid_val = int(usdt_bid / 10) if (usdt_bid and usdt_bid > 100000) else int(usdt_bid or 0)
                btc_usdt_val = round(btc_last, 2) if btc_last else 0.0

                last_btc_usdt = btc_usdt_val

                if last_usdt_bid is None or (usdt_bid_val != last_usdt_bid) or (btc_usdt_val != last_btc_usdt):
                    crypto_msg = (
                        f"💵 <b>تتر:</b> {usdt_bid_val:,} تومان {get_arrow(usdt_bid_val, last_usdt_bid)}\n"
                        f"🪙 <b>بیت‌کوین:</b> ${btc_usdt_val:,.2f} {get_arrow(btc_usdt_val, last_btc_usdt)}\n"
                        f"⏰ {now_str}"
                    )
                    send_message(crypto_msg)

                    last_usdt_bid = usdt_bid_val
                    last_btc_usdt = btc_usdt_val

            time.sleep(10)

        except Exception as e:
            print(f"خطا در حلقه اصلی: {repr(e)}")
            time.sleep(10)

# ---- ۵. اجرا ----
if __name__ == "__main__":
    t_flask = threading.Thread(target=run_flask)
    t_flask.daemon = True
    t_flask.start()

    t_10m = threading.Thread(target=chart_10m_loop)
    t_10m.daemon = True
    t_10m.start()

    t_1h = threading.Thread(target=chart_1h_loop)
    t_1h.daemon = True
    t_1h.start()

    t_daily = threading.Thread(target=daily_and_periodic_charts_loop)
    t_daily.daemon = True
    t_daily.start()

    bot_loop()
