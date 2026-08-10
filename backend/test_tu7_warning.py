from main import get_machines_cpk

res = get_machines_cpk(target_date='2026-07-07', article10='0315508000', indicator='rfh1', min_samples=10)
tu_rows = res['data'].get('终检-均匀性 (TU)', [])
tu7 = [r for r in tu_rows if r['machine'] == 'TU7']

print("TU7 Warning Result:")
if tu7:
    row = tu7[0]
    print(f"  Machine: {row['machine']}")
    print(f"  Multi CPK: {row['multi_cpk']}")
    print(f"  Multi Is Warning: {row['multi_is_warning']}")
    print(f"  Multi Rule A: {row['multi_rule_a']} (count: {row['multi_rule_a_count']})")
    print(f"  Multi Rule B: {row['multi_rule_b']}")
    print(f"  Multi Warning Threshold: {row['multi_warning_threshold']}")
else:
    print("  TU7 not found in response")
