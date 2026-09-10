import sys
sys.path.insert(0, "untitled1_v2/backend")
from main import get_articles_warning_cpk, reload_duckdb_data

reload_duckdb_data()

print("--- Testing get_articles_warning_cpk with max_cpk=0.9 on 2026-08-10 ---")
res = get_articles_warning_cpk(
    indicator="rfpp",
    study_to="2026-08-10",
    min_samples=30,
    max_cpk=0.9
)
data = res.get("data", [])
print(f"Total returned specs: {len(data)}")
for i, item in enumerate(data[:10]):
    print(f"{i+1}. Spec: {item['article10']}, CPK: {item['single_cpk']}, N: {item['sample_size']}, NegContrib: {item['stable_score']}")
