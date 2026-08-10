# === CELL 1 ===
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 设置 matplotlib 画图风格，使其美观、现代
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans'] # 确保中文正常显示
plt.rcParams['axes.unicode_minus'] = False # 确保负号正常显示
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12

# === CELL 2 ===
import ipynbname

# 获取当前 Jupyter Notebook 的绝对路径
try:
    nb_path = ipynbname.path()
    print(f"Jupyter 自身路径: {nb_path}")
except Exception as e:
    print(f"获取失败: {e}")


#

# === CELL 3 ===
# 读取清洗后的 Parquet 数据集
data_path = os.path.join("data_clean", "E://111//yield_flat_table_30d_2_cleaned2.parquet")
if not os.path.exists(data_path):
    data_path = "yield_flat_table_30d_2_cleaned2.parquet"

print(f"正在读取最新清洗后的数据集: {data_path}")
df = pd.read_parquet(data_path)
print(f"数据读取成功！共计 {len(df):,} 行，{len(df.columns)} 列。")

# === CELL 4 ===
# 2.1 独立规格型号 (article10) 数量与异常率
unique_articles = df['article10'].nunique()
anomaly_counts = df['grade_anomaly_new'].value_counts()
anomaly_rate = df['grade_anomaly_new'].mean() * 100

print(f"1. 独立规格型号 (article10) 数量: {unique_articles} 种")
print(f"2. 数据记录总条数: {len(df):,} 条")
print(f"   - 正常记录数 (0): {anomaly_counts.get(0, 0):,} 条 ({100 - anomaly_rate:.2f}%)")
print(f"   - 异常记录数 (1): {anomaly_counts.get(1, 0):,} 条 ({anomaly_rate:.2f}%)")

# === CELL 5 ===
# 2.2 各工位 (Workcenter) 独立设备数量统计
wc_cols = [col for col in df.columns if 'workcenter' in col]
wc_nunique = df[wc_cols].nunique().reset_index()
wc_nunique.columns = ['工位列名称', '独立设备/工位数']
wc_nunique = wc_nunique.sort_values(by='独立设备/工位数', ascending=False)

print("=== 各工位 (Workcenter) 独立设备数排名 ===")
display(wc_nunique)

# === CELL 6 ===
# 2.3 各部件批次 (Lot) 独立批次数量统计
lot_cols = [col for col in df.columns if 'lot' in col]
lot_nunique = df[lot_cols].nunique().reset_index()
lot_nunique.columns = ['部件批次列名称', '独立批次数量 (Lots)']
lot_nunique = lot_nunique.sort_values(by='独立批次数量 (Lots)', ascending=False)

print("=== 各部件批次 (Lot) 独立批次数量排名 ===")
display(lot_nunique)

# === CELL 7 ===
# 按日度统计产量和异常率
df['date'] = df['ct_shiftdate'].dt.date
daily_stats = df.groupby('date')['grade_anomaly_new'].agg(['count', 'mean']).reset_index()
daily_stats = daily_stats.sort_values('date').iloc[:-1]
daily_stats['anomaly_rate_pct'] = daily_stats['mean'] * 100

# 计算每日正常和异常的样本量
daily_stats['anomaly_count'] = daily_stats['count'] * daily_stats['mean']
daily_stats['normal_count'] = daily_stats['count'] - daily_stats['anomaly_count']

# 绘制双 Y 轴图表
fig, ax1 = plt.subplots(figsize=(14, 7))

# 1. 绘制日产量 (正常 vs 异常，堆叠柱状图) - 左轴
color_normal = '#1a73e8'   # 蓝色代表正常产量
color_anomaly = '#d93025'  # 红色代表异常
ax1.bar(daily_stats['date'], daily_stats['normal_count'], color=color_normal, alpha=0.4, width=0.6, label='正常样本量')
ax1.bar(daily_stats['date'], daily_stats['anomaly_count'], bottom=daily_stats['normal_count'], color=color_anomaly, alpha=0.8, width=0.6, label='异常样本量')

ax1.set_xlabel('生产日期 (Date)', labelpad=10)
ax1.set_ylabel('日度产量 / 样本量 (条)', color='black')
ax1.tick_params(axis='y', labelcolor='black')
ax1.set_xticks(daily_stats['date'])
ax1.set_xticklabels(daily_stats['date'], rotation=45, ha='right')

# 2. 绘制日异常率 (%) - 折线图 - 右轴
ax2 = ax1.twinx()
ax2.plot(daily_stats['date'], daily_stats['anomaly_rate_pct'], color=color_anomaly, marker='o', linewidth=2.5, label='日异常率 (右轴)')
ax2.set_ylabel('物理指标异常率 (%)', color=color_anomaly)
ax2.tick_params(axis='y', labelcolor=color_anomaly)
ax2.grid(False)

# 绘制平均异常率辅助线
mean_daily_anomaly = daily_stats['anomaly_rate_pct'].mean()
ax2.axhline(mean_daily_anomaly, color='#f9ab00', linestyle='--', linewidth=1.2, label=f'平均异常率 ({mean_daily_anomaly:.2f}%)')

# 合并图例
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

plt.title("轮胎日度产量与物理指标异常率变化趋势对比 (双 Y 轴)", fontsize=14, weight='bold', pad=15)
fig.tight_layout()
plt.show()

# === CELL 8 ===
# 按周度统计产量和异常率 (使用每周一日期代表该周)
df['week_start'] = df['ct_shiftdate'].dt.to_period('W').dt.start_time
weekly_stats = df.groupby('week_start')['grade_anomaly_new'].agg(['count', 'mean']).reset_index()
weekly_stats['anomaly_rate_pct'] = weekly_stats['mean'] * 100

# 格式化日期字符串
weekly_stats['week_label'] = weekly_stats['week_start'].dt.strftime('%Y-%m-%d')

# 绘制双 Y 轴图表
fig, ax1 = plt.subplots(figsize=(12, 6.5))

# 1. 绘制周产量 (条数) - 柱状图 (左轴)
color_volume_wk = '#1a73e8'
ax1.bar(weekly_stats['week_label'], weekly_stats['count'], color=color_volume_wk, alpha=0.35, width=0.4, label='周产量 (左轴)')
ax1.set_xlabel('周起始日期 (Week Start)', labelpad=10)
ax1.set_ylabel('周度产量 / 样本量 (条)', color=color_volume_wk)
ax1.tick_params(axis='y', labelcolor=color_volume_wk)

