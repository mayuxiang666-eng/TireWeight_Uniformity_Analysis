file_path = "d:/Ava/untitled1/untitled1_v2/backend/main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 策略：在所有引用 tu_first_shift_date 的 GROUP BY 聚合查询中，
# 于 WHERE 子句中追加 tu_first_shift_date IS NOT NULL 过滤
import re

count = 0

# 1. 修复 warning-cpk 的核心 sql_all 查询
# WHERE "group" IS NOT NULL AND ... => 追加 tu_first_shift_date IS NOT NULL
old = 'WHERE "group" IS NOT NULL AND "group" != \'None\' AND "group" != \'\''
new = 'WHERE "group" IS NOT NULL AND "group" != \'None\' AND "group" != \'\'\n            AND tu_first_shift_date IS NOT NULL'
n = content.count(old)
content = content.replace(old, new)
count += n
print(f"Fixed 'group' WHERE clauses: {n} instances")

# 2. 修复 cpk/trend 等按日期 GROUP BY 的查询中缺乏 NULL 过滤的情况
# 对于形如 WHERE {normalized_col} = ? AND {indicator_col} IS NOT NULL 的查询
old2 = 'WHERE {normalized_col} = ? AND {indicator_col} IS NOT NULL'
new2 = 'WHERE {normalized_col} = ? AND {indicator_col} IS NOT NULL AND tu_first_shift_date IS NOT NULL'
n2 = content.count(old2)
content = content.replace(old2, new2)
count += n2
print(f"Fixed normalized_col WHERE clauses: {n2} instances")

# 3. 机台 CPK 接口中的 date_col::DATE = ?::DATE 查询
old3 = 'WHERE {col} IS NOT NULL AND article10 = ? AND {date_col}::DATE = ?::DATE'
new3 = 'WHERE {col} IS NOT NULL AND article10 = ? AND {date_col}::DATE = ?::DATE AND {date_col} IS NOT NULL'
n3 = content.count(old3)
content = content.replace(old3, new3)
count += n3
print(f"Fixed machine CPK WHERE clauses: {n3} instances")

# 4. 机台窗口查询 date_col::DATE >= 
old4 = 'WHERE {col} = ? AND {indicator_col} IS NOT NULL\n                      AND {date_col}::DATE >='
new4 = 'WHERE {col} = ? AND {indicator_col} IS NOT NULL AND {date_col} IS NOT NULL\n                      AND {date_col}::DATE >='
n4 = content.count(old4)
content = content.replace(old4, new4)
count += n4
print(f"Fixed machine window WHERE clauses: {n4} instances")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\nTotal fixes applied: {count}")
print("Done!")
