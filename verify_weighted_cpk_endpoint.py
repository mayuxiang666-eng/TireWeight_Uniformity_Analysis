import urllib.request
import json

try:
    url = 'http://127.0.0.1:8000/api/trend/cpk?grain=daily'
    response = urllib.request.urlopen(url)
    data = json.loads(response.read())
    print("CPK API Status:", data.get("status"))
    if data.get("status") == "success":
        print("Dates count:", len(data.get("data", {}).get("dates", [])))
        print("Groups in trend:", list(data.get("data", {}).get("cpk_trends", {}).keys()))
        for g, vals in data.get("data", {}).get("cpk_trends", {}).items():
            valid_vals = [v for v in vals if v is not None]
            print(f"  Group {g}: total={len(vals)}, non-null={len(valid_vals)}, first 3 non-null={valid_vals[:3]}")
    else:
        print("API Error Message:", data.get("message"))
except Exception as e:
    print("Verification request failed:", e)
