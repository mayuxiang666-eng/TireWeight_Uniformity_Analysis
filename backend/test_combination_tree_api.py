import urllib.request
import urllib.parse
import json
import sys

def run_tests():
    base_url = "http://127.0.0.1:8000/api/machines/combination-tree"
    
    # 1. Test normal case
    params = {
        "spec": "0315626056",
        "start_wc": "gt_workcenter",
        "end_wc": "tu_first_workcenter",
        "indicator": "rfpp"
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    print(f"Test 1: Call combination-tree API with valid parameters:")
    try:
        with urllib.request.urlopen(url) as res:
            data = json.loads(res.read().decode('utf-8'))
            assert data.get("status") == "success", f"API status is {data.get('status')}"
            payload = data.get("data", {})
            assert "study_columns" in payload, "Missing study_columns in response"
            assert "paths" in payload, "Missing paths in response"
            print("  - Normal case: SUCCESS. Paths count:", len(payload["paths"]))
    except Exception as e:
        print("  - Normal case: FAILED:", e)
        sys.exit(1)

    # 2. Test invalid workcenter name validation
    invalid_params = {
        "spec": "0315626056",
        "start_wc": "invalid_wc",
        "end_wc": "tu_first_workcenter"
    }
    url2 = f"{base_url}?{urllib.parse.urlencode(invalid_params)}"
    print(f"\nTest 2: Call combination-tree API with invalid workcenter:")
    try:
        with urllib.request.urlopen(url2) as res:
            data = json.loads(res.read().decode('utf-8'))
            assert data.get("status") == "error", "API should return error status"
            assert "Invalid workcenters" in data.get("message", ""), f"Error message mismatch: {data.get('message')}"
            print("  - Invalid workcenter: SUCCESS (returned error correctly)")
    except Exception as e:
        print("  - Invalid workcenter: FAILED:", e)
        sys.exit(1)

    # 3. Test date range filtering
    dr_params = {
        "spec": "0315626056",
        "start_wc": "gt_workcenter",
        "end_wc": "tu_first_workcenter",
        "start_date": "2026-07-01",
        "end_date": "2026-07-15"
    }
    url3 = f"{base_url}?{urllib.parse.urlencode(dr_params)}"
    print(f"\nTest 3: Call combination-tree API with date range:")
    try:
        with urllib.request.urlopen(url3) as res:
            data = json.loads(res.read().decode('utf-8'))
            assert data.get("status") == "success"
            print("  - Date range filtering: SUCCESS")
    except Exception as e:
        print("  - Date range filtering: FAILED:", e)
        sys.exit(1)

    print("\nALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
