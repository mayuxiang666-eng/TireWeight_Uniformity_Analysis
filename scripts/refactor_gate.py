# -*- coding: utf-8 -*-
"""
Automation script to check Stage Gates for Backend Modularization Refactoring
Strictly adhering to docs/backend_modularization_execution_constraints.md
"""
import os
import sys
import glob
import py_compile
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

def check_gate_syntax():
    """G-1 Syntax gate: py_compile all .py files in backend"""
    py_files = glob.glob(os.path.join(ROOT_DIR, "backend", "**", "*.py"), recursive=True)
    failed = []
    for f in py_files:
        try:
            py_compile.compile(f, doraise=True)
        except Exception as e:
            failed.append((f, str(e)))
    if failed:
        print("[FAIL] Syntax check failed on:", failed)
        return False
    print(f"[PASS] Syntax check passed on {len(py_files)} files.")
    return True

def check_gate_no_placeholders():
    """G-6 Zero placeholder gate: detect TODOs, NotImplementedError, empty function stubs (def foo(): pass)"""
    new_dirs = [os.path.join(ROOT_DIR, "backend", d) for d in ["core", "services", "routers"]]
    py_files = []
    for d in new_dirs:
        if os.path.exists(d):
            py_files.extend(glob.glob(os.path.join(d, "**", "*.py"), recursive=True))

    failed = []
    for f in py_files:
        if os.path.basename(f) == "__init__.py":
            continue
        with open(f, "r", encoding="utf-8") as fp:
            lines = fp.readlines()
        for idx, line in enumerate(lines):
            stripped = line.strip()
            # 1. Flag TODO / FIXME comments
            if re.search(r'#\s*(TODO|FIXME|placeholder)', stripped, re.IGNORECASE):
                failed.append((f, idx + 1, stripped))
            # 2. Flag NotImplementedError
            if "NotImplementedError" in stripped or "NotImplemented" in stripped:
                failed.append((f, idx + 1, stripped))
            # 3. Flag function stubs: line after def is just pass
            if stripped.startswith("def ") and idx + 1 < len(lines):
                next_line = lines[idx + 1].strip()
                if next_line == "pass":
                    failed.append((f, idx + 2, f"Stub function: {stripped} -> pass"))
    if failed:
        print("[FAIL] Placeholder detected:", failed)
        return False
    print("[PASS] Zero placeholders verified.")
    return True

def check_gate_no_dead_code():
    """G-7 No dead code backflow gate"""
    new_dirs = [os.path.join(ROOT_DIR, "backend", d) for d in ["core", "services", "routers"]]
    py_files = []
    for d in new_dirs:
        if os.path.exists(d):
            py_files.extend(glob.glob(os.path.join(d, "**", "*.py"), recursive=True))

    dead_patterns = [
        "api/insights",
        "LOT_MAP",
        "def get_periods",
        "diagnose_machine",
        "compute_machine_all_weighted_cpk"
    ]
    failed = []
    for f in py_files:
        with open(f, "r", encoding="utf-8") as fp:
            content = fp.read()
            for p in dead_patterns:
                if p in content:
                    failed.append((f, p))
    if failed:
        print("[FAIL] Dead code backflow detected:", failed)
        return False
    print("[PASS] No dead code backflow verified.")
    return True

def check_gate_no_circular_imports():
    """G-3 Dependency direction gate"""
    indicators_file = os.path.join(ROOT_DIR, "backend", "core", "indicators.py")
    if os.path.exists(indicators_file):
        with open(indicators_file, "r", encoding="utf-8") as fp:
            for line in fp:
                s = line.strip()
                if s.startswith("from backend.services") or s.startswith("import backend.services") or s.startswith("from backend.routers"):
                    print("[FAIL] indicators.py imports services or routers:", s)
                    return False

    service_files = glob.glob(os.path.join(ROOT_DIR, "backend", "services", "*.py"))
    for f in service_files:
        with open(f, "r", encoding="utf-8") as fp:
            for line in fp:
                s = line.strip()
                if s.startswith("from backend.services") or s.startswith("import backend.services"):
                    print(f"[FAIL] Cross-service import detected in {f}: {s}")
                    return False
    print("[PASS] No circular or cross-service imports verified.")
    return True

if __name__ == "__main__":
    s_ok = check_gate_syntax()
    p_ok = check_gate_no_placeholders()
    d_ok = check_gate_no_dead_code()
    c_ok = check_gate_no_circular_imports()
    if s_ok and p_ok and d_ok and c_ok:
        print("\n>>> ALL CODE QUALITY GATES PASSED <<<")
        sys.exit(0)
    else:
        print("\n>>> SOME GATES FAILED <<<")
        sys.exit(1)
