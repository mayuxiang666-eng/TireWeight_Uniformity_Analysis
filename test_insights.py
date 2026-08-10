import urllib.request, json
try:
    url = 'http://127.0.0.1:8000/api/insights?baseline_from=2026-06-08&baseline_to=2026-06-11&study_from=2026-06-05&study_to=2026-06-09&min_yield=50'
    response = urllib.request.urlopen(url)
    print(json.loads(response.read()))
except Exception as e:
    print(e)