# 2. 绘制周异常率 (%) - 折线图 (右轴)
ax2 = ax1.twinx()
color_anomaly_wk = '#d93025'
ax2.plot(weekly_stats['week_label'], weekly_stats['anomaly_rate_pct'], color=color_anomaly_wk, marker='^', markersize=8, linewidth=2.5, label='周异常率 (右轴)')
ax2.set_ylabel('物理指标异常率 (%)', color=color_anomaly_wk)
ax2.tick_params(axis='y', labelcolor=color_anomaly_wk)
ax2.grid(False)

# 在周折线上标记具体异常率的百分比文字标签
for idx, row in weekly_stats.iterrows():
    ax2.text(idx, row['anomaly_rate_pct'] + 0.1, f"{row['anomaly_rate_pct']:.2f}%", 
             ha='center', va='bottom', fontsize=10, weight='bold', color='#c2185b')

# 绘制平均异常率辅助线
mean_weekly_anomaly = weekly_stats['anomaly_rate_pct'].mean()
ax2.axhline(mean_weekly_anomaly, color='#f9ab00', linestyle='--', linewidth=1.2, label=f'平均异常率 ({mean_weekly_anomaly:.2f}%)')

# 合并图例
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

plt.title("轮胎周度产量与物理指标异常率变化趋势对比 (双 Y 轴)", fontsize=14, weight='bold', pad=15)
fig.tight_layout()
plt.show()

# === CELL 9 ===
# 5.1 设定基准期与研究期的日期范围（支持日维度自定义）
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

min_date_val = df['ct_shiftdate'].min().date()
max_date_val = df['ct_shiftdate'].max().date()

# 默认选取前 10 天为基准期，其余为研究期
baseline_start = str(min_date_val)
baseline_end = str(min_date_val + pd.Timedelta(days=9))
study_start = str(min_date_val + pd.Timedelta(days=10))
study_end = str(max_date_val)

print(f"数据日期范围: {min_date_val} 至 {max_date_val}")
print(f"基准期: {baseline_start} 至 {baseline_end}")
print(f"研究期: {study_start} 至 {study_end}")

# 过滤数据
df_baseline = df[(df['ct_shiftdate'].dt.date >= pd.to_datetime(baseline_start).date()) &
                 (df['ct_shiftdate'].dt.date <= pd.to_datetime(baseline_end).date())].copy()

df_study = df[(df['ct_shiftdate'].dt.date >= pd.to_datetime(study_start).date()) &
               (df['ct_shiftdate'].dt.date <= pd.to_datetime(study_end).date())].copy()

n_baseline = len(df_baseline)
n_study = len(df_study)
print(f"基准期样本数: {n_baseline:,}，研究期样本数: {n_study:,}")

