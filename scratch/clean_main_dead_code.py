# -*- coding: utf-8 -*-
"""
Script to clean up dead commented code, remove decommissioned /api/machines route,
merge duplicate /api/etl/reload route, and ensure unified calc_cpk in backend/main.py.
"""
import re

with open("scratch/server_main.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Deduplicate /api/etl/reload: remove early handle_etl_reload definition
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
    print("1. Removed early handle_etl_reload.")
else:
    print("Warning: early handle_etl_reload pattern not matched.")

# Ensure the main reload_etl_data handles both POST and GET
content = re.sub(
    r'@app\.post\("/api/etl/reload"\)\s*def reload_etl_data\(\):',
    '@app.post("/api/etl/reload")\n@app.get("/api/etl/reload")\ndef reload_etl_data():',
    content
)
print("1b. Added GET decorator to reload_etl_data.")

# 2. Remove dead helpers: LOT_MAP and get_periods
dead_helpers_pattern = re.compile(
    r'# 工位与批次物料对应关系\s*LOT_MAP = \{.*?'
    r'def get_periods\(.*?\n    return baseline_from, baseline_to, study_from, study_to\n\n+',
    re.DOTALL
)
m = dead_helpers_pattern.search(content)
if m:
    content = content[:m.start()] + content[m.end():]
    print("2. Removed dead helpers LOT_MAP and get_periods.")
else:
    print("Warning: dead helpers pattern not matched.")

# 3. Remove dead commented block 1 (# ── 1. 总览摘要 ... up to # ── 4.4. 全量规格型号列表)
block1_pattern = re.compile(
    r'# ── 1\. 总览摘要.*?'
    r'(?=# ── 4\.4\. 全量规格型号列表)',
    re.DOTALL
)
m = block1_pattern.search(content)
if m:
    content = content[:m.start()] + content[m.end():]
    print("3. Removed dead commented block 1 (summary, daily, weekly, articles).")
else:
    print("Warning: block 1 pattern not matched.")

# 4. Remove dead commented block 2 (# ── 5. 规格型号下钻：日度趋势)
block2_pattern = re.compile(
    r'# ── 5\. 规格型号下钻：日度趋势.*?'
    r'(?=# ── 6\.)',
    re.DOTALL
)
m = block2_pattern.search(content)
if m:
    content = content[:m.start()] + content[m.end():]
    print("4. Removed dead commented block 2 (articles/{article}/trend).")
else:
    print("Warning: block 2 pattern not matched.")

# 5. Remove decommissioned Q4 route @app.get("/api/machines") (starts at # ── 6. 工位机台异常排行 up to @app.get("/api/machines/cpk"))
machines_pattern = re.compile(
    r'# ── 6\. 工位机台异常排行.*?'
    r'(?=@app\.get\("/api/machines/cpk"\))',
    re.DOTALL
)
m = machines_pattern.search(content)
if m:
    content = content[:m.start()] + content[m.end():]
    print("5. Removed decommissioned /api/machines route (Q4).")
else:
    print("Warning: machines pattern not matched.")

# 6. Remove dead commented block 3 (# ── 7. 自动生成预警建议接口 ... up to # ── 11. 过滤选项：规格列表)
block3_pattern = re.compile(
    r'# ── 7\. 自动生成预警建议接口.*?'
    r'(?=# ── 11\. 过滤选项：规格列表)',
    re.DOTALL
)
m = block3_pattern.search(content)
if m:
    content = content[:m.start()] + content[m.end():]
    print("6. Removed dead commented block 3 (insights, suspects, combinations, paths, lots).")
else:
    print("Warning: block 3 pattern not matched.")

# 7. Unify CPK in main.py:
# Replace compute_machine_all_weighted_cpk: cpk_i = max(0.0, min(5.0, cpk_i))
content = re.sub(
    r'cpk_i = \(spec_usl - m_v\) / \(3\.0 \* s_v \+ 1e-5\) if s_v > 0 else 1\.33\s*cpk_i = max\(0\.0, min\(5\.0, cpk_i\)\)',
    'cpk_i = calc_cpk(m_v, s_v, spec_usl)',
    content
)

# Replace get_machines_cpk: spec_cpk = round(max(0.0, min(5.0, ...)))
content = re.sub(
    r'spec_cpk = round\(max\(0\.0, min\(5\.0, \(global_usl - spec_avg\) / \(3\.0 \* spec_std\)\)\), 2\) if spec_std > 0 else 1\.33',
    'spec_cpk = round(calc_cpk(spec_avg, spec_std, global_usl, global_lsl), 2)',
    content
)

# Replace get_machines_cpk: multi_cpk = round(max(0.0, min(5.0, ...)))
content = re.sub(
    r'multi_cpk = round\(max\(0\.0, min\(5\.0, \(global_usl - multi_avg\) / \(3\.0 \* multi_std\)\)\), 2\) if multi_std > 0 else 1\.33',
    'multi_cpk = round(calc_cpk(multi_avg, multi_std, global_usl, global_lsl), 2)',
    content
)

# Replace historical c_v in get_machines_cpk
content = re.sub(
    r'c_v = round\(max\(0\.0, min\(5\.0, \(global_usl - m_v\) / \(3\.0 \* s_v\)\)\), 2\) if s_v > 0 else 1\.33',
    'c_v = round(calc_cpk(m_v, s_v, global_usl, global_lsl), 2)',
    content
)

# Replace get_best_tu_machine_for_spec
content = re.sub(
    r'cpk = \(global_usl - avg_v\) / \(3\.0 \* std_v\) if std_v > 0\.0 else 1\.33\s*r\[\'cpk\'\] = cpk',
    'cpk = calc_cpk(avg_v, std_v, global_usl)\n                r[\'cpk\'] = cpk',
    content
)

# Replace get_machine_best_process_sankey q_score cpk_val
content = re.sub(
    r'cpk_val = \(global_usl - avg_v\) / \(3\.0 \* std_v\) if std_v > 0\.0 else 1\.33\s*cpk_val = max\(0\.0, min\(5\.0, cpk_val\)\)\s*q_score = cpk_val',
    'cpk_val = calc_cpk(avg_v, std_v, global_usl)\n                    q_score = cpk_val',
    content
)

with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(content)

print(f"Cleaned main.py written successfully! Total lines: {len(content.splitlines())}")
