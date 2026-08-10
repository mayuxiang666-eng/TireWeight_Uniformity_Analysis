from main import qry
import numpy as np

# 完整复现 warning-cpk 逻辑，找到 '<' NoneType 错误
target_date = '2026-07-07'
indicator = 'rfpp'
min_samples = 30

sql_all = """
    SELECT
        tu_first_shift_date::DATE AS time_period,
        article10,
        COUNT(*) AS sample_size,
        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) AS avg_rfpp,
        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) AS std_rfpp,
        AVG(TRY_CAST(rfh1wc_first AS DOUBLE)) AS avg_rfh1,
        STDDEV(TRY_CAST(rfh1wc_first AS DOUBLE)) AS std_rfh1,
        COALESCE(ANY_VALUE(standard_rfpp),
                 CASE ANY_VALUE("group")
                     WHEN 'GROUP 1'  THEN 10.5
                     WHEN 'GROUP 2A' THEN 11.5
                     WHEN 'GROUP 2B' THEN 12.5
                     WHEN 'GROUP 3'  THEN 12.5
                 END) * 10.0 AS usl_rfpp,
        COALESCE(ANY_VALUE(standard_rfh1),
                 CASE ANY_VALUE("group")
                     WHEN 'GROUP 1'  THEN 7.5
                     WHEN 'GROUP 2A' THEN 8.5
                     WHEN 'GROUP 2B' THEN 9.0
                     WHEN 'GROUP 3'  THEN 9.5
                 END) * 10.0 AS usl_rfh1
    FROM clean_yield
    WHERE "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
    GROUP BY 1, 2
    HAVING COUNT(*) >= 10
    ORDER BY 2, 1
"""

all_rows = qry(sql_all)
print(f'Total rows fetched: {len(all_rows)}')

article_data = {}
for r in all_rows:
    article_data.setdefault(r['article10'], []).append(r)

results = []
errors = []

for art, day_list in article_data.items():
    try:
        day_list.sort(key=lambda x: x['time_period'])

        all_cpk = []
        all_dates = []
        target_cpk = None
        target_size = None
        prev_cpk = None

        for d in day_list:
            if indicator == 'rfpp':
                avg_v, std_v, usl_v = d['avg_rfpp'], d['std_rfpp'], d['usl_rfpp']
            else:
                avg_v, std_v, usl_v = d['avg_rfh1'], d['std_rfh1'], d['usl_rfh1']

            if std_v is None or std_v <= 1e-6 or usl_v is None:
                continue
            cpk = (usl_v - avg_v) / (3.0 * std_v)
            if np.isnan(cpk) or np.isinf(cpk):
                continue

            date_str = str(d['time_period'])
            if date_str == target_date:
                prev_cpk = all_cpk[-1] if all_cpk else None
                target_cpk = float(cpk)
                target_size = d['sample_size']

            all_cpk.append(float(cpk))
            all_dates.append(date_str)

        if target_cpk is None or (target_size is not None and target_size < min_samples):
            continue

        if not all_cpk:
            continue

        mean_cpk = float(np.mean(all_cpk))
        std_cpk = float(np.std(all_cpk, ddof=1)) if len(all_cpk) > 1 else 0.0
        threshold = mean_cpk - std_cpk
        
        if target_cpk >= threshold:
            continue

        diff = 0.0
        is_declining = False
        if prev_cpk is not None:
            diff = target_cpk - prev_cpk
            is_declining = diff < 0

        results.append({
            "article10": art,
            "stable_score": round(target_cpk, 4),
        })

    except Exception as e:
        errors.append((art, str(e)))

print(f'Results count: {len(results)}')
print(f'Errors count: {len(errors)}')
if errors:
    print('First 5 errors:')
    for art, err in errors[:5]:
        print(f'  {art}: {err}')
if results:
    results.sort(key=lambda x: x['stable_score'])
    print('Top 5 warning articles:')
    for r in results[:5]:
        print(' ', r)