if n_baseline > 0 and n_study > 0:
    # 计算整体轮胎级别异常率变化
    r_baseline = df_baseline['grade_anomaly_new'].mean()
    r_study = df_study['grade_anomaly_new'].mean()
    delta_r_pct = (r_study - r_baseline) * 100
    print(f"整体轮胎异常率变化: {r_baseline*100:.4f}% -> {r_study*100:.4f}% (变化差值: {delta_r_pct:+.4f} 百分点)")

    # ==============================================================================
    # 1. 规格型号维度 (article10) 异常率贡献度分析
    # ==============================================================================
    # 计算两期各规格的样本数与异常数
    baseline_art = df_baseline.groupby('article10')['grade_anomaly_new'].agg(['count', 'sum']).rename(
        columns={'count': 'n_base', 'sum': 'anomaly_base'}
    )
    study_art = df_study.groupby('article10')['grade_anomaly_new'].agg(['count', 'sum']).rename(
        columns={'count': 'n_study', 'sum': 'anomaly_study'}
    )

    # 合并计算权重与贡献
    art_contrib = pd.merge(baseline_art, study_art, on='article10', how='outer').fillna(0)
    art_contrib['w_base'] = art_contrib['n_base'] / n_baseline
    art_contrib['w_study'] = art_contrib['n_study'] / n_study
    art_contrib['r_base'] = np.where(art_contrib['n_base'] > 0, art_contrib['anomaly_base'] / art_contrib['n_base'], 0.0)
    art_contrib['r_study'] = np.where(art_contrib['n_study'] > 0, art_contrib['anomaly_study'] / art_contrib['n_study'], 0.0)

    # 贡献百分点 = (w_study * r_study - w_base * r_base) * 100
    art_contrib['contribution_pct'] = (art_contrib['w_study'] * art_contrib['r_study'] - art_contrib['w_base'] * art_contrib['r_base']) * 100
    art_contrib['dimension'] = '规格型号 (article10)'
    art_contrib = art_contrib.reset_index().rename(columns={'article10': 'factor_name'})

    # 验证规格维度公式闭合性
    sum_art_contrib = art_contrib['contribution_pct'].sum()
    print(f"  [验证] 规格维度贡献总和: {sum_art_contrib:+.4f}% (闭合差: {abs(sum_art_contrib - delta_r_pct):.2e}%)")

    # ==============================================================================
    # 2. 机台维度 (排除检测工序，具体到加工机台) 异常率贡献度分析
    # ==============================================================================
    # 获取 12 个前工序工艺步骤列名
    wc_cols = [col for col in df.columns if 'workcenter' in col and not col.startswith(('tu_', 'tb_', 'tg_'))]

    def melt_to_machines(df_in):
        melt_cols = ['barcode', 'grade_anomaly_new']
        df_melt = df_in[melt_cols + wc_cols].copy()
        
        # 为了防止不同工序机台重名，将机台名称拼接上工序前缀
        for col in wc_cols:
            df_melt[col] = df_melt[col].apply(lambda x: f"{col}:{x}" if pd.notna(x) else np.nan)
            
        df_melted = df_melt.melt(
            id_vars=melt_cols,
            value_vars=wc_cols,
            var_name='workcenter_step',
            value_name='machine'
        )
        return df_melted.dropna(subset=['machine'])

    df_baseline_melt = melt_to_machines(df_baseline)
    df_study_melt = melt_to_machines(df_study)

    n_baseline_melt = len(df_baseline_melt)
    n_study_melt = len(df_study_melt)

    # 计算重塑后空间的异常率
    r_base_melt = df_baseline_melt['grade_anomaly_new'].mean() if n_baseline_melt > 0 else 0
    r_study_melt = df_study_melt['grade_anomaly_new'].mean() if n_study_melt > 0 else 0
    delta_r_melt_pct = (r_study_melt - r_base_melt) * 100
    print(f"  [验证] 重塑工序空间异常率变化: {r_base_melt*100:.4f}% -> {r_study_melt*100:.4f}% (变化差值: {delta_r_melt_pct:+.4f} 百分点)")

    # 计算各具体机台的样本数与异常数
    baseline_mach = df_baseline_melt.groupby('machine')['grade_anomaly_new'].agg(['count', 'sum']).rename(
        columns={'count': 'n_base', 'sum': 'anomaly_base'}
    )
    study_mach = df_study_melt.groupby('machine')['grade_anomaly_new'].agg(['count', 'sum']).rename(
        columns={'count': 'n_study', 'sum': 'anomaly_study'}
    )

    # 合并计算权重与贡献
    mach_contrib = pd.merge(baseline_mach, study_mach, on='machine', how='outer').fillna(0)
    mach_contrib['w_base'] = mach_contrib['n_base'] / n_baseline_melt if n_baseline_melt > 0 else 0.0
    mach_contrib['w_study'] = mach_contrib['n_study'] / n_study_melt if n_study_melt > 0 else 0.0
    mach_contrib['r_base'] = np.where(mach_contrib['n_base'] > 0, mach_contrib['anomaly_base'] / mach_contrib['n_base'], 0.0)
    mach_contrib['r_study'] = np.where(mach_contrib['n_study'] > 0, mach_contrib['anomaly_study'] / mach_contrib['n_study'], 0.0)

    # 贡献百分点
    mach_contrib['contribution_pct'] = (mach_contrib['w_study'] * mach_contrib['r_study'] - mach_contrib['w_base'] * mach_contrib['r_base']) * 100
    mach_contrib['dimension'] = '具体机台 (machine)'
    mach_contrib = mach_contrib.reset_index().rename(columns={'machine': 'factor_name'})

    # 验证工序机台维度公式闭合性
    sum_mach_contrib = mach_contrib['contribution_pct'].sum()
    print(f"  [验证] 机台维度贡献总和: {sum_mach_contrib:+.4f}% (闭合差: {abs(sum_mach_contrib - delta_r_melt_pct):.2e}%)")

    # ==============================================================================
    # 3. 双维度统一合并排行榜与分析对比
    # ==============================================================================
    cols_to_keep = ['factor_name', 'dimension', 'contribution_pct', 'n_base', 'n_study']
    combined_ranking = pd.concat([
        art_contrib[cols_to_keep],
        mach_contrib[cols_to_keep]
    ], axis=0)

    # 按贡献绝对值从大到小排序
    combined_ranking['abs_contribution'] = combined_ranking['contribution_pct'].abs()
    combined_ranking = combined_ranking.sort_values(by='abs_contribution', ascending=False).reset_index(drop=True)

    print("\n" + "="*80)
    print("=== 规格型号 vs 具体加工机台：异常率变化驱动力统一合并排行榜 ===")
    print("="*80)
    display(combined_ranking.head(15).style.format({'contribution_pct': '{:+.4f}%', 'abs_contribution': '{:.4f}%'}))
    print("="*80)
    
    # 维度总解释力对比总结报告
    total_abs_art_contrib = art_contrib['contribution_pct'].abs().sum()
    total_abs_wc_contrib = mach_contrib['contribution_pct'].abs().sum()

    print("\n" + "="*60)
    print("=== 双维度对异常变化率的影响/解释力对比总结报告 ===")
    print("="*60)
    print(f"1. 规格型号维度 (article10) 总绝对贡献量: {total_abs_art_contrib:.4f} 百分点")
    print(f"2. 前工序机台维度 (machine) 总绝对贡献量: {total_abs_wc_contrib:.4f} 百分点")
    print("-"*60)
    
    if total_abs_art_contrib > total_abs_wc_contrib:
        ratio = total_abs_art_contrib / (total_abs_wc_contrib + 1e-8)
        print(f"结论：【规格型号维度】的主导能力更强，其总绝对贡献量是机台维度的 {ratio:.2f} 倍。")
        print("建议：应优先从产品规格设计、配方及规格排产结构调整的角度切入治理异常。")
    else:
        ratio = total_abs_wc_contrib / (total_abs_art_contrib + 1e-8)
        print(f"结论：【前工序机台维度】的主导能力更强，其总绝对贡献量是规格维度的 {ratio:.2f} 倍。")
        print("建议：应优先从生产工艺流程稳定性、设备健康度管理及原材料一致性的角度切入治理异常。")
    print("="*60)

    # 绘图对比 Top 10 驱动因子
    fig, ax = plt.subplots(figsize=(14, 7))
    top_10 = combined_ranking.head(10)

    colors = ['#1a73e8' if d == '规格型号 (article10)' else '#d93025' for d in top_10['dimension']]
    bars = ax.bar(top_10['factor_name'], top_10['contribution_pct'], color=colors, alpha=0.75, width=0.5)
    ax.set_ylabel('对异常率变化的贡献度 (百分点)', color='black', weight='bold')
    ax.set_xlabel('驱动因素名称 (规格型号 / 工序机台)', labelpad=10, weight='bold')
    ax.set_xticks(range(len(top_10)))
    ax.set_xticklabels(top_10['factor_name'], rotation=45, ha='right', fontsize=9)
    ax.axhline(0, color='black', linewidth=0.8, linestyle='-')

    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:+.3f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3 if height >= 0 else -12),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, weight='bold')

    # 添加维度图例
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#1a73e8', alpha=0.75, label='规格型号维度 (article10)'),
        Patch(facecolor='#d93025', alpha=0.75, label='前工序机台维度 (machine)')
    ]
    ax.legend(handles=legend_elements, loc='upper right')

    plt.title("规格型号与前工序机台对整体异常率变化贡献排行 (Top 10)", fontsize=13, weight='bold', pad=15)
    plt.grid(True, linestyle=':', alpha=0.5)
    plt.tight_layout()
    plt.show()
else:
    print("当前选取的时间范围样本量为 0，请检查日期范围设置。")


# === CELL 10 ===
# 6.1 设定保留阈值，计算所需规格数量
threshold = 0.80  # 目标保留 80% 的总驱动贡献量

# 复制规格型号的贡献表，并根据绝对值进行排序（前面已排好，此处做安全复制）
plot_df = art_contrib.copy()
plot_df['abs_contribution'] = plot_df['contribution_pct'].abs()
plot_df = plot_df.sort_values(by='abs_contribution', ascending=False).reset_index(drop=True)

