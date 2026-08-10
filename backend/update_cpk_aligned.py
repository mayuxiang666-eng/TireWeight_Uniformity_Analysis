file_path = "d:/Ava/untitled1/untitled1_v2/backend/main.py"
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

start_idx = None
end_idx = None

for i, l in enumerate(lines):
    if 'def get_machines_cpk(' in l:
        start_idx = i - 1  # @app.get line
    if 'def get_machine_process_sankey(' in l or '@app.get("/api/machines/process-sankey")' in l:
        end_idx = i
        break

print(f"Replacing lines {start_idx + 1} to {end_idx + 1}")

new_code = '''@app.get("/api/machines/cpk")
def get_machines_cpk(
    target_date: str = Query(...),
    article10: str = Query(...),
    indicator: str = Query("rfpp"), # "rfpp" | "rfh1"
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_samples: int = Query(10),
):
    try:
        indicator_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
        date_col = "tu_first_shift_date"

        if not target_date or not isinstance(target_date, str) or 'annotation=' in str(target_date):
            res = qry("SELECT MAX(tu_first_shift_date)::DATE AS max_d FROM clean_yield")[0]
            target_date = str(res['max_d'])
        else:
            target_date = str(target_date)

        if not end_date or not isinstance(end_date, str) or 'annotation=' in str(end_date):
            end_date = target_date
        else:
            end_date = str(end_date)

        if not start_date or not isinstance(start_date, str) or 'annotation=' in str(start_date):
            dt_obj = datetime.strptime(end_date, "%Y-%m-%d")
            start_date = (dt_obj - timedelta(days=7)).strftime("%Y-%m-%d")
        else:
            start_date = str(start_date)

        col_sql = """
            SELECT column_name
            FROM (DESCRIBE SELECT * FROM clean_yield LIMIT 1)
            WHERE column_name LIKE '%workcenter%'
              AND column_name != 'css_workcenter'
        """
        wc_cols = [r["column_name"] for r in qry(col_sql)]

        # 全局 USL 基准
        usl_sql = f"SELECT AVG(TRY_CAST({indicator_col} AS DOUBLE)) + 3.0 * COALESCE(STDDEV(TRY_CAST({indicator_col} AS DOUBLE)), 0.0) as usl FROM clean_yield"
        usl_res = qry(usl_sql)
        global_usl = float(usl_res[0]['usl']) if usl_res and usl_res[0]['usl'] is not None else 100.0

        wc_name_map = {
            "tread_workcenter": "胎面 (Tread)",
            "bead_workcenter": "胎圈 (Bead)",
            "inner_liner_workcenter": "内衬 (Inner Liner)",
            "sidewall_workcenter": "胎侧 (Sidewall)",
            "first_breaker_workcenter": "带束层1 (Breaker 1)",
            "second_breaker_workcenter": "带束层2 (Breaker 2)",
            "first_ply_workcenter": "帘布层 (Ply 1)",
            "wound_cap_ply1_workcenter": "冠带层1 (Wound Cap 1)",
            "wound_cap_ply2_workcenter": "冠带层2 (Wound Cap 2)",
            "ccs_workcenter": "胎胚成型 (CCS)",
            "gt_workcenter": "生胎成型 (GT)",
            "ct_workcenter": "硫化 (CT)",
            "tu_first_workcenter": "终检-均匀性 (TU)",
            "tg_first_workcenter": "终检-几何形 (TG)",
            "tb_first_workcenter": "终检-动平衡 (TB)",
        }

        grouped = {}

        for col in wc_cols:
            wc_label = wc_name_map.get(col, col)
            
            # 1. 查当天的活跃机台 (按选中单规格)
            active_sql = f"""
                SELECT 
                    CAST({col} AS VARCHAR) as machine,
                    COUNT(*) as spec_n,
                    AVG(TRY_CAST({indicator_col} AS DOUBLE)) as spec_avg,
                    STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as spec_std
                FROM clean_yield
                WHERE {col} IS NOT NULL AND article10 = ? AND {date_col}::DATE = ?::DATE AND {date_col} IS NOT NULL
                GROUP BY 1
                HAVING COUNT(*) >= ?
            """
            m_rows = qry(active_sql, [article10, target_date, min_samples])
            if not m_rows:
                continue

            grouped[wc_label] = []

            for r in m_rows:
                m_code = str(r['machine'])
                spec_n = int(r['spec_n'])
                spec_avg = float(r['spec_avg']) if r['spec_avg'] is not None else 0.0
                spec_std = float(r['spec_std']) if r['spec_std'] is not None else 0.0

                if spec_std > 0:
                    spec_cpk = round(max(0.0, min(5.0, (global_usl - spec_avg) / (3.0 * spec_std))), 2)
                else:
                    spec_cpk = 1.33

                # ── 单规格 CPK 预警判断 (基于 CPK 序列与 CPK 预警线对齐) ──
                spec_hist_sql = f"""
                    SELECT 
                        {date_col}::DATE as dt,
                        AVG(TRY_CAST({indicator_col} AS DOUBLE)) as day_avg,
                        STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as day_std
                    FROM clean_yield
                    WHERE {col} = ? AND article10 = ? AND {indicator_col} IS NOT NULL AND {date_col} IS NOT NULL
                    GROUP BY 1
                    ORDER BY 1 ASC
                """
                s_hist_rows = qry(spec_hist_sql, [m_code, article10])
                s_cpk_series = []
                for h in s_hist_rows:
                    m_v = float(h['day_avg']) if h['day_avg'] is not None else 0.0
                    s_v = float(h['day_std']) if h['day_std'] is not None else 0.0
                    c_v = round(max(0.0, min(5.0, (global_usl - m_v) / (3.0 * s_v))), 2) if s_v > 0 else 1.33
                    s_cpk_series.append((str(h['dt']), c_v))

                spec_rule_a = 0
                spec_rule_b = 0
                spec_rule_a_count = 0
                spec_threshold = 0.0

                if s_cpk_series:
                    s_cpk_vals = [c[1] for c in s_cpk_series]
                    s_mean = float(np.mean(s_cpk_vals))
                    s_std = float(np.std(s_cpk_vals))
                    spec_threshold = round(max(0.0, s_mean - 1.0 * s_std), 2)
                    
                    # 截至选中日期的历史点
                    s_up_to_target = [c for c in s_cpk_series if c[0] <= target_date]
                    spec_rule_a_count = sum(1 for c in s_up_to_target if c[1] <= spec_threshold)
                    if spec_rule_a_count >= 2:
                        spec_rule_a = 1

                    # 连续 3 天下降
                    if len(s_up_to_target) >= 4:
                        recent_3 = [c[1] for c in s_up_to_target[-4:]]
                        diffs = [recent_3[i] - recent_3[i-1] for i in range(1, 4)]
                        if all(d < 0 for d in diffs):
                            spec_rule_b = 1

                spec_is_warning = 1 if (spec_rule_a == 1 or spec_rule_b == 1) else 0


                # ── 多规格 (全规格产量加权) CPK 预警判断 ──
                multi_today_sql = f"""
                    SELECT 
                        COUNT(*) as multi_n,
                        AVG(TRY_CAST({indicator_col} AS DOUBLE)) as multi_avg,
                        STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as multi_std
                    FROM clean_yield
                    WHERE {col} = ? AND {date_col}::DATE = ?::DATE AND {date_col} IS NOT NULL
                """
                multi_t_res = qry(multi_today_sql, [m_code, target_date])
                if multi_t_res and multi_t_res[0]['multi_n']:
                    multi_n = int(multi_t_res[0]['multi_n'])
                    multi_avg = float(multi_t_res[0]['multi_avg']) if multi_t_res[0]['multi_avg'] is not None else 0.0
                    multi_std = float(multi_t_res[0]['multi_std']) if multi_t_res[0]['multi_std'] is not None else 0.0
                else:
                    multi_n, multi_avg, multi_std = spec_n, spec_avg, spec_std

                if multi_std > 0:
                    multi_cpk = round(max(0.0, min(5.0, (global_usl - multi_avg) / (3.0 * multi_std))), 2)
                else:
                    multi_cpk = 1.33

                multi_hist_sql = f"""
                    SELECT 
                        {date_col}::DATE as dt,
                        AVG(TRY_CAST({indicator_col} AS DOUBLE)) as day_avg,
                        STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as day_std
                    FROM clean_yield
                    WHERE {col} = ? AND {indicator_col} IS NOT NULL AND {date_col} IS NOT NULL
                    GROUP BY 1
                    ORDER BY 1 ASC
                """
                m_hist_rows = qry(multi_hist_sql, [m_code])
                m_cpk_series = []
                for h in m_hist_rows:
                    m_v = float(h['day_avg']) if h['day_avg'] is not None else 0.0
                    s_v = float(h['day_std']) if h['day_std'] is not None else 0.0
                    c_v = round(max(0.0, min(5.0, (global_usl - m_v) / (3.0 * s_v))), 2) if s_v > 0 else 1.33
                    m_cpk_series.append((str(h['dt']), c_v))

                multi_rule_a = 0
                multi_rule_b = 0
                multi_rule_a_count = 0
                multi_threshold = 0.0

                if m_cpk_series:
                    m_cpk_vals = [c[1] for c in m_cpk_series]
                    m_mean = float(np.mean(m_cpk_vals))
                    m_std = float(np.std(m_cpk_vals))
                    multi_threshold = round(max(0.0, m_mean - 1.0 * m_std), 2)

                    m_up_to_target = [c for c in m_cpk_series if c[0] <= target_date]
                    multi_rule_a_count = sum(1 for c in m_up_to_target if c[1] <= multi_threshold)
                    if multi_rule_a_count >= 2:
                        multi_rule_a = 1

                    if len(m_up_to_target) >= 4:
                        m_recent_3 = [c[1] for c in m_up_to_target[-4:]]
                        mdiffs = [m_recent_3[i] - m_recent_3[i-1] for i in range(1, 4)]
                        if all(d < 0 for d in mdiffs):
                            multi_rule_b = 1

                multi_is_warning = 1 if (multi_rule_a == 1 or multi_rule_b == 1) else 0

                grouped[wc_label].append({
                    "workcenter_col": col,
                    "machine": m_code,
                    
                    # 单规格
                    "spec_n": spec_n,
                    "spec_avg": round(spec_avg, 2),
                    "spec_std": round(spec_std, 2),
                    "spec_cpk": spec_cpk,
                    "spec_is_warning": spec_is_warning,
                    "spec_rule_a": spec_rule_a,
                    "spec_rule_b": spec_rule_b,
                    "spec_rule_a_count": spec_rule_a_count,
                    "spec_warning_threshold": spec_threshold,

                    # 多规格 (全规格产量加权)
                    "multi_n": multi_n,
                    "multi_avg": round(multi_avg, 2),
                    "multi_std": round(multi_std, 2),
                    "multi_cpk": multi_cpk,
                    "multi_is_warning": multi_is_warning,
                    "multi_rule_a": multi_rule_a,
                    "multi_rule_b": multi_rule_b,
                    "multi_rule_a_count": multi_rule_a_count,
                    "multi_warning_threshold": multi_threshold,

                    "is_warning": spec_is_warning or multi_is_warning
                })

        # 按是否预警降序，预警机台最靠前
        for wc_label in grouped:
            grouped[wc_label].sort(key=lambda x: (x.get("multi_is_warning", 0), x.get("spec_is_warning", 0)), reverse=True)

        return {"status": "success", "data": sanitize_data(grouped)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@app.get("/api/machines/cpk/trend")
def get_machine_cpk_trend(
    machine: str = Query(...),
    workcenter_col: str = Query(...),
    indicator: str = Query("rfpp"), # "rfpp" | "rfh1"
    article10: Optional[str] = Query(None),
    mode: Optional[str] = Query(None) # "single" | "multi"
):
    try:
        indicator_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
        normalized_col = workcenter_col if workcenter_col.endswith("_workcenter") else f"{workcenter_col}_workcenter"
        date_col = "tu_first_shift_date"

        usl_sql = f"SELECT AVG(TRY_CAST({indicator_col} AS DOUBLE)) + 3.0 * COALESCE(STDDEV(TRY_CAST({indicator_col} AS DOUBLE)), 0.0) as usl FROM clean_yield"
        usl_res = qry(usl_sql)
        global_usl = float(usl_res[0]['usl']) if usl_res and usl_res[0]['usl'] is not None else 100.0

        where_parts = [f"{normalized_col} = ?", f"{indicator_col} IS NOT NULL", f"{date_col} IS NOT NULL"]
        params = [machine]

        # 单规格模式
        if (mode == "single" or mode == "spec_3sigma") or (article10 and mode != "multi" and mode != "all_3sigma"):
            where_parts.append("article10 = ?")
            params.append(article10)

        where_clause = "WHERE " + " AND ".join(where_parts)

        sql = f"""
            SELECT 
                {date_col}::DATE AS time_period,
                COUNT(*) AS sample_size,
                AVG(TRY_CAST({indicator_col} AS DOUBLE)) AS mean_val,
                STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) AS std_val
            FROM clean_yield
            {where_clause}
            GROUP BY 1
            HAVING COUNT(*) >= 1
            ORDER BY 1
        """
        rows = qry(sql, params)
        trend_data = []
        cpk_list = []

        for r in rows:
            m_val = float(r['mean_val']) if r['mean_val'] is not None else 0.0
            s_val = float(r['std_val']) if r['std_val'] is not None else 0.0
            
            if s_val > 0:
                cpk_val = round(max(0.0, min(5.0, (global_usl - m_val) / (3.0 * s_val))), 2)
            else:
                cpk_val = 1.33

            cpk_list.append(cpk_val)

            trend_data.append({
                "date": str(r['time_period']),
                "sample_size": int(r['sample_size']),
                "mean_val": round(m_val, 2),
                "std_val": round(s_val, 2),
                "cpk_val": cpk_val
            })

        # 计算 CPK 控制限与预警基准线 (Mean - 1*std)
        cpk_mean = float(np.mean(cpk_list)) if cpk_list else 1.33
        cpk_std = float(np.std(cpk_list)) if len(cpk_list) > 1 else 0.0
        warning_threshold = round(max(0.0, cpk_mean - 1.0 * cpk_std), 2)

        return {
            "status": "success",
            "mode": mode or ("single" if article10 else "multi"),
            "data": sanitize_data(trend_data),
            "control_limits": {
                "cpk_mean": round(cpk_mean, 2),
                "cpk_std": round(cpk_std, 2),
                "warning_threshold": warning_threshold
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

\n\n'''

final_lines = lines[:start_idx] + [new_code] + lines[end_idx:]
with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(final_lines)

print("Updated backend/main.py for aligned CPK warning logic cleanly.")
