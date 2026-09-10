import urllib.request
import json

try:
    print("1. Calling /api/reload-data to reload DuckDB memory table in running backend...")
    req = urllib.request.Request("http://127.0.0.1:8000/api/reload-data", method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        print("Reload response:", resp.read().decode('utf-8'))
except Exception as e:
    print("Reload error:", e)

try:
    print("\n2. Fetching /api/cgrs/records from running server...")
    url = "http://127.0.0.1:8000/api/cgrs/records?workcenter=TB224&date=2026-08-10&article=0312053000&indicator=rfpp"
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print("Status:", data.get("status"))
        comp = data.get("comparison", {})
        print("Comparison summary:")
        print("  has_cgrs:", comp.get("has_cgrs"))
        print("  latest_event_time:", comp.get("latest_event_time"))
        print("  latest_n_before:", comp.get("latest_n_before"))
        print("  latest_n_after:", comp.get("latest_n_after"))
        print("  latest_cpk_before:", comp.get("latest_cpk_before"))
        print("  latest_cpk_after:", comp.get("latest_cpk_after"))
        print("  latest_yoy_pct:", comp.get("latest_yoy_pct"))
except Exception as e:
    print("Fetch error:", e)