total_driving_contrib = plot_df['abs_contribution'].sum()

print(f"总规格异常驱动力贡献量（绝对值）: {total_driving_contrib:.4f} 百分点")
print(f"目标保留贡献率: {threshold * 100:.0f}%")
print("--------------------------------------------------")

selected_n = 1
for n in range(1, len(plot_df) + 1):
    cum_contrib_n = plot_df['abs_contribution'].head(n).sum()
    ratio = cum_contrib_n / total_driving_contrib if total_driving_contrib > 0 else 0
    print(f"选取前 {n:2d} 个规格：累计贡献量 = {cum_contrib_n:.4f}%, 占比 = {ratio * 100:.2f}%")
    if ratio >= threshold:
        selected_n = n
        break

print("--------------------------------------------------")
print(f"结论：要保留至少 {threshold * 100:.0f}% 的规格驱动力，需要选择前 {selected_n} 个规格。\n")

# 6.2 筛选含有这些规格的记录，用于进一步靶向研究
target_articles = plot_df.head(selected_n)['factor_name'].tolist()

# 过滤出研究期（Study Period）内包含这几个关键规格的数据
df_further_study = df_study[df_study['article10'].isin(target_articles)].copy()

# 进一步过滤出在这些核心规格中被判定为异常的记录
anomaly_col = 'grade_anomaly_new' if 'grade_anomaly_new' in df_further_study.columns else 'any_anomaly'
df_further_study_anomalies = df_further_study[df_further_study[anomaly_col] == 1]

print(f"=== 靶向研究数据集筛选报告 ===")
print(f"1. 锁定核心规格 (共 {len(target_articles)} 个): {target_articles}")
print(f"2. 在研究期 ({study_start} 至 {study_end}) 内：")
print(f"   - 核心规格的总样本量: {len(df_further_study):,} 条")
print(f"   - 核心规格的异常记录数: {len(df_further_study_anomalies):,} 条")
print(f"3. 已生成变量 `df_further_study` (全部核心规格数据) 与 `df_further_study_anomalies` (核心规格异常数据) 供进一步分析。")


# === CELL 11 ===
from sklearn.cluster import KMeans
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# === CELL 12 ===


# 1. 获取 12 个前工序工艺步骤列名作为聚类特征（排除 tu_, tb_, tg_ 开头的检测端）
wc_cols = [col for col in df.columns if 'workcenter' in col and not col.startswith(('tu_', 'tb_', 'tg_'))]

# 2. 对分类机台特征进行 One-Hot 编码（缺失值填充为 'Missing'）
print("正在对前工序机台特征进行 One-Hot 编码...")
df_cat = df_further_study[wc_cols].fillna('Missing').astype(str)
X_encoded = pd.get_dummies(df_cat)

# 3. 区分正常和异常样本索引
is_normal = df_further_study['grade_anomaly_new'] == 0
is_anomaly = df_further_study['grade_anomaly_new'] == 1

print(f"特征处理完成！特征维度: {X_encoded.shape}")
print(f"其中正常样本数: {is_normal.sum():,} 条，异常样本数: {is_anomaly.sum():,} 条。")

# === CELL 13 ===
# 定义聚类画像函数（支持大样本量时的 representative 下采样优化）
def analyze_clustering_paths(X_sub, df_sub, title_prefix, sample_size=None):
    print(f"\n" + "="*60)
    print(f"=== 开始对 【{title_prefix}】 数据进行工艺路径聚类分析 ===")
    
    # 针对超大样本量进行随机下采样以提升 KMeans 运行速度
    if sample_size and len(df_sub) > sample_size:
        print(f"提示：由于总样本量较大（{len(df_sub):,} 条），下采样至 {sample_size:,} 条记录进行加速计算。")
        sample_idx = df_sub.sample(n=sample_size, random_state=42).index
        X_sub_fit = X_sub.loc[sample_idx]
        df_sub_fit = df_sub.loc[sample_idx]
    else: 
        print(f"总样本量: {len(df_sub):,} 条")
        X_sub_fit = X_sub
        df_sub_fit = df_sub

    if len(df_sub_fit) < 10:
        print("样本量过小，跳过聚类。")
        return
        
    # 4.1 肘部评估法确定最佳 K 值
    K = range(1, 8)
    inertias = []
    for k in K:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=5)  # 适当控制 n_init 兼顾速度与稳定性
        kmeans.fit(X_sub_fit)
        inertias.append(kmeans.inertia_)
        
    # 自动定位拐点 (使用二阶导数极值点进行智能推荐)
    if len(inertias) > 2:
        diffs = np.diff(inertias)
        diffs_2 = np.diff(diffs)
        best_k = K[np.argmax(diffs_2) + 1]
    else:
        best_k = 3
    print(f"系统智能推荐的聚类数 K = {best_k} (依据肘部折线拐点)")
    
    # 绘制肘部曲线
    plt.figure(figsize=(6, 4.5))
    color_line = '#d93025' if '异常' in title_prefix else '#1a73e8'
    plt.plot(K, inertias, 'bo-', linewidth=2, markersize=6, color=color_line)
    plt.axvline(best_k, color='black', linestyle='--', label=f'肘部折线拐点 (K={best_k})')
    plt.xlabel('聚类数量 K', fontweight='bold', labelpad=8)
    plt.ylabel('簇内平方和 (Inertia)', fontweight='bold', labelpad=8)
    plt.title(f'【{title_prefix}】数据 - KMeans 肘部评估曲线', fontweight='bold', pad=12)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.show()
    
    # 4.2 运行最佳 K 值的聚类模型
    kmeans_best = KMeans(n_clusters=best_k, random_state=42, n_init=5)
    cluster_labels = kmeans_best.fit_predict(X_sub_fit)
    
    # 合并标签回数据表中
    df_sub_res = df_sub_fit.copy()
    df_sub_res['cluster'] = cluster_labels
    
    # 预计算每个工序中每台机台在全量数据中的自然基准占比
    total_all = len(df_further_study)
    baseline_machine_pct = {}
    for col in wc_cols:
        counts = df_further_study[col].value_counts()
        baseline_machine_pct[col] = (counts / total_all).to_dict()

    # 4.3 描述性统计：统计每个聚类簇的工艺路径画像
    for cluster_id in sorted(df_sub_res['cluster'].unique()):
        df_cluster = df_sub_res[df_sub_res['cluster'] == cluster_id]
        cluster_size = len(df_cluster)
        cluster_pct = cluster_size / len(df_sub_res) * 100
        print(f"\n👉 【聚类簇 Cluster {cluster_id}】 样本量: {cluster_size:,} 条 ({cluster_pct:.2f}% of fit sample)")
        print("   主导工艺路径特征 (各工序首要加工设备及流向占比, 已使用 Step Lift 排序且仅展示 Top 1):")
        
        path_summary = []
        for col in wc_cols:
            anomaly_counts = df_cluster[col].value_counts()
            df_counts = pd.DataFrame({'anomaly_cnt': anomaly_counts}).fillna(0)
            df_counts['P_anomaly'] = df_counts['anomaly_cnt'] / cluster_size
            df_counts['natural_pct'] = df_counts.index.map(lambda x: baseline_machine_pct[col].get(x, 1e-8))
            df_counts['StepLift'] = df_counts['P_anomaly'] / (df_counts['natural_pct'] + 1e-8)
            
            # Sort candidates of this workcenter descending by StepLift
            df_counts_sorted = df_counts.sort_values('StepLift', ascending=False)
            
            # For both normal and abnormal, we only keep the Top 1 Step Lift machine
            if not df_counts_sorted.empty:
                machine = df_counts_sorted.index[0]
                row = df_counts_sorted.iloc[0]
                path_summary.append({
                    '制造工序步骤 (Step)': col.replace('_workcenter', ''),
                    '首选设备机台 (Dominant Machine)': machine,
                    '工艺集中度 (Concentration Ratio)': f"{row['P_anomaly']*100:.2f}%",
                    '全量自然基准占比 (Natural Baseline%)': f"{row['natural_pct']*100:.2f}%",
                    'Step Lift (修正提升度)': f"{row['StepLift']:.2f}x",
                    'StepLift_raw': row['StepLift']
                })
        
        # Sort the workcenters by Step Lift descending
        path_summary_sorted = sorted(path_summary, key=lambda x: x['StepLift_raw'], reverse=True)
        # Remove the temporary key
        for item in path_summary_sorted:
            item.pop('StepLift_raw', None)
            
        summary_df = pd.DataFrame(path_summary_sorted)
        display(summary_df.style.set_properties(**{'text-align': 'left'}))
    print("="*60)

