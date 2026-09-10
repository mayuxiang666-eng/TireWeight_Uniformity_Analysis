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

print("CGRS Records count:", len(res.get('data', [])))
for r in res.get('data', []):
    print("Record:", r.get('TechOffsetLocalDate'), r.get('ParameterName'), r.get('event_timestamp'))

comp = res.get('comparison', {})
print("\nComparison events count:", comp.get('events_count'))
if comp.get('events'):
    for ev in comp['events']:
        print(f"Event {ev.get('date_time_str')}: Pre N={ev.get('n_before')}, Post N={ev.get('n_after')}")

ctrl = get("/api/cgrs/controlled-analysis", {
    "workcenter": "TB224",
    "date": "2026-08-10",
    "article": "0312053000",
    "indicator": "rfpp",
    "second_workcenter_col": "ct_workcenter"
})

print("\nControlled analysis events count:", ctrl.get('events_count'))
if ctrl.get('events'):
    for p in ctrl['events'][0].get('paths', []):
        print(f"Path {p.get('path_label')}: Pre N={p.get('n_before')}, Post N={p.get('n_after')}")
