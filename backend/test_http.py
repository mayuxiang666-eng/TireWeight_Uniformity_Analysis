import urllib.request
import json

try:
    req = urllib.request.urlopen("http://127.0.0.1:8000/api/summary")
    res = json.loads(req.read().decode('utf-8'))
    print("Backend response status:", res.get("status"))
except Exception as e:
    print("Backend fetch error:", e)
