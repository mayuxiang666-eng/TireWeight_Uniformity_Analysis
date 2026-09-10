import duckdb
import os
import numpy as np

con = duckdb.connect()
parquet_path = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
cgrs_path = "untitled1_v2/backend/data/CGRS.csv"

con.execute(f"CREATE TABLE clean_yield AS SELECT * FROM read_parquet('{parquet_path}')")
con.execute(f"""
    CREATE OR REPLACE TABLE cgrs_records AS 
    SELECT 
        *,
        COALESCE(
            TRY_CAST(STRPTIME(SPLIT_PART(TechOffsetLocalDate, ' ', 1), '%Y/%m/%d') AS DATE),
            TRY_CAST(SPLIT_PART(TechOffsetLocalDate, ' ', 1) AS DATE)
        ) AS match_date,
        COALESCE(
            TRY_CAST(STRPTIME(TechOffsetLocalDate, '%Y/%m/%d %H:%M') AS TIMESTAMP),
            TRY_CAST(STRPTIME(TechOffsetLocalDate, '%Y/%m/%d %H:%M:%S') AS TIMESTAMP),
            TRY_CAST(TechOffsetLocalDate AS TIMESTAMP)
        ) AS event_timestamp
    FROM read_csv_auto('{cgrs_path}', all_varchar=True)
""")

cols = [r[0] for r in con.execute("DESCRIBE clean_yield").fetchall()]
if 'tu_first_loc_timestamp' not in cols and 'tu_first_shift_date' in cols:
    con.execute("ALTER TABLE clean_yield ADD COLUMN tu_first_loc_timestamp VARCHAR")
    con.execute("UPDATE clean_yield SET tu_first_loc_timestamp = COALESCE(gt_loc_timestamp, tu_first_shift_date)")

def calc_cpk(mean, std, usl, lsl=None):
    if std <= 1e-6:
        return 1.33
    if lsl is None:
        return max(0.0, min(5.0, (usl - mean) / (3.0 * std)))
    cpu = (usl - mean) / (3.0 * std)
    cpl = (mean - lsl) / (3.0 * std)
    return max(0.0, min(5.0, min(cpu, cpl)))

def get_spec_limits(art, ind):
    if ind == 'weight':
        return 0.28, -0.28
    if ind == 'cony':
        return 95.0, -95.0
    return 100.0, None

