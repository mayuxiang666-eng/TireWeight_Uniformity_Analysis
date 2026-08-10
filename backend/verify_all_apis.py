import urllib.request, json, sys

# 设置 utf-8 输出
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 50)
print("All API Verification")
print("=" * 50)

tests = [
    ("Warning articles (rfpp)", "http://127.0.0.1:8000/api/articles/warning-cpk?indicator=rfpp&only_declining=false&study_from=2026-07-07&study_to=2026-07-07&min_samples=30"),
    ("Warning articles (rfh1)", "http://127.0.0.1:8000/api/articles/warning-cpk?indicator=rfh1&only_declining=false&study_from=2026-07-07&study_to=2026-07-07&min_samples=30"),
    ("CPK daily trend", "http://127.0.0.1:8000/api/trend/cpk?grain=daily"),
    ("Machine CPK list", "http://127.0.0.1:8000/api/machines/cpk?target_date=2026-07-07&article10=0315980000&indicator=rfpp&min_samples=10"),
    ("Machine CPK trend", "http://127.0.0.1:8000/api/machines/cpk/trend?machine=TB134&workcenter_col=ccs_workcenter&indicator=rfpp&article10=0315980000"),
    ("Date range filter", "http://127.0.0.1:8000/api/filters/daterange"),
]

all_ok = True
for name, url in tests:
    try:
        res = urllib.request.urlopen(url, timeout=10)
        data = json.loads(res.read())
        status = data.get('status', 'unknown')
        if status == 'success':
            d = data.get('data', {})
            size = len(d) if isinstance(d, (list, dict)) else '-'
            print(f"  [OK] {name}: status=success, data count={size}")
        else:
            print(f"  [FAIL] {name}: {data.get('message', '?')}")
            all_ok = False
    except Exception as e:
        print(f"  [ERR] {name}: {e}")
        all_ok = False

print()
print("Result:", "ALL PASS" if all_ok else "SOME FAILED")
print("=" * 50)
