with open('backend/main.py', 'r', encoding='utf-8') as f:
    text = f.read()

for i, line in enumerate(text.splitlines(), 1):
    if ('usl' in line.lower() or 'cpk' in line.lower()) and ('/ (3' in line or '/ (3.0' in line):
        print(f"Line {i:4d}: {line.strip()[:100]}")
