from main import qry
import numpy as np

# 分析 None time_period 的根源
sql_none = """
    SELECT
        article10,
        tu_first_shift_date,
        tu_first_shift_date::DATE AS time_period,
        COUNT(*) as cnt
    FROM clean_yield
    WHERE "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
      AND TRY_CAST(tu_first_shift_date AS DATE) IS NULL
    GROUP BY 1, 2, 3
    LIMIT 10
"""
try:
    rows = qry(sql_none)
    print(f'Rows with NULL time_period cast: {len(rows)}')
    for r in rows:
        print(' ', r)
except Exception as e:
    print('Error:', e)

# 检查 tu_first_shift_date 字段中有哪些不能转换为 DATE 的值
sql_bad = """
    SELECT DISTINCT tu_first_shift_date, COUNT(*) as cnt
    FROM clean_yield
    WHERE TRY_CAST(tu_first_shift_date AS DATE) IS NULL
    GROUP BY 1
    LIMIT 10
"""
try:
    rows = qry(sql_bad)
    print(f'Bad date values: {len(rows)}')
    for r in rows:
        print(' ', r)
except Exception as e:
    print('Error:', e)
