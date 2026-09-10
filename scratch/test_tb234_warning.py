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

res = get("/api/machines/process-sankey", {
    "article10": "0315980000",
    "target_date": "2026-08-12",
    "indicator": "rfpp"
})

top_list = res.get('data', {}).get('top_warning_machines', [])
print("Top warning machines count:", len(top_list))
for m in top_list:
    print("  Rank:", m.get('rank'), "Machine:", m.get('machine'), "Col:", m.get('workcenter_col'), "Impact:", m.get('impact_score'))
