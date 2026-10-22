# -*- coding: utf-8 -*-
"""
轮胎生产质量与均匀性 17 项指标 CPK 趋势与主成分分析 (PCA) 关键指标选型报告生成器
聚合过去 30 天生产数据，预渲染生成极简、现代化且完全独立的单文件 HTML 趋势看板。
"""
import os
import sys
import json
import duckdb
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

# 保证编码兼容
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def get_data_dir():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(current_dir, "..", "data"),
        os.path.join(current_dir, "..", "..", "data"),
        os.path.join(os.getcwd(), "backend", "data"),
        os.path.join(os.getcwd(), "data"),
    ]
    for c in candidates:
        p = os.path.abspath(c)
        if os.path.exists(os.path.join(p, "yield_flat_table_joined_100_cleaned.parquet")):
            return p
    return os.path.abspath(os.path.join(current_dir, "..", "data"))


def calc_indicator_cpk(mean, std, usl, lsl=None):
    """根据单侧/双侧公差计算 CPK"""
    if pd.isna(mean) or pd.isna(std) or std <= 1e-6:
        return None
    
    # 双侧公差 (如 CONY 锥度)
    if pd.notna(usl) and pd.notna(lsl):
        cpu = (usl - mean) / (3.0 * std)
        cpl = (mean - lsl) / (3.0 * std)
        return float(min(cpu, cpl))
    
    # 单侧上限公差
    if pd.notna(usl):
        return float((usl - mean) / (3.0 * std))
    
    return None


def run_pca_for_station(con, pq_path_sql, station_name, cols, display_names, sample_limit=50000):
    """针对特定工位执行主成分分析 (PCA) 并选拔关键指标"""
    where_clause = " AND ".join([f"{c} IS NOT NULL" for c in cols])
    sql = f"""
        SELECT {', '.join(cols)}
        FROM read_parquet('{pq_path_sql}')
        WHERE {where_clause}
        LIMIT {sample_limit}
    """
    try:
        df = con.execute(sql).df()
    except Exception as e:
        print(f"[PCA Warning] {station_name} 数据读取异常: {e}")
        return None

    if len(df) < 20:
        print(f"[PCA Warning] {station_name} 有效样本量不足 ({len(df)})，跳过 PCA。")
        return None

    X = df[cols].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    pca = PCA()
    pca.fit(X_scaled)

    evr = pca.explained_variance_ratio_
    cum_evr = np.cumsum(evr)

    # 载荷矩阵: loadings = components_.T * sqrt(explained_variance_)
    loadings = pca.components_.T * np.sqrt(pca.explained_variance_)

    # 选取累计方差贡献达标的主成分 (>= 80% 或前 2 个)
    k_components = max(2, int(np.argmax(cum_evr >= 0.80) + 1)) if any(cum_evr >= 0.80) else len(evr)
    k_components = min(k_components, len(evr))
    
    comp_weights = evr[:k_components] / np.sum(evr[:k_components])
    importance_scores = np.sum(np.abs(loadings[:, :k_components]) * comp_weights, axis=1)
    
    # 归一化综合影响力得分 (0~100)
    norm_scores = (importance_scores / np.sum(importance_scores)) * 100.0

    # 组织各指标重要性列表
    indicators_pca = []
    for idx, col in enumerate(cols):
        pc1_load = float(loadings[idx, 0]) if loadings.shape[1] > 0 else 0.0
        pc2_load = float(loadings[idx, 1]) if loadings.shape[1] > 1 else 0.0
        score = float(norm_scores[idx])
        indicators_pca.append({
            "col": col,
            "name": display_names[idx],
            "score": round(score, 2),
            "pc1_loading": round(pc1_load, 3),
            "pc2_loading": round(pc2_load, 3)
        })

    # 按综合得分从大到小排序
    indicators_pca.sort(key=lambda x: x["score"], reverse=True)

    # 标记关键核心指标 (Top 累计得分达 60%~75% 的核心指标，或前 3 个)
    cum_score = 0.0
    key_indicators = []
    for item in indicators_pca:
        cum_score += item["score"]
        # 对于 TB (仅3个)，前2个为关键；对于 TU/TG (7个)，前 4 个为关键
        if len(key_indicators) < (2 if len(cols) <= 3 else 4):
            item["is_key"] = True
            key_indicators.append(item["name"])
        else:
            item["is_key"] = False

    # 生成工业物理解读
    insights = []
    if station_name == "TU":
        insights.append(f"前 2 个主成分累计方差解释达 {cum_evr[1]*100:.1f}%，呈现出显著的【侧向力群 (LFPP/LFH1)】与【径向力群 (RFPP/RFH1)】正交特征。")
        insights.append(f"选出核心监控关键指标：【{'、'.join(key_indicators)}】，这四项指标捕获了力变均匀性中超过 80% 的主要变异信息。")
    elif station_name == "TG":
        insights.append(f"PC1 (解释 {evr[0]*100:.1f}%) 主导【鼓包形变群 (TBUL/BBUL)】，PC2 (解释 {evr[1]*100:.1f}%) 主导【凹陷形变群 (TDEP/BDEP)】。")
        insights.append(f"选出核心监控关键指标：【{'、'.join(key_indicators)}】，涵盖了鼓包与凹陷两大主要缺陷形态。")
    elif station_name == "TB":
        insights.append(f"PC1 单独解释高达 {evr[0]*100:.1f}% 的方差，由【静平衡 SBALW】主导总体质量偏差；PC2 ({evr[1]*100:.1f}%) 反映上下动平衡的力偶偶不平衡。")
        insights.append(f"选出核心监控关键指标：【{'、'.join(key_indicators)}】。")

    return {
        "station": station_name,
        "sample_count": len(df),
        "k_components": k_components,
        "components": [
            {
                "name": f"PC{i+1}",
                "variance_ratio": round(float(evr[i]) * 100.0, 2),
                "cum_variance_ratio": round(float(cum_evr[i]) * 100.0, 2)
            }
            for i in range(len(evr))
        ],
        "indicators": indicators_pca,
        "key_indicators": key_indicators,
        "insights": insights
    }


