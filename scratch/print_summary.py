import json
import pandas as pd

with open("untitled1_v2/scratch/cgrs_path_results.json", encoding="utf-8") as f:
    data = json.load(f)

df = pd.DataFrame(data)

print("=== 1. 样本充足的有效对比路径 (n_b >= 10 and n_a >= 10, 共 15 条) ===")
valid = df[df['category'] == '有效对比路径 (样本充足 >=10)'].sort_values('rfpp_cpk_diff', ascending=False)
cols_show = ['path', 'n_b', 'n_a', 'rfpp_m_b', 'rfpp_m_a', 'rfpp_m_diff', 'rfpp_s_b', 'rfpp_s_a', 'rfpp_s_diff', 'rfpp_cpk_b', 'rfpp_cpk_a', 'rfpp_cpk_diff', 'rfpp_cpk_pct',
             'rfh1_m_b', 'rfh1_m_a', 'rfh1_m_diff', 'rfh1_s_b', 'rfh1_s_a', 'rfh1_s_diff', 'rfh1_cpk_b', 'rfh1_cpk_a', 'rfh1_cpk_diff', 'rfh1_cpk_pct']
print(valid[cols_show].to_string(index=False))

print("\n=== 2. 小样本对比路径 (0 < n_b < 10 或 0 < n_a < 10, 共 13 条) ===")
small = df[df['category'] == '小样本对比路径 (<10)'].sort_values('rfpp_cpk_diff', ascending=False)
print(small[cols_show].to_string(index=False))

print("\n=== 3. 仅在修改后出现的新路径 (共 50 条中的前 10 条示例) ===")
post_only = df[df['category'] == '仅修改后存在路径']
print(post_only[['path', 'n_b', 'n_a', 'rfpp_m_a', 'rfpp_s_a', 'rfpp_cpk_a', 'rfh1_m_a', 'rfh1_s_a', 'rfh1_cpk_a']].head(10).to_string(index=False))
