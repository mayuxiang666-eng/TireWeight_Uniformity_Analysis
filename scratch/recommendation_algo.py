import os
import sys
import math
import argparse
import pandas as pd
import numpy as np

# 将 backend 路径添加到 sys.path
backend_dir = r"d:\Ava\untitled1\untitled1_v2\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from main import get_cgrs_controlled_analysis

def recommend_parameters_for_machine(workcenter: str, target_date: str, article10: str, indicator: str = 'rfpp', top_k: int = 3):
    """
    针对指定机台、日期与规格，基于【标准化欧式距离 + 样本容量开方加权得分】推荐最适 CGRS 调参组合
    """
    print(f"\n================================================================================")
    print(f"  RFPP CGRS 参数智能推荐引擎 (机台: [{workcenter}] | 日期: [{target_date}] | 规格: [{article10}])")
    print(f"================================================================ failure / start ===\n")
    
    # 1. 抓取当前机台的 CGRS 调参分析数据
    curr_res = get_cgrs_controlled_analysis(
        workcenter=workcenter,
        date=target_date,
        article=article10,
        indicator=indicator
    )
    
    if not curr_res.get('has_cgrs') or not curr_res.get('events'):
        print(f"[Notice] 当前机台 [{workcenter}] 在 [{target_date}] 暂无 CGRS 调参记录或有效数据。")
        return None
        
    curr_events = curr_res['events']
    latest_curr_event = curr_events[0]
    curr_params = latest_curr_event.get('params_changed', [])
    
    if not curr_params:
        print("[Notice] 当前机台未检测到参数变动明细。")
        return None
        
    # 构造当前机台状态向量: { (param_code, param_local): from_val }
    curr_vector = {}
    for p in curr_params:
        key = p.get('param_local') or p.get('param_code')
        try:
            curr_vector[key] = float(p.get('from_val', 0.0))
        except (ValueError, TypeError):
            curr_vector[key] = 0.0
            
    print(f"[当前机台状态向量] 共包含 {len(curr_vector)} 项调参特征:")
    for k, v in curr_vector.items():
        print(f"   - {k}: {v}")
    
    # 2. 搜索同型号成型机台 (例如 TB2xx) 近 7 天的历史调参记录
    wc_prefix = workcenter[:3] if len(workcenter) >= 3 else workcenter
    candidate_wcs = [f"{wc_prefix}{i:02d}" for i in range(1, 60)]
    
    history_samples = []
    base_dt = pd.to_datetime(target_date)
    
    for day_offset in range(7):
        search_date = (base_dt - pd.Timedelta(days=day_offset)).strftime('%Y-%m-%d')
        for candidate_wc in candidate_wcs:
            # 排除当前事件自身
            if candidate_wc == workcenter and search_date == target_date:
                continue
                
            analysis = get_cgrs_controlled_analysis(
                workcenter=candidate_wc,
                date=search_date,
                article=article10,
                indicator=indicator
            )
            
            if not analysis.get('has_cgrs') or not analysis.get('events'):
                continue
                
            for ev in analysis['events']:
                eff_paths = ev.get('effective_paths', [])
                if not eff_paths:
                    continue
                    
                all_b, all_a = [], []
                for path in eff_paths:
                    all_b.extend(path.get('vals_before', []))
                    all_a.extend(path.get('vals_after', []))
                    
                nb, na = len(all_b), len(all_a)
                if nb < 5 or na < 5:
                    continue
                    
                mb, ma = np.mean(all_b), np.mean(all_a)
                sb = np.std(all_b, ddof=1) if nb > 1 else np.std(all_b)
                sa = np.std(all_a, ddof=1) if na > 1 else np.std(all_a)
                
                usl = 100.0
                cpk_b = (usl - mb) / (3.0 * sb) if sb > 1e-6 else 0.0
                cpk_a = (usl - ma) / (3.0 * sa) if sa > 1e-6 else 0.0
                yoy = ((cpk_a - cpk_b) / abs(cpk_b) * 100.0) if abs(cpk_b) > 1e-4 else 0.0
                
                n_total = nb + na
                score = yoy * math.sqrt(n_total)
                
                hist_vector = {}
                for p in ev.get('params_changed', []):
                    k = p.get('param_local') or p.get('param_code')
                    try:
                        hist_vector[k] = float(p.get('from_val', 0.0))
                    except (ValueError, TypeError):
                        hist_vector[k] = 0.0
                        
                history_samples.append({
                    'workcenter': candidate_wc,
                    'date': search_date,
                    'timestamp': ev.get('date_time_str') or ev.get('timestamp'),
                    'params_changed': ev.get('params_changed', []),
                    'hist_vector': hist_vector,
                    'n_before': nb,
                    'n_after': na,
                    'n_total': n_total,
                    'cpk_before': round(cpk_b, 3),
                    'cpk_after': round(cpk_a, 3),
                    'raw_yoy': round(yoy, 2),
                    'score': round(score, 2)
                })
                
    print(f"\n[OK] 搜寻到近 7 天同型号机台共 {len(history_samples)} 条历史调参样本事件。")
    if not history_samples:
        return None
        
    # 3. 计算标准化欧式距离 (Standardized Euclidean Distance)
    all_keys = set(curr_vector.keys())
    for sample in history_samples:
        all_keys.update(sample['hist_vector'].keys())
    all_keys = list(all_keys)
    
    param_min_max = {}
    for k in all_keys:
        vals = [curr_vector.get(k, 0.0)]
        for s in history_samples:
            vals.append(s['hist_vector'].get(k, 0.0))
        param_min_max[k] = (min(vals), max(vals))
        
    for sample in history_samples:
        dist_sq = 0.0
        for k in all_keys:
            v_curr = curr_vector.get(k, 0.0)
            v_hist = sample['hist_vector'].get(k, 0.0)
            min_v, max_v = param_min_max[k]
            range_v = max_v - min_v if (max_v - min_v) > 1e-6 else 1.0
            
            norm_curr = (v_curr - min_v) / range_v
            norm_hist = (v_hist - min_v) / range_v
            dist_sq += (norm_curr - norm_hist) ** 2
            
        sample['distance'] = round(math.sqrt(dist_sq), 4)
        
    # 4. 按距离排序选取 Top-K
    sorted_by_dist = sorted(history_samples, key=lambda x: x['distance'])
    top_k_samples = sorted_by_dist[:top_k]
    
    print(f"\n--------------------------------------------------------------------------------")
    print(f"  Top-{top_k} 最近距离历史调参事件")
    print(f"--------------------------------------------------------------------------------")
    for rank, s in enumerate(top_k_samples, 1):
        print(f"  Rank #{rank} | 机台: {s['workcenter']} | 日期: {s['date']} | 距离: {s['distance']} | 加权得分: {s['score']} | 实际增幅: {s['raw_yoy']}%")
        
    # 5. 选取 Score > 0 且最高者生成推荐
    positive_top_k = [s for s in top_k_samples if s['score'] > 0]
    positive_top_k.sort(key=lambda x: x['score'], reverse=True)
    
    if not positive_top_k:
        print("\n[Notice] Top-K 最近事件中未发现正向改善的有效调参经验。")
        return top_k_samples
        
    best_recommend_event = positive_top_k[0]
    print(f"\n================================================================================")
    print(f"  [BEST RECOMMENDATION] 选中历史经验事件: 机台 [{best_recommend_event['workcenter']}] ({best_recommend_event['timestamp']})")
    print(f"================================================================================")
    print(f"   - 状态特征距离: {best_recommend_event['distance']}")
    print(f"   - 历史 CPK 优化效果: CPK {best_recommend_event['cpk_before']} -> {best_recommend_event['cpk_after']} (实际增幅: +{best_recommend_event['raw_yoy']}%)")
    print(f"   - 样本量支撑: 改前 {best_recommend_event['n_before']} 胎, 改后 {best_recommend_event['n_after']} 胎 (总计 {best_recommend_event['n_total']} 胎)")
    print("   - 具体参数调优建议:")
    for p in best_recommend_event['params_changed']:
        name = p.get('param_local') or p.get('param_code')
        f_val = p.get('from_val')
        t_val = p.get('to_val')
        print(f"     -> [{name}]: 从当前设定值 {f_val} 建议调整为 -> {t_val}")
        
    return top_k_samples

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RFPP CGRS Parameter Recommendation Engine")
    parser.add_argument("--workcenter", type=str, default="TB244", help="成型机台编号 (默认: TB244)")
    parser.add_argument("--date", type=str, default="2026-08-14", help="查询日期 (默认: 2026-08-14)")
    parser.add_argument("--article", type=str, default="0313888056", help="规格 10 位编码 (默认: 0313888056)")
    parser.add_argument("--indicator", type=str, default="rfpp", help="质量指标 (默认: rfpp)")
    parser.add_argument("--top-k", type=int, default=3, help="Top-K 最近邻数量 (默认: 3)")
    args = parser.parse_args()
    
    recommend_parameters_for_machine(
        workcenter=args.workcenter,
        target_date=args.date,
        article10=args.article,
        indicator=args.indicator,
        top_k=args.top_k
    )
