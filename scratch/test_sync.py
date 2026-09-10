import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Test TB243 for article 0315980059 and date 2026-07-18
url_ctrl = 'http://127.0.0.1:8000/api/cgrs/controlled-analysis?workcenter=TB243&date=2026-07-18&article=0315980059&indicator=rfpp'
res_ctrl = json.loads(urllib.request.urlopen(url_ctrl).read())
ev_ctrl = res_ctrl['events'][0]
ov = ev_ctrl['overall_summary']
print('=== 1. Controlled Analysis (CGRS Dialog) ===')
print('  改前加总 N:', ov['n_before'], 'CPK:', ov['cpk_before'], '➔ 改后加总 N:', ov['n_after'], 'CPK:', ov['cpk_after'])
print('  总体 CPK 净变:', ov['cpk_diff'], '| 全路径总体增幅:', ov['yoy_pct'], '%')

url_rec = 'http://127.0.0.1:8000/api/cgrs/records?workcenter=TB243&date=2026-07-18&article=0315980059&indicator=rfpp'
res_rec = json.loads(urllib.request.urlopen(url_rec).read())
comp = res_rec['comparison']
print('=== 2. CGRS Records / Sankey Node Comparison ===')
print('  改前加总 N:', comp['latest_n_before'], 'CPK:', comp['latest_cpk_before'], '➔ 改后加总 N:', comp['latest_n_after'], 'CPK:', comp['latest_cpk_after'])
print('  总体 CPK 净变:', comp['latest_cpk_diff'], '| 全路径总体增幅:', comp['latest_yoy_pct'], '%')

# Verify exact match
match = (
    ov['n_before'] == comp['latest_n_before'] and
    ov['n_after'] == comp['latest_n_after'] and
    ov['cpk_before'] == comp['latest_cpk_before'] and
    ov['cpk_after'] == comp['latest_cpk_after'] and
    ov['yoy_pct'] == comp['latest_yoy_pct']
)
print('\n=== VERIFICATION RESULT ===')
print('Is 100% Strictly Identical:', match)
