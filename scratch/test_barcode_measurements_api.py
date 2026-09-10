import sys
sys.path.insert(0, "untitled1_v2/backend")
from main import get_article_barcode_measurements, reload_duckdb_data

reload_duckdb_data()

for ind in ["rfpp", "rfh1", "cony", "weight"]:
    print(f"\n--- Testing get_article_barcode_measurements for indicator={ind} ---")
    res = get_article_barcode_measurements(
        article10="0312053000",
        target_date="2026-08-10",
        indicator=ind
    )
    print("Status:", res.get("status"))
    summary = res.get("summary", {})
    print("Summary:", summary)
    data = res.get("data", [])
    print(f"Data rows: {len(data)}, Sample 1st row: {data[0] if data else None}")
