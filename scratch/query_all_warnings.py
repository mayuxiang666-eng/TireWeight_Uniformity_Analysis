import urllib.request
import urllib.parse
import json

# Get all daily trend dates
try:
    response = urllib.request.urlopen('http://127.0.0.1:8000/api/trend/cpk?grain=daily')
    trend_data = json.loads(response.read())
    dates = trend_data.get("data", {}).get("dates", [])
    print(f"Total dates in dataset: {len(dates)}")
    
    # Scan dates
    success_dates = []
    for d in dates:
        warn_url = f'http://127.0.0.1:8000/api/articles/warning-cpk?study_from={d}&study_to={d}&indicator=rfh1'
        warn_res = urllib.request.urlopen(warn_url)
        warn_data = json.loads(warn_res.read())
        articles = warn_data.get("data", [])
        if articles:
            print(f"Date {d} found {len(articles)} warnings: {[a['article10'] for a in articles]}")
            success_dates.append(d)
        else:
            # Check without the CPK threshold filter to see if it's because of sample size or CPK
            pass
            
    print(f"Scan complete. Found {len(success_dates)} dates with warnings.")
except Exception as e:
    print("Failed scanning:", e)
