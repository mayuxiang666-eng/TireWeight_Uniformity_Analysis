import urllib.request
import json

url = 'http://127.0.0.1:8000/api/trend/cpk?grain=daily&article10=0359791000'
try:
    response = urllib.request.urlopen(url)
    data = json.loads(response.read())
    dates = data["data"]["dates"]
    rfpp = data["data"]["cpk_trends"]["RFPP 综合 CPK"]
    rfh1 = data["data"]["cpk_trends"]["RFH1 综合 CPK"]
    
    print("Trend values for 0359791000:")
    for d, p, h in zip(dates, rfpp, rfh1):
        print(f"Date: {d}, RFPP: {p}, RFH1: {h}")
except Exception as e:
    print("Error:", e)
