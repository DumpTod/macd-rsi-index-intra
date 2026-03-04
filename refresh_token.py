import hashlib
import requests
import os

# ── YOUR CREDENTIALS — fill these in ──────────────────────
APP_ID       = "EMRCD1JW93-100"
SECRET_KEY   = "VZKGCP1AA6"
PIN          = "2504"
RENDER_API_KEY     = "rnd_HAAzJetaMsj3gX5h64TMdcqFKuIY"
RENDER_SERVICE_ID  = "srv-d6j994ma2pns7397pao0"
# ──────────────────────────────────────────────────────────

REFRESH_TOKEN_FILE = "fyers_refresh_token.txt"
REFRESH_URL = "https://api-t2.fyers.in/api/v3/validate-refresh-token"

def get_sha256(app_id, secret_key):
    combined = f"{app_id}:{secret_key}"
    return hashlib.sha256(combined.encode()).hexdigest()

def get_access_token():
    # Read saved refresh token
    if not os.path.exists(REFRESH_TOKEN_FILE):
        print("❌ No refresh token file found. Run initial authentication first.")
        return None

    with open(REFRESH_TOKEN_FILE, "r") as f:
        refresh_token = f.read().strip()

    app_id_hash = get_sha256(APP_ID, SECRET_KEY)

    payload = {
        "grant_type":    "refresh_token",
        "appIdHash":     app_id_hash,
        "refreshToken":  refresh_token,
        "pin":           PIN,
    }

    response = requests.post(REFRESH_URL, json=payload)
    data = response.json()

    if data.get("s") == "ok":
        access_token = data["access_token"]
        print(f"✅ New access token obtained!")
        return access_token
    else:
        print(f"❌ Failed: {data}")
        return None

def update_render_env(access_token):
    url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/env-vars"
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = [
        {"key": "FYERS_ACCESS_TOKEN", "value": access_token}
    ]
    response = requests.put(url, json=payload, headers=headers)
    if response.status_code == 200:
        print("✅ Render updated with new access token!")
    else:
        print(f"❌ Render update failed: {response.text}")

def trigger_redeploy():
    url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/deploys"
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}"}
    requests.post(url, headers=headers)
    print("✅ Render redeployment triggered!")

if __name__ == "__main__":
    token = get_access_token()
    if token:
        update_render_env(token)
        trigger_redeploy()
```

---

Now do these steps one by one:

**Step 1** — Fill in `APP_ID`, `SECRET_KEY`, `PIN` in the script.

**Step 2** — Get your Render API Key:
- Go to render.com → click your profile photo → **Account Settings** → **API Keys** → create one → copy it

**Step 3** — Get your Render Service ID:
- Go to your backend service on Render
- Look at the URL — it looks like `dashboard.render.com/web/srv-XXXXXXXXXX`
- Copy the `srv-XXXXXXXXXX` part

**Step 4** — Every morning before 9:30 AM, just run:
```
python refresh_token.py
