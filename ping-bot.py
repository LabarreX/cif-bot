import threading
import time
import random
import requests
from flask import Flask, jsonify

app = Flask(__name__)

SITE_NAME = "Site ping - CIF-Bot"
OTHER_SITE = "https://cif-bot.onrender.com/"
PING_INTERVAL = 100
PING_JITTER = 30
REQUEST_TIMEOUT = 5
UA = f"{SITE_NAME}-keepalive/1.0"

@app.route("/")
def index():
    return f"{SITE_NAME} is alive and pinging {OTHER_SITE}", 200

@app.route("/keepalive")
def keepalive():
    return jsonify({"status": "ok", "site": SITE_NAME}), 200

def ping_loop():
    """Boucle qui ping l’autre site régulièrement."""
    backoff = 1.0
    while True:
        try:
            jitter = random.uniform(0, PING_JITTER)
            time.sleep(jitter)

            url = OTHER_SITE.rstrip("/") + "/keepalive"
            headers = {"User-Agent": UA}
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

            if resp.status_code == 200:
                backoff = 1.0
                time.sleep(max(0, PING_INTERVAL - jitter))
            else:
                backoff = min(300, backoff * 2)
                time.sleep(backoff)
        except Exception:
            backoff = min(300, backoff * 2)
            time.sleep(backoff)

def run():
    t = threading.Thread(target=ping_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    run()
