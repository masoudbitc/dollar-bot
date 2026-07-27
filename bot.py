import os
import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime

# توکن به صورت امن از تنظیمات Render خوانده می‌شود
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = -1003721340249

last_price = None

# ---- session با retry برای نوبیتکس ----
nobitex_session = requests.Session()
retries = Retry(
    total=6,
    backoff_factor=0.8,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False
)
nobitex_session.mount("https://", HTTPAdapter(max_retries=retries))

def get_price():
    try:
        url = "https://apiv2.nobitex.ir/v3/orderbook/USDTIRT"
        r = nobitex_session.get(url, timeout=(5, 20))

        if r.status_code != 200:
            print("Error getting price: HTTP", r.status_code, "body:", r.text[:300])
            return None

        data = r.json()

        # قیمت اصلی: lastTradePrice (ریال)
        if data.get("lastTradePrice") is not None:
            return int(float(data["lastTradePrice"]))

        # fallback با best bid/ask
        bids = data.get("bids", [])
        asks = data.get("asks", [])

        best_bid = float(bids[0][0]) if isinstance(bids, list) and bids else None
        best_ask = float(asks[0][0]) if isinstance(asks, list) and asks else None

        if best_bid is not None and best_ask is not None:
            return int((best_bid + best_ask) / 2)
        if best_bid is not None:
            return int(best_bid)
        if best_ask is not None:
            return int(best_ask)

        return None

    except Exception as e:
        print("Error getting price:", repr(e))
        return None


def send_message(text):
    if not TOKEN:
        print("خطا: توکن ربات (BOT_TOKEN) در تنظیمات Render ست نشده است!")
        return

    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
        if res.status_code != 200:
            print("Error sending message:", res.status_code, res.text[:300])
    except Exception as e:
        print("Error sending message:", repr(e))


print("ربات شروع شد، ارسال پیام تست به کانال...")
send_message("🤖 ربات قیمت USDT فعال شد!")

while True:
    price = get_price()

    if price is None:
        print("قیمت دریافت نشد، 1 ثانیه دیگر تلاش می‌کنم...")
        time.sleep(1)
        continue

    # اولین بار: فقط ذخیره کنیم
    if last_price is None:
        last_price = price
        time.sleep(1)
        continue

    if price != last_price:
        now = datetime.now().strftime("%H:%M:%S")
        message = f"{now} | {price:,}"
        print(message)
        send_message(message)
        last_price = price

    time.sleep(1)