def calculate_cgrs_cpk_comparison(workcenter, article10, target_date=None, indicator="rfpp", limit_n=50):
    wc_clean = str(workcenter).strip().upper()
    cgrs_candidates = [wc_clean]
    gt_candidates = [wc_clean]
    
    if wc_clean.startswith("TB2"):
        cgrs_candidates.append("TB1" + wc_clean[3:])
        gt_candidates.append("TB" + wc_clean[3:])
    elif wc_clean.startswith("TB1"):
        gt_candidates.append("TB2" + wc_clean[3:])
        gt_candidates.append("TB" + wc_clean[3:])
    elif wc_clean.startswith("TB") and len(wc_clean) == 4 and wc_clean[2:].isdigit():
        cgrs_candidates.append("TB1" + wc_clean[2:])
        gt_candidates.append("TB2" + wc_clean[2:])

    # 1. 查询该机台在指定日期的所有 CGRS 调参事件
    cgrs_placeholders = ",".join(["?"] * len(cgrs_candidates))
    cgrs_sql = f"""
        SELECT 
            event_timestamp,
            TechOffsetLocalDate,
            ParameterLocalName,
            ParameterName,
            ParameterValue,
            TechOffsetHistoryValueFrom,
            TechOffsetHistoryValueTo,
            TechOffsetValue,
            ParameterUnitSymbol,
            ProdSpecific2,
            COALESCE(TechOffsetComments, TechOffsetHistoryComments, '') AS comments
        FROM cgrs_records
        WHERE Workcenter IN ({cgrs_placeholders})
          AND event_timestamp IS NOT NULL
    """
    cgrs_params = list(cgrs_candidates)
    if target_date:
        cgrs_sql += " AND match_date = ?::DATE"
        cgrs_params.append(target_date)
    
    if article10 and article10.strip():
        art_clean = article10.strip()
        prefix7 = art_clean[:7]
        cgrs_sql += " AND (ProdSpecific2 IS NULL OR ProdSpecific2 = '' OR ProdSpecific2 = ? OR ProdSpecific2 LIKE ? OR ProdSpecific1 = ? OR ProdSpecific1 LIKE ?)"
        cgrs_params.extend([art_clean, f"{prefix7}%", art_clean, f"{prefix7}%"])
        
    cgrs_sql += " ORDER BY event_timestamp DESC"
    
    raw_rows = con.execute(cgrs_sql, cgrs_params).fetchall()
    cols_desc = [d[0] for d in con.description]
    cgrs_rows = [dict(zip(cols_desc, r)) for r in raw_rows]
    
    if not cgrs_rows:
        return {"has_cgrs": False, "events_count": 0, "events": []}
        
    # 按 event_timestamp 分组聚合多参数批次调整
    grouped_events = {}
    for r in cgrs_rows:
        ts = r['event_timestamp']
        if ts not in grouped_events:
            grouped_events[ts] = {
                "timestamp": ts,
                "date_time_str": r['TechOffsetLocalDate'],
                "params_changed": []
            }
        grouped_events[ts]["params_changed"].append({
            "param_local": r['ParameterLocalName'] or r['ParameterName'],
            "param_code": r['ParameterName'],
            "std_val": r['ParameterValue'],
            "from_val": r['TechOffsetHistoryValueFrom'],
            "to_val": r['TechOffsetHistoryValueTo'] or r['TechOffsetValue'],
            "unit": r['ParameterUnitSymbol'],
            "comments": r['comments']
        })
        
    if indicator == "weight":
        ind_col = "((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)"
        val_extra = ", (TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) as diff_kg"
    elif indicator == "cony":
        ind_col = "TRY_CAST(cony_first AS DOUBLE)"
        val_extra = ""
    else:
        ind_col = f"TRY_CAST({'rfppwc_first' if indicator == 'rfpp' else 'rfh1wc_first'} AS DOUBLE)"
        val_extra = ""
        
    usl, lsl = get_spec_limits(article10, indicator)
    gt_placeholders = ",".join(["?"] * len(gt_candidates))
    
    events_result = []
    
    for ts, ev in grouped_events.items():
        base_where = f"gt_workcenter IN ({gt_placeholders}) AND article10 = ? AND {ind_col} IS NOT NULL"
        base_params = list(gt_candidates) + [article10]
        
        # 修改前 50 条 (DESC: 紧靠修改时刻之前)
        sql_before = f"""
            SELECT 
                {ind_col} as val
                {val_extra}
            FROM clean_yield
            WHERE {base_where}
              AND TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) < ?::TIMESTAMP
            ORDER BY TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) DESC
            LIMIT {limit_n}
        """
        rows_before = con.execute(sql_before, base_params + [ts]).fetchall()
        
        # 修改后 50 条 (ASC: 紧靠修改时刻之后)
        sql_after = f"""
            SELECT 
                {ind_col} as val
                {val_extra}
            FROM clean_yield
            WHERE {base_where}
              AND TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) >= ?::TIMESTAMP
            ORDER BY TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) ASC
            LIMIT {limit_n}
        """
        rows_after = con.execute(sql_after, base_params + [ts]).fetchall()
        
        vals_before = [float(r[0]) for r in rows_before if r[0] is not None]
        vals_after = [float(r[0]) for r in rows_after if r[0] is not None]
        
        n_before = len(vals_before)
        n_after = len(vals_after)
        
        if n_before == 0 and n_after == 0:
            continue
            
        mean_before = float(np.mean(vals_before)) if n_before > 0 else 0.0
        std_before = float(np.std(vals_before, ddof=1)) if n_before > 1 else (float(np.std(vals_before)) if n_before == 1 else 0.0)
        
        mean_after = float(np.mean(vals_after)) if n_after > 0 else 0.0
        std_after = float(np.std(vals_after, ddof=1)) if n_after > 1 else (float(np.std(vals_after)) if n_after == 1 else 0.0)
        
        mean_diff = mean_after - mean_before
        
        if indicator == "weight":
            cpk_before = mean_before
            cpk_after = mean_after
            cpk_diff = mean_diff
            yoy_pct = ((abs(mean_before) - abs(mean_after)) / abs(mean_before) * 100.0) if abs(mean_before) > 1e-4 else 0.0
        else:
            cpk_before = calc_cpk(mean_before, std_before, usl, lsl)
            cpk_after = calc_cpk(mean_after, std_after, usl, lsl)
            cpk_diff = cpk_after - cpk_before
            yoy_pct = ((cpk_after - cpk_before) / cpk_before * 100.0) if cpk_before > 1e-4 else 0.0
            
        events_result.append({
            "timestamp": str(ts),
            "date_time_str": ev["date_time_str"],
            "params_changed": ev["params_changed"],
            "n_before": n_before,
            "n_after": n_after,
            "mean_before": round(mean_before, 3),
            "mean_after": round(mean_after, 3),
            "std_before": round(std_before, 3),
            "std_after": round(std_after, 3),
            "mean_diff": round(mean_diff, 3),
            "cpk_before": round(cpk_before, 3),
            "cpk_after": round(cpk_after, 3),
            "cpk_diff": round(cpk_diff, 3),
            "yoy_growth_pct": round(yoy_pct, 2),
            "sample_sufficient": (n_before >= limit_n and n_after >= limit_n)
        })
        
    if not events_result:
        return {"has_cgrs": False, "events_count": 0, "events": []}
        
    latest = events_result[0]
    return {
        "has_cgrs": True,
        "events_count": len(events_result),
        "latest_event_time": latest["date_time_str"],
        "latest_yoy_pct": latest["yoy_growth_pct"],
        "latest_cpk_before": latest["cpk_before"],
        "latest_cpk_after": latest["cpk_after"],
        "latest_cpk_diff": latest["cpk_diff"],
        "latest_mean_before": latest["mean_before"],
        "latest_mean_after": latest["mean_after"],
        "latest_mean_diff": latest["mean_diff"],
        "latest_n_before": latest["n_before"],
        "latest_n_after": latest["n_after"],
        "latest_sample_sufficient": latest["sample_sufficient"],
        "latest_params": [p.get("param_local") for p in latest["params_changed"]],
        "events": events_result
    }

print("\n--- Test Calculation for TB222 on 2026-08-13 ---")
res = calculate_cgrs_cpk_comparison(workcenter="TB222", article10="0314176000", target_date="2026-08-13", indicator="rfpp")
import json
print(json.dumps(res, indent=2, ensure_ascii=False))
