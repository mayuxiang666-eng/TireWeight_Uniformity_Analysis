file_path = "d:/Ava/untitled1/untitled1_v2/backend/main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 找所有 FROM clean_yield 后跟 WHERE 的地方
import re

# 找到所有 FROM clean_yield 的位置，检查是否已有 tu_first_shift_date IS NOT NULL
matches = list(re.finditer(r'FROM clean_yield\s+WHERE', content))
print(f"Found {len(matches)} 'FROM clean_yield WHERE' clauses")

for m in matches:
    start = m.start()
    chunk = content[start:start+300]
    has_null_check = 'tu_first_shift_date IS NOT NULL' in chunk
    has_where = True
    print(f"  Pos {start}: has null check = {has_null_check}")
    print(f"    {chunk[:120].strip()!r}")
    print()
