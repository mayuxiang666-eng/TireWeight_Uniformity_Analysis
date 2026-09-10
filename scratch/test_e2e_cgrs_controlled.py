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

def run_tests():
    # 1. 查找 2026-08-13 有 CGRS 记录的机台
    print("=== Testing multiple cases ===")
    
    test_cases = [
        {"workcenter": "TB122", "date": "2026-08-13", "article": "0314176000", "indicator": "rfpp", "second_workcenter_col": "ct_workcenter"},
        {"workcenter": "TB183", "date": "2026-08-13", "article": "0312426000", "indicator": "rfpp", "second_workcenter_col": "ct_workcenter"},
        {"workcenter": "TB175", "date": "2026-08-13", "article": "0359321000", "indicator": "rfpp", "second_workcenter_col": "tu_first_workcenter"},
        {"workcenter": "TB114", "date": "2026-08-13", "article": "0312840000", "indicator": "weight", "second_workcenter_col": "ct_workcenter"},
    ]

    for tc in test_cases:
        res = get("/api/cgrs/controlled-analysis", tc)
        print(f"\nWorkcenter: {tc['workcenter']}, Date: {tc['date']}, Article: {tc['article']}, Col: {tc['second_workcenter_col']}")
        print(f"  Status: {res.get('status')}, has_cgrs: {res.get('has_cgrs')}, events: {res.get('events_count')}")
        print(f"  Conclusion Type: {res.get('conclusion_type')}")
        print(f"  Conclusion Text: {res.get('conclusion_text')}")
        print(f"  Second Machines: {res.get('second_machines')}")
        if res.get('events') and len(res['events']) > 0:
            for p in res['events'][0].get('paths', []):
                print(f"    -> Path: {p['path_label']} | Pre: N={p['n_before']} CPK={p['cpk_before']} | Post: N={p['n_after']} CPK={p['cpk_after']} | YoY: {p['yoy_pct']}%")

if __name__ == "__main__":
    run_tests()
