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

# Let's test with second_workcenter_col = "ct_workcenter"
res_ctrl = get("/api/cgrs/controlled-analysis", {
    "workcenter": "TB234",
    "date": "2026-08-12",
    "article": "0315980000",
    "indicator": "rfpp",
    "second_workcenter_col": "ct_workcenter"
})

print("Status:", res_ctrl.get('status'))
print("Conclusion Type:", res_ctrl.get('conclusion_type'))
print("Conclusion Text:", res_ctrl.get('conclusion_text'))
print("Second machines:", res_ctrl.get('second_machines'))
if res_ctrl.get('events'):
    for p in res_ctrl['events'][0].get('paths', []):
        print(f"  Path: {p['path_label']} | Pre N={p['n_before']} CPK={p['cpk_before']} | Post N={p['n_after']} CPK={p['cpk_after']} | YoY={p['yoy_pct']}%")
