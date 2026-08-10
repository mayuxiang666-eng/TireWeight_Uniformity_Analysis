import urllib.request
import json
import numpy as np

url = 'http://127.0.0.1:8000/api/trend/cpk?grain=daily'
try:
    response = urllib.request.urlopen(url)
    data = json.loads(response.read())
    rfh1 = [v for v in data["data"]["cpk_trends"]["RFH1 综合 CPK"] if v is not None]
    
    print(f"Total points: {len(rfh1)}")
    print(f"Mean of overall: {np.mean(rfh1):.4f}")
    print(f"Std of overall: {np.std(rfh1, ddof=1):.4f}")
    print(f"Mean - Std: {np.mean(rfh1) - np.std(rfh1, ddof=1):.4f}")
    print("All values:")
    for d, val in zip(data["data"]["dates"], data["data"]["cpk_trends"]["RFH1 综合 CPK"]):
        print(f"  {d}: {val}")
except Exception as e:
    print("Error:", e)
