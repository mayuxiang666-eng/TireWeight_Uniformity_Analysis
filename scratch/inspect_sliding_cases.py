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

# Let's test TB122, TB183, TB175 on 2026-08-13
for wc in ["TB122", "TB183", "TB175"]:
    res_main = get("/api/cgrs/records", {
        "workcenter": wc,
        "date": "2026-08-13",
        "indicator": "rfpp"
    })
    comp = res_main.get('comparison', {})
    print(f"\nWorkcenter: {wc} | Comparison events: {comp.get('events_count')}")
    if comp.get('events'):
        for ev in comp['events']:
            print(f"  Event at {ev.get('date_time_str')}: Pre N={ev.get('n_before')} CPK={ev.get('cpk_before')} | Post N={ev.get('n_after')} CPK={ev.get('cpk_after')} | YoY={ev.get('yoy_growth_pct')}%")

    res_ctrl = get("/api/cgrs/controlled-analysis", {
        "workcenter": wc,
        "date": "2026-08-13",
        "indicator": "rfpp",
        "second_workcenter_col": "ct_workcenter"
    })
    print(f"  Controlled analysis: {res_ctrl.get('conclusion_type')}")
    if res_ctrl.get('events'):
        for p in res_ctrl['events'][0].get('paths', []):
            print(f"    Path: {p['path_label']} | Pre N={p['n_before']} CPK={p['cpk_before']} | Post N={p['n_after']} CPK={p['cpk_after']} | YoY={p['yoy_pct']}%")
