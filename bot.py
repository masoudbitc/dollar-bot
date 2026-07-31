import os
import requests
import time
import threading
import json
import urllib.parse
import jdatetime
from flask import Flask
from datetime import datetime, timezone, timedelta

# ---- ۱. وب‌سرور برای Render و UptimeRobot ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ---- ۲. تنظیمات ربات و زمان ایران ----
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = -1003721340249

# تاریخچه‌ها (شامل انس طلا)
btc_history_10m = []
gold_toman_10m = []
gold_global_10m = []
usdt_history_10m = []
xau_history_10m = []
time_history_10m = []

btc_history_1h = []
gold_toman_1h = []
gold_global_1h = []
usdt_history_1h = []
xau_history_1h = []
time_history_1h = []

btc_history_daily = []
gold_toman_daily = []
gold_global_daily = []
usdt_history_daily = []
xau_history_daily = []

last_usdt_bid = None
last_btc_usdt = None
last_xau_usd = None
last_gold_18k_nobitex = None
last_gold_18k_global = None

def get_iran_datetime():
    iran_offset = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(iran_offset)

def get_iran_time_date():
    now = get_iran_datetime()
    j_now = jdatetime.datetime.fromgregorian(datetime=now)
    time_str = now.strftime("%H:%M:%S")
    date_str = j_now.strftime("%Y/%m/%d")
    return f"{time_str} - {date_str}"

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
        print(f"[{get_iran_time_date()}] Nobitex error ({symbol}): {repr(e)}")
    return None, None, None

def fetch_usdt_real_price():
    _, _, last_trade = fetch_nobitex_orderbook("USDTIRT")
    if last_trade and last_trade > 100000:
        return float(last_trade)
    
    try:
        url = "https://api.nobitex.ir/market/stats"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            stats = r.json().get("stats", {})
            usdt_stat = stats.get("usdt-irt", {})
            val = float(usdt_stat.get("latest", 0))
            if val > 100000:
                return val
    except Exception:
        pass
    return None

