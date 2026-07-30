import os
import requests
import time
import threading
import io
import matplotlib
matplotlib.use('Agg')  # اجرای بدون محیط گرافیکی سرور
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
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

# ذخیره تاریخچه قیمت‌ها برای رسم چارت (حداکثر ۶۰ نقطه معادل ۱ ساعت)
btc_history = []
gold_history = []
time_history = []

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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/"
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
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
        return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"[{get_iran_time()}] خطا در ارسال پیام: {repr(e)}")

def send_photo_bytes(image_bytes, caption):
    """ارسال مستقیم تصویر تولیدشده به تلگرام"""
    if not TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        files = {'photo': ('chart.png', image_bytes, 'image/png')}
        data = {'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'}
        res = requests.post(url, data=data, files=files, timeout=20)
        if res.status_code != 200:
            print(f"[{get_iran_time()}] خطا در ارسال عکس: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"[{get_iran_time()}] استثنا در ارسال عکس: {repr(e)}")

def generate_pro_chart(prices, times, title, main_color='#00F0FF', fill_color='#00F0FF22'):
    """رسم یک چارت مدرن و پیشرفته با تم تاریک سبک تریدینگ‌ویو"""
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    
    # رنگ پس‌زمینه
    fig.patch.set_facecolor('#131722')
    ax.set_facecolor('#131722')

    # رسم خط قیمت و سایه زیر آن
    ax.plot(times, prices, color=main_color, linewidth=2.5, label='Price')
    ax.fill_between(times, prices, min(prices) * 0.999, color=main_color, alpha=0.15)

    # تنظیمات عنوان و شبکه‌بندی
    ax.set_title(title, fontsize=14, fontweight='bold', color='#FFFFFF', pad=15)
    ax.grid(True, linestyle='--', color='#2A2E39', alpha=0.7)

    # تزیین محورها
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#2A2E39')
    ax.spines['bottom'].set_color('#2A2E39')
    
    plt.xticks(rotation=30, fontsize=8, color='#B2B5BE')
    plt.yticks(fontsize=9, color='#B2B5BE')
    
    # نمایش آخرین قیمت در انتهای چارت
    if prices:
        last_price = prices[-1]
        ax.annotate(f' ${last_price:,.2f}', 
                    xy=(times[-1], last_price), 
                    xytext=(times[-1], last_price),
                    fontsize=10, fontweight='bold', color='#FFFFFF',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=main_color, alpha=0.8))

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf.getvalue()

# ---- 3. پردازش ارسال چارت‌های تصویری ساعتی ----
def hourly_chart_loop():
    """ارسال چارت واقعی پس از ۲۰ دقیقه تجمع داده، و سپس هر ۱ ساعت یک‌بار"""
    # ۱۰ دقیقه صبر اولیه تا ربات حداقل چند نقطه واقعی قیمت ذخیره کند
    time.sleep(600) 
    
    while True:
        try:
            now_str = get_iran_time()
            
            # اگر حداقل ۵ نقطه واقعی ثبت شده باشد چارت ارسال می‌شود
            if len(btc_history) >= 5 and len(gold_history) >= 5:
                # ۱. چارت بیت‌کوین (رنگ نارنجی کریپتویی)
                btc_bytes = generate_pro_chart(btc_history, time_history, "BTC/USDT 1-Hour Chart", main_color='#F7931A')
                send_photo_bytes(btc_bytes, f"📊 <b>چارت نوسانات بیت‌کوین</b>\n⏰ <b>{now_str}</b>")
                time.sleep(3)

                # ۲. چارت انس طلا (رنگ طلایی)
                gold_bytes = generate_pro_chart(gold_history, time_history, "XAU/USD Gold Chart", main_color='#FFD700')
                send_photo_bytes(gold_bytes, f"📊 <b>چارت نوسانات انس جهانی طلا</b>\n⏰ <b>{now_str}</b>")

                print(f"[{now_str}] تصاویر چارت‌های واقعی با موفقیت ارسال شدند.")
            else:
                print(f"[{now_str}] داده‌های واقعی هنوز کافی نیستند (کمتر از ۵ نقطه).")
            
        except Exception as e:
            print(f"خطا در ایجاد/ارسال چارت: {repr(e)}")
            
        # هر ۳۶۰۰ ثانیه (۱ ساعت) ارسال مجدد
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

            usdt_mid = (usdt_bid + usdt_ask) / 2 if (usdt_bid and usdt_ask) else usdt_last
            xaut_mid = (xaut_bid + xaut_ask) / 2 if (xaut_bid and xaut_ask) else xaut_last

            if xau_usd is not None and xaut_mid is not None and usdt_mid is not None:
                now_str_gold = get_iran_time()
                xau_usd_val = round(xau_usd, 2)
                xaut_irt_val = int(xaut_mid / 10) if xaut_mid > 1000000 else int(xaut_mid)
                usdt_toman = int(usdt_mid / 10) if usdt_mid > 100000 else int(usdt_mid)

                gold_18k_nobitex = int((xaut_irt_val / 31.1034768) * (18.0 / 24.0))
                gold_18k_global = int(((xau_usd_val * usdt_toman) / 31.1034768) * (18.0 / 24.0))

                # ذخیره داده‌های طلا جهت رسم چارت
                if len(gold_history) == 0 or gold_history[-1] != xau_usd_val:
                    gold_history.append(xau_usd_val)
                    if len(gold_history) > 60: gold_history.pop(0)

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

            time.sleep(5)

            # -------------------------------------------------------------
            # گام ۲: (ثانیه ۵) بررسی و ارسال پیام تتر و بیت‌کوین
            # -------------------------------------------------------------
            _, _, btc_last = fetch_nobitex_orderbook("BTCUSDT")

            if usdt_bid is not None and usdt_ask is not None and btc_last is not None:
                now_str_crypto = get_iran_time()
                usdt_bid_val = int(usdt_bid / 10) if usdt_bid > 100000 else int(usdt_bid)
                usdt_ask_val = int(usdt_ask / 10) if usdt_ask > 100000 else int(usdt_ask)
                btc_usdt_val = round(btc_last, 2)

                # ذخیره قیمت‌های بیت‌کوین و زمان جهت رسم چارت
                if len(btc_history) == 0 or btc_history[-1] != btc_usdt_val:
                    btc_history.append(btc_usdt_val)
                    time_history.append(now_str_crypto[:5])
                    if len(btc_history) > 60: 
                        btc_history.pop(0)
                        time_history.pop(0)

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
            time.sleep(5)

        except Exception as e:
            print(f"خطا در حلقه اصلی: {repr(e)}")
            time.sleep(5)

# ---- 5. اجرا ----
if __name__ == "__main__":
    t_flask = threading.Thread(target=run_flask)
    t_flask.daemon = True
    t_flask.start()

    t_chart = threading.Thread(target=hourly_chart_loop)
    t_chart.daemon = True
    t_chart.start()

    bot_loop()
