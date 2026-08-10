from fastapi.testclient import TestClient
import sys
import os

# Add backend directory to path
sys.path.append(r"d:\Ava\untitled1\untitled1_v2\backend")

from main import app

client = TestClient(app)

print("=== Testing / (root) ===")
res = client.get("/")
print("Status:", res.status_code)
print("JSON:", res.json())

print("\n=== Testing /api/summary ===")
res = client.get("/api/summary")
print("Status:", res.status_code)
print("JSON:", res.json())

print("\n=== Testing /api/trend/daily ===")
res = client.get("/api/trend/daily")
print("Status:", res.status_code)
print("Records:", len(res.json().get("data", [])))
print("Sample:", res.json().get("data", [])[:2] if res.json().get("data") else "None")

print("\n=== Testing /api/trend/cpk ===")
res = client.get("/api/trend/cpk?grain=daily")
print("Status:", res.status_code)
cpk_data = res.json().get("data", {})
print("Dates count:", len(cpk_data.get("dates", [])))
print("Groups in cpk_trends:", list(cpk_data.get("cpk_trends", {}).keys()))
for g, trend in cpk_data.get("cpk_trends", {}).items():
    valid_points = [x for x in trend if x is not None]
    print(f"Group {g}: valid points={len(valid_points)}, sample={valid_points[:5]}")
