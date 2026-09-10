import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from main import get_cgrs_records, get_machine_process_sankey

def test_all_indicators():
    for ind in ["rfpp", "rfh1", "cony", "weight"]:
        print(f"--- Testing indicator: {ind} ---")
        res_cgrs = get_cgrs_records(workcenter="TB222", date="2026-08-13", article="0314176000", indicator=ind)
        assert res_cgrs.get("status") == "success", f"Error: {res_cgrs.get('message')}"
        comp = res_cgrs.get("comparison", {})
        print(f"  get_cgrs_records [{ind}]: has_cgrs={comp.get('has_cgrs')}, YoY={comp.get('latest_yoy_pct')}%, events={comp.get('events_count')}")

        res_sankey = get_machine_process_sankey(article10="0314176000", target_date="2026-08-13", indicator=ind, min_samples=1)
        assert res_sankey.get("status") == "success", f"Error: {res_sankey.get('message')}"
        nodes = res_sankey.get("data", {}).get("nodes", [])
        gt_with_cgrs = [n for n in nodes if n.get("cgrs_comparison") and n["cgrs_comparison"].get("has_cgrs")]
        print(f"  get_machine_process_sankey [{ind}]: Total nodes={len(nodes)}, GT with CGRS={len(gt_with_cgrs)}")
        for gn in gt_with_cgrs:
            c = gn["cgrs_comparison"]
            print(f"    -> {gn['name']}: YoY={c.get('latest_yoy_pct')}%, pre={c.get('latest_cpk_before')} (N={c.get('latest_n_before')}), post={c.get('latest_cpk_after')} (N={c.get('latest_n_after')})")

    print("\n[SUCCESS] All indicators passed CGRS comparison tests successfully!")

if __name__ == "__main__":
    test_all_indicators()