# 执行异常样本聚类
analyze_clustering_paths(X_encoded[is_anomaly], df_further_study[is_anomaly], "异常样本 (grade_anomaly_new=1)")


# === CELL 14 ===
# 执行正常样本聚类（采样优化）
analyze_clustering_paths(X_encoded[is_normal], df_further_study[is_normal], "正常样本 (grade_anomaly_new=0)", sample_size=20000)

# === CELL 15 ===
# === 异常聚类双机台联合 Step Lift 诊断 ===
import pandas as pd
import numpy as np
import itertools
from sklearn.cluster import KMeans

# 1. 拟合 KMeans 聚类模型并打标签
km_best = KMeans(n_clusters=2, random_state=42, n_init=5)
df_anomaly_res = df_further_study[is_anomaly].copy()
df_anomaly_res['cluster'] = km_best.fit_predict(X_encoded[is_anomaly])

total_all = len(df_further_study)
baseline_machine_pct = {}
for col in wc_cols:
    counts = df_further_study[col].value_counts()
    baseline_machine_pct[col] = (counts / total_all).to_dict()

# 2. 对每个异常聚类簇分别进行双机台排列组合与 Step Lift 分析
for cluster_id in sorted(df_anomaly_res['cluster'].unique()):
    df_cluster = df_anomaly_res[df_anomaly_res['cluster'] == cluster_id]
    cluster_size = len(df_cluster)
    
    print(f"\n👉 【异常簇 Cluster {cluster_id}】 双机台联合 Step Lift 诊断 (Top 5 嫌疑设备排列组合)")
    
    # 提取各工段 Step Lift 排名前 5 的候选设备机台
    step_top_5 = {}
    for col in wc_cols:
        anomaly_counts = df_cluster[col].value_counts()
        df_counts = pd.DataFrame({'anomaly_cnt': anomaly_counts}).fillna(0)
        df_counts['P_anomaly'] = df_counts['anomaly_cnt'] / cluster_size
        df_counts['natural_pct'] = df_counts.index.map(lambda x: baseline_machine_pct[col].get(x, 1e-8))
        df_counts['StepLift'] = df_counts['P_anomaly'] / (df_counts['natural_pct'] + 1e-8)
        
        df_counts_sorted = df_counts.sort_values('StepLift', ascending=False)
        step_top_5[col] = df_counts_sorted.head(5).index.tolist()
        
    # 对嫌疑候选设备进行跨工序的两两组合遍历
    comb_results = []
    for col1, col2 in itertools.combinations(wc_cols, 2):
        machs1 = step_top_5[col1]
        machs2 = step_top_5[col2]
        
        for m1 in machs1:
            for m2 in machs2:
                # 联合匹配条件
                cond_all = (df_further_study[col1] == m1) & (df_further_study[col2] == m2)
                total_matches = cond_all.sum()
                
                cond_cluster = (df_cluster[col1] == m1) & (df_cluster[col2] == m2)
                anomaly_matches = cond_cluster.sum()
                
                # 排产数量过滤门槛 (>= 30)，避免小样本噪点
                if total_matches >= 30:
                    P_anomaly_comb = anomaly_matches / cluster_size
                    P_natural_comb = total_matches / total_all
                    joint_step_lift = P_anomaly_comb / (P_natural_comb + 1e-8)
                    
                    comb_results.append({
                        '工序1': col1.replace('_workcenter', ''),
                        '机台1': m1,
                        '工序2': col2.replace('_workcenter', ''),
                        '机台2': m2,
                        '组合总产量': total_matches,
                        '组合异常数': anomaly_matches,
                        '联合 Step Lift': joint_step_lift,
                        'lift_raw': joint_step_lift
                    })
                    
    comb_df = pd.DataFrame(comb_results)
    if not comb_df.empty:
        comb_df = comb_df.sort_values('lift_raw', ascending=False).reset_index(drop=True)
        
        # 格式化表格输出 (Top 10)
        styled_df = comb_df.head(10).drop(columns=['lift_raw']).style.format({
            '组合总产量': '{:,}条',
            '组合异常数': '{:,}条',
            '联合 Step Lift': '{:.2f}x'
        }).set_properties(**{'text-align': 'left'})
        display(styled_df)
    else:
        print('   未计算出符合条件的双机台组合。')