def fetch_btc_price_usdt():
    try:
        url = "https://scanner.tradingview.com/crypto/scan"
        payload = {"symbols": {"tickers": ["BINANCE:BTCUSDT"]}, "columns": ["close"]}
        r = requests.post(url, json=payload, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("data"):
                val = float(data["data"][0]["d"][0])
                if val > 1000:
                    return val
    except Exception as e:
        print(f"[{get_iran_time_date()}] TradingView BTC error: {repr(e)}")
    return None

def fetch_gold_price():
    url = "https://scanner.tradingview.com/global/scan"
    payload = {"symbols": {"tickers": ["TVC:GOLD"]}, "columns": ["close"]}
    headers = {"User-Agent": "Mozilla/5.0", "Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/"}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("data"):
                val = float(data["data"][0]["d"][0])
                if val > 500:
                    return val
    except Exception:
        pass

    try:
        url = "https://data-asg.goldprice.org/dbXRates/USD"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                val = float(items[0].get("xauPrice", 0))
                if val > 500:
                    return val
    except Exception:
        pass
    return 2650.0

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

def get_quickchart_url(labels, data, title, date_str, color="rgb(247, 147, 26)"):
    full_title = f"{title} | تاریخ: {date_str}"
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
            "title": {"display": True, "text": full_title, "fontColor": "#fff", "fontSize": 14},
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

def get_quickchart_dual_url(labels, data1, label1, color1, data2, label2, color2, title, date_str):
    full_title = f"{title} | تاریخ: {date_str}"
    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {"label": label1, "data": data1, "borderColor": color1, "backgroundColor": color1.replace("rgb", "rgba").replace(")", ", 0.1)"), "fill": False, "borderWidth": 2, "pointRadius": 2},
                {"label": label2, "data": data2, "borderColor": color2, "backgroundColor": color2.replace("rgb", "rgba").replace(")", ", 0.1)"), "fill": False, "borderWidth": 2, "pointRadius": 2}
            ]
        },
        "options": {
            "title": {"display": True, "text": full_title, "fontColor": "#fff", "fontSize": 14},
            "legend": {"display": True, "labels": {"fontColor": "#ccc"}},
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
    if not data_list or len(data_list) < 1:
        return
    now_dt = get_iran_datetime()
    j_now = jdatetime.datetime.fromgregorian(datetime=now_dt)
    date_str = j_now.strftime("%Y/%m/%d")
    now_str = get_iran_time_date()
    
    title = f"چارت {asset_name} - تایم فریم {timeframe_str}"
    chart_url = get_quickchart_url(times_list, data_list, title, date_str, color)
    caption = f"📊 <b>{title}</b>\n⏰ {now_str}"
    send_photo_url(chart_url, caption)

def publish_dual_gold_chart(timeframe_str, toman_data, global_data, times_list):
    if not toman_data or not global_data or len(toman_data) < 1:
        return
    now_dt = get_iran_datetime()
    j_now = jdatetime.datetime.fromgregorian(datetime=now_dt)
    date_str = j_now.strftime("%Y/%m/%d")
    now_str = get_iran_time_date()

    title = f"چارت مقایسه‌ای طلا ۱۸ عیار - تایم فریم {timeframe_str}"
    chart_url = get_quickchart_dual_url(
        times_list, 
        toman_data, "طلا/تومان ۱۸ عیار", "rgb(255, 215, 0)", 
        global_data, "طلا/تتر ۱۸ عیار", "rgb(38, 166, 154)", 
        title, date_str
    )
    caption = f"📊 <b>{title}</b>\n⏰ {now_str}"
    send_photo_url(chart_url, caption)

# ---- ۳. حلقه‌های زمان‌بندی چارت‌ها ----
def chart_10m_loop():
    while True:
        try:
            now = get_iran_datetime()
            current_minute = now.minute
            next_ten_minute = ((current_minute // 10) + 1) * 10
            
            if next_ten_minute >= 60:
                target_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            else:
                target_time = now.replace(minute=next_ten_minute, second=0, microsecond=0)
            
            sleep_secs = (target_time - now).total_seconds()
            if sleep_secs > 0:
                time.sleep(sleep_secs)

            now_chk = get_iran_datetime()
            if now_chk.minute == 0 or (now_chk.hour == 21 and now_chk.minute == 0):
                time.sleep(10)
                continue

            if last_btc_usdt and last_gold_18k_nobitex and last_gold_18k_global and last_usdt_bid and last_xau_usd:
                btc_history_10m.append(last_btc_usdt)
                gold_toman_10m.append(last_gold_18k_nobitex)
                gold_global_10m.append(last_gold_18k_global)
                usdt_history_10m.append(last_usdt_bid)
                xau_history_10m.append(last_xau_usd)
                time_history_10m.append(now_chk.strftime("%H:%M"))
                
                if len(btc_history_10m) > 30:
                    btc_history_10m.pop(0)
                    gold_toman_10m.pop(0)
                    gold_global_10m.pop(0)
                    usdt_history_10m.pop(0)
                    xau_history_10m.pop(0)
                    time_history_10m.pop(0)

                publish_chart("بیتکوین", "10 دقیقه ای", btc_history_10m, time_history_10m, "rgb(247, 147, 26)")
                time.sleep(3)
                publish_dual_gold_chart("10 دقیقه ای", gold_toman_10m, gold_global_10m, time_history_10m)
                time.sleep(3)
                publish_chart("تتر", "10 دقیقه ای", usdt_history_10m, time_history_10m, "rgb(38, 166, 154)")
                time.sleep(3)
                publish_chart("انس طلا", "10 دقیقه ای", xau_history_10m, time_history_10m, "rgb(234, 179, 8)")

        except Exception as e:
            print(f"خطا در چارت ۱۰ دقیقه‌ای: {repr(e)}")
            time.sleep(10)

def chart_1h_loop():
    while True:
        try:
            now = get_iran_datetime()
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            time.sleep((next_hour - now).total_seconds())

            now = get_iran_datetime()
            if now.hour == 21:
                continue

            if last_btc_usdt and last_gold_18k_nobitex and last_gold_18k_global and last_usdt_bid and last_xau_usd:
                btc_history_1h.append(last_btc_usdt)
                gold_toman_1h.append(last_gold_18k_nobitex)
                gold_global_1h.append(last_gold_18k_global)
                usdt_history_1h.append(last_usdt_bid)
                xau_history_1h.append(last_xau_usd)
                time_history_1h.append(now.strftime("%H:%M"))

                if len(btc_history_1h) > 24:
                    btc_history_1h.pop(0)
                    gold_toman_1h.pop(0)
                    gold_global_1h.pop(0)
                    usdt_history_1h.pop(0)
                    xau_history_1h.pop(0)
                    time_history_1h.pop(0)

                publish_chart("بیتکوین", "1 ساعته", btc_history_1h, time_history_1h, "rgb(247, 147, 26)")
                time.sleep(3)
                publish_dual_gold_chart("1 ساعته", gold_toman_1h, gold_global_1h, time_history_1h)
                time.sleep(3)
                publish_chart("تتر", "1 ساعته", usdt_history_1h, time_history_1h, "rgb(38, 166, 154)")
                time.sleep(3)
                publish_chart("انس طلا", "1 ساعته", xau_history_1h, time_history_1h, "rgb(234, 179, 8)")
        except Exception as e:
            print(f"خطا در چارت ۱ ساعته: {repr(e)}")
            time.sleep(60)

def daily_and_periodic_charts_loop():
    while True:
        try:
            now = get_iran_datetime()
            target = now.replace(hour=21, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            time.sleep((target - now).total_seconds())

            now = get_iran_datetime()
            j_now = jdatetime.datetime.fromgregorian(datetime=now)

            if last_btc_usdt and last_gold_18k_nobitex and last_gold_18k_global and last_usdt_bid and last_xau_usd:
                btc_history_daily.append(last_btc_usdt)
                gold_toman_daily.append(last_gold_18k_nobitex)
                gold_global_daily.append(last_gold_18k_global)
                usdt_history_daily.append(last_usdt_bid)
                xau_history_daily.append(last_xau_usd)
                
                if len(btc_history_daily) > 30:
                    btc_history_daily.pop(0)
                    gold_toman_daily.pop(0)
                    gold_global_daily.pop(0)
                    usdt_history_daily.pop(0)
                    xau_history_daily.pop(0)
                
                dates_list = [jdatetime.datetime.fromgregorian(datetime=now).strftime("%m/%d")] * len(btc_history_daily)

                def send_all_periodic(timeframe_name):
                    publish_chart("بیتکوین", timeframe_name, btc_history_daily, dates_list, "rgb(247, 147, 26)")
                    time.sleep(3)
                    publish_dual_gold_chart(timeframe_name, gold_toman_daily, gold_global_daily, dates_list)
                    time.sleep(3)
                    publish_chart("تتر", timeframe_name, usdt_history_daily, dates_list, "rgb(38, 166, 154)")
                    time.sleep(3)
                    publish_chart("انس طلا", timeframe_name, xau_history_daily, dates_list, "rgb(234, 179, 8)")
                    time.sleep(3)

                send_all_periodic("روزانه")
                if now.weekday() == 4:
                    send_all_periodic("هفتگی")
                if j_now.day == 1:
                    send_all_periodic("ماهانه")
                if j_now.day == 1 and j_now.month in [1, 4, 7, 10]:
                    send_all_periodic("فصلی")
                    send_all_periodic("سالیانه")

        except Exception as e:
            print(f"خطا در چارت‌های دوره‌ای: {repr(e)}")
            time.sleep(60)

# ---- ۴. حلقه قیمت‌های لحظه‌ای ----
def bot_loop():
    global last_usdt_bid, last_btc_usdt, last_xau_usd
    global last_gold_18k_nobitex, last_gold_18k_global
    
    current_time = get_iran_time_date()
    print(f"ربات شروع شد | زمان: {current_time}")
    send_message(f"🤖 <b>ربات فعال شد!</b>\n⏰ {current_time}")

    while True:
        try:
            now_str = get_iran_time_date()
            
            xau_usd = fetch_gold_price()
            xaut_bid, xaut_ask, xaut_last = fetch_nobitex_orderbook("XAUTIRT")
            usdt_real_val = fetch_usdt_real_price()
            _, _, usdt_last_trade = fetch_nobitex_orderbook("USDTIRT")
            btc_usdt_val_raw = fetch_btc_price_usdt()

            usdt_mid = usdt_real_val if usdt_real_val else usdt_last_trade

            # --- بخش طلا ---
            if xau_usd and xau_usd > 500 and usdt_mid and usdt_mid > 10000:
                xau_usd_val = round(xau_usd, 2)
                usdt_toman = int(usdt_mid / 10)
                
                xaut_irt_val = int(xaut_bid / 10) if (xaut_bid and xaut_bid > 1000000) else (int(xaut_last / 10) if xaut_last and xaut_last > 1000000 else 0)

                gold_18k_nobitex = int((xaut_irt_val / 31.1034768) * (18.0 / 24.0)) if xaut_irt_val > 100000 else 0
                gold_18k_global = int(((xau_usd_val * usdt_toman) / 31.1034768) * (18.0 / 24.0))

                if gold_18k_global > 1000000:
                    gold_msg = (
                        f"🥇 <b>انس طلا:</b> ${xau_usd_val:,.2f} {get_arrow(xau_usd_val, last_xau_usd)}\n"
                        f"🔱 <b>طلا/تومان ۱۸ عیار:</b> {gold_18k_nobitex:,} تومان {get_arrow(gold_18k_nobitex, last_gold_18k_nobitex)}\n"
                        f"🌐 <b>طلا/تتر ۱۸ عیار:</b> {gold_18k_global:,} تومان {get_arrow(gold_18k_global, last_gold_18k_global)}\n"
                        f"⏰ {now_str}"
                    )
                    send_message(gold_msg)

                    last_xau_usd = xau_usd_val
                    if gold_18k_nobitex > 100000:
                        last_gold_18k_nobitex = gold_18k_nobitex
                    last_gold_18k_global = gold_18k_global

            time.sleep(3)

            # --- بخش تتر و بیت‌کوین ---
            usdt_bid_val = int(usdt_mid / 10) if (usdt_mid and usdt_mid > 100000) else (last_usdt_bid or 0)
            btc_usdt_val = round(btc_usdt_val_raw, 2) if (btc_usdt_val_raw and btc_usdt_val_raw > 1000) else (last_btc_usdt or 0)

            if usdt_bid_val > 10000 and btc_usdt_val > 1000:
                crypto_msg = (
                    f"💵 <b>تتر:</b> {usdt_bid_val:,} تومان {get_arrow(usdt_bid_val, last_usdt_bid)}\n"
                    f"🪙 <b>بیت‌کوین:</b> ${btc_usdt_val:,.2f} {get_arrow(btc_usdt_val, last_btc_usdt)}\n"
                    f"⏰ {now_str}"
                )
                send_message(crypto_msg)

                last_btc_usdt = btc_usdt_val
                last_usdt_bid = usdt_bid_val

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