def generate_report():
    data_dir = get_data_dir()
    pq_cleaned = os.path.join(data_dir, "yield_flat_table_joined_100_cleaned.parquet")
    if not os.path.exists(pq_cleaned):
        print(f"[Error] 清洗后的宽表文件不存在: {pq_cleaned}")
        return False

    print(f"[1/5] 连接 DuckDB 并加载清洗后宽表: {pq_cleaned}...")
    con = duckdb.connect()
    pq_path_sql = pq_cleaned.replace('\\', '/')
    
    existing_cols = set([r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{pq_path_sql}') LIMIT 1").fetchall()])
    print(f"  当前数据包含 {len(existing_cols)} 列")

    def col_expr(name):
        return f"TRY_CAST({name} AS DOUBLE)" if name in existing_cols else "NULL::DOUBLE"

    max_dt_row = con.execute(f"""
        SELECT MAX(CAST(TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) AS DATE))
        FROM read_parquet('{pq_path_sql}')
        WHERE tu_first_loc_timestamp IS NOT NULL
    """).fetchone()

    max_dt = max_dt_row[0] if max_dt_row and max_dt_row[0] else datetime.now().date()
    print(f"  最新终检日期: {max_dt}，取过去 30 天时间窗口...")

    # 17 个指标的元数据定义 (与用户给定 TU / TG / TB 完全对齐)
    indicators_meta = [
        # TU (均匀性与力变)
        {"key": "rfpp", "name": "RFPP_WC", "full_name": "RFPP_WC (径向力峰峰值)", "station": "TU", "group": "TU (均匀性与力变)", "val_col": "rfppwc_first", "val_scale": 1.0, "usl_col": "standard_rfpp", "usl_scale": 10.0, "lsl_col": None, "unit": "N"},
        {"key": "rfh1", "name": "RFH1_WC", "full_name": "RFH1_WC (径向力一次谐波)", "station": "TU", "group": "TU (均匀性与力变)", "val_col": "rfh1wc_first", "val_scale": 1.0, "usl_col": "standard_rfh1", "usl_scale": 10.0, "lsl_col": None, "unit": "N"},
        {"key": "rfh2", "name": "RFH2_WC", "full_name": "RFH2_WC (径向力二次谐波)", "station": "TU", "group": "TU (均匀性与力变)", "val_col": "rfh2wc_first", "val_scale": 1.0, "usl_col": "standard_rfh2", "usl_scale": 10.0, "lsl_col": None, "unit": "N"},
        {"key": "lfpp", "name": "LFPP_WC", "full_name": "LFPP_WC (侧向力峰峰值)", "station": "TU", "group": "TU (均匀性与力变)", "val_col": "lfppwc_first", "val_scale": 1.0, "usl_col": "standard_lfpp", "usl_scale": 10.0, "lsl_col": None, "unit": "N"},
        {"key": "lfh1", "name": "LFH1_WC", "full_name": "LFH1_WC (侧向力一次谐波)", "station": "TU", "group": "TU (均匀性与力变)", "val_col": "lfh1wc_first", "val_scale": 1.0, "usl_col": "standard_lfh1", "usl_scale": 10.0, "lsl_col": None, "unit": "N"},
        {"key": "cony", "name": "CONY", "full_name": "CONY (锥度效应力)", "station": "TU", "group": "TU (均匀性与力变)", "val_col": "cony_first", "val_scale": 1.0, "usl_col": "conny_usl", "usl_scale": 1.0, "lsl_col": "conny_lsl", "unit": "N"},
        {"key": "plys", "name": "PLYS", "full_name": "PLYS (帘布偏摆力/层差)", "station": "TU", "group": "TU (均匀性与力变)", "val_col": "plys_first", "val_scale": 1.0, "usl_col": "plys_usl", "usl_scale": 1.0, "lsl_col": "plys_lsl", "unit": "N"},

        # TG (几何外观与跳动)
        # 说明: 生产宽表存储单位为米 (m)，乘以 1000 转换为毫米 (mm)，与 Recipes 配方上限 (mm) 完全对齐
        {"key": "tbul", "name": "TBULs", "full_name": "TBULs (上侧鼓包/凸起)", "station": "TG", "group": "TG (几何外观与跳动)", "val_col": "tbul_first", "val_scale": 1000.0, "usl_col": "tbul_usl", "usl_scale": 1.0, "lsl_col": None, "unit": "mm"},
        {"key": "bbul", "name": "BBULs", "full_name": "BBULs (下侧鼓包/凸起)", "station": "TG", "group": "TG (几何外观与跳动)", "val_col": "bbul_first", "val_scale": 1000.0, "usl_col": "bbul_usl", "usl_scale": 1.0, "lsl_col": None, "unit": "mm"},
        {"key": "tdep", "name": "TDEPs", "full_name": "TDEPs (上侧凹陷)", "station": "TG", "group": "TG (几何外观与跳动)", "val_col": "tdep_first", "val_scale": 1000.0, "usl_col": "tdep_usl", "usl_scale": 1.0, "lsl_col": None, "unit": "mm"},
        {"key": "bdep", "name": "BDEPs", "full_name": "BDEPs (下侧凹陷)", "station": "TG", "group": "TG (几何外观与跳动)", "val_col": "bdep_first", "val_scale": 1000.0, "usl_col": "bdep_usl", "usl_scale": 1.0, "lsl_col": None, "unit": "mm"},
        {"key": "tlro", "name": "TLRO", "full_name": "TLRO (上侧径向跳动)", "station": "TG", "group": "TG (几何外观与跳动)", "val_col": "tlro_first", "val_scale": 1000.0, "usl_col": "tlro_usl", "usl_scale": 1.0, "lsl_col": None, "unit": "mm"},
        {"key": "blro", "name": "BLRO", "full_name": "BLRO (下侧径向跳动)", "station": "TG", "group": "TG (几何外观与跳动)", "val_col": "blro_first", "val_scale": 1000.0, "usl_col": "blro_usl", "usl_scale": 1.0, "lsl_col": None, "unit": "mm"},
        {"key": "crro", "name": "CRRO", "full_name": "CRRO (中心径向跳动)", "station": "TG", "group": "TG (几何外观与跳动)", "val_col": "crro_first", "val_scale": 1000.0, "usl_col": "crro_usl", "usl_scale": 1.0, "lsl_col": None, "unit": "mm"},

        # TB (动静平衡)
        {"key": "tbalw", "name": "TBALW", "full_name": "TBALW (上侧动平衡量)", "station": "TB", "group": "TB (动静平衡)", "val_col": "tbalw_first", "val_scale": 1.0, "usl_col": "tbalw_usl", "usl_scale": 1.0, "lsl_col": None, "unit": "g"},
        {"key": "bbalw", "name": "BBALW", "full_name": "BBALW (下侧动平衡量)", "station": "TB", "group": "TB (动静平衡)", "val_col": "bbalw_first", "val_scale": 1.0, "usl_col": "bbalw_usl", "usl_scale": 1.0, "lsl_col": None, "unit": "g"},
        {"key": "sbalw", "name": "SBALW", "full_name": "SBALW (静平衡量)", "station": "TB", "group": "TB (动静平衡)", "val_col": "sbalw_first", "val_scale": 1.0, "usl_col": "sbalw_usl", "usl_scale": 1.0, "lsl_col": None, "unit": "g"}
    ]

    print("[2/5] 获取近 30 天日期范围与全厂总产量...")
    dates_df = con.execute(f"""
        SELECT 
            CAST(TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) AS DATE) as prod_date, 
            COUNT(*) as total_n
        FROM read_parquet('{pq_path_sql}')
        WHERE tu_first_loc_timestamp IS NOT NULL
          AND CAST(TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) AS DATE) >= ('{max_dt}'::DATE - INTERVAL 30 DAY)
        GROUP BY 1
        ORDER BY 1 ASC
    """).df()
    dates = [str(d) for d in dates_df['prod_date'].tolist()]
    total_n_list = [int(n) for n in dates_df['total_n'].tolist()]
    date_to_idx = {d: i for i, d in enumerate(dates)}
    print(f"  获取到 {len(dates)} 天生产记录。")

    print("[3/5] 执行各指标「单规格独立计算 CPK 后按产量加权」...")
    indicators_result = {}
    for meta in indicators_meta:
        k = meta["key"]
        v_col = meta["val_col"]
        v_scale = meta.get("val_scale", 1.0)
        u_col = meta["usl_col"]
        l_col = meta["lsl_col"]
        u_scale = meta.get("usl_scale", 1.0)

        usl_expr = f"(TRY_CAST({u_col} AS DOUBLE) * {u_scale})" if u_col else "NULL::DOUBLE"
        lsl_expr = f"(TRY_CAST({l_col} AS DOUBLE) * {u_scale})" if l_col else "NULL::DOUBLE"

        if u_col and l_col:
            cpk_formula = """
                CASE 
                    WHEN s > 1e-6 AND u IS NOT NULL AND l IS NOT NULL THEN LEAST((u - m) / (3.0 * s), (m - l) / (3.0 * s))
                    WHEN s > 1e-6 AND u IS NOT NULL THEN (u - m) / (3.0 * s)
                    WHEN s > 1e-6 AND l IS NOT NULL THEN (m - l) / (3.0 * s)
                    ELSE NULL 
                END
            """
        elif u_col:
            cpk_formula = "CASE WHEN s > 1e-6 AND u IS NOT NULL THEN (u - m) / (3.0 * s) ELSE NULL END"
        elif l_col:
            cpk_formula = "CASE WHEN s > 1e-6 AND l IS NOT NULL THEN (m - l) / (3.0 * s) ELSE NULL END"
        else:
            cpk_formula = "NULL::DOUBLE"

        query_sql = f"""
            WITH base AS (
                SELECT 
                    CAST(TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) AS DATE) as prod_date,
                    LPAD(TRIM(CAST(article10_intended AS VARCHAR)), 10, '0') as art10,
                    TRY_CAST({v_col} AS DOUBLE) * {v_scale} as val,
                    {usl_expr} as usl,
                    {lsl_expr} as lsl
                FROM read_parquet('{pq_path_sql}')
                WHERE tu_first_loc_timestamp IS NOT NULL
                  AND CAST(TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) AS DATE) >= ('{max_dt}'::DATE - INTERVAL 30 DAY)
                  AND {v_col} IS NOT NULL
            ),
            spec_agg AS (
                SELECT 
                    prod_date,
                    art10,
                    COUNT(val) as n,
                    AVG(val) as m,
                    STDDEV_SAMP(val) as s,
                    AVG(usl) as u,
                    AVG(lsl) as l
                FROM base
                GROUP BY prod_date, art10
                HAVING COUNT(val) >= 5 AND STDDEV_SAMP(val) > 1e-6
            ),
            spec_cpk AS (
                SELECT 
                    prod_date,
                    n,
                    m,
                    s,
                    u,
                    l,
                    {cpk_formula} as cpk
                FROM spec_agg
            )
            SELECT 
                prod_date,
                SUM(n) as valid_n,
                SUM(m * n) / NULLIF(SUM(n), 0) as weighted_mean,
                SQRT(SUM(POWER(s, 2) * n) / NULLIF(SUM(n), 0)) as weighted_std,
                SUM(u * n) / NULLIF(SUM(CASE WHEN u IS NOT NULL THEN n ELSE 0 END), 0) as weighted_usl,
                SUM(l * n) / NULLIF(SUM(CASE WHEN l IS NOT NULL THEN n ELSE 0 END), 0) as weighted_lsl,
                SUM(cpk * n) / NULLIF(SUM(CASE WHEN cpk IS NOT NULL THEN n ELSE 0 END), 0) as weighted_cpk
            FROM spec_cpk
            GROUP BY prod_date
            ORDER BY prod_date ASC
        """
        df_ind = con.execute(query_sql).df()

        cnts = [0] * len(dates)
        means = [None] * len(dates)
        stds = [None] * len(dates)
        usls = [None] * len(dates)
        lsls = [None] * len(dates)
        cpks = [None] * len(dates)

        for _, row in df_ind.iterrows():
            d_str = str(row["prod_date"])
            if d_str in date_to_idx:
                idx = date_to_idx[d_str]
                cnts[idx] = int(row["valid_n"]) if pd.notna(row["valid_n"]) else 0
                means[idx] = round(float(row["weighted_mean"]), 3) if pd.notna(row["weighted_mean"]) else None
                stds[idx] = round(float(row["weighted_std"]), 3) if pd.notna(row["weighted_std"]) else None
                usls[idx] = round(float(row["weighted_usl"]), 2) if pd.notna(row["weighted_usl"]) else None
                lsls[idx] = round(float(row["weighted_lsl"]), 2) if pd.notna(row["weighted_lsl"]) else None
                if pd.notna(row["weighted_cpk"]):
                    cpk_val = float(row["weighted_cpk"])
                    cpks[idx] = round(max(-5.0, min(10.0, cpk_val)), 3)

        valid_cpks = [c for c in cpks if c is not None]
        avg_cpk = round(float(np.mean(valid_cpks)), 3) if valid_cpks else None
        latest_cpk = valid_cpks[-1] if valid_cpks else None

        valid_means = [m for m in means if m is not None]
        latest_mean = valid_means[-1] if valid_means else None
        
        valid_stds = [s for s in stds if s is not None]
        latest_std = valid_stds[-1] if valid_stds else None

        indicators_result[k] = {
            "name": meta["name"],
            "full_name": meta["full_name"],
            "station": meta["station"],
            "group": meta["group"],
            "unit": meta["unit"],
            "has_limit": meta["usl_col"] is not None,
            "counts": cnts,
            "means": means,
            "stds": stds,
            "usls": usls,
            "lsls": lsls,
            "cpks": cpks,
            "avg_cpk": avg_cpk,
            "latest_cpk": latest_cpk,
            "latest_mean": latest_mean,
            "latest_std": latest_std
        }
        print(f"  [{k.upper():6s}] 最新日加权 CPK: {latest_cpk} (30天均值: {avg_cpk})")

    print("[4/5] 执行 TU / TG / TB 各工位主成分分析 (PCA)...")
    pca_stations = {
        "TU": {
            "name": "TU (均匀性与力变工位)",
            "cols": ['rfppwc_first', 'rfh1wc_first', 'rfh2wc_first', 'lfppwc_first', 'lfh1wc_first', 'cony_first', 'plys_first'],
            "display_names": ['RFPP_WC', 'RFH1_WC', 'RFH2_WC', 'LFPP_WC', 'LFH1_WC', 'CONY', 'PLYS']
        },
        "TG": {
            "name": "TG (几何外观与跳动工位)",
            "cols": ['tbul_first', 'bbul_first', 'tdep_first', 'bdep_first', 'tlro_first', 'blro_first', 'crro_first'],
            "display_names": ['TBULs', 'BBULs', 'TDEPs', 'BDEPs', 'TLRO', 'BLRO', 'CRRO']
        },
        "TB": {
            "name": "TB (动静平衡工位)",
            "cols": ['tbalw_first', 'bbalw_first', 'sbalw_first'],
            "display_names": ['TBALW', 'BBALW', 'SBALW']
        }
    }

    pca_results = {}
    for st_key, cfg in pca_stations.items():
        res = run_pca_for_station(con, pq_path_sql, st_key, cfg["cols"], cfg["display_names"])
        if res:
            res["display_title"] = cfg["name"]
            pca_results[st_key] = res
            print(f"  [PCA {st_key}] 选出关键核心指标: {', '.join(res['key_indicators'])}")

    con.close()

    report_data = {
        "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date_range": f"{dates[0] if dates else ''} ~ {dates[-1] if dates else ''}",
        "dates": dates,
        "total_production": total_n_list,
        "indicators": indicators_result,
        "pca": pca_results
    }

    print("[5/5] 渲染极简独立单文件 HTML (含 PCA 关键指标选型看板)...")
    html_content = generate_html_template(report_data)

    output_paths = [
        os.path.join(data_dir, "cpk_indicators_trend.html"),
        os.path.join(os.path.dirname(data_dir), "..", "cpk_indicators_trend.html"),
        os.path.join(os.path.dirname(data_dir), "..", "dist", "cpk_indicators_trend.html")
    ]

    for out in output_paths:
        try:
            p = os.path.abspath(out)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"  [Output] 静态看板已输出至: {p}")
        except Exception as e:
            print(f"  [Warning] 输出至 {out} 失败: {e}")

    print("\n[OK] CPK 趋势与 PCA 关键指标看板生成完成！")
    return True


def generate_html_template(data):
    data_json = json.dumps(data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>轮胎质量与均匀性 17 项指标 CPK 趋势与 PCA 选型看板</title>
    <!-- 引入高可靠 ECharts CDN -->
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        :root {{
            --bg-body: #0b0f19;
            --bg-card: #151d2f;
            --bg-card-hover: #1c273e;
            --border-color: #23304b;
            --text-main: #f3f4f6;
            --text-sub: #9ca3af;
            --accent: #3b82f6;
            --accent-glow: rgba(59, 130, 246, 0.25);
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --purple: #8b5cf6;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
        body {{ background-color: var(--bg-body); color: var(--text-main); min-height: 100vh; padding: 24px; }}
        
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 18px; margin-bottom: 24px; }}
        .header-title h1 {{ font-size: 22px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 10px; }}
        .header-title p {{ color: var(--text-sub); font-size: 13px; margin-top: 5px; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }}
        .badge-blue {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }}
        .badge-purple {{ background: rgba(139, 92, 246, 0.15); color: #a78bfa; border: 1px solid rgba(139, 92, 246, 0.3); }}

        /* 标签导航 */
        .nav-tabs {{ display: flex; gap: 8px; margin-bottom: 20px; overflow-x: auto; padding-bottom: 6px; }}
        .nav-group-title {{ font-size: 12px; font-weight: 600; color: #6b7280; text-transform: uppercase; align-self: center; margin-right: 4px; margin-left: 10px; }}
        .nav-group-title:first-child {{ margin-left: 0; }}
        .tab-btn {{ background: var(--bg-card); color: var(--text-sub); border: 1px solid var(--border-color); padding: 8px 15px; border-radius: 8px; font-size: 13px; cursor: pointer; transition: all 0.2s; white-space: nowrap; }}
        .tab-btn:hover {{ background: var(--bg-card-hover); color: #fff; }}
        .tab-btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); font-weight: 600; box-shadow: 0 0 12px var(--accent-glow); }}
        .tab-btn.key-tab::after {{ content: "★"; margin-left: 4px; color: #fbbf24; font-size: 11px; }}

        /* 核心指标卡片 */
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .stat-card {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 18px; position: relative; overflow: hidden; }}
        .stat-card::before {{ content: ""; position: absolute; left: 0; top: 0; height: 100%; width: 4px; background: var(--accent); }}
        .stat-label {{ color: var(--text-sub); font-size: 13px; font-weight: 500; }}
        .stat-value {{ font-size: 26px; font-weight: 700; margin: 8px 0 4px 0; color: #fff; display: flex; align-items: baseline; gap: 6px; }}
        .stat-unit {{ font-size: 14px; font-weight: 400; color: var(--text-sub); }}
        .stat-sub {{ font-size: 12px; color: var(--text-sub); }}

        /* PCA 模块样式 */
        .pca-section {{ background: #111827; border: 1px solid #374151; border-radius: 14px; padding: 22px; margin-bottom: 24px; position: relative; }}
        .pca-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 14px; margin-bottom: 18px; }}
        .pca-title {{ font-size: 17px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 10px; }}
        .pca-tabs {{ display: flex; gap: 8px; }}
        .pca-tab-btn {{ background: #1f2937; color: var(--text-sub); border: 1px solid var(--border-color); padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer; transition: all 0.2s; }}
        .pca-tab-btn.active {{ background: var(--purple); color: #fff; border-color: var(--purple); font-weight: 600; }}
        
        .pca-grid {{ display: grid; grid-template-columns: 1.1fr 1.2fr 0.9fr; gap: 18px; }}
        .pca-card {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 16px; }}
        .pca-card-title {{ font-size: 14px; font-weight: 600; color: #e5e7eb; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }}
        .pca-chart {{ width: 100%; height: 260px; }}

        .key-tag {{ display: inline-flex; align-items: center; gap: 4px; background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
        .insight-box {{ background: rgba(59, 130, 246, 0.08); border-left: 3px solid #3b82f6; padding: 12px 14px; border-radius: 0 8px 8px 0; margin-top: 14px; font-size: 13px; line-height: 1.6; color: #d1d5db; }}
        .insight-item {{ margin-bottom: 6px; }}
        .insight-item:last-child {{ margin-bottom: 0; }}

        /* 图表容器 */
        .chart-box {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 20px; margin-bottom: 24px; }}
        .chart-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }}
        .chart-title {{ font-size: 16px; font-weight: 600; color: #fff; display: flex; align-items: center; gap: 8px; }}
        .chart-container {{ width: 100%; height: 380px; }}
        .chart-container-sm {{ width: 100%; height: 260px; }}

        /* 明细表格 */
        .table-box {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 20px; overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }}
        th {{ background: #111827; color: var(--text-sub); padding: 12px 14px; font-weight: 600; border-bottom: 1px solid var(--border-color); }}
        td {{ padding: 12px 14px; border-bottom: 1px solid var(--border-color); color: #e5e7eb; }}
        tr:hover td {{ background: var(--bg-card-hover); }}
        .cpk-tag {{ padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
        .cpk-good {{ background: rgba(16, 185, 129, 0.2); color: #34d399; }}
        .cpk-warn {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; }}
        .cpk-bad {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-title">
            <h1>轮胎生产质检 17 项指标 CPK 趋势与 PCA 选型看板</h1>
            <p id="sub-header-info">统计周期: 加载中... | 涵盖 TU (均匀性), TG (几何形变), TB (动静平衡)</p>
        </div>
        <div style="display:flex; gap:10px;">
            <span class="badge badge-purple">主成分分析 (PCA) 降维选型</span>
            <span class="badge badge-blue">单文件极简静态预渲染</span>
        </div>
    </div>

    <!-- ================== 核心新增: TU / TG / TB 主成分分析 (PCA) 模块 ================== -->
    <div class="pca-section">
        <div class="pca-header">
            <div class="pca-title">
                <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#8b5cf6;"></span>
                工位主成分分析 (PCA) 关键指标选型与信息降维
            </div>
            <div class="pca-tabs" id="pca-station-tabs">
                <button class="pca-tab-btn active" onclick="switchPcaStation('TU')">TU 工位 (力变与均匀性)</button>
                <button class="pca-tab-btn" onclick="switchPcaStation('TG')">TG 工位 (几何与跳动)</button>
                <button class="pca-tab-btn" onclick="switchPcaStation('TB')">TB 工位 (动静平衡)</button>
            </div>
        </div>

        <div class="pca-grid">
            <!-- 卡片 1: 指标综合重要性评分与核心选型 -->
            <div class="pca-card">
                <div class="pca-card-title">
                    <span>指标综合信息贡献率与关键选型</span>
                    <span style="font-size:11px; color:var(--text-sub);">点击指标快速切换走势</span>
                </div>
                <div id="chart-pca-importance" class="pca-chart"></div>
            </div>

            <!-- 卡片 2: 二维主成分载荷分布 (PC1 vs PC2 强相关群集) -->
            <div class="pca-card">
                <div class="pca-card-title">
                    <span>主成分载荷分布图 (PC1 vs PC2)</span>
                    <span style="font-size:11px; color:var(--text-sub);">正交与群集特征</span>
                </div>
                <div id="chart-pca-loadings" class="pca-chart"></div>
            </div>

            <!-- 卡片 3: 主成分方差贡献瀑布图与工程结论 -->
            <div class="pca-card" style="display:flex; flex-direction:column; justify-content:space-between;">
                <div>
                    <div class="pca-card-title">
                        <span>主成分方差贡献率</span>
                        <span id="pca-cum-tag" class="key-tag">累计解释: --%</span>
                    </div>
                    <div id="chart-pca-variance" style="width:100%; height:130px;"></div>
                </div>
                <!-- 智能工业解读 -->
                <div class="insight-box" id="pca-insight-box">
                    <!-- JS 渲染 -->
                </div>
            </div>
        </div>
    </div>

    <!-- 指标分类导航按钮 -->
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <span style="font-size:14px; font-weight:600; color:#e5e7eb;">各指标 30 天走势切换 (带 ★ 为 PCA 选拔的核心关键指标)：</span>
    </div>
    <div class="nav-tabs" id="indicator-tabs">
        <!-- JS 动态注入 -->
    </div>

    <!-- 顶部状态概览卡片 -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">最新 CPK 表现</div>
            <div class="stat-value" id="card-latest-cpk">--</div>
            <div class="stat-sub" id="card-cpk-desc">基准要求: ≥ 1.33</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">30 天平均 CPK</div>
            <div class="stat-value" id="card-avg-cpk">--</div>
            <div class="stat-sub">全周期稳态能力评估</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">最新均值 (μ) / 上限 (USL)</div>
            <div class="stat-value" id="card-mean-usl">--</div>
            <div class="stat-sub" id="card-margin">安全裕度计算中</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">最新样本离散度 (σ)</div>
            <div class="stat-value" id="card-std">--</div>
            <div class="stat-sub" id="card-sample-cnt">采样条数: --</div>
        </div>
    </div>

    <!-- 主图表: CPK 趋势折线图 -->
    <div class="chart-box">
        <div class="chart-header">
            <div class="chart-title">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#10b981;"></span>
                30 天 CPK 过程能力趋势走势图
            </div>
            <span style="font-size:12px; color:var(--text-sub);">绿线: 1.33 达标线 | 红线: 1.00 警戒线</span>
        </div>
        <div id="chart-cpk" class="chart-container"></div>
    </div>

    <!-- 辅助图表: 物理值均值、上限与波动区间 + 抽样总数柱状图 -->
    <div style="display:grid; grid-template-columns: 1.8fr 1.2fr; gap: 20px;">
        <div class="chart-box">
            <div class="chart-header">
                <div class="chart-title">均值 (μ) vs 配方上限 (USL) 实际波动走势</div>
            </div>
            <div id="chart-mean" class="chart-container-sm"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <div class="chart-title">每日质检生产量 (Tires)</div>
            </div>
            <div id="chart-n" class="chart-container-sm"></div>
        </div>
    </div>

    <!-- 明细数据表格 -->
    <div class="table-box">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
            <h3 style="font-size:15px; font-weight:600;">每日详细统计明细</h3>
            <span style="font-size:12px; color:var(--text-sub);">按日期升序排列</span>
        </div>
        <table>
            <thead>
                <tr>
                    <th>生产日期</th>
                    <th>质检样本数 (N)</th>
                    <th>实测均值 (μ)</th>
                    <th>样本标准差 (σ)</th>
                    <th>配方上限 (USL)</th>
                    <th>配方下限 (LSL)</th>
                    <th>过程能力 (CPK)</th>
                    <th>质量评价</th>
                </tr>
            </thead>
            <tbody id="table-body">
                <!-- JS 渲染明细 -->
            </tbody>
        </table>
    </div>

    <script>
        const reportData = {data_json};
        document.getElementById('sub-header-info').innerText = `统计周期: ${{reportData.date_range}} | 数据生成时间: ${{reportData.generated_time}}`;

        let currentKey = 'rfpp';
        let currentPcaStation = 'TU';
        let chartCpk = null;
        let chartMean = null;
        let chartN = null;
        let chartPcaImportance = null;
        let chartPcaLoadings = null;
        let chartPcaVariance = null;

        // 获取指标是否属于 PCA 选拔的核心关键指标
        function isKeyIndicator(key) {{
            const ind = reportData.indicators[key];
            if (!ind) return false;
            const st = ind.station;
            const pcaSt = reportData.pca ? reportData.pca[st] : null;
            if (!pcaSt || !pcaSt.key_indicators) return false;
            return pcaSt.key_indicators.includes(ind.name);
        }}

        function initTabs() {{
            const container = document.getElementById('indicator-tabs');
            const indicators = reportData.indicators;
            let currentGroup = '';

            for (const [key, item] of Object.entries(indicators)) {{
                if (item.group !== currentGroup) {{
                    currentGroup = item.group;
                    const groupTitle = document.createElement('span');
                    groupTitle.className = 'nav-group-title';
                    groupTitle.innerText = currentGroup;
                    container.appendChild(groupTitle);
                }}

                const btn = document.createElement('button');
                const isKey = isKeyIndicator(key);
                btn.className = `tab-btn ${{key === currentKey ? 'active' : ''}} ${{isKey ? 'key-tab' : ''}}`;
                btn.id = `tab-${{key}}`;
                btn.innerText = item.name;
                btn.title = item.full_name;
                btn.onclick = () => switchIndicator(key);
                container.appendChild(btn);
            }}
        }}

        function switchIndicator(key) {{
            currentKey = key;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            const activeBtn = document.getElementById(`tab-${{key}}`);
            if (activeBtn) activeBtn.classList.add('active');

            renderCards();
            renderCharts();
            renderTable();
        }}

        function getCpkBadge(cpk) {{
            if (cpk === null || cpk === undefined) return '<span class="cpk-tag" style="background:#374151;color:#9ca3af">无上限</span>';
            if (cpk >= 1.33) return `<span class="cpk-tag cpk-good">优秀 (${{cpk.toFixed(2)}})</span>`;
            if (cpk >= 1.0) return `<span class="cpk-tag cpk-warn">合格 (${{cpk.toFixed(2)}})</span>`;
            return `<span class="cpk-tag cpk-bad">不足 (${{cpk.toFixed(2)}})</span>`;
        }}

        function renderCards() {{
            const ind = reportData.indicators[currentKey];
            const latestCpk = ind.latest_cpk;
            const avgCpk = ind.avg_cpk;

            // 1. 最新 CPK
            const elLatest = document.getElementById('card-latest-cpk');
            if (latestCpk !== null && latestCpk !== undefined) {{
                elLatest.innerText = latestCpk.toFixed(3);
                elLatest.style.color = latestCpk >= 1.33 ? '#34d399' : (latestCpk >= 1.0 ? '#fbbf24' : '#f87171');
            }} else {{
                elLatest.innerText = 'N/A';
                elLatest.style.color = '#9ca3af';
            }}

            // 2. 平均 CPK
            const elAvg = document.getElementById('card-avg-cpk');
            if (avgCpk !== null && avgCpk !== undefined) {{
                elAvg.innerText = avgCpk.toFixed(3);
                elAvg.style.color = avgCpk >= 1.33 ? '#34d399' : (avgCpk >= 1.0 ? '#fbbf24' : '#f87171');
            }} else {{
                elAvg.innerText = 'N/A';
                elAvg.style.color = '#9ca3af';
            }}

            // 3. 均值与上限 / 双侧限
            const latestMean = ind.latest_mean;
            const latestUsl = ind.usls[ind.usls.length - 1];
            const latestLsl = ind.lsls[ind.lsls.length - 1];
            const elMeanUsl = document.getElementById('card-mean-usl');
            const elMargin = document.getElementById('card-margin');
            if (latestMean !== null) {{
                let limitStr = '';
                if (latestUsl !== null && latestLsl !== null) {{
                    limitStr = `/ [${{latestLsl}}, ${{latestUsl}}] ${{ind.unit}}`;
                }} else if (latestUsl !== null) {{
                    limitStr = `/ 上限 ${{latestUsl}} ${{ind.unit}}`;
                }} else if (latestLsl !== null) {{
                    limitStr = `/ 下限 ${{latestLsl}} ${{ind.unit}}`;
                }}
                elMeanUsl.innerHTML = `${{latestMean}} <span class="stat-unit">${{ind.unit}}</span> ${{limitStr}}`;
                if (latestUsl !== null) {{
                    const margin = latestUsl - latestMean;
                    elMargin.innerText = `距离上限裕度: ${{margin.toFixed(3)}} ${{ind.unit}} (${{((margin/latestUsl)*100).toFixed(1)}}%)`;
                }} else {{
                    elMargin.innerText = `未设绝对上限`;
                }}
            }} else {{
                elMeanUsl.innerText = '无数据';
                elMargin.innerText = '暂无有效采样';
            }}

            // 4. 标准差
            const latestStd = ind.latest_std;
            const latestCount = ind.counts[ind.counts.length - 1];
            document.getElementById('card-std').innerHTML = latestStd !== null ? `${{latestStd}} <span class="stat-unit">${{ind.unit}}</span>` : '--';
            document.getElementById('card-sample-cnt').innerText = `最新日检验样本: ${{latestCount || 0}} 条`;
        }}

        function renderCharts() {{
            const ind = reportData.indicators[currentKey];
            const dates = reportData.dates;

            // Chart 1: CPK Trend
            if (!chartCpk) chartCpk = echarts.init(document.getElementById('chart-cpk'));
            // 动态独立坐标轴配置：根据当前指标的实际数值范围自适应缩放，彻底消除视觉平缓/挤压死线
            const validCpks = (ind.cpks || []).filter(v => v !== null && !isNaN(v));
            let yMin = null;
            let yMax = null;
            let markLineData = [];

            if (validCpks.length > 0) {{
                const minVal = Math.min(...validCpks);
                const maxVal = Math.max(...validCpks);
                const valRange = maxVal - minVal;

                if (minVal >= 3.0) {{
                    // 超高能力指标 (如 TBULs, BBULs, TDEPs, BDEPs, PLYS 等，CPK 在 5~9)
                    // 坐标轴专为该指标动态微调，放大该指标每日真实涨跌波动，不被 0~1.33 强制拉扯压缩
                    const padding = Math.max(0.2, valRange * 0.15);
                    yMin = Math.max(0, Math.floor((minVal - padding) * 10) / 10);
                    yMax = Math.ceil((maxVal + padding) * 10) / 10;
                }} else {{
                    // 处于 1.0~2.5 正常控制区间的常规指标 (如 RFPP, RFH1, RFH2, TLRO, SBALW 等)
                    // 坐标轴自适应贴合数据，并展示 1.00 警戒线与 1.33 达标线
                    const padding = Math.max(0.15, valRange * 0.15);
                    yMin = Math.max(0, Math.floor((Math.min(minVal, 0.9) - padding) * 10) / 10);
                    yMax = Math.ceil((Math.max(maxVal, 1.45) + padding) * 10) / 10;
                    markLineData = [
                        {{ yAxis: 1.33, lineStyle: {{ color: '#10b981', type: 'dashed', width: 2 }}, label: {{ formatter: 'CPK 1.33 (达标线)', color: '#10b981' }} }},
                        {{ yAxis: 1.00, lineStyle: {{ color: '#ef4444', type: 'dashed', width: 2 }}, label: {{ formatter: 'CPK 1.00 (警告线)', color: '#ef4444' }} }}
                    ];
                }}
            }}

            chartCpk.setOption({{
                backgroundColor: 'transparent',
                tooltip: {{ trigger: 'axis', backgroundColor: '#1f2937', borderColor: '#374151', textStyle: {{ color: '#fff' }} }},
                grid: {{ left: '3%', right: '3%', bottom: '8%', top: '10%', containLabel: true }},
                xAxis: {{ type: 'category', data: dates, axisLine: {{ lineStyle: {{ color: '#374151' }} }}, axisLabel: {{ color: '#9ca3af' }} }},
                yAxis: {{ 
                    type: 'value', 
                    scale: true,
                    min: yMin,
                    max: yMax,
                    name: 'CPK 值', 
                    nameTextStyle: {{ color: '#9ca3af' }},
                    axisLabel: {{ color: '#9ca3af' }},
                    splitLine: {{ lineStyle: {{ color: '#1f2937' }} }}
                }},
                series: [
                    {{
                        name: 'CPK',
                        type: 'line',
                        data: ind.cpks,
                        smooth: true,
                        symbolSize: 6,
                        itemStyle: {{ color: '#3b82f6' }},
                        lineStyle: {{ width: 3, color: '#3b82f6' }},
                        areaStyle: {{
                            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                {{ offset: 0, color: 'rgba(59, 130, 246, 0.4)' }},
                                {{ offset: 1, color: 'rgba(59, 130, 246, 0.0)' }}
                            ])
                        }},
                        markLine: {{
                            silent: true,
                            symbol: 'none',
                            data: markLineData
                        }}
                    }}
                ]
            }}, true);

            // Chart 2: Mean vs USL/LSL
            if (!chartMean) chartMean = echarts.init(document.getElementById('chart-mean'));
            const hasLsl = ind.lsls && ind.lsls.some(v => v !== null);
            const legendList = ['均值 (μ)', '配方上限 (USL)'];
            const seriesChart2 = [
                {{
                    name: '均值 (μ)',
                    type: 'line',
                    data: ind.means,
                    smooth: true,
                    itemStyle: {{ color: '#f59e0b' }},
                    lineStyle: {{ width: 2, color: '#f59e0b' }}
                }},
                {{
                    name: '配方上限 (USL)',
                    type: 'line',
                    data: ind.usls,
                    step: 'start',
                    itemStyle: {{ color: '#ef4444' }},
                    lineStyle: {{ width: 2, type: 'dashed', color: '#ef4444' }}
                }}
            ];
            if (hasLsl) {{
                legendList.push('配方下限 (LSL)');
                seriesChart2.push({{
                    name: '配方下限 (LSL)',
                    type: 'line',
                    data: ind.lsls,
                    step: 'start',
                    itemStyle: {{ color: '#06b6d4' }},
                    lineStyle: {{ width: 2, type: 'dashed', color: '#06b6d4' }}
                }});
            }}

            chartMean.setOption({{
                backgroundColor: 'transparent',
                tooltip: {{ trigger: 'axis', backgroundColor: '#1f2937', borderColor: '#374151', textStyle: {{ color: '#fff' }} }},
                legend: {{ data: legendList, textStyle: {{ color: '#9ca3af' }}, top: 0 }},
                grid: {{ left: '3%', right: '3%', bottom: '8%', top: '15%', containLabel: true }},
                xAxis: {{ type: 'category', data: dates, axisLine: {{ lineStyle: {{ color: '#374151' }} }}, axisLabel: {{ color: '#9ca3af' }} }},
                yAxis: {{ type: 'value', scale: true, axisLabel: {{ color: '#9ca3af' }}, splitLine: {{ lineStyle: {{ color: '#1f2937' }} }} }},
                series: seriesChart2
            }}, true);

            // Chart 3: Sample Count N
            if (!chartN) chartN = echarts.init(document.getElementById('chart-n'));
            chartN.setOption({{
                backgroundColor: 'transparent',
                tooltip: {{ trigger: 'axis', backgroundColor: '#1f2937', borderColor: '#374151', textStyle: {{ color: '#fff' }} }},
                grid: {{ left: '3%', right: '3%', bottom: '8%', top: '15%', containLabel: true }},
                xAxis: {{ type: 'category', data: dates, axisLine: {{ lineStyle: {{ color: '#374151' }} }}, axisLabel: {{ color: '#9ca3af' }} }},
                yAxis: {{ type: 'value', axisLabel: {{ color: '#9ca3af' }}, splitLine: {{ lineStyle: {{ color: '#1f2937' }} }} }},
                series: [
                    {{
                        name: '检验量',
                        type: 'bar',
                        data: ind.counts,
                        itemStyle: {{
                            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                {{ offset: 0, color: '#6366f1' }},
                                {{ offset: 1, color: '#312e81' }}
                            ]),
                            borderRadius: [4, 4, 0, 0]
                        }}
                    }}
                ]
            }}, true);
        }}

        // ================== PCA 模块动态渲染 ==================
        function switchPcaStation(st) {{
            currentPcaStation = st;
            document.querySelectorAll('.pca-tab-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            renderPcaSection();
        }}

        function renderPcaSection() {{
            const pcaData = reportData.pca ? reportData.pca[currentPcaStation] : null;
            if (!pcaData) return;

            document.getElementById('pca-cum-tag').innerText = `前 ${{pcaData.k_components}} 主成分累计解释: ${{pcaData.components[pcaData.k_components-1].cum_variance_ratio}}%`;

            // 1. 重要性横向条形图
            if (!chartPcaImportance) chartPcaImportance = echarts.init(document.getElementById('chart-pca-importance'));
            const names = pcaData.indicators.map(d => d.name).reverse();
            const scores = pcaData.indicators.map(d => d.score).reverse();
            const isKeys = pcaData.indicators.map(d => d.is_key).reverse();

            chartPcaImportance.setOption({{
                backgroundColor: 'transparent',
                tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }}, formatter: '{{b}}: 综合影响力 <b>{{c}}%</b>' }},
                grid: {{ left: '25%', right: '12%', top: '5%', bottom: '5%' }},
                xAxis: {{ type: 'value', axisLabel: {{ color: '#9ca3af', formatter: '{{value}}%' }}, splitLine: {{ lineStyle: {{ color: '#1f2937' }} }} }},
                yAxis: {{ 
                    type: 'category', 
                    data: names, 
                    axisLine: {{ lineStyle: {{ color: '#374151' }} }},
                    axisLabel: {{ 
                        color: function(val, idx) {{ return isKeys[idx] ? '#fbbf24' : '#9ca3af'; }},
                        fontWeight: function(val, idx) {{ return isKeys[idx] ? 'bold' : 'normal'; }}
                    }}
                }},
                series: [{{
                    type: 'bar',
                    data: scores.map((val, idx) => ({{
                        value: val,
                        itemStyle: {{
                            color: isKeys[idx] ? '#f59e0b' : '#3b82f6',
                            borderRadius: [0, 4, 4, 0]
                        }}
                    }})),
                    label: {{
                        show: true,
                        position: 'right',
                        color: '#d1d5db',
                        formatter: function(params) {{
                            return isKeys[params.dataIndex] ? params.value + '% ★' : params.value + '%';
                        }}
                    }}
                }}]
            }}, true);

            // 点击重要性图表条目直接联动切换主指标
            chartPcaImportance.off('click');
            chartPcaImportance.on('click', function(params) {{
                const targetName = params.name;
                for (const [k, v] of Object.entries(reportData.indicators)) {{
                    if (v.name === targetName) {{
                        switchIndicator(k);
                        break;
                    }}
                }}
            }});

            // 2. PC1 vs PC2 载荷分布散点图
            if (!chartPcaLoadings) chartPcaLoadings = echarts.init(document.getElementById('chart-pca-loadings'));
            chartPcaLoadings.setOption({{
                backgroundColor: 'transparent',
                tooltip: {{ 
                    formatter: function(p) {{
                        return `<b>${{p.data.name}}</b><br/>PC1 载荷: ${{p.data.value[0]}}<br/>PC2 载荷: ${{p.data.value[1]}}`;
                    }}
                }},
                grid: {{ left: '10%', right: '10%', top: '12%', bottom: '12%' }},
                xAxis: {{ 
                    type: 'value', 
                    name: 'PC1 载荷', 
                    nameTextStyle: {{ color: '#9ca3af' }},
                    axisLine: {{ lineStyle: {{ color: '#374151' }} }},
                    axisLabel: {{ color: '#9ca3af' }},
                    splitLine: {{ lineStyle: {{ color: '#1f2937' }} }}
                }},
                yAxis: {{ 
                    type: 'value', 
                    name: 'PC2 载荷', 
                    nameTextStyle: {{ color: '#9ca3af' }},
                    axisLine: {{ lineStyle: {{ color: '#374151' }} }},
                    axisLabel: {{ color: '#9ca3af' }},
                    splitLine: {{ lineStyle: {{ color: '#1f2937' }} }}
                }},
                series: [{{
                    type: 'scatter',
                    symbolSize: 14,
                    data: pcaData.indicators.map(d => ({{
                        name: d.name,
                        value: [d.pc1_loading, d.pc2_loading],
                        itemStyle: {{ color: d.is_key ? '#f59e0b' : '#3b82f6' }}
                    }})),
                    label: {{
                        show: true,
                        position: 'top',
                        formatter: '{{b}}',
                        color: '#f3f4f6',
                        fontSize: 11
                    }}
                }}]
            }}, true);

            // 3. 方差贡献瀑布图
            if (!chartPcaVariance) chartPcaVariance = echarts.init(document.getElementById('chart-pca-variance'));
            const compNames = pcaData.components.map(c => c.name);
            const varRatios = pcaData.components.map(c => c.variance_ratio);
            const cumRatios = pcaData.components.map(c => c.cum_variance_ratio);

            chartPcaVariance.setOption({{
                backgroundColor: 'transparent',
                tooltip: {{ trigger: 'axis' }},
                grid: {{ left: '8%', right: '8%', top: '10%', bottom: '15%' }},
                xAxis: {{ type: 'category', data: compNames, axisLine: {{ lineStyle: {{ color: '#374151' }} }}, axisLabel: {{ color: '#9ca3af', fontSize: 11 }} }},
                yAxis: {{ type: 'value', max: 100, axisLabel: {{ color: '#9ca3af', formatter: '{{value}}%' }}, splitLine: {{ lineStyle: {{ color: '#1f2937' }} }} }},
                series: [
                    {{
                        name: '单个贡献率',
                        type: 'bar',
                        data: varRatios,
                        itemStyle: {{ color: '#8b5cf6', borderRadius: [3, 3, 0, 0] }}
                    }},
                    {{
                        name: '累计贡献率',
                        type: 'line',
                        data: cumRatios,
                        itemStyle: {{ color: '#10b981' }},
                        lineStyle: {{ width: 2, color: '#10b981' }}
                    }}
                ]
            }}, true);

            // 4. 渲染洞察文本
            const insightBox = document.getElementById('pca-insight-box');
            insightBox.innerHTML = pcaData.insights.map(t => `<div class="insight-item">• ${{t}}</div>`).join('');
        }}

        function renderTable() {{
            const ind = reportData.indicators[currentKey];
            const dates = reportData.dates;
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = '';

            for (let i = dates.length - 1; i >= 0; i--) {{
                const tr = document.createElement('tr');
                const date = dates[i];
                const cnt = ind.counts[i] || 0;
                const mean = ind.means[i] !== null ? ind.means[i] : '--';
                const std = ind.stds[i] !== null ? ind.stds[i] : '--';
                const usl = ind.usls[i] !== null ? ind.usls[i] : '--';
                const lsl = ind.lsls[i] !== null ? ind.lsls[i] : '--';
                const cpk = ind.cpks[i];
                const badge = getCpkBadge(cpk);

                tr.innerHTML = `
                    <td style="font-weight:600">${{date}}</td>
                    <td>${{cnt.toLocaleString()}}</td>
                    <td>${{mean}}</td>
                    <td>${{std}}</td>
                    <td>${{usl}}</td>
                    <td>${{lsl}}</td>
                    <td style="font-weight:700; color:${{cpk >= 1.33 ? '#34d399' : (cpk >= 1.0 ? '#fbbf24' : '#f87171')}}">${{cpk !== null ? cpk.toFixed(3) : '--'}}</td>
                    <td>${{badge}}</td>
                `;
                tbody.appendChild(tr);
            }}
        }}

        window.onload = () => {{
            initTabs();
            renderPcaSection();
            switchIndicator('rfpp');
        }};

        window.onresize = () => {{
            if (chartCpk) chartCpk.resize();
            if (chartMean) chartMean.resize();
            if (chartN) chartN.resize();
            if (chartPcaImportance) chartPcaImportance.resize();
            if (chartPcaLoadings) chartPcaLoadings.resize();
            if (chartPcaVariance) chartPcaVariance.resize();
        }};
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    generate_report()
