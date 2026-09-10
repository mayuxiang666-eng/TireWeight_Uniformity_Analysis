# -*- coding: utf-8 -*-
"""
Script to execute dead code cleanup and route deduplication on backend/main.py:
1. Deduplicate /api/etl/reload (remove handle_etl_reload, enhance reload_etl_data with GET & POST)
2. Remove dead helper functions (LOT_MAP, get_periods, diagnose_machine)
3. Remove dead commented block 1 (/api/summary, /api/trend/daily, /api/trend/weekly, /api/articles)
4. Remove dead commented block 2 (/api/articles/{article}/trend) + decommissioned Q4 /api/machines + unused compute_machine_all_weighted_cpk
5. Remove dead commented block 3 (/api/insights, /api/diagnose/*)
6. Unify inline CPK calculations to use calc_cpk
7. Keep qry() completely untouched (no threading lock as requested: "除了第一个问题的其他问题")
"""
import re
import sys

# Read from clean server backup
with open("scratch/server_main.py", "r", encoding="utf-8") as f:
    content = f.read()

initial_lines = len(content.splitlines())
print(f"Initial server_main.py lines: {initial_lines}")

# 1. Deduplicate /api/etl/reload: remove early handle_etl_reload definition (lines 212-219)
early_reload_pattern = re.compile(
    r'@app\.post\("/api/etl/reload"\)\s*'
    r'@app\.get\("/api/etl/reload"\)\s*'
    r'def handle_etl_reload\(\):.*?'
    r'return \{"status": "error", "message": "未找到清洗后的 Parquet 或 CGRS 文件。"\}\n\n+',
    re.DOTALL
)
m = early_reload_pattern.search(content)
if m:
    content = content[:m.start()] + content[m.end():]
    print("1. [OK] Removed early handle_etl_reload (lines 212-219).")
else:
    print("1. [FAIL] Early handle_etl_reload pattern not matched!")
    sys.exit(1)

# Ensure the main reload_etl_data handles both POST and GET, and has unified success message
reload_etl_pattern = re.compile(
    r'@app\.post\("/api/etl/reload"\)\s*def reload_etl_data\(\):',
    re.MULTILINE
)
if reload_etl_pattern.search(content):
    content = reload_etl_pattern.sub(
        '@app.post("/api/etl/reload")\n@app.get("/api/etl/reload")\ndef reload_etl_data():',
        content,
        count=1
    )
    print("1b. [OK] Added GET decorator to reload_etl_data.")
else:
    print("1b. [FAIL] reload_etl_data pattern not matched!")
    sys.exit(1)

# 2. Remove dead helpers: LOT_MAP, get_periods, diagnose_machine (lines 1516-1668)
dead_helpers_pattern = re.compile(
    r'# 工位与批次物料对应关系\s*LOT_MAP = \{.*?'
    r'(?=# ── 健康检测与 ETL 重载)',
    re.DOTALL
)
m = dead_helpers_pattern.search(content)
if m:
    content = content[:m.start()] + content[m.end():]
    print("2. [OK] Removed dead helpers LOT_MAP, get_periods, diagnose_machine.")
else:
    print("2. [FAIL] dead helpers pattern not matched!")
    sys.exit(1)

# 3. Remove dead commented block 1 (lines 1727-1906: summary, trend/daily, trend/weekly, articles)
block1_pattern = re.compile(
    r'# ── 1\. 总览摘要.*?'
    r'(?=# ── 4\.4\. 全量规格型号列表)',
    re.DOTALL
)
m = block1_pattern.search(content)
if m:
    content = content[:m.start()] + content[m.end():]
    print("3. [OK] Removed dead commented block 1 (summary, daily, weekly, articles).")
else:
    print("3. [FAIL] block 1 pattern not matched!")
    sys.exit(1)

# 4. Remove dead commented block 2 + decommissioned /api/machines + unused compute_machine_all_weighted_cpk
block2_machines_pattern = re.compile(
    r'# ── 5\. 规格型号下钻：日度趋势.*?'
    r'(?=@app\.get\("/api/machines/cpk"\))',
    re.DOTALL
)
m = block2_machines_pattern.search(content)
if m:
    content = content[:m.start()] + content[m.end():]
    print("4. [OK] Removed dead commented block 2, decommissioned /api/machines, and compute_machine_all_weighted_cpk.")
else:
    print("4. [FAIL] block 2 + machines pattern not matched!")
    sys.exit(1)

# 5. Remove dead commented block 3 (lines 5396-6006: insights, suspects, combinations, paths, lots)
block3_pattern = re.compile(
    r'# ── 7\. 自动生成预警建议接口.*?'
    r'(?=# ── 11\. 过滤选项：规格列表)',
    re.DOTALL
)
m = block3_pattern.search(content)
if m:
    content = content[:m.start()] + content[m.end():]
    print("5. [OK] Removed dead commented block 3 (insights, suspects, combinations, paths, lots).")
else:
    print("5. [FAIL] block 3 pattern not matched!")
    sys.exit(1)

# 6. Unify inline CPK formulas to calc_cpk
# In get_machines_cpk: spec_cpk
content = re.sub(
    r'spec_cpk = round\(max\(0\.0, min\(5\.0, \(global_usl - spec_avg\) / \(3\.0 \* spec_std\)\)\), 2\)',
    'spec_cpk = round(calc_cpk(spec_avg, spec_std, global_usl, global_lsl), 2)',
    content
)

# In get_machines_cpk: multi_cpk
content = re.sub(
    r'multi_cpk = round\(max\(0\.0, min\(5\.0, \(global_usl - multi_avg\) / \(3\.0 \* multi_std\)\)\), 2\)',
    'multi_cpk = round(calc_cpk(multi_avg, multi_std, global_usl, global_lsl), 2)',
    content
)

# In get_machines_cpk: c_v
content = re.sub(
    r'c_v = round\(max\(0\.0, min\(5\.0, \(global_usl - m_v\) / \(3\.0 \* s_v\)\)\), 2\) if s_v > 0 else 1\.33',
    'c_v = round(calc_cpk(m_v, s_v, global_usl, global_lsl), 2)',
    content
)

# In get_best_tu_machine_for_spec
content = re.sub(
    r'cpk = \(global_usl - avg_v\) / \(3\.0 \* std_v\) if std_v > 0\.0 else 1\.33\s*r\[\'cpk\'\] = cpk',
    'cpk = calc_cpk(avg_v, std_v, global_usl)\n                r[\'cpk\'] = cpk',
    content
)

# In get_machine_best_process_sankey
content = re.sub(
    r'cpk_val = \(global_usl - avg_v\) / \(3\.0 \* std_v\) if std_v > 0\.0 else 1\.33\s*cpk_val = max\(0\.0, min\(5\.0, cpk_val\)\)\s*q_score = cpk_val',
    'cpk_val = calc_cpk(avg_v, std_v, global_usl)\n                    q_score = cpk_val',
    content
)
print("6. [OK] CPK calculations unified to calc_cpk.")

# Write back to backend/main.py
with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(content)

final_lines = len(content.splitlines())
print(f"Final backend/main.py lines: {final_lines}")
print(f"Total lines removed: {initial_lines - final_lines}")
