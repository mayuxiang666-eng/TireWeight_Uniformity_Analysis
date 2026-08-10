import urllib.request, json

# 测试 warning-cpk 修复后的接口
url = 'http://127.0.0.1:8000/api/articles/warning-cpk?indicator=rfpp&only_declining=false&study_from=2026-07-07&study_to=2026-07-07&min_samples=30'
res = urllib.request.urlopen(url)
data = json.loads(res.read())
print('Status:', data.get('status'))
arts = data.get('data', [])
print('Warning articles count:', len(arts))
for a in arts[:5]:
    print(f"  {a['article10']}: cpk={a['stable_score']}, mean={a['mean_cpk']}, declining={a['is_declining']}")

print()
# 测试 CPK 趋势接口
url2 = 'http://127.0.0.1:8000/api/trend/cpk?grain=daily'
res2 = urllib.request.urlopen(url2)
data2 = json.loads(res2.read())
print('CPK trend status:', data2.get('status'))
trend_data = data2.get('data', {})
dates = trend_data.get('dates', [])
print('Trend dates count:', len(dates))
if dates:
    print('Last 3 dates:', dates[-3:])

print()
# 测试机台 CPK 接口
url3 = 'http://127.0.0.1:8000/api/machines/cpk?target_date=2026-07-07&article10=0315980000&indicator=rfpp&min_samples=10'
res3 = urllib.request.urlopen(url3)
data3 = json.loads(res3.read())
print('Machine CPK status:', data3.get('status'))
m_data = data3.get('data', {})
print('Machine groups:', list(m_data.keys())[:3])
