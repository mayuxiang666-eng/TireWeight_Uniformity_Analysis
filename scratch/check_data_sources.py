import os
import sys

sys.path.insert(0, "untitled1_v2/backend")
from main import get_cleaned_data_path, get_cgrs_data_path

cleaned_path = get_cleaned_data_path()
cgrs_path = get_cgrs_data_path()

print("Cleaned Parquet path:", cleaned_path)
print("  Exists:", os.path.exists(cleaned_path))
if os.path.exists(cleaned_path):
    print("  Size:", round(os.path.getsize(cleaned_path) / (1024*1024), 2), "MB")
    import time
    print("  Last Modified:", time.ctime(os.path.getmtime(cleaned_path)))

print("\nCGRS CSV path:", cgrs_path)
print("  Exists:", os.path.exists(cgrs_path))
if os.path.exists(cgrs_path):
    print("  Size:", round(os.path.getsize(cgrs_path) / (1024*1024), 2), "MB")
    import time
    print("  Last Modified:", time.ctime(os.path.getmtime(cgrs_path)))
