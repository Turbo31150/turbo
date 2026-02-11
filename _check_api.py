import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json, urllib.request
url = "https://contract.mexc.com/api/v1/contract/ticker?symbol=BTC_USDT"
resp = urllib.request.urlopen(url, timeout=10)
data = json.loads(resp.read())
print(json.dumps(data["data"], indent=2))
