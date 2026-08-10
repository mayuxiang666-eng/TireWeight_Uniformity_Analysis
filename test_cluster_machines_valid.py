import urllib.request
import json

try:
    url = 'http://127.0.0.1:8000/api/machines?baseline_from=2026-06-13&baseline_to=2026-06-22&study_from=2026-06-23&study_to=2026-07-02&min_yield=50&workcenter_col=tread&cluster_id=0&cluster_type=anomaly'
    response = urllib.request.urlopen(url)
    data = json.loads(response.read())
    print("Machines response status:", data.get("status"))
    print("Fetched machines count:", len(data.get("data", [])))
    if data.get("data"):
        print("First machine details:")
        print(json.dumps(data.get("data")[0], indent=2))
except Exception as e:
    print("Error during request:", e)