# === CELL 16 ===
# === 10.6 异常聚类簇主导机台批次 (Lot) 风险提升度分析 ===
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
import pandas as pd
import numpy as np

# 1. 预计算每个工序中每台机台在全量数据中的自然基准占比
total_all = len(df_further_study)
baseline_machine_pct = {}
for col in wc_cols:
    counts = df_further_study[col].value_counts()
    baseline_machine_pct[col] = (counts / total_all).to_dict()

# 2. 重新聚类（获取异常簇 0 和 1 的最新状态）
km_best = KMeans(n_clusters=2, random_state=42, n_init=5)
df_anomaly_res = df_further_study[is_anomaly].copy()
df_anomaly_res['cluster'] = km_best.fit_predict(X_encoded[is_anomaly])

# 映射工序与批次列的对应关系
lot_col_map = {col.replace('_lot', '_workcenter'): col for col in df_further_study.columns if 'lot' in col}

cluster_top_lots_dict = {}  # 收集 Top 3 批次用于 10.7 关联分析

# 3. 对每一个异常簇进行主导机台的批次分析与可视化
for cluster_id in sorted(df_anomaly_res['cluster'].unique()):
    df_cluster = df_anomaly_res[df_anomaly_res['cluster'] == cluster_id]
    cluster_size = len(df_cluster)
    
    # 计算该簇内所有工序机台的 Step Lift
    path_summary = []
    for col in wc_cols:
        mode_series = df_cluster[col].value_counts()
        if not mode_series.empty:
            top_machine   = mode_series.index[0]
            top_count     = mode_series.iloc[0]
            concentration = top_count / cluster_size
            natural_pct   = baseline_machine_pct[col].get(top_machine, 1e-8)
            step_lift     = concentration / (natural_pct + 1e-8)
            path_summary.append({
                'col': col,
                'machine': top_machine,
                'concentration': concentration,
                'natural_pct': natural_pct,
                'step_lift': step_lift
            })
            
    # 按 Step Lift 降序排序，选取前 8 名
    path_summary_sorted = sorted(path_summary, key=lambda x: x['step_lift'], reverse=True)
    top_8_candidates = path_summary_sorted[:8]
    
    print(f"\n" + "="*95)
    print(f"👉 【异常簇 Cluster {cluster_id}】 Top 8 主导机台的物料批次 (Lot) 风险提升度分析")
    print(f"="*95)
    
    valid_charts = []
    for cand in top_8_candidates:
        col = cand['col']
        machine = cand['machine']
        lot_col = lot_col_map.get(col, None)
        
        if lot_col:
            # 1. 过滤出该机台在全量中的总产量与异常量（包含异常和非异常）
            df_machine_all = df_further_study[df_further_study[col] == machine]
            df_machine_anomaly = df_further_study[is_anomaly & (df_further_study[col] == machine)]
            
            total_machine_tires = len(df_machine_all)
            total_machine_anomalies = len(df_machine_anomaly)
            
            if total_machine_anomalies > 0:
                # 2. 遍历该机台上出现过的【所有批次】并计算其各自的指标
                unique_lots_on_machine = df_machine_all[lot_col].dropna().unique()
                
                lot_metrics = []
                for lot_name in unique_lots_on_machine:
                    # 在该机台上的异常胎数
                    lot_anomaly_cnt = (df_machine_anomaly[lot_col] == lot_name).sum()
                    # 在该机台上的总产量
                    lot_total_cnt = (df_machine_all[lot_col] == lot_name).sum()
                    
                    # 双重门槛过滤：总产量大于 30 条，且异常数不少于 5 条
                    if lot_total_cnt > 50 and lot_anomaly_cnt >= 5:
                        anomaly_share = lot_anomaly_cnt / total_machine_anomalies # 异常中占比 (分子)
                        overall_share = lot_total_cnt / total_machine_tires       # 全局中占比 (分母)
                        lot_lift = anomaly_share / (overall_share + 1e-8)          # 提升倍数
                        
                        lot_metrics.append({
                            'Lot': lot_name,
                            'anomaly_cnt': lot_anomaly_cnt,
                            'anomaly_share': anomaly_share,
                            'total_cnt': lot_total_cnt,
                            'overall_share': overall_share,
                            'lot_lift': lot_lift
                        })
                        
                # 3. 按 Lot Lift 降序排序，选取 Top 10 最高风险提升的批次
                lot_metrics_sorted = sorted(lot_metrics, key=lambda x: x['lot_lift'], reverse=True)
                top_10_lots = lot_metrics_sorted[:10]
                
                if top_10_lots:
                    # 4. 构造伴随表格和可视化数据
                    lot_risk_details = []
                    for item in top_10_lots:
                        lot_risk_details.append({
                            '物料批次 (Lot)': item['Lot'],
                            '异常数 (条)': item['anomaly_cnt'],
                            '异常中该机台该批次占比 (%)': item['anomaly_share'],
                            '机台总产量 (条)': item['total_cnt'],
                            '全局中该机台该批次占比 (%)': item['overall_share'],
                            '提升倍数 (vs 机台基准)': item['lot_lift']
                        })
                    
                    valid_charts.append({
                        'step': col.replace('_workcenter', ''),
                        'machine': machine,
                        'top_lots': top_10_lots,
                        'risk_df': pd.DataFrame(lot_risk_details),
                        'total_anomalies': total_machine_anomalies,
                        'unique_lots': df_machine_anomaly[lot_col].nunique()
                    })
                    
                    # 收集 Top 3 高危批次信息
                    if cluster_id not in cluster_top_lots_dict:
                        cluster_top_lots_dict[cluster_id] = []
                    cluster_top_lots_dict[cluster_id].append({
                        'step': col.replace('_workcenter', ''),
                        'machine': machine,
                        'lot_col': lot_col,
                        'top_3_lots': [item['Lot'] for item in top_10_lots[:3]]
                    })
            else:
                print(f"工序 [{col.replace('_workcenter','')}] 机台 [{machine}] 在计算时间内无异常样本。")
        else:
            print(f"提示：工序 [{col.replace('_workcenter','')}] 机台 [{machine}] 无对应 Lot 批次列，跳过分析。")
            
    # 5. 开始绘制该异常簇的柱状图和伴随表格
    for chart in valid_charts:
        print(f"\n" + "-"*90)
        print(f"🔹 工序: 【{chart['step']}】 | 核心机台: 【{chart['machine']}】")
        print(f"  (当前机台总异常数: {chart['total_anomalies']:,} 条，涉及有异常的物料批次: {chart['unique_lots']:,} 个)")
        print(f"-"*90)
        
        # 5.1 绘制横向柱状图展示 Top 10 Lift
        fig, ax = plt.subplots(figsize=(7.5, max(3, len(chart['top_lots']) * 0.4)))
        
        # 为了让最高 Lift 排在最上面，将列表倒序绘制
        top_lots_rev = chart['top_lots'][::-1]
        lots = [item['Lot'] for item in top_lots_rev]
        lifts = [item['lot_lift'] for item in top_lots_rev]
        anomaly_cnts = [item['anomaly_cnt'] for item in top_lots_rev]
        total_cnts = [item['total_cnt'] for item in top_lots_rev]
        
        bars = ax.barh(lots, lifts, color='#d93025', alpha=0.75, height=0.5)
        ax.set_xlabel('提升倍数 (Lot Lift vs 机台基准)', fontsize=9, fontweight='bold')
        ax.set_ylabel('物料批次 (Lot)', fontsize=9, fontweight='bold')
        ax.set_title(f"【{chart['step']} - {chart['machine']}】 Top {len(chart['top_lots'])} 物料批次风险提升度 (Lot Lift) 排行", fontsize=10, fontweight='bold', pad=10)
        
        # 在柱子右侧标注 Lift 和 样本比例
        for idx, bar in enumerate(bars):
            width = bar.get_width()
            a_cnt = anomaly_cnts[idx]
            t_cnt = total_cnts[idx]
            ax.annotate(f'{width:.2f}x ({a_cnt}/{t_cnt})',
                        xy=(width, bar.get_y() + bar.get_height() / 2),
                        xytext=(5, 0),
                        textcoords="offset points",
                        ha='left', va='center', fontsize=8, weight='bold', color='black')
        
        # 设置 x 轴范围留白
        max_lift = max(lifts) if lifts else 1
        ax.set_xlim(0, max_lift * 1.25)
        
        plt.grid(True, axis='x', linestyle=':', alpha=0.5)
        plt.tight_layout()
        plt.show()
        
        # 5.2 展示机台内部的局部修正风险表格
        display(chart['risk_df'].style.format({
            '异常数 (条)': '{:,}',
            '异常中该机台该批次占比 (%)': '{:.2%}',
            '机台总产量 (条)': '{:,}',
            '全局中该机台该批次占比 (%)': '{:.2%}',
            '提升倍数 (vs 机台基准)': '{:.2f}x'
        }).set_properties(**{'text-align': 'left'}))


