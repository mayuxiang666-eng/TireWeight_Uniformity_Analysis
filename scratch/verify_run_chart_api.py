import urllib.request
import urllib.parse
import json

BASE = "http://localhost:8000"

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        query_str = urllib.parse.urlencode(params)
        url = f"{url}?{query_str}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

res = get("/api/cgrs/records", {
    "workcenter": "TB224",
    "date": "2026-08-10",
    "article": "0312053000",
    "indicator": "rfpp"
})

comp = res.get('comparison', {})
if comp.get('events'):
    ev = comp['events'][0]
    print(f"Event: {ev.get('date_time_str')}")
    print(f"Pre N={ev.get('n_before')}, Post N={ev.get('n_after')}")
    print(f"USL={ev.get('usl')}, LSL={ev.get('lsl')}")
    series = ev.get('barcodes_series', [])
    print(f"Barcodes series total length: {len(series)}")
    if series:
        print("First 3 pre:", series[:3])
        print("Last 3 post:", series[-3:])
