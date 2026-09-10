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

def test_endpoints():
    print("1. Testing /api/machines/process-sankey for top_warning_machines...")
    sankey_res = get("/api/machines/process-sankey", {
        "article10": "0314176000",
        "indicator": "rfpp",
        "target_date": "2026-08-13"
    })
    data = sankey_res.get("data", {})
    top_warn = data.get("top_warning_machines", [])
    print(f"Top warning machines: {json.dumps(top_warn, ensure_ascii=False, indent=2)}")

    print("\n2. Testing /api/cgrs/controlled-analysis...")
    ctrl_res = get("/api/cgrs/controlled-analysis", {
        "workcenter": "TB122",
        "date": "2026-08-13",
        "article": "0314176000",
        "indicator": "rfpp",
        "second_workcenter_col": "ct_workcenter"
    })
    print(f"Controlled analysis response summary:")
    print(f"  has_cgrs: {ctrl_res.get('has_cgrs')}")
    print(f"  events_count: {ctrl_res.get('events_count')}")
    print(f"  conclusion_type: {ctrl_res.get('conclusion_type')}")
    print(f"  conclusion_text: {ctrl_res.get('conclusion_text')}")
    print(f"  second_machines: {ctrl_res.get('second_machines')}")
    if ctrl_res.get('events'):
        print(f"  paths in first event: {json.dumps(ctrl_res['events'][0].get('paths', []), ensure_ascii=False, indent=2)}")

    print("\n3. Testing /api/cgrs/controlled-analysis with nonexistent CGRS...")
    no_cgrs = get("/api/cgrs/controlled-analysis", {
        "workcenter": "TB999",
        "date": "2026-08-13",
        "indicator": "rfpp"
    })
    print(f"No CGRS response: {no_cgrs.get('conclusion_type')}, message: {no_cgrs.get('message')}")

if __name__ == "__main__":
    test_endpoints()
