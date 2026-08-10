from main import qry

rows = qry("""
    SELECT DISTINCT article10, COUNT(*) as cnt 
    FROM clean_yield 
    WHERE tu_first_workcenter = 'TU7' AND tu_first_shift_date::DATE = '2026-07-07'
    GROUP BY 1
""")
print("TU7 articles on 2026-07-07:", rows)
