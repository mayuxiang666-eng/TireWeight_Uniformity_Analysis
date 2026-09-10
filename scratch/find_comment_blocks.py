with open('backend/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

in_comment_block = False
start_idx = 0
comment_blocks = []

for i, line in enumerate(lines):
    s = line.strip()
    if s.startswith('#') and not s.startswith('# ──') and not s.startswith('# -*-'):
        if not in_comment_block:
            in_comment_block = True
            start_idx = i
    else:
        if in_comment_block:
            in_comment_block = False
            if i - start_idx >= 5:
                comment_blocks.append((start_idx + 1, i, i - start_idx, lines[start_idx].strip()[:60]))

for start, end, count, sample in comment_blocks:
    print(f"Lines {start:4d}-{end:4d} ({count:3d} lines): {sample}")
