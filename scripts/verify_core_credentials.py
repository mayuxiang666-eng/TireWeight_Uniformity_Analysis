# -*- coding: utf-8 -*-
"""
Verify Phase 1 migration credentials:
Compare function bodies between backend/main.py and backend/core/*.py
"""
import ast
import inspect
import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

with open(os.path.join(ROOT_DIR, "scratch", "baseline_main.py"), "r", encoding="utf-8") as f:
    main_code = f.read()

main_ast = ast.parse(main_code)

def get_ast_func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None

import backend.core.serializer as serializer
import backend.core.config as config
import backend.core.db as db
import backend.core.cpk as cpk
import backend.core.time_utils as time_utils
import backend.core.cache_utils as cache_utils

funcs_to_check = [
    ("sanitize_data", "sanitize_data", serializer.sanitize_data, 26),
    ("get_cleaned_data_path", "get_cleaned_data_path", config.get_cleaned_data_path, 50),
    ("get_cgrs_data_path", "get_cgrs_data_path", config.get_cgrs_data_path, 66),
    ("reload_duckdb_data", "reload_duckdb_data", db.reload_duckdb_data, 110),
    ("build_production_time_where", "build_production_time_where", time_utils.build_production_time_where, 170),
    ("qry", "qry", db.qry, 392),
    ("get_spec_usl", "get_spec_usl", cpk.get_spec_usl, 405),
    ("get_spec_limits", "get_spec_limits", cpk.get_spec_limits, 490),
    ("calc_cpk", "calc_cpk", cpk.calc_cpk, 515),
    ("get_phase_sql_condition", "get_phase_sql_condition", time_utils.get_phase_sql_condition, 1491),
    ("_recommend_cache_get", "recommend_cache_get", cache_utils.recommend_cache_get, 5101),
]

print("=== MIGRATION CREDENTIALS REPORT (PHASE 1) ===")
print(f"{'Function Name':<30} | {'Orig Line':<10} | {'Module':<25} | {'Similarity'}")
print("-" * 85)

for orig_name, new_name, fobj, orig_line in funcs_to_check:
    orig_ast_node = get_ast_func(main_ast, orig_name)
    orig_src = ast.unparse(orig_ast_node).strip() if orig_ast_node else None
    
    # AST parse the new module
    mod_file = inspect.getsourcefile(fobj)
    with open(mod_file, "r", encoding="utf-8") as mf:
        mod_ast = ast.parse(mf.read())
    new_ast_node = get_ast_func(mod_ast, new_name)
    new_src = ast.unparse(new_ast_node).strip() if new_ast_node else None

    if orig_src and new_src:
        # Compare normalized AST unparsed representations
        if orig_src == new_src:
            sim = "100.0% (Exact AST Match)"
        else:
            # calculate char similarity
            import difflib
            ratio = difflib.SequenceMatcher(None, orig_src, new_src).ratio() * 100
            sim = f"{ratio:.2f}%"
    else:
        sim = "N/A (AST Node Not Found)"
    
    mod_name = os.path.basename(mod_file)
    print(f"{orig_name:<30} | {orig_line:<10} | {mod_name:<25} | {sim}")

print("=" * 85)