# === CELL 17 ===
# === 10.8 特定高危 Lot 与各规格 (Article) 交互风险对照热力图 (单元格数量修正版) ===
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

# 💡【配置项 1】：在此填入您想要观测的特定物料批次号
selected_lot = '992L05HLPOAIO'  

# 💡【配置项 2】：单元格最小排产门槛。只有 Lot-Article 组合排产达到此数量才计算 Lift，否则显示为 NaN (避开小样本噪音)
cell_min_qty = 10  

# 💡【配置项 3】：提升度计算公式模式。可选值：'vs_article' (对照规格平均) | 'vs_lot' (对照批次平均) | 'vs_machine' (对照机台平均)
lift_formula_mode = 'vs_article'  


# 确保异常掩码
anomaly_col = 'grade_anomaly_new' if 'grade_anomaly_new' in df_study.columns else 'any_anomaly'

# ==============================================================================
# 1. 自动定位该物料批次 (selected_lot) 所属的工序、列名、加工机台与所涉及的产品规格
# ==============================================================================
selected_lot_clean = selected_lot.strip().upper()
found_lot_col = None
use_df = None

# 先在 df_study (全量数据集) 中查找
for col in df_study.columns:
    if 'lot' in col:
        if (df_study[col].astype(str).str.upper().str.strip() == selected_lot_clean).any():
            found_lot_col = col
            break

if not found_lot_col:
    print(f"⚠️ 错误：在全量数据中也未找到批次【{selected_lot}】。")
    # 模糊匹配联想
    similar_lots = []
    prefix = selected_lot_clean[:6]
    for col in df_study.columns:
        if 'lot' in col:
            unique_vals = df_study[col].dropna().unique()
            for val in unique_vals:
                if str(val).upper().startswith(prefix):
                    similar_lots.append(val)
    if similar_lots:
        print(f"💡 系统为您联想，您是不是想输入以下真实批次之一？:")
        print(f"   {list(set(similar_lots))[:10]}")
