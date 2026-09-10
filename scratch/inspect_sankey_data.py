import sys
import os

backend_dir = r"d:\Ava\untitled1\untitled1_v2\backend"
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from main import qry, get_machine_process_sankey, get_machine_best_process_sankey

dt_res = qry("SELECT MAX(tu_first_shift_date)::DATE as max_d, article10 FROM clean_yield GROUP BY 2 ORDER BY count(*) DESC LIMIT 1")
print("Top date and article:", dt_res)
target_d = str(dt_res[0]['max_d'])
art = str(dt_res[0]['article10'])

from main import qry, get_machine_process_sankey, get_machine_best_process_sankey

dt_res = qry("SELECT MAX(tu_first_shift_date)::DATE as max_d, article10 FROM clean_yield GROUP BY 2 ORDER BY count(*) DESC LIMIT 1")
target_d = str(dt_res[0]['max_d'])
art = str(dt_res[0]['article10'])

for ind in ["rfpp", "cony", "weight"]:
    print(f"\n=================== Indicator: {ind} ===================")
    s_res = get_machine_process_sankey(article10=art, indicator=ind, target_date=target_d, min_samples=1)
    s_nodes = s_res.get("data", {}).get("nodes", [])
    print(f"Single Sankey Nodes ({len(s_nodes)}):")
    for n in s_nodes[:3]:
        print(" ", n)

    b_res = get_machine_best_process_sankey(article10=art, indicator=ind, min_samples=1)
    b_nodes = b_res.get("data", {}).get("nodes", [])
    print(f"Best Sankey Nodes ({len(b_nodes)}):")
    for n in b_nodes[:3]:
        print(" ", n)