else:
    wc_col = found_lot_col.replace('_lot', '_workcenter')
    step_name = found_lot_col.replace('_lot', '')
    
    # 检查在 df_further_study 子集里是否存在
    in_further = (df_further_study[found_lot_col].astype(str).str.upper().str.strip() == selected_lot_clean).any()
    if in_further:
        print(f"ℹ️ 该批次在靶向研究数据集 `df_further_study` 中找到，将使用 `df_further_study` 进行计算。")
        use_df = df_further_study
    else:
        print(f"ℹ️ 提示：该批次在子集 `df_further_study` 中被规格过滤。已自动回退到完整的 `df_study` 数据集进行分析。")
        use_df = df_study

    is_anomaly = use_df[anomaly_col] == 1

    # 锁定该 Lot 投产的主要物理机台
    df_lot_data = use_df[use_df[found_lot_col].astype(str).str.upper().str.strip() == selected_lot_clean]
    selected_machine = df_lot_data[wc_col].value_counts().index[0]
    
    # 锁定该 Lot 在该机台上涉及的规格
    involved_articles = df_lot_data[df_lot_data[wc_col] == selected_machine]['article10'].dropna().unique().tolist()
    involved_articles = [art for art in involved_articles if art in target_articles]
    
    if not involved_articles:
        involved_articles = df_lot_data[df_lot_data[wc_col] == selected_machine]['article10'].dropna().unique().tolist()
        
    print("\n" + "="*95)
    print(f"🎯 【已定位 Lot: {selected_lot}】")
    print(f"   - 所属工序: 【{step_name}】 | 主要投产机台: 【{selected_machine}】")
    print(f"   - 实际涉及的产品规格 (Articles): {involved_articles}")
    print("="*95)

    # ==============================================================================
    # 2. 获取在同一机台上，生产过这些规格的其他对比物料批次 (Other Lots)
    # ==============================================================================
    df_machine_all = use_df[use_df[wc_col] == selected_machine]
    df_machine_anomaly = use_df[is_anomaly & (use_df[wc_col] == selected_machine)]
    
    # 获取同机台上生产过这些规格的所有其他批次
    candidate_lots = df_machine_all[df_machine_all['article10'].isin(involved_articles)][found_lot_col].dropna().unique().tolist()
    
    # 过滤掉产量低于 30 条的小排产批次
    valid_comparison_lots = []
    for lot_name in candidate_lots:
        cnt = (df_machine_all[found_lot_col] == lot_name).sum()
        if cnt > 30:
            valid_comparison_lots.append(lot_name)
            
    lot_volumes = {lot: (df_machine_all[found_lot_col] == lot).sum() for lot in valid_comparison_lots}
    sorted_lots = sorted(valid_comparison_lots, key=lambda x: lot_volumes[x], reverse=True)
    
    comparison_lots = [selected_lot]
    for lot in sorted_lots:
        if str(lot).upper().strip() != selected_lot_clean and len(comparison_lots) < 10:
            comparison_lots.append(lot)
            
    # ==============================================================================
    # 3. 计算规格内 Lift 提升度矩阵（增加单元格级数量修正）
    # ==============================================================================
    heatmap_matrix = []
    
    # 预计算机台和各批次在机台上的总体均值，供不同公式使用
    machine_avg_rate = len(df_machine_anomaly) / len(df_machine_all) if len(df_machine_all) > 0 else 0
    
    for lot_name in comparison_lots:
        row_data = {}
        df_lot_all = df_machine_all[df_machine_all[found_lot_col] == lot_name]
        df_lot_anomaly = df_machine_anomaly[df_machine_anomaly[found_lot_col] == lot_name]
        lot_avg_rate = len(df_lot_anomaly) / len(df_lot_all) if len(df_lot_all) > 0 else 0
        
        for art in involved_articles:
            df_art_all = df_machine_all[df_machine_all['article10'] == art]
            df_art_anomaly = df_machine_anomaly[df_machine_anomaly['article10'] == art]
            
            df_lot_art_all = df_art_all[df_art_all[found_lot_col] == lot_name]
            df_lot_art_anomaly = df_art_anomaly[df_art_anomaly[found_lot_col] == lot_name]
            
            n_lot_art_all = len(df_lot_art_all)
            n_lot_art_anomaly = len(df_lot_art_anomaly)
            
            # 【核心修正】：若该批次在当前规格下排产量低于 cell_min_qty，则不具备统计意义，置为 NaN
            if n_lot_art_all < cell_min_qty:
                row_data[art] = np.nan
                continue
                
            lot_art_rate = n_lot_art_anomaly / n_lot_art_all
            
            # 根据用户配置的模式，套用不同的 Lift 修正公式
            if lift_formula_mode == 'vs_article':
                art_rate = len(df_art_anomaly) / len(df_art_all) if len(df_art_all) > 0 else 0
                within_lift = lot_art_rate / (art_rate + 1e-8) if art_rate > 0 else 0
            elif lift_formula_mode == 'vs_lot':
                within_lift = lot_art_rate / (lot_avg_rate + 1e-8) if lot_avg_rate > 0 else 0
            elif lift_formula_mode == 'vs_machine':
                within_lift = lot_art_rate / (machine_avg_rate + 1e-8) if machine_avg_rate > 0 else 0
                
            row_data[art] = within_lift
        heatmap_matrix.append(row_data)
        
    df_heatmap = pd.DataFrame(heatmap_matrix, index=comparison_lots)
    
    # ==============================================================================
    # 4. 绘制 Lot - Article 规格交互风险矩阵热力图
    # ==============================================================================
    plt.figure(figsize=(12, min(7, len(comparison_lots) * 0.65 + 2)))
    
    y_labels = [f"★ {lot} (Target)" if str(lot).upper().strip() == selected_lot_clean else lot for lot in comparison_lots]
    
    # 在标题中动态展示公式说明
    formula_titles = {
        'vs_article': '对照规格平均异常率 (vs Article Avg)',
        'vs_lot': '对照批次整体平均异常率 (vs Lot Overall Avg)',
        'vs_machine': '对照机台总体平均异常率 (vs Machine Avg)'
    }
    
    # 绘制热力图 (NaN 值会自动在图中被绘制为灰色空白背景)
    sns.heatmap(df_heatmap, annot=True, fmt=".2f", cmap="Reds", yticklabels=y_labels, cbar_kws={'label': 'Lift'}, mask=df_heatmap.isnull())
    plt.title(f"🔍 机台【{selected_machine}】工序【{step_name}】 - 批次与规格交互风险诊断对比矩阵\n({formula_titles[lift_formula_mode]}，小样本已过滤)", fontsize=11, fontweight='bold', pad=15)
    plt.ylabel("物料批次 (Lot)", fontweight='bold')
    plt.xlabel("规格型号 (Article)", fontweight='bold')
    plt.xticks(rotation=15, ha='right')
    plt.tight_layout()
    plt.show()
    
    # ==============================================================================
    # 5. 输出明细数据表格，包含排产与异常频数
    # ==============================================================================
    table_rows = []
    for lot_name in comparison_lots:
        for art in involved_articles:
            df_art_all = df_machine_all[df_machine_all['article10'] == art]
            df_art_anomaly = df_machine_anomaly[df_machine_anomaly['article10'] == art]
            
            n_lot_art_all = (df_art_all[found_lot_col] == lot_name).sum()
            n_lot_art_anomaly = (df_art_anomaly[found_lot_col] == lot_name).sum()
            
            val = df_heatmap.loc[lot_name, art]
            lift_str = f"{val:.2f}x" if not np.isnan(val) else "已屏蔽 (排产不足)"
            
            table_rows.append({
                '是否目标批次': '★ 是' if str(lot_name).upper().strip() == selected_lot_clean else '否',
                '物料批次 (Lot)': lot_name,
                '产品规格 (Article)': art,
                '在该规格下排产量 (条)': n_lot_art_all,
                '在该规格下异常量 (条)': n_lot_art_anomaly,
                '交互提升度 (Lift)': lift_str
            })
            
    df_details = pd.DataFrame(table_rows)
    display(df_details.style.format({
        '在该规格下排产量 (条)': '{:,}',
        '在该规格下异常量 (条)': '{:,}'
    }).set_properties(**{'text-align': 'left'}))